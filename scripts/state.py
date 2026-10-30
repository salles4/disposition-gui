import threading
import os
import json
import time
import requests
from datetime import datetime, timedelta
from scripts.app_context import socketio
import scripts.config as config
from scripts.utils import ADMIN_CAR_CODES, ADMIN_MOTORCYCLE_CODES, format_plate


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

# LPR cameras that posted detections but are not in camera_mapping yet
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

    # Get chosen camera plate and type based on confidence
    cam_plate = None
    cam_type = None
    
    f_cam = r.get("front_camera")
    b_cam = r.get("back_camera")
    
    if f_cam and b_cam:
        f_conf = float(f_cam.get("confidence", 0) or 0)
        b_conf = float(b_cam.get("confidence", 0) or 0)
        if f_conf >= b_conf:
            cam_plate = f_cam.get("plate")
            cam_type = f_cam.get("vehicle_type")
        else:
            cam_plate = b_cam.get("plate")
            cam_type = b_cam.get("vehicle_type")
    elif f_cam:
        cam_plate = f_cam.get("plate")
        cam_type = f_cam.get("vehicle_type")
    elif b_cam:
        cam_plate = b_cam.get("plate")
        cam_type = b_cam.get("vehicle_type")

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
    dispo = (r.get("disposition") or "").lower()
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
    return update_reconciliation_field(plate_key, date_str, "ticketing_decision", decision)

def update_reconciliation_field(plate_key, date_str, field, value):
    global daily_reconciliation_history

    # Extract date part if full ISO string
    if date_str and "T" in date_str:
        date_str = date_str.split("T")[0]
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    updated_record = None
    
    with reconciliation_lock:
        # Keep the in-flight record in sync too, otherwise its next save would drop the field
        if plate_key in pending_reconciliations:
            pending_reconciliations[plate_key][field] = value

        # If the date is today, we can find and update it directly in daily_reconciliation_history
        if date_str == today_str:
            ensure_today_history()
            existing_idx = next((i for i, item in enumerate(daily_reconciliation_history) if item["plate_key"] == plate_key), None)
            if existing_idx is not None:
                daily_reconciliation_history[existing_idx][field] = value
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
                        records[existing_idx][field] = value
                        updated_record = records[existing_idx]
                        
                        write_json_atomic(metadata_file, records)
                except Exception as e:
                    print(f"Error updating historical reconciliation log for date {date_str}: {e}", flush=True)

    return updated_record

SERVER_SAVE_CHECK_DELAY = 45  # seconds after first detection before asking the server about an entry

def plate_no_has_record(plate):
    """True when /api/payment/plate-no knows the plate, i.e. the entry was saved on the server."""
    res = requests.post(f"{config.API_BASE_URL}/api/payment/plate-no",
                        json={"licence_plate_no": plate, "terminal": config.TERMINAL_ID},
                        headers=config.HEADERS, timeout=5)
    if res.status_code == 200:
        res_json = res.json()
        if res_json.get("success") and res_json.get("data"):
            return True
        text = (res_json.get("message") or "").lower()
    else:
        text = res.text.lower()
    # Already-paid plates are rejected, but they still exist on the server
    return any(k in text for k in ["already paid", "payment successful", "enter park"])

def check_entry_saved_on_server(plate_key):
    with reconciliation_lock:
        record = pending_reconciliations.get(plate_key) or next(
            (r for r in daily_reconciliation_history if r.get("plate_key") == plate_key), None)
        if not record or (record.get("direction") or "entry").lower() != "entry":
            return
        first_seen = record.get("first_seen")

    key_plate = plate_key.split('_')[0]
    # The server may store car plates spaced ("ABC 1234"), so try both spellings
    candidates = list(dict.fromkeys([key_plate, format_plate(key_plate)[0]]))
    saved = False
    for plate in candidates:
        try:
            if plate_no_has_record(plate):
                saved = True
                break
        except Exception as e:
            print(f"[SERVER SAVE CHECK] {plate}: {e}", flush=True)

    updated_record = update_reconciliation_field(plate_key, first_seen, "server_saved", saved)
    if updated_record:
        socketio.emit('reconciled_vehicle_updated', updated_record, to='admin_room')

def schedule_server_save_check(plate_key):
    timer = threading.Timer(SERVER_SAVE_CHECK_DELAY, check_entry_saved_on_server, args=(plate_key,))
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

    incoming_plates = {clean_source_plate(d) for _, d in sources}
    _, data = sources[0]
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

    with reconciliation_lock:
        # 1. Search for a recent matching record in pending within 2 minutes (120 seconds) of incoming_dt
        for key, rec in list(pending_reconciliations.items()):
            if get_record_plates(key, rec) & incoming_plates:
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
                if get_record_plates(key, rec) & incoming_plates:
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

        # =========================================================
        # 🎯 AUTOMATED DISPOSITION TRUTH TABLE CALCULATOR
        # =========================================================
        # Map parameters dynamically (Default fallbacks protect from crash splits)
        flp = 1 if (record["front_camera"] and record["front_camera"].get("plate")) else 0
        fvt = 1 if (record["front_camera"] and record["front_camera"].get("vehicle_type") == "MOTORCYCLE") else 0
        blp = 1 if (record["back_camera"] and record["back_camera"].get("plate")) else 0
        bvt = 1 if (record["back_camera"] and record["back_camera"].get("vehicle_type") == "MOTORCYCLE") else 0

        # Tuple key index map matching matrix sequence targets
        truth_table = {
            (0, 0, 0, 0): "NA", 
            (0, 0, 0, 1): "Ticket", 
            (0, 0, 1, 0): "Car LP", 
            (0, 0, 1, 1): "Motor LP",
            (0, 1, 0, 0): "Ticket", 
            (0, 1, 0, 1): "Ticket", 
            (0, 1, 1, 0): "Ticket", 
            (0, 1, 1, 1): "Motor LP",
            (1, 0, 0, 0): "Car LP",    # Fixed Line 9
            (1, 0, 0, 1): "Car LP",
            (1, 0, 1, 0): "Car LP",
            (1, 0, 1, 1): "Car LP",
            (1, 1, 0, 0): "NA",        # 🔥 Fixed Line 13 from "Car LP" to "NA"
            (1, 1, 0, 1): "NA",
            (1, 1, 1, 0): "NA",
            (1, 1, 1, 1): "NA"
        }

        # Match row configuration and append output label code
        record["disposition"] = truth_table.get((flp, fvt, blp, bvt), "NA")

        # Update match status based on our category calculator
        record["status"] = get_record_stats_category(record)

    save_reconciled_record_to_disk(record)