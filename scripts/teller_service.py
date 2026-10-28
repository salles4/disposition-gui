import eventlet
# MUST be the very first thing executed to prevent requests and time from blocking WebSockets
eventlet.monkey_patch()

import time, json, os, random, threading, signal, sys, logging, atexit
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room 
from requests.exceptions import RequestException
from typing import Optional

# =========================================================
# 🎨 TERMINAL COLORS
# =========================================================
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# =========================================================
# ⚙️ CONFIGURATION
# =========================================================
SIM_MODE = os.getenv("SIM_MODE", "SCHEDULED").strip().upper()
WAIT_OPTIONS = [15] # Seconds between scheduled payments

def get_cooldown():
    try:
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = json.load(f)
                return int(config.get("teller_cooldown_seconds", 3))
    except: pass
    return 3

def get_process_delay():
    try:
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = json.load(f)
                return int(config.get("teller_process_delay_seconds", 2))
    except: pass
    return 2

def is_real_device_payment_enabled():
    try:
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = json.load(f)
                return bool(config.get("real_device_payment", False))
    except: pass
    return False

# Import token dynamically from config.py to ensure it is always valid and synchronized
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.config import TOKEN, API_BASE_URL
from scripts.utils import format_plate

# UNIFIED BASE HOST pointing to the API_BASE_URL config
BASE_HOST = API_BASE_URL

application_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

