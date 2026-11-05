import threading
import os
import json
import time
import requests
from datetime import datetime, timedelta
from scripts.app_context import socketio
import scripts.config as config
from scripts.utils import ADMIN_CAR_CODES, ADMIN_MOTORCYCLE_CODES, format_plate
from scripts.disposition import decide_disposition


def write_json_atomic(path, data):
    """Same JSON layout as before, but written to a temp file and swapped in,
    so a crash mid-write can't leave a truncated file behind."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp_path, path)

# ==============================================================================
# 🔒 ORIGINAL CORE LOCKS & RUNTIME VARIABLES (RESTORED)
# ==============================================================================
queue_lock = threading.Lock()
matching_lock = threading.Lock()
detections_lock = threading.Lock()

upcoming_entries = []     
scheduled_payments = []  
scheduled_exits = []     

connected_terminals = {}

# LPR cameras that posted detections but are not under any terminal gate yet
# {ip: {"ip", "mac", "channel_name", "last_plate", "last_seen", "hits"}}
unregistered_cameras = {}

sim_stats = {
    "queued": 0,  
    "parked": 0,  
    "paid": 0,    
    "exited": 0   
}

logs_history = []

last_displayed_entry = {}  # {gate_id: [ {"plate": plate, "time": datetime.now(), "matched": False} ]}
last_displayed_exit = {}   # {gate_id: [ {"plate": plate, "time": datetime.now(), "matched": False} ]}

DETECTIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recent_detections.json")
recent_detections = []
detections_lock = threading.Lock()
is_hcp_connected = False

# Full-size camera frames live in logs/media and are served on demand via get_detection_images.
# Keeping them in recent_detections made the list (and its JSON file) grow to hundreds of MB.
HEAVY_DETECTION_KEYS = ("front_plate_image", "front_vehicle_image", "back_plate_image", "back_vehicle_image")

def strip_heavy_detection_images(det):
    for key in HEAVY_DETECTION_KEYS:
        det.pop(key, None)
    return det

def load_recent_detections():
    global recent_detections
    os.makedirs(os.path.dirname(DETECTIONS_FILE), exist_ok=True)
    if os.path.exists(DETECTIONS_FILE):
        try:
            with open(DETECTIONS_FILE, "r", encoding="utf-8") as f:
                recent_detections = [strip_heavy_detection_images(d) for d in json.load(f)]
        except Exception as e:
            print(f"Error loading recent detections: {e}", flush=True)

def save_recent_detections():
    try:
        os.makedirs(os.path.dirname(DETECTIONS_FILE), exist_ok=True)
        write_json_atomic(DETECTIONS_FILE, recent_detections)
    except Exception as e:
        print(f"Error saving recent detections: {e}", flush=True)

# Load recent detections on startup
load_recent_detections()


def read_reconciliation_log(date_str):
    metadata_file = os.path.join(RECON_LOG_DIR, f"reconciliation_log_{date_str}.json")
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def enrich_detection_images(det):
    det_copy = dict(det)
    
    # Identify keys based on dictionary structure
    front_key = "plate_image_front" if "plate_image_front" in det_copy else "img_front"
    back_key = "plate_image_back" if "plate_image_back" in det_copy else "img_back"
    plate_key_name = "plate_no" if "plate_no" in det_copy else "det_plate"
    ts_key_name = "timestamp" if "timestamp" in det_copy else "ts"
    
    # If the images are already base64, do nothing
    if (det_copy.get(front_key) and str(det_copy[front_key]).startswith("data:")) or \
       (det_copy.get(back_key) and str(det_copy[back_key]).startswith("data:")):
        return det_copy
        
    plate_no = det_copy.get(plate_key_name)
    timestamp = det_copy.get(ts_key_name)
    if plate_no and timestamp:
        # Guessed date from timestamp (format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM:SS")
        date_str = timestamp.split(" ")[0] if " " in timestamp else (timestamp.split("T")[0] if "T" in timestamp else datetime.now().strftime("%Y-%m-%d"))
        
        clean_plate = plate_no.replace(" ", "").strip().upper()
        try:
            if "T" in timestamp:
                det_dt = datetime.fromisoformat(timestamp.replace("Z", ""))
            else:
                det_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except Exception:
            det_dt = datetime.now()
            
        # Normalize naive det_dt
        if det_dt.tzinfo is not None:
            det_dt = det_dt.replace(tzinfo=None)
            
        # Detections from earlier days aren't in today's in-memory history, so read that day's log instead
        past_history = None
        if date_str != current_history_date:
            past_history = read_reconciliation_log(date_str)

        matched_key = None
        with reconciliation_lock:
            for key, rec in list(pending_reconciliations.items()):
                if not rec or not isinstance(rec, dict):
                    continue
                if clean_plate in get_record_plates(key, rec):
                    first_seen_str = rec.get("first_seen")
                    if first_seen_str:
                        try:
                            rec_dt = datetime.fromisoformat(first_seen_str.replace("Z", ""))
                            if rec_dt.tzinfo is not None:
                                rec_dt = rec_dt.replace(tzinfo=None)
                            if abs((det_dt - rec_dt).total_seconds()) <= 120:
                                matched_key = rec.get("plate_key")
                                break
                        except Exception:
                            pass
            
            if not matched_key:
                for rec in (past_history if past_history is not None else daily_reconciliation_history):
                    if not rec or not isinstance(rec, dict):
                        continue
                    key = rec.get("plate_key", "")
                    if clean_plate in get_record_plates(key, rec):
                        first_seen_str = rec.get("first_seen")
                        if first_seen_str:
                            try:
                                rec_dt = datetime.fromisoformat(first_seen_str.replace("Z", ""))
                                if rec_dt.tzinfo is not None:
                                    rec_dt = rec_dt.replace(tzinfo=None)
                                if abs((det_dt - rec_dt).total_seconds()) <= 120:
                                    matched_key = rec.get("plate_key")
                                    break
                            except Exception:
                                pass
                                
        if matched_key:
            media_dir = os.path.join(RECON_LOG_DIR, "media", date_str)
            individual_media_file = os.path.join(media_dir, f"{matched_key}.json")
            if os.path.exists(individual_media_file):
                try:
                    with open(individual_media_file, "r", encoding="utf-8") as f:
                        media = json.load(f)
                        
                        # Assign all 4 discrete image formats
                        det_copy["front_plate_image"] = media.get("front_plate_image") or ""
                        det_copy["front_vehicle_image"] = media.get("front_vehicle_image") or ""
                        det_copy["back_plate_image"] = media.get("back_plate_image") or ""
                        det_copy["back_vehicle_image"] = media.get("back_vehicle_image") or ""
                        
                        # Maintain legacy keys for default fallbacks
                        front_img = media.get("front_plate_image") or media.get("front_vehicle_image")
                        back_img = media.get("back_plate_image") or media.get("back_vehicle_image")
                        if front_img:
                            det_copy[front_key] = front_img
                        if back_img:
                            det_copy[back_key] = back_img
                except Exception:
                    pass
    return det_copy



# ==============================================================================
# 🔄 RECONCILIATION ENGINE STATE & ATOMIC STORAGE
# ==============================================================================
reconciliation_lock = threading.Lock()
pending_reconciliations = {}
daily_reconciliation_history = []
current_history_date = None

RECON_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
if not os.path.exists(RECON_LOG_DIR):
    os.makedirs(RECON_LOG_DIR)

def load_today_reconciliation_history():
    """Loads only lightweight metadata into memory for snappy reloads."""
    global daily_reconciliation_history, current_history_date
    date_str = datetime.now().strftime("%Y-%m-%d")
    current_history_date = date_str
    metadata_file = os.path.join(RECON_LOG_DIR, f"reconciliation_log_{date_str}.json")
    
    with reconciliation_lock:
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    daily_reconciliation_history = json.load(f)
                print(f"[BOOTLOAD] Recovered {len(daily_reconciliation_history)} lightweight metadata logs.", flush=True)
            except Exception as e:
                print(f"[BOOTLOAD WARNING] Failed parsing today's log file: {e}", flush=True)
                daily_reconciliation_history = []
                # Set the unreadable file aside so the next save doesn't overwrite what's left of it
                try:
                    corrupt_file = metadata_file.replace(".json", f".corrupt-{datetime.now().strftime('%H%M%S')}")
                    os.replace(metadata_file, corrupt_file)
                    print(f"[BOOTLOAD WARNING] Moved unreadable log to {corrupt_file}", flush=True)
                except Exception as move_err:
                    print(f"[BOOTLOAD WARNING] Could not set aside unreadable log: {move_err}", flush=True)
        else:
            daily_reconciliation_history = []

def ensure_today_history():
    global daily_reconciliation_history, current_history_date
    today_str = datetime.now().strftime("%Y-%m-%d")
    if current_history_date != today_str:
        load_today_reconciliation_history()

all_time_stats = None

def get_record_stats_category(r):
    if not r:
        return "partial"
        
    if not r.get("core_event") and not r.get("hikcentral"):
        return "partial"

    # Get chosen camera plate and type from the disposition flow
    decision = decide_disposition(r)
    cam = r.get(f"{decision['chosen_camera']}_camera") or {}
    cam_plate = cam.get("plate")
    cam_type = cam.get("vehicle_type")

    admin_plate = r["core_event"].get("plate_no") if r.get("core_event") else None
    admin_type = r["core_event"].get("vehicle_type_code", "").upper() if r.get("core_event") else None

    hcp_plate = r["hikcentral"].get("plate") if r.get("hikcentral") else None
    hcp_type = r["hikcentral"].get("vehicleType", "").upper() if r.get("hikcentral") else None

    # Normalize plates
    norm_cam = cam_plate.replace(" ", "").upper() if cam_plate else None
    norm_admin = admin_plate.replace(" ", "").upper() if admin_plate else None
    norm_hcp = hcp_plate.replace(" ", "").upper() if hcp_plate else None

    unique_plates = {p for p in [norm_cam, norm_admin, norm_hcp] if p}
    unique_types = {t for t in [cam_type, admin_type, hcp_type] if t}

    # All different mismatches
    if norm_cam and norm_admin and norm_hcp and norm_cam != norm_admin and norm_cam != norm_hcp and norm_admin != norm_hcp:
        return "mismatch"

    if cam_type and admin_type and hcp_type and cam_type != admin_type and cam_type != hcp_type and admin_type != hcp_type:
        return "mismatch"

    # All match
    if len(unique_plates) <= 1 and len(unique_types) <= 1:
        return "matched"

    # Auto-resolution helper using disposition target
    dispo = decision["disposition"].lower()
    dispo_target = None
    if "motor" in dispo:
        dispo_target = "MOTORCYCLE"
    elif "car" in dispo:
        dispo_target = "CAR"

    if len(unique_plates) <= 1 and dispo_target:
        if admin_type == dispo_target and hcp_type != dispo_target:
            return "corrected"
        if hcp_type == dispo_target and admin_type != dispo_target:
            return "corrected"

    if len(unique_plates) > 1 and cam_plate:
        if norm_cam == norm_admin or norm_cam == norm_hcp:
            return "corrected"

    return "mismatch"

def get_all_time_reconciliation_stats():
    stats = {"matched": 0, "corrected": 0, "mismatch": 0, "partial": 0, "total": 0}
    try:
        if os.path.exists(RECON_LOG_DIR):
            for filename in os.listdir(RECON_LOG_DIR):
                if filename.startswith("reconciliation_log_") and filename.endswith(".json"):
                    filepath = os.path.join(RECON_LOG_DIR, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            records = json.load(f)
                            for r in records:
                                cat = get_record_stats_category(r)
                                stats[cat] += 1
                                stats["total"] += 1
                    except Exception as e:
                        print(f"Error loading stats file {filename}: {e}", flush=True)
    except Exception as e:
        print(f"Error getting all-time stats: {e}", flush=True)
    return stats

def init_all_time_stats():
    global all_time_stats
    all_time_stats = get_all_time_reconciliation_stats()

def get_available_reconciliation_dates():
    dates = []
    try:
        if os.path.exists(RECON_LOG_DIR):
            for filename in os.listdir(RECON_LOG_DIR):
                if filename.startswith("reconciliation_log_") and filename.endswith(".json"):
                    date_part = filename[len("reconciliation_log_"):-len(".json")]
                    dates.append(date_part)
    except Exception as e:
        print(f"Error listing reconciliation dates: {e}", flush=True)
    dates.sort(reverse=True)
    return dates

def get_reconciliation_history_for_date(date_query):
    # Saved rows can predate the current rules, so the dashboard always gets a fresh decision
    records = load_reconciliation_history_for_date(date_query)
    for record in records:
        record.update(decide_disposition(record))
    return records

def load_reconciliation_history_for_date(date_query):
    global daily_reconciliation_history
    if date_query == "today":
        ensure_today_history()
        today_str = datetime.now().strftime("%Y-%m-%d")
        with reconciliation_lock:
            original_len = len(daily_reconciliation_history)
            cleaned = [r for r in daily_reconciliation_history if r.get("first_seen", "").startswith(today_str)]
            if len(cleaned) < original_len:
                daily_reconciliation_history = cleaned
                metadata_file = os.path.join(RECON_LOG_DIR, f"reconciliation_log_{today_str}.json")
                try:
                    write_json_atomic(metadata_file, daily_reconciliation_history)
                    print(f"[REPAIR] Cleaned {original_len - len(cleaned)} leaked records from today's log.", flush=True)
                except Exception as e:
                    print(f"Error saving cleaned today's log: {e}", flush=True)
            return list(daily_reconciliation_history)
            
    elif date_query == "all":
        all_records = []
        try:
            dates = get_available_reconciliation_dates()
            for d in dates:
                metadata_file = os.path.join(RECON_LOG_DIR, f"reconciliation_log_{d}.json")
                if os.path.exists(metadata_file):
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        records = json.load(f)
                        # Filter to ensure records belong to date file d
                        cleaned = [r for r in records if r.get("first_seen", "").startswith(d)]
                        all_records.extend(cleaned)
        except Exception as e:
            print(f"Error loading all reconciliation history: {e}", flush=True)
        # Sort by first_seen ascending so when reversed in frontend it is descending (newest first)
        all_records.sort(key=lambda x: x.get("first_seen", ""), reverse=False)
        return all_records
        
    else:
        metadata_file = os.path.join(RECON_LOG_DIR, f"reconciliation_log_{date_query}.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    records = json.load(f)
                cleaned = [r for r in records if r.get("first_seen", "").startswith(date_query)]
                if len(cleaned) < len(records):
                    try:
                        write_json_atomic(metadata_file, cleaned)
                        print(f"[REPAIR] Cleaned {len(records) - len(cleaned)} leaked records from date {date_query} log.", flush=True)
                    except Exception as e:
                        print(f"Error rewriting cleaned log for date {date_query}: {e}", flush=True)
                return cleaned
            except Exception as e:
                print(f"Error loading reconciliation log for date {date_query}: {e}", flush=True)
        return []


def start_reconciliation_cleanup_thread():
    def cleanup_loop():
        while True:
            time.sleep(60)  # Check every minute
            now = datetime.now()
            with reconciliation_lock:
                to_remove = []
                for key, record in list(pending_reconciliations.items()):
                    last_active_str = record.get("last_active")
                    if last_active_str:
                        try:
                            last_active_dt = datetime.fromisoformat(last_active_str)
                            if now - last_active_dt > timedelta(minutes=5):
                                to_remove.append(key)
                        except Exception:
                            # Fallback to first_seen
                            first_seen_str = record.get("first_seen")
                            if first_seen_str:
                                try:
                                    first_seen_dt = datetime.fromisoformat(first_seen_str)
                                    if now - first_seen_dt > timedelta(minutes=5):
                                        to_remove.append(key)
                                except Exception:
                                    pass
                    else:
                        first_seen_str = record.get("first_seen")
                        if first_seen_str:
                            try:
                                first_seen_dt = datetime.fromisoformat(first_seen_str)
                                if now - first_seen_dt > timedelta(minutes=5):
                                    to_remove.append(key)
                            except Exception:
                                pass
                for key in to_remove:
                    pending_reconciliations.pop(key, None)
                    
    threading.Thread(target=cleanup_loop, daemon=True).start()

load_today_reconciliation_history()
init_all_time_stats()
start_reconciliation_cleanup_thread()

def update_ticketing_decision(plate_key, date_str, decision):
    return update_reconciliation_fields(plate_key, date_str, {"ticketing_decision": decision})

def update_reconciliation_fields(plate_key, date_str, fields):
    global daily_reconciliation_history

    # Extract date part if full ISO string
    if date_str and "T" in date_str:
        date_str = date_str.split("T")[0]
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    updated_record = None
    
    with reconciliation_lock:
        # Keep the in-flight record in sync too, otherwise its next save would drop the fields
        if plate_key in pending_reconciliations:
            pending_reconciliations[plate_key].update(fields)

        # If the date is today, we can find and update it directly in daily_reconciliation_history
        if date_str == today_str:
            ensure_today_history()
            existing_idx = next((i for i, item in enumerate(daily_reconciliation_history) if item["plate_key"] == plate_key), None)
            if existing_idx is not None:
                daily_reconciliation_history[existing_idx].update(fields)
                updated_record = daily_reconciliation_history[existing_idx]
                
                # Write to disk
                metadata_file = os.path.join(RECON_LOG_DIR, f"reconciliation_log_{today_str}.json")
                try:
                    write_json_atomic(metadata_file, daily_reconciliation_history)
                except Exception as e:
                    print(f"[METADATA UPDATE ERROR] {e}", flush=True)
        else:
            # It's an older date, read from its specific file
            metadata_file = os.path.join(RECON_LOG_DIR, f"reconciliation_log_{date_str}.json")
            if os.path.exists(metadata_file):
                try:
                    records = []
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    
                    existing_idx = next((i for i, item in enumerate(records) if item["plate_key"] == plate_key), None)
                    if existing_idx is not None:
                        records[existing_idx].update(fields)
                        updated_record = records[existing_idx]
                        
                        write_json_atomic(metadata_file, records)
                except Exception as e:
                    print(f"Error updating historical reconciliation log for date {date_str}: {e}", flush=True)

    return updated_record

SERVER_SAVE_CHECK_DELAY = 45  # seconds after first detection before asking the server about an entry or exit
SERVER_EXIT_MATCH_WINDOW = 600  # seconds; a further time_out belongs to another visit of the same plate

def summarize_plate_no_reply(res_json, queried_plate, normal_response):
    """The /plate-no fields shown under Admin Read. The full reply also carries store/billing info we don't need."""
    data = res_json.get("data") if isinstance(res_json.get("data"), dict) else {}
    vehicle_info = res_json.get("vehicle_info") if isinstance(res_json.get("vehicle_info"), dict) else {}
    message = res_json.get("message")
    summary = {
        "queried_plate": queried_plate,
        # False for message-only replies (already paid, no payment required): the dashboard hides those from Server Read
        "normal_response": normal_response,
        "checked_at": datetime.now().isoformat(),
        "plate_no": res_json.get("plate_no") or data.get("plate_no"),
        "reference_no": res_json.get("reference_no") or data.get("reference_no"),
        "ticket_no": res_json.get("ticket_no") or data.get("ticket_no"),
        "transaction_id": data.get("transaction_id"),
        "vehicle_type": data.get("vehicle_type_name") or vehicle_info.get("vehicle_type"),
        "customer_type": data.get("customer_type_name"),
        "gate_id": res_json.get("gate_id"),
        "entry": res_json.get("entry"),
        "parking_duration": res_json.get("parking_duration"),
        "total_amount": data.get("total_amount"),
        "reason": data.get("reason"),
        "message": message if isinstance(message, str) else None,
    }
    return {k: v for k, v in summary.items() if v not in (None, "")}

def lookup_plate_on_server(plate):
    """Summary of the /api/payment/plate-no reply when the server knows the plate (the entry was saved), else None."""
    res = requests.post(f"{config.API_BASE_URL}/api/payment/plate-no",
                        json={"licence_plate_no": plate, "terminal": config.TERMINAL_ID},
                        headers=config.HEADERS, timeout=5)
    try:
        res_json = res.json()
    except ValueError:
        res_json = {}
    if not isinstance(res_json, dict):
        res_json = {}

    data = res_json.get("data")
    normal_response = bool(res.status_code == 200 and res_json.get("success") and data)
    found = normal_response
    # "No payment required" replies (e.g. the old ENTRY_GRACE) come back as success: false
    # with data.payment_required: false, but the transaction exists.
    # Same rule as noPaymentRequired() in the teller app (src/services/PlateLookup.js).
    if not found and isinstance(data, dict) and data.get("payment_required") is False:
        found = True
    if not found:
        message = res_json.get("message")
        text = (message if isinstance(message, str) else res.text).lower()
        # Already-paid plates are rejected, but they still exist on the server
        found = any(k in text for k in ["already paid", "payment successful", "enter park"])
    return summarize_plate_no_reply(res_json, plate, normal_response) if found else None

def summarize_payment_report_row(row, queried_plate):
    """The /reports/payment fields kept on the row. The full reply also carries VAT and store info we don't need."""
    summary = {
        "queried_plate": queried_plate,
        "normal_response": True,
        "checked_at": datetime.now().isoformat(),
        "plate_no": row.get("plate_no"),
        "invoice_no": row.get("invoice_no"),
        "transaction_id": row.get("transaction_id"),
        "ticket_no": row.get("ticket_no"),
        "customer_type": row.get("customer_type"),
        "vehicle_type": row.get("vehicle_type"),
        "time_in": row.get("time_in"),
        "time_out": row.get("time_out"),
        "time_paid": row.get("time_paid"),
        "entry_point": row.get("entry_point"),
        "exit_point": row.get("exit_point"),
        "amount_paid": row.get("amount_paid"),
        "payment_method": row.get("payment_method"),
        "payment_channel": row.get("payment_channel"),
    }
    return {k: v for k, v in summary.items() if v not in (None, "")}

def lookup_exit_on_server(plate, first_seen):
    """Summary of the /api/reports/payment row for this exit, else None."""
    seen_dt = datetime.fromisoformat(first_seen).replace(tzinfo=None)
    res = requests.get(f"{config.API_BASE_URL}/api/reports/payment", params={
        "search": plate,
        "page": 1,
        "per_page": 15,
        "limit": 15,
        "offset": 0,
        "sort_by": "time_out",
        "sort_order": "desc",
        # Runs to the day of the check so an exit just past midnight is still in range
        "start_date": f"{seen_dt:%Y-%m-%d} 00:00:00",
        "end_date": f"{datetime.now():%Y-%m-%d} 23:59:59",
    }, headers=config.ADMIN_HEADERS, timeout=5)
    res.raise_for_status()
    res_json = res.json()
    rows = res_json.get("data") if isinstance(res_json, dict) else None

    # search is a partial match, so a row only counts with the exact plate and a time_out close to this detection
    wanted_plate = plate.replace(" ", "").upper()
    best_row, best_gap = None, SERVER_EXIT_MATCH_WINDOW
    for row in rows if isinstance(rows, list) else []:
        if (row.get("plate_no") or "").replace(" ", "").upper() != wanted_plate:
            continue
        try:
            gap = abs((datetime.strptime(row.get("time_out") or "", "%Y-%m-%d %H:%M:%S") - seen_dt).total_seconds())
        except ValueError:
            continue
        if gap <= best_gap:
            best_row, best_gap = row, gap
    return summarize_payment_report_row(best_row, plate) if best_row else None