LOGS_DIR = os.path.join(application_path, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

DATA_DIR = os.path.join(application_path, "data")
os.makedirs(DATA_DIR, exist_ok=True)

LOCAL_QUEUE_FILE = os.path.join(DATA_DIR, "teller_queue.json")
current_date_str = datetime.now().strftime("%Y-%m-%d")
EVENT_LOG_FILE = os.path.join(LOGS_DIR, f"teller_events_{current_date_str}.txt")
HISTORY_LOG_FILE = os.path.join(LOGS_DIR, f"teller_history_{current_date_str}.txt")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

RAM_LOG_FILE = os.path.join(LOGS_DIR, "ram_usage.csv")
ram_history = []

def load_ram_history():
    global ram_history
    if os.path.exists(RAM_LOG_FILE):
        try:
            import csv
            with open(RAM_LOG_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                for row in rows[-500:]:
                    ram_history.append({
                        "timestamp": row.get("Timestamp", ""),
                        "terminal_id": row.get("Terminal ID", ""),
                        "app_used_mb": int(row.get("App Used MB", 0)),
                        "device_used_mb": int(row.get("Device Used MB", 0)),
                        "device_total_mb": int(row.get("Device Total MB", 0))
                    })
        except Exception as e:
            print(f"Failed to load RAM history from CSV: {e}")

def log_ram_telemetry(terminal_id: str, status: str, app_used: int, avail: int, total: int, critical: bool):
    file_exists = os.path.exists(RAM_LOG_FILE)
    try:
        import csv
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        used = total - avail
        with open(RAM_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Terminal ID", "Status", "App Used MB", "Device Available MB", "Device Total MB", "Device Used MB", "Is Critical"])
            writer.writerow([now_str, terminal_id, status, app_used, avail, total, used, critical])
            
        with mailbox_lock:
            ram_history.append({
                "timestamp": now_str,
                "terminal_id": terminal_id,
                "app_used_mb": app_used,
                "device_used_mb": used,
                "device_total_mb": total
            })
            if len(ram_history) > 500:
                ram_history.pop(0)
    except Exception as e:
        print(f"Failed to log RAM telemetry: {e}")

api_session = requests.Session()
api_session.headers.update(HEADERS)

SEARCH_DELAY = 20  
TIMEOUT_LIMIT = 60

PROCESSED_PLATES_FILE = os.path.join(DATA_DIR, "processed_plates.json")

def load_processed_plates():
    try:
        if os.path.exists(PROCESSED_PLATES_FILE):
            os.remove(PROCESSED_PLATES_FILE)
    except: pass
    return set()

def save_processed_plate(plate: str):
    try:
        with mailbox_lock:
            stats["processed_plates"].add(plate.upper())
            data = list(stats["processed_plates"])
            with open(PROCESSED_PLATES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save processed plate {plate}: {e}")

def trigger_exit_immediately(plate: str, vehicle_type: str = "CAR"):
    p_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        api_session.post(
            f"{BASE_HOST}/api/lpr",
            json={
                "gate_id": 8,
                "plate_no": plate.upper(),
                "vehicle_type": vehicle_type.upper(),
                "created_at": p_time_str,
                "timestamp": p_time_str,
                "time_out": p_time_str
            },
            timeout=5
        )
        record(f"Triggered immediate LPR Exit for already paid vehicle [{plate}]", "EXIT")
    except Exception as e:
        record(f"Failed to trigger auto-exit for plate {plate}: {e}", "WARN")

# =========================================================
# APP & SOCKET SETUP
# =========================================================
app = Flask(__name__)
CORS(app)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 🛑 TERMINAL TRACKER & CONCURRENCY STATE
active_terminals = {}      # Tracks connected terminals: { sid: terminal_id }
active_workers = {}        # Tracks background tasks: { sid: greenlet }
active_transactions = set() # Tracks plates currently being processed: { plate_no }
terminal_states = {}       # Tracks per-terminal mailbox/status: { terminal_id: { "status": "IDLE", "latest_telemetry": {} } }

mailbox_lock = threading.RLock()

stats = {
    "total_success": 0,
    "total_collected": 0.0,
    "processed_plates": load_processed_plates(),
    "start_time": datetime.now(),
    "terminal_counts": {} # Tracks transactions per terminal
}

scheduled_payments = {}

# =========================================================
# 📝 LOGGING & REPORTING FUNCTIONS
# =========================================================
def start_session_logging():
    timestamp = datetime.now().strftime("%B %d, %Y - %I:%M:%S %p")
    header = f"""
======================================================================
PARKING TELLER SCRIPT SIMULATION LOGS
Starting Date & Time of Simulation: {timestamp}
Mode: {SIM_MODE}
Sequence Pattern: {WAIT_OPTIONS} Minutes (Sequential)
Feature: Round-Robin Distribution & Real-Time Terminal Counters
======================================================================
"""
    try:
        with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(header)
    except: pass

def end_session_logging():
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    footer = f"\n--- END OF SESSION ({timestamp}) ---\n\n"
    try:
        with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(footer)
    except: pass

atexit.register(end_session_logging)

def record(msg, type="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    color = bcolors.ENDC
    icon = "[*]"
    
    if type == "SUCCESS": color = bcolors.OKGREEN; icon = "[OK]"
    elif type == "WARN": color = bcolors.WARNING; icon = "[WARN]"
    elif type == "ERROR" or type == "RESET": color = bcolors.FAIL; icon = "[ERR]"
    elif type == "BILL": color = bcolors.OKCYAN; icon = "[BILL]"
    elif type == "SCAN": color = bcolors.OKBLUE; icon = "[SCAN]"
    elif type == "SKIP": color = bcolors.WARNING; icon = "[SKIP]"
    elif type == "TIME": color = bcolors.HEADER; icon = "[TIME]"
    elif type == "CONNECT": color = bcolors.OKGREEN; icon = "[CONN]"
    elif type == "DISCONNECT": color = bcolors.FAIL; icon = "[DISCO]"
    elif type == "INFO": color = bcolors.ENDC; icon = "[INFO]"
    elif type == "STATS": color = bcolors.OKCYAN; icon = "[STATS]"

    try:
        print(f"{color}[{timestamp}] {icon} {msg}{bcolors.ENDC}", flush=True)
    except UnicodeEncodeError:
        safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
        print(f"{color}[{timestamp}] {icon} {safe_msg}{bcolors.ENDC}", flush=True)

    try:
        with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{type}] {msg}\n")
    except: pass

def update_report(plate, fee, is_paid=True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    runtime = str(datetime.now() - stats["start_time"]).split('.')[0]
    
    summary = f"""------------------------------------------------------------
GENERATION DATE: {timestamp}
MODE: {SIM_MODE}
TOTAL RUN TIME: {runtime}
STATUS: IN-PROGRESS

Successful Payments: {stats['total_success']}
TOTAL REVENUE:       P{stats['total_collected']:.2f}
------------------------------------------------------------
TRANSACTIONS PER TERMINAL:
"""
    for term, count in stats["terminal_counts"].items():
        summary += f" - {term}: {count} transactions\n"
    
    summary += "------------------------------------------------------------\n"
    
    try:
        with open(os.path.join(LOGS_DIR, "teller_summary_report.txt"), "w", encoding="utf-8") as f:
            f.write(summary)
        
        status_text = f"P{fee:.2f} (PAID)" if is_paid else "ALREADY PAID (Skipped UI)"
        with open(HISTORY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] - {plate}: {status_text}\n")
    except: pass

# =========================================================
# 🛠️ HELPERS
# =========================================================
ENTRY_TIMES_FILE = os.path.join(DATA_DIR, "entry_times.json")

def save_entry_time(plate: str, time_in: str):
    try:
        with mailbox_lock:
            data = {}
            if os.path.exists(ENTRY_TIMES_FILE):
                with open(ENTRY_TIMES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[plate.upper()] = time_in
            with open(ENTRY_TIMES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        record(f"Failed to save entry time for {plate}: {e}", "WARN")

def get_entry_time(plate: str) -> Optional[str]:
    try:
        with mailbox_lock:
            if os.path.exists(ENTRY_TIMES_FILE):
                with open(ENTRY_TIMES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get(plate.upper())
    except:
        pass
    return None

def get_random_parking_duration() -> int:
    """Returns a random parking duration in minutes based on specified probabilities:
    - 80% chance: 45 minutes to 4 hours (45 - 240 mins)
    - 15% chance: 4 hours to 5 hours (240 - 300 mins)
    - 5% chance: 5 hours to 9 hours (300 - 540 mins)
    """
    prob = random.random()
    if prob < 0.80:
        return random.randint(45, 240)
    elif prob < 0.95:
        return random.randint(240, 300)
    else:
        return random.randint(300, 540)

PAID_PLATES_FILE = os.path.join(DATA_DIR, "paid_plates.json")

def record_paid_plate(plate: str, time_paid: str, vehicle_type: str = "CAR"):
    try:
        with mailbox_lock:
            data = []
            if os.path.exists(PAID_PLATES_FILE):
                with open(PAID_PLATES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            # Avoid duplicates
            if not any(tx.get("plate_no") == plate.upper() for tx in data):
                data.append({
                    "plate_no": plate.upper(),
                    "time_paid": time_paid,
                    "vehicle_type": vehicle_type
                })
                with open(PAID_PLATES_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        record(f"Failed to record paid plate {plate}: {e}", "WARN")

def reset_system_state(terminal_id, reason="Unknown Error"):
    global terminal_states
    with mailbox_lock:
        if terminal_id in terminal_states:
            terminal_states[terminal_id]["status"] = "IDLE"
        else:
            terminal_states[terminal_id] = {"status": "IDLE", "latest_telemetry": {}}
    
    record(f"[{terminal_id}] SYSTEM RESET: {reason} - Returning to IDLE state.", "RESET")

def remove_from_queue(plate_to_remove):
    try:
        with mailbox_lock:
            if not os.path.exists(LOCAL_QUEUE_FILE): return
            
            with open(LOCAL_QUEUE_FILE, "r") as f:
                queue = json.load(f)
            
            original_len = len(queue)
            new_queue = [p for p in queue if str(p).strip().upper() != plate_to_remove]
            
            if len(new_queue) < original_len:
                with open(LOCAL_QUEUE_FILE, "w") as f:
                    json.dump(new_queue, f, indent=2)
    except: pass

def signal_handler(sig, frame):
    print("\n")
    record("Stopping script...", "WARN")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_next_available_plate(terminal_id):
    if not is_real_device_payment_enabled():
        return None
    global scheduled_payments
    with mailbox_lock:
        master_list = []
        if os.path.exists(LOCAL_QUEUE_FILE):
            try:
                with open(LOCAL_QUEUE_FILE, "r") as f:
                    master_list = json.load(f)
                    master_list = [str(p).strip().upper() for p in master_list]
            except: pass
            
        if SIM_MODE == 'IMMEDIATE':
            for plate in master_list:
                if plate not in stats["processed_plates"] and plate not in active_transactions:
                    active_transactions.add(plate)
                    return plate
                    
        elif SIM_MODE == 'SCHEDULED':
            current_time = datetime.now()
            # Find plates in scheduled_payments that are ready (current_time >= due)
            # and not already in active_transactions
            ready_plates = [
                p for p, due in scheduled_payments.items()
                if current_time >= due and p not in active_transactions and p not in stats["processed_plates"]
            ]
            if ready_plates:
                selected_plate = ready_plates[0]
                active_transactions.add(selected_plate)
                return selected_plate
                
        return None

def sync_queue_with_active_parked():
    try:
        active_plates = set()
        sync_success = False
        
        # 1. Fetch active parked list
        try:
            res = api_session.get(f"{BASE_HOST}/api/parked/active", timeout=10)
            if res.status_code == 200:
                res_json = res.json()
                if res_json.get("success"):
                    sync_success = True
                    for tx in res_json.get("data", []):
                        if tx.get("plate_no"):
                            formatted_plate, _ = format_plate(tx.get("plate_no"))
                            if formatted_plate:
                                active_plates.add(formatted_plate)
        except Exception as e:
            record(f"Error fetching active parked list: {e}", "WARN")

        # 2. Fetch flagged parked list (over 24 hours)
        try:
            res_flagged = api_session.get(f"{BASE_HOST}/api/parked/flagged", timeout=10)
            if res_flagged.status_code == 200:
                res_json_flagged = res_flagged.json()
                if res_json_flagged.get("success"):
                    sync_success = True
                    for tx in res_json_flagged.get("data", []):
                        if tx.get("plate_no"):
                            formatted_plate, _ = format_plate(tx.get("plate_no"))
                            if formatted_plate:
                                active_plates.add(formatted_plate)
        except Exception as e:
            record(f"Error fetching flagged parked list: {e}", "WARN")

        if sync_success:
            with mailbox_lock:
                    queue = []
                    if os.path.exists(LOCAL_QUEUE_FILE):
                        try:
                            with open(LOCAL_QUEUE_FILE, "r") as f:
                                queue = json.load(f)
                                queue = [str(p).strip().upper() for p in queue]
                        except:
                            pass
                    
                    # Filter existing: only keep plates that are currently active in the database
                    new_queue = [p for p in queue if p in active_plates]
                    
                    # Add active plates that are not in the queue and not processed in this session
                    added_count = 0
                    for plate in active_plates:
                        if plate not in new_queue and plate not in stats["processed_plates"]:
                            new_queue.append(plate)
                            added_count += 1
                    
                    if new_queue != queue:
                        with open(LOCAL_QUEUE_FILE, "w") as f:
                            json.dump(new_queue, f, indent=2)
                        socketio.emit('queue_update', {"queue": new_queue})
                        record(f"Synced queue with active parked list. Queue size: {len(new_queue)} (Removed stale, added {added_count} missing)", "INFO")
                    else:
                        record(f"Queue sync complete. No changes required. Queue size: {len(new_queue)}", "INFO")
    except Exception as e:
        record(f"Sync exception: {e}", "ERROR")


# =========================================================
# 🌐 FLASK API & SOCKET EVENTS
# =========================================================
@app.route('/add-to-queue', methods=['POST'])
def add_to_queue():
    data = request.json
    raw_plate = data.get("plate_no", "")
    plate, _ = format_plate(raw_plate)
    time_in = data.get("time_in")
    if plate:
        if time_in:
            save_entry_time(plate, time_in)
        with mailbox_lock:
            queue = []
            if os.path.exists(LOCAL_QUEUE_FILE):
                try:
                    with open(LOCAL_QUEUE_FILE, "r") as f:
                        queue = json.load(f)
                except: pass
            
            if plate not in queue:
                queue.append(plate)
                with open(LOCAL_QUEUE_FILE, "w") as f:
                    json.dump(queue, f, indent=2)
                socketio.emit('queue_update', {"queue": queue})
                    
        record(f"Added to Queue: [{plate}]" + (f" | Entry Time: {time_in}" if time_in else ""), "INFO")
        return jsonify({"status": "added"}), 200
    return jsonify({"status": "invalid"}), 400

@app.route('/update-token', methods=['POST'])
def update_token():
    token = str((request.json or {}).get("token", "")).strip()
    if not token:
        return jsonify({"status": "invalid"}), 400
    api_session.headers["Authorization"] = f"Bearer {token}"
    record("API token updated from admin UI.", "INFO")
    return jsonify({"status": "updated"}), 200

@app.route('/get-queue', methods=['GET'])
def get_queue():
    queue = []
    with mailbox_lock: 
        if os.path.exists(LOCAL_QUEUE_FILE):
            try:
                with open(LOCAL_QUEUE_FILE, "r") as f:
                    queue = json.load(f)
            except: pass
    return jsonify({"queue": queue}), 200

@app.route('/get-status', methods=['GET'])
def get_status():
    queue_len = 0
    if os.path.exists(LOCAL_QUEUE_FILE):
        try:
            with open(LOCAL_QUEUE_FILE, "r") as f:
                queue_len = len(json.load(f))
        except: pass

    terminals_info = []
    with mailbox_lock:
        active_ids = set(active_terminals.values())
        for term_id, state in terminal_states.items():
            terminals_info.append({
                "terminal_id": term_id,
                "is_active": term_id in active_ids,
                "status": state.get("status", "IDLE") if term_id in active_ids else "OFFLINE",
                "latest_telemetry": state.get("latest_telemetry", {}),
                "tx_count": stats["terminal_counts"].get(term_id, 0)
            })

        active_tx_list = list(active_transactions)
        success_count = stats["total_success"]
        collected_amt = stats["total_collected"]
        uptime = (datetime.now() - stats["start_time"]).total_seconds()
        ram_history_copy = list(ram_history)

    return jsonify({
        "success": True,
        "active_terminals": terminals_info,
        "active_transactions": active_tx_list,
        "queue_size": queue_len,
        "total_success": success_count,
        "total_collected": collected_amt,
        "uptime_seconds": int(uptime),
        "ram_history": ram_history_copy
    }), 200

@app.route('/download-ram-logs', methods=['GET'])
def download_ram_logs():
    if os.path.exists(RAM_LOG_FILE):
        from flask import send_from_directory
        return send_from_directory(directory=LOGS_DIR, path="ram_usage.csv", as_attachment=True)
    return jsonify({"success": False, "message": "No RAM log file found"}), 404

# --- WEBSOCKET LISTENERS ---
@socketio.on('connect')
def handle_connect():
    pass

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in active_terminals:
        terminal_id = active_terminals.pop(request.sid)
        
        tx_count = stats["terminal_counts"].get(terminal_id, 0)
        
        record(f"Device disconnected! [Terminal ID: {terminal_id}]", "DISCONNECT")
        record(f"{terminal_id} processed a total of {tx_count} transactions before disconnecting.", "WARN")
        record(f"Current Active Terminals: {list(active_terminals.values())}\n", "INFO")
        
        if request.sid in active_workers:
            active_workers.pop(request.sid)

@socketio.on('register_terminal')
def handle_register(data):
    terminal_id = data.get('terminal_id', '').strip()
    if terminal_id:
        active_terminals[request.sid] = terminal_id
        join_room(terminal_id) 
        
        if terminal_id not in stats["terminal_counts"]:
            stats["terminal_counts"][terminal_id] = 0
            
        record(f"Device connected! [Terminal ID: {terminal_id}]", "CONNECT")
        record(f"Current Active Terminals: {list(active_terminals.values())}\n", "INFO")
        
        if request.sid not in active_workers:
            active_workers[request.sid] = socketio.start_background_task(run_terminal_worker, terminal_id, request.sid)

@socketio.on('ui_result')
def handle_ui_result(data):
    status = data.get("status")
    global terminal_states
    terminal_id = active_terminals.get(request.sid)
    if not terminal_id:
        return
        
    with mailbox_lock:
        if terminal_id not in terminal_states:
            terminal_states[terminal_id] = {"status": "IDLE", "latest_telemetry": {}}
            
        if status == "SUCCESS":
            terminal_states[terminal_id]["status"] = "SUCCESS"
        elif status == "FAILED":
            terminal_states[terminal_id]["status"] = "FAILED"
        
        # Capture the new memory metrics safely
        app_used = data.get("app_used_mb", 0)
        avail = data.get("device_avail_mb", 0)
        total = data.get("device_total_mb", 0)
        critical = data.get("is_memory_critical", False)
        
        terminal_states[terminal_id]["latest_telemetry"] = {
            "app_used_mb": app_used,
            "device_avail_mb": avail,
            "device_total_mb": total,
            "is_memory_critical": critical
        }
        
        # Log to the CSV file
        log_ram_telemetry(terminal_id, status, app_used, avail, total, critical)

# =========================================================
# 🧠 CORE PROCESSOR
# =========================================================
def check_status_only(plate):
    try:
        # Determine terminal ID dynamically
        terminal_id = "HaH-B5-02-00057"
        if active_terminals:
            terminal_id = list(active_terminals.values())[0]
            
        res = api_session.post(f"{BASE_HOST}/api/payment/plate-no",
                               json={"licence_plate_no": plate, "terminal": terminal_id},
                               timeout=3)
                               
        if res.status_code != 200:
            err_text = res.text.lower()
            if "already paid" in err_text or "payment successful" in err_text or "enter park" in err_text:
                return 'PAID'
            if "not inside" in err_text or "exited" in err_text or "no transaction" in err_text:
                return 'EXIT'
            record(f"[DEBUG] check_status_only for [{plate}] failed: HTTP {res.status_code} - {res.text}", "WARN")
            return 'ERROR'
            
        res_json = res.json()
        if not res_json.get("success"):
            msg = (res_json.get("message") or "").lower()
            if "already paid" in msg or "payment successful" in msg or "enter park" in msg:
                return 'PAID'
            if "not inside" in msg or "exited" in msg or "no transaction" in msg:
                return 'EXIT'
            record(f"[DEBUG] check_status_only for [{plate}] success=False: {res_json.get('message')}", "WARN")
            return 'ERROR'
            
        data = res_json.get("data", {})
        if not data:
            record(f"[DEBUG] check_status_only for [{plate}] data is empty", "WARN")
            return 'ERROR'
            
        fee = float(data.get("total_amount", 0.0))
        if fee <= 0:
            return 'PAID'
            
        return 'UNPAID'
        
    except Exception as e:
        record(f"[DEBUG] Exception in check_status_only for [{plate}]: {e}", "ERROR")
        return 'ERROR'

def process_vehicle_transaction(plate, selected_sid, selected_terminal):
    try:
        # Direct Payment Check / Bill retrieval
        try:
            pay_info_res = api_session.post(f"{BASE_HOST}/api/payment/plate-no",
                                            json={"licence_plate_no": plate, "terminal": selected_terminal},
                                            timeout=5)
        except RequestException as e:
            reset_system_state(selected_terminal, f"Network Error (Bill): {e}")
            return False

        if pay_info_res.status_code != 200:
            # Check if it failed because it's already paid or exited
            err_text = pay_info_res.text.lower()
            if "already paid" in err_text or "payment successful" in err_text or "enter park" in err_text:
                record(f"Plate [{plate}] is already paid. Skipping.", "SKIP")
                save_processed_plate(plate)
                update_report(plate, 0, is_paid=False)
                # Record paid plate for exit simulation
                p_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                record_paid_plate(plate, p_time_str, "CAR")
                remove_from_queue(plate)
                trigger_exit_immediately(plate, "CAR")
                return True
            if "not inside" in err_text or "exited" in err_text or "no transaction" in err_text:
                record(f"Plate [{plate}] has no active transaction or has already exited. Removing from queue.", "SKIP")
                remove_from_queue(plate)
                save_processed_plate(plate)
                return True
                
            reset_system_state(selected_terminal, f"API Error ({pay_info_res.status_code}): {pay_info_res.text}")
            return False
            
        res_json = pay_info_res.json()
        if not res_json.get("success"):
            msg = (res_json.get("message") or "").lower()
            if "already paid" in msg or "payment successful" in msg or "enter park" in msg:
                record(f"Plate [{plate}] is already paid (from success=False). Skipping.", "SKIP")
                save_processed_plate(plate)
                update_report(plate, 0, is_paid=False)
                # Record paid plate for exit simulation
                p_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                record_paid_plate(plate, p_time_str, res_json.get("data", {}).get("vehicle_type", "CAR").upper())
                remove_from_queue(plate)
                trigger_exit_immediately(plate, res_json.get("data", {}).get("vehicle_type", "CAR").upper())
                return True
            if "not inside" in msg or "exited" in msg or "no transaction" in msg:
                record(f"Plate [{plate}] has no active transaction or has already exited. Removing from queue.", "SKIP")
                remove_from_queue(plate)
                save_processed_plate(plate)
                return True
                
            reset_system_state(selected_terminal, f"Payment calculation failed for {plate}: {res_json.get('message')}")
            return False

        # If success=True, extract billing details
        ref_no = res_json.get("reference_no")
        fee = float(res_json.get("data", {}).get("total_amount", 0.0))
        
        # If fee is 0, check if already paid or skip
        if fee <= 0:
            record(f"Plate [{plate}] has zero bill or is already paid. Skipping.", "SKIP")
            save_processed_plate(plate)
            # Record it as paid
            p_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            record_paid_plate(plate, p_time_str, res_json.get("data", {}).get("vehicle_type", "CAR").upper())
            remove_from_queue(plate)
            trigger_exit_immediately(plate, res_json.get("data", {}).get("vehicle_type", "CAR").upper())
            return True

        # Use actual current time for payment
        payment_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Proceed with UI transaction!
        record(f"{selected_terminal} scans plate [{plate}] | Payment Time: {payment_time_str}...", "SCAN")
        record(f"Plate [{plate}] amounts to P{fee:.2f}", "BILL")
        
        if execute_ui_transaction(plate, ref_no, fee, selected_sid, selected_terminal, payment_time_str):
            save_processed_plate(plate)
            stats["total_success"] += 1
            stats["total_collected"] += fee
            
            stats["terminal_counts"][selected_terminal] = stats["terminal_counts"].get(selected_terminal, 0) + 1
            current_terminal_tx = stats["terminal_counts"][selected_terminal]
            
            update_report(plate, fee, is_paid=True)
            record(f"Transaction Complete! Plate: {plate} | Paid at: {payment_time_str} | Total Revenue: P{stats['total_collected']:.2f}", "SUCCESS")
            record(f"{selected_terminal} CURRENT TALLY: {current_terminal_tx} Transactions", "STATS")
            
            # Record successfully paid plate for exit simulation
            record_paid_plate(plate, payment_time_str, res_json.get("data", {}).get("vehicle_type", "CAR").upper())
            remove_from_queue(plate)
            trigger_exit_immediately(plate, res_json.get("data", {}).get("vehicle_type", "CAR").upper())
            return True
        else:
            reset_system_state(selected_terminal, "UI Transaction Failed/Timed Out")
            return False

    except Exception as e:
        reset_system_state(selected_terminal, f"Script Error: {e}")
        return False

def execute_ui_transaction(plate, ref, fee, selected_sid, selected_terminal, sim_payment_time_str):
    global terminal_states
    
    with mailbox_lock:
        if selected_terminal not in terminal_states:
            terminal_states[selected_terminal] = {}
        terminal_states[selected_terminal]["status"] = "WAITING"
    
    # 🚦 1. PUSH TO VUE: Process Plate
    socketio.emit('instruction', {
        "action": "PROCESS_PLATE", 
        "plate": plate, 
        "terminal_id": selected_terminal,
        "timestamp": sim_payment_time_str
    }, room=selected_terminal) 
    
    socketio.sleep(get_process_delay()) 
    
    possible_bills = [100, 200, 500, 1000]
    valid_options = [b for b in possible_bills if b >= fee]
    cash = fee
    if fee <= 1000 and valid_options:
        cash = float(random.choice(valid_options))
    
    # 🚦 2. PUSH TO VUE: Pay Now
    payload = {
        "action": "PAY_NOW", 
        "amount": fee, 
        "cash": cash, 
        "ref": ref, 
        "plate": plate, 
        "terminal_id": selected_terminal,
        "timestamp": sim_payment_time_str
    }
    socketio.emit('instruction', payload, room=selected_terminal) 
    
    record(f"{selected_terminal} processing payment (Cash: P{cash:.2f})...", "TIME")

    # 🚦 3. WAIT FOR VUE TO EMIT 'ui_result'
    start_wait = time.time()
    while (time.time() - start_wait) < TIMEOUT_LIMIT:
        # Check if the terminal is still active
        if selected_sid not in active_terminals:
            return False
            
        with mailbox_lock:
            state = terminal_states.get(selected_terminal, {})
            status = state.get("status")
            if status in ["SUCCESS", "FAILED"]:
                # Extract the latest captured metrics
                telemetry = state.get("latest_telemetry", {})
                app_used = telemetry.get("app_used_mb", 0)
                avail = telemetry.get("device_avail_mb", 0)
                total = telemetry.get("device_total_mb", 0)
                critical = telemetry.get("is_memory_critical", False)
                
                # Determine log color/severity based on the critical flag
                log_type = "WARN" if critical else "STATS"
                
                if critical:
                    record(f"MEMORY CRITICAL ON {selected_terminal}! App: {app_used}MB | Free: {avail}MB/{total}MB", log_type)
                else:
                    record(f"{selected_terminal} Memory: {app_used}MB | {avail}MB/{total}MB", log_type)
                
                state["status"] = "IDLE"
                return True if status == "SUCCESS" else False
        socketio.sleep(1)
    
    return False

# =========================================================
# 🎮 MAIN SIMULATION LOOP
# =========================================================
def run_terminal_worker(terminal_id, sid):
    record(f"Worker simulation started for {terminal_id}", "SUCCESS")
    while True:
        with mailbox_lock:
            # Check if this session is still the active session for this terminal
            if active_terminals.get(sid) != terminal_id:
                break
        
        plate = get_next_available_plate(terminal_id)
        if not plate:
            socketio.sleep(2)
            continue
            
        success = process_vehicle_transaction(plate, sid, terminal_id)
        
        with mailbox_lock:
            if plate in active_transactions:
                active_transactions.remove(plate)
                
        if success:
            cooldown = get_cooldown()
            record(f"[{terminal_id}] Next car arriving in {cooldown}s...\n{'-'*50}", "TIME")
            socketio.sleep(cooldown)
        else:
            with mailbox_lock:
                if SIM_MODE == 'SCHEDULED' and plate in scheduled_payments:
                    # Reschedule failed payment slightly
                    scheduled_payments[plate] = datetime.now() + timedelta(seconds=30)
            socketio.sleep(5)
            
    record(f"Worker simulation stopped for {terminal_id}", "WARN")

def manage_scheduler():
    global scheduled_payments
    wait_sequence_index = 0
    last_sync_time = time.time()
    
    start_session_logging()

    print("\n" + "="*50)
    record(f"TELLER AUTOMATION SCHEDULER STARTED", "SUCCESS")
    record(f"Mode: {SIM_MODE}", "INFO")
    print("="*50 + "\n")

    # Initial synchronization
    sync_queue_with_active_parked()

    while True:
        try:
            if not is_real_device_payment_enabled():
                socketio.sleep(2)
                continue

            if time.time() - last_sync_time > 30:
                sync_queue_with_active_parked()
                last_sync_time = time.time()

            if SIM_MODE == 'SCHEDULED':
                master_list = []
                with mailbox_lock: 
                    if os.path.exists(LOCAL_QUEUE_FILE):
                        try:
                            with open(LOCAL_QUEUE_FILE, "r") as f:
                                master_list = json.load(f)
                                master_list = [str(p).strip().upper() for p in master_list]
                        except: pass

                current_time = datetime.now()

                for plate in master_list:
                    pending_count = sum(1 for p in scheduled_payments if p not in stats["processed_plates"])
                    if pending_count >= 50:
                        break

                    if plate not in stats["processed_plates"] and plate not in scheduled_payments:
                        status = check_status_only(plate)
                        if status == 'EXIT': 
                            remove_from_queue(plate)
                            save_processed_plate(plate)
                            continue
                        if status == 'PAID':
                            save_processed_plate(plate)
                            update_report(plate, 0, is_paid=False)
                            # Record already paid plate for exit simulation
                            record(f"Plate {plate} has already been paid", "STATS")
                            p_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            record_paid_plate(plate, p_time_str, "CAR")
                            remove_from_queue(plate)
                            trigger_exit_immediately(plate, "CAR")
                            continue
                        elif status == 'ERROR': continue
                        
                        wait_seconds = WAIT_OPTIONS[wait_sequence_index]
                        due_time = current_time + timedelta(seconds=wait_seconds)
                        scheduled_payments[plate] = due_time

                        time_str = due_time.strftime("%H:%M:%S")
                        record(f"Scheduled [{plate}] at {time_str} (+{wait_seconds}s)", "INFO")
                        wait_sequence_index = (wait_sequence_index + 1) % len(WAIT_OPTIONS)

            socketio.sleep(2)
        except Exception as main_e:
            record(f"CRITICAL SCHEDULER EXCEPTION: {main_e}", "ERROR")
            socketio.sleep(5)

if __name__ == "__main__":
    load_ram_history()
    socketio.start_background_task(manage_scheduler)
    socketio.run(app, host='0.0.0.0', port=5010, debug=False, use_reloader=False)