def check_saved_on_server(plate_key):
    with reconciliation_lock:
        record = pending_reconciliations.get(plate_key) or next(
            (r for r in daily_reconciliation_history if r.get("plate_key") == plate_key), None)
        if not record:
            return
        is_exit = (record.get("direction") or "entry").lower() == "exit"
        first_seen = record.get("first_seen")
        chosen_plate = record.get("chosen_plate")

    key_plate = (chosen_plate or plate_key.split('_')[0]).replace(" ", "")
    # The server may store car plates spaced ("ABC 1234"), so try both spellings
    candidates = list(dict.fromkeys([key_plate, format_plate(key_plate)[0]]))
    server_record = None
    for plate in candidates:
        try:
            server_record = lookup_exit_on_server(plate, first_seen) if is_exit else lookup_plate_on_server(plate)
            if server_record:
                break
        except Exception as e:
            print(f"[SERVER SAVE CHECK] {plate}: {e}", flush=True)

    updated_record = update_reconciliation_fields(plate_key, first_seen, {
        "server_saved": server_record is not None,
        "server_record": server_record,
    })
    if updated_record:
        socketio.emit('reconciled_vehicle_updated', updated_record, to='admin_room')

def schedule_server_save_check(plate_key):
    timer = threading.Timer(SERVER_SAVE_CHECK_DELAY, check_saved_on_server, args=(plate_key,))
    timer.daemon = True
    timer.start()

def save_reconciled_record_to_disk(unified_data):
    """Splits data payload into pure text log and heavy base64 image data log."""
    global daily_reconciliation_history
    ensure_today_history()
    date_str = datetime.now().strftime("%Y-%m-%d")
    metadata_file = os.path.join(RECON_LOG_DIR, f"reconciliation_log_{date_str}.json")
    
    plate_key = unified_data["plate_key"]

    media_payload = {
        "plate_key": plate_key,
        "front_plate_image": unified_data["front_camera"].get("plate_image") if unified_data["front_camera"] else "",
        "front_vehicle_image": unified_data["front_camera"].get("vehicle_image") if unified_data["front_camera"] else "",
        "back_plate_image": unified_data["back_camera"].get("plate_image") if unified_data["back_camera"] else "",
        "back_vehicle_image": unified_data["back_camera"].get("vehicle_image") if unified_data["back_camera"] else ""
    }

    metadata_payload = json.loads(json.dumps(unified_data))  
    if metadata_payload["front_camera"]:
        metadata_payload["front_camera"].pop("plate_image", None)
        metadata_payload["front_camera"].pop("vehicle_image", None)
    if metadata_payload["back_camera"]:
        metadata_payload["back_camera"].pop("plate_image", None)
        metadata_payload["back_camera"].pop("vehicle_image", None)

    with reconciliation_lock:
        existing_idx = next((i for i, item in enumerate(daily_reconciliation_history) if item["plate_key"] == plate_key), None)
        
        # Incrementally update all-time stats cache
        global all_time_stats
        if all_time_stats is not None:
            if existing_idx is not None:
                old_cat = get_record_stats_category(daily_reconciliation_history[existing_idx])
                all_time_stats[old_cat] = max(0, all_time_stats[old_cat] - 1)
                all_time_stats["total"] = max(0, all_time_stats["total"] - 1)
            
            new_cat = get_record_stats_category(metadata_payload)
            all_time_stats[new_cat] += 1
            all_time_stats["total"] += 1

        if existing_idx is not None:
            daily_reconciliation_history[existing_idx] = metadata_payload
        else:
            daily_reconciliation_history.append(metadata_payload)
            
        try:
            write_json_atomic(metadata_file, daily_reconciliation_history)
        except Exception as e:
            print(f"[METADATA WRITE ERROR] {e}", flush=True)

        # Save Media Map to individual file
        media_dir = os.path.join(RECON_LOG_DIR, "media", date_str)
        try:
            os.makedirs(media_dir, exist_ok=True)
            individual_media_file = os.path.join(media_dir, f"{plate_key}.json")
            write_json_atomic(individual_media_file, media_payload)
        except Exception as e:
            print(f"[MEDIA WRITE ERROR] {e}", flush=True)
            
    socketio.emit('new_reconciled_vehicle', metadata_payload, to='admin_room')
    if all_time_stats is not None:
        socketio.emit('all_time_reconciliation_stats_response', all_time_stats, to='admin_room')
    try:
        dates = get_available_reconciliation_dates()
        socketio.emit('available_reconciliation_dates_response', dates, to='admin_room')
    except Exception:
        pass


def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def clean_source_plate(data):
    raw_plate = data.get("plate") or data.get("plate_no") or ""
    return raw_plate.replace(" ", "").strip().upper()

def get_record_plates(key, rec):
    """Every plate this record answers to: its key plate plus each source's read (UNKNOWN reads excluded)."""
    plates = {key.split('_')[0]}
    for source_plate in [
        (rec.get("front_camera") or {}).get("plate"),
        (rec.get("back_camera") or {}).get("plate"),
        (rec.get("hikcentral") or {}).get("plate"),
        (rec.get("core_event") or {}).get("plate_no"),
    ]:
        if source_plate:
            clean = source_plate.replace(" ", "").strip().upper()
            if clean and clean not in ("UNKNOWN", "EMPTY"):
                plates.add(clean)
    return plates

PAIR_WINDOW_SECONDS = 4  # the other camera's read of the same vehicle arrives within this long of the first read
PAIR_MAX_PLATE_DISTANCE = 2  # front and back can disagree by OCR noise; a bigger difference is another vehicle
CAMERA_SLOTS = {"FRONT_CAM": ("front", "front_camera", "back_camera"), "BACK_CAM": ("back", "back_camera", "front_camera")}

def find_lane_partner(data, incoming_dt):
    """The row in this camera's lane that this read belongs to: a read from either camera, of the same vehicle.
    Covers the other camera's read and a repeat trigger of the same camera.
    An UNKNOWN read on either side has no text to compare, so it pairs on lane and time alone."""
    plate = clean_source_plate(data)
    best_key, best_score = None, None
    for key, rec in pending_reconciliations.items():
        reads = [r for r in (rec.get("front_camera"), rec.get("back_camera")) if r]
        if not reads:
            continue
        if (rec.get("terminal_id") != data.get("terminal_id") or rec.get("gate") != f"GATE {data.get('gate_id')}"
                or rec.get("direction") != data.get("direction")):
            continue
        try:
            gap = abs((incoming_dt - datetime.fromisoformat(rec.get("first_camera_at"))).total_seconds())
        except (TypeError, ValueError):
            continue
        if gap > PAIR_WINDOW_SECONDS:
            continue
        distance = min(
            0 if "UNKNOWN" in (plate, clean_source_plate(read)) else levenshtein_distance(plate, clean_source_plate(read))
            for read in reads
        )
        if distance <= PAIR_MAX_PLATE_DISTANCE and (best_score is None or (distance, gap) < best_score):
            best_key, best_score = key, (distance, gap)
    return best_key

def read_replaces_existing(existing, data):
    """A repeat trigger only replaces a camera's read if it's at least as good, so a late bad read can't undo a good one."""
    if not existing or clean_source_plate(existing) == "UNKNOWN":
        return True
    if clean_source_plate(data) == "UNKNOWN":
        return False
    return (data.get("confidence") or 0) >= (existing.get("confidence") or 0)

BARRIER_MATCH_WINDOW = 600  # seconds; an exit barrier only opens after payment, well past the 120s window used for plate reads
BARRIER_RETRY_DELAY = 5  # seconds between attempts, since the barrier event can arrive before the plate reads
BARRIER_MAX_ATTEMPTS = 4

def find_record_for_barrier(barrier, plate, direction, opened_dt):
    """The row closest to the barrier time with this plate and direction. Rows with no direction yet (no camera read) also qualify."""
    best_record, best_gap = None, BARRIER_MATCH_WINDOW
    for rec in list(pending_reconciliations.values()) + daily_reconciliation_history:
        if plate not in get_record_plates(rec.get("plate_key", ""), rec):
            continue
        rec_direction = (rec.get("direction") or "").lower()
        if rec_direction and direction and rec_direction != direction:
            continue
        # A row already opened by another transaction belongs to an earlier visit of the same plate
        rec_barrier = rec.get("barrier")
        if rec_barrier and rec_barrier.get("transaction_id") != barrier.get("transaction_id"):
            continue
        try:
            rec_dt = datetime.fromisoformat(rec.get("first_seen")).replace(tzinfo=None)
        except (TypeError, ValueError):
            continue
        gap = abs((opened_dt - rec_dt).total_seconds())
        if gap <= best_gap:
            best_record, best_gap = rec, gap
    return best_record

def apply_barrier_open(barrier, attempt=1):
    """Stores a server barrier event on its plate's row and pushes the update to the dashboard."""
    plate = clean_source_plate(barrier)
    direction = (barrier.get("direction") or "").lower()
    try:
        opened_dt = datetime.strptime(barrier.get("barrier_open_at") or "", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        opened_dt = None
    if not plate or not opened_dt:
        print(f"[BARRIER] Skipped event without a plate or open time: {barrier}", flush=True)
        return

    ensure_today_history()
    with reconciliation_lock:
        record = find_record_for_barrier(barrier, plate, direction, opened_dt)
        if record:
            plate_key = record.get("plate_key")
            first_seen = record.get("first_seen")
            fields = {"barrier": barrier}
            if direction and not record.get("direction"):
                fields["direction"] = direction

    if not record:
        if attempt < BARRIER_MAX_ATTEMPTS:
            timer = threading.Timer(BARRIER_RETRY_DELAY, apply_barrier_open, args=(barrier, attempt + 1))
            timer.daemon = True
            timer.start()
        else:
            print(f"[BARRIER] No {direction} row found for {plate} at {barrier.get('barrier_open_at')}", flush=True)
        return

    updated_record = update_reconciliation_fields(plate_key, first_seen, fields)
    if updated_record:
        socketio.emit('reconciled_vehicle_updated', updated_record, to='admin_room')

def process_and_buffer_data(source_type, data):
    process_and_buffer_bundle([(source_type, data)])

def process_and_buffer_bundle(sources):
    """Merges one or more (source_type, data) pairs into the same reconciliation record.
    Sources that arrive in a single message (e.g. HCP + admin disposition) must be bundled
    here so they always share a row, even when their plate reads disagree."""
    ensure_today_history()
    sources = [(st, d) for st, d in sources if clean_source_plate(d) and clean_source_plate(d) != "EMPTY"]
    if not sources:
        return

    # UNKNOWN says nothing about which vehicle this is, so it never matches a row by plate
    incoming_plates = {clean_source_plate(d) for _, d in sources} - {"UNKNOWN"}
    first_source, data = sources[0]
    incoming_plate = clean_source_plate(data)

    now = datetime.now()

    # Parse incoming timestamp for time-window matching
    ts_str = data.get("time") or data.get("timestamp") or now.isoformat()
    incoming_dt = None
    try:
        if "T" in ts_str:
            incoming_dt = datetime.fromisoformat(ts_str.replace("Z", ""))
        else:
            incoming_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        incoming_dt = now

    # Normalize incoming_dt to be timezone-naive
    if incoming_dt.tzinfo is not None:
        incoming_dt = incoming_dt.replace(tzinfo=None)

    matched_key = None

    # HCP knows its direction, so its exit read can't land on the same plate's entry row (or the reverse)
    hcp_direction = data.get("direction") if first_source == "HCP" else None
    def direction_conflicts(rec):
        return bool(hcp_direction and rec.get("direction") and rec.get("direction") != hcp_direction)

    with reconciliation_lock:
        # 0. A camera read first looks for the other camera's read of the same vehicle in its lane
        if first_source in CAMERA_SLOTS:
            matched_key = find_lane_partner(data, incoming_dt)

        # 1. Search for a recent matching record in pending within 2 minutes (120 seconds) of incoming_dt
        for key, rec in list(pending_reconciliations.items()):
            if matched_key:
                break
            if get_record_plates(key, rec) & incoming_plates and not direction_conflicts(rec):
                rec_dt = None
                first_seen_str = rec.get("first_seen")
                if first_seen_str:
                    try:
                        rec_dt = datetime.fromisoformat(first_seen_str)
                        if rec_dt.tzinfo is not None:
                            rec_dt = rec_dt.replace(tzinfo=None)
                    except Exception:
                        pass
                if rec_dt and abs((incoming_dt - rec_dt).total_seconds()) <= 120:
                    matched_key = key
                    break

        # 2. If not found in pending, check today's daily history for a recent matching record
        if not matched_key:
            for rec in daily_reconciliation_history:
                key = rec.get("plate_key", "")
                if get_record_plates(key, rec) & incoming_plates and not direction_conflicts(rec):
                    rec_dt = None
                    first_seen_str = rec.get("first_seen")
                    if first_seen_str:
                        try:
                            rec_dt = datetime.fromisoformat(first_seen_str)
                            if rec_dt.tzinfo is not None:
                                rec_dt = rec_dt.replace(tzinfo=None)
                        except Exception:
                            pass
                    if rec_dt and abs((incoming_dt - rec_dt).total_seconds()) <= 120:
                        matched_key = key
                        pending_reconciliations[matched_key] = rec
                        break

        # 3. If still not matched, generate a new unique key with a timestamp suffix
        if not matched_key:
            timestamp_suffix = incoming_dt.strftime("%H%M%S")
            candidate_key = f"{incoming_plate}_{timestamp_suffix}"
            counter = 1
            while (candidate_key in pending_reconciliations) or any(r.get("plate_key") == candidate_key for r in daily_reconciliation_history):
                candidate_key = f"{incoming_plate}_{timestamp_suffix}_{counter}"
                counter += 1
            matched_key = candidate_key

        # 4. If new session, initialize record
        if matched_key not in pending_reconciliations:
            pending_reconciliations[matched_key] = {
                "plate_key": matched_key,
                "first_seen": now.isoformat(),
                "status": "partial",
                "disposition": "NA",
                "core_event": None,
                "front_camera": None,
                "back_camera": None,
                "hikcentral": None
            }
            schedule_server_save_check(matched_key)

        record = pending_reconciliations[matched_key]
        record["last_active"] = now.isoformat()

        def normalize_camera_vehicle_type(raw_type):
            if not raw_type: return "CAR"
            clean_type = str(raw_type).strip().upper().replace("/", "")
            # if clean_type in ["SEDAN", "SUVMPV", "MINIVAN", "PICKUPTRUCK", "VEHICLE", "CAR"]: return "CAR"
            if clean_type in ["TWOWHEELER", "MOTORCYCLE", "MOTORBIKE", "BIKE", "TWO-WHEELER", "MOTOR VEHICLE", "TWOWHEELVEHICLE"]: return "MOTORCYCLE"
            return "CAR"

        # Ingestion assignments
        for source_type, data in sources:
            if source_type in CAMERA_SLOTS:
                # Kept from the first read: later triggers replace a camera's read but must not move this
                if not record.get("first_camera_at"):
                    record["first_camera"] = CAMERA_SLOTS[source_type][0]
                    record["first_camera_at"] = data.get("timestamp")
                if not read_replaces_existing(record.get(CAMERA_SLOTS[source_type][1]), data):
                    continue

            if source_type == "AVAILABLE_SPACE":
                raw_admin_code = data.get("vehicle_type")
                admin_code = str(raw_admin_code).strip()
                admin_vehicle_string = "CAR" if admin_code in ADMIN_CAR_CODES else ("MOTORCYCLE" if admin_code in ADMIN_MOTORCYCLE_CODES else "OTHERS")
            
                raw_img_name = data.get("plate_image_back")
                http_image_url = f"{config.API_BASE_URL}/anpr/{raw_img_name}" if raw_img_name else ""

                record["core_event"] = {
                    "plate_no": data.get("plate_no"),
                    "vehicle_type_code": admin_vehicle_string,
                    "raw_type_received": raw_admin_code,
                    "gate_id": data.get("gate_id"),
                    "timestamp": data.get("time"),
                    "percentage": data.get("percentage"),
                    "image_url": http_image_url
                }
            
            elif source_type == "FRONT_CAM":
                record["front_camera"] = {
                    "plate": data.get("plate"),
                    "vehicle_type": normalize_camera_vehicle_type(data.get("vehicleType")),
                    "raw_type_received": data.get("vehicleType"),
                    "confidence": data.get("confidence"),
                    "timestamp": data.get("timestamp"),
                    "plate_image": data.get("plateImage"),      
                    "vehicle_image": data.get("vehicleImage")
                }
                if data.get("terminal_id"):
                    record["terminal_id"] = data.get("terminal_id")
                    record["terminal_name"] = data.get("terminal_name")
                if data.get("gate_id"):
                    record["gate"] = f"GATE {data.get('gate_id')}"
                if data.get("direction"):
                    record["direction"] = data.get("direction")
            
            elif source_type == "BACK_CAM":
                record["back_camera"] = {
                    "plate": data.get("plate"),
                    "vehicle_type": normalize_camera_vehicle_type(data.get("vehicleType")),
                    "raw_type_received": data.get("vehicleType"),
                    "confidence": data.get("confidence"),
                    "timestamp": data.get("timestamp"),
                    "plate_image": data.get("plateImage"),
                    "vehicle_image": data.get("vehicleImage")
                }
                if data.get("terminal_id"):
                    record["terminal_id"] = data.get("terminal_id")
                    record["terminal_name"] = data.get("terminal_name")
                if data.get("gate_id"):
                    record["gate"] = f"GATE {data.get('gate_id')}"
                if data.get("direction"):
                    record["direction"] = data.get("direction")
            
            elif source_type == "HCP":
                record["hikcentral"] = {
                    "plate": data.get("plate"),
                    "vehicleType": normalize_camera_vehicle_type(data.get("vehicleType")),
                    "raw_type_received": data.get("vehicleType"),
                    "gateName": data.get("gateName"),
                    "timestamp": data.get("timestamp")
                }
                # Cameras know their lane's direction better, so this only fills a row without one
                if data.get("direction") and not record.get("direction"):
                    record["direction"] = data.get("direction")

        record.update(decide_disposition(record))

        # Update match status based on our category calculator
        record["status"] = get_record_stats_category(record)

    save_reconciled_record_to_disk(record)