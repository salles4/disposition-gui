import os
import csv
import sys
from datetime import datetime
from scripts.app_context import socketio
from scripts.state import logs_history
from scripts.utils import format_plate

# Configure safe maximum CSV field size limit to prevent image base64 load crashes
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

class LogColors:
    RESET = "\033[0m"
    CYAN, YELLOW, MAGENTA, GREEN, RED, BOLD = "\033[36m", "\033[33m", "\033[35m", "\033[32m", "\033[31m", "\033[1m"

def log_event(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    color = {"ENTRY": LogColors.YELLOW, "EXIT": LogColors.GREEN, "PAY": LogColors.MAGENTA, "ADMIN": LogColors.CYAN, "ERROR": LogColors.RED}.get(level, LogColors.CYAN)
    print(f"[{ts}] {color}[{level}] {msg}{LogColors.RESET}", flush=True)
    
    log_entry = {
        "ts": ts,
        "level": level,
        "msg": msg
    }
    logs_history.append(log_entry)
    if len(logs_history) > 100:
        logs_history.pop(0)
    
    try:
        socketio.emit('new_log', log_entry, to='admin_room')
    except Exception:
        pass

MANUAL_REPORT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manual_verification_report.csv")

def log_manual_verification(stage, gate, det_plate, det_type, act_plate, act_type, status, remarks, img_front, img_back):
    file_exists = os.path.exists(MANUAL_REPORT_FILE)
    try:
        with open(MANUAL_REPORT_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Timestamp", "Stage", "Gate", 
                    "Detected Plate", "Detected Type", 
                    "Actual Plate", "Actual Type", 
                    "Result", "Remarks", 
                    "Image Front", "Image Back"
                ])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                stage,
                f"GATE {gate}",
                det_plate,
                str(det_type).upper(),
                act_plate,
                str(act_type).upper(),
                status,
                remarks,
                img_front,
                img_back
            ])
        
        socketio.emit('manual_verification_new', {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stage": stage,
            "gate": f"GATE {gate}",
            "det_plate": det_plate,
            "det_type": str(det_type).upper(),
            "act_plate": act_plate,
            "act_type": str(act_type).upper(),
            "status": status,
            "remarks": remarks,
            "img_front": img_front,
            "img_back": img_back
        }, to='admin_room')

        log_event(f"[MANUAL] {stage} Gate {gate} | Det: {det_plate} ({det_type}) | Actual: {act_plate} ({act_type}) | Result: {status}", "STATS")
    except Exception as e:
        log_event(f"Error writing manual verification report: {e}", "ERROR")

import json

MANUAL_HISTORY_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "manual_verification_history.json")

def load_manual_verification_history(limit=None):
    if not os.path.exists(MANUAL_HISTORY_JSON):
        return []
    try:
        with open(MANUAL_HISTORY_JSON, "r", encoding="utf-8") as f:
            records = json.load(f)
        formatted = []
        for r in records:
            formatted.append({
                "ts": r.get("ts", ""),
                "stage": r.get("stage", "ENTRY"),
                "gate": r.get("gate", "1"),
                "det_plate": r.get("det_plate", ""),
                "det_type": r.get("det_type", "CAR"),
                "act_plate": r.get("act_plate", ""),
                "act_type": r.get("act_type", "CAR"),
                "status": r.get("status", "CORRECT"),
                "remarks": r.get("remarks", ""),
                "img_front": r.get("img_front", ""),
                "img_back": r.get("img_back", "")
            })
        if limit is not None:
            return formatted[:limit]
        return formatted
    except Exception as e:
        print(f"Error loading manual history JSON: {e}", flush=True)
        return []

def clear_manual_verification_report():
    try:
        if os.path.exists(MANUAL_REPORT_FILE):
            os.remove(MANUAL_REPORT_FILE)
    except Exception as e:
        print(f"Error clearing manual verification report CSV: {e}", flush=True)

def update_manual_verification_record(ts, det_plate, status, act_plate, act_type, remarks):
    if not os.path.exists(MANUAL_HISTORY_JSON):
        return False
        
    records = []
    try:
        with open(MANUAL_HISTORY_JSON, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception:
        return False
        
    updated = False
    target_rec = None
    for r in records:
        if r.get("ts") == ts and r.get("det_plate") == det_plate:
            r["status"] = status
            r["act_plate"] = act_plate
            r["act_type"] = act_type
            r["remarks"] = remarks
            target_rec = r
            updated = True
            break
            
    if not updated:
        return False
        
    try:
        with open(MANUAL_HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=4, ensure_ascii=False)
    except Exception:
        return False
        
    # Sync with CSV report file
    try:
        if status == "CORRECT":
            rows = []
            headers = []
            csv_updated = False
            file_exists = os.path.exists(MANUAL_REPORT_FILE)
            if file_exists:
                with open(MANUAL_REPORT_FILE, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    headers = next(reader, [])
                    for row in reader:
                        ts_idx = headers.index("Timestamp") if "Timestamp" in headers else 0
                        det_plate_idx = headers.index("Detected Plate") if "Detected Plate" in headers else 3
                        act_plate_idx = headers.index("Actual Plate") if "Actual Plate" in headers else 5
                        act_type_idx = headers.index("Actual Type") if "Actual Type" in headers else 6
                        result_idx = headers.index("Result") if "Result" in headers else 7
                        remarks_idx = headers.index("Remarks") if "Remarks" in headers else 8
                        
                        if len(row) > max(ts_idx, det_plate_idx, act_plate_idx, act_type_idx, result_idx, remarks_idx):
                            if row[ts_idx] == ts and row[det_plate_idx] == det_plate:
                                row[result_idx] = status
                                row[act_plate_idx] = act_plate
                                row[act_type_idx] = act_type
                                row[remarks_idx] = remarks
                                csv_updated = True
                        rows.append(row)
                
            if csv_updated:
                with open(MANUAL_REPORT_FILE, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if headers:
                        writer.writerow(headers)
                    writer.writerows(rows)
            else:
                log_manual_verification(
                    stage=target_rec.get("stage", "ENTRY"),
                    gate=target_rec.get("gate", "1"),
                    det_plate=det_plate,
                    det_type=target_rec.get("det_type", "CAR"),
                    act_plate=act_plate,
                    act_type=act_type,
                    status=status,
                    remarks=remarks,
                    img_front=target_rec.get("img_front", ""),
                    img_back=target_rec.get("img_back", "")
                )
        else:
            if os.path.exists(MANUAL_REPORT_FILE):
                rows = []
                headers = []
                csv_removed = False
                with open(MANUAL_REPORT_FILE, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    headers = next(reader, [])
                    for row in reader:
                        ts_idx = headers.index("Timestamp") if "Timestamp" in headers else 0
                        det_plate_idx = headers.index("Detected Plate") if "Detected Plate" in headers else 3
                        if len(row) > max(ts_idx, det_plate_idx):
                            if row[ts_idx] == ts and row[det_plate_idx] == det_plate:
                                csv_removed = True
                                continue
                        rows.append(row)
                if csv_removed:
                    with open(MANUAL_REPORT_FILE, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        if headers:
                            writer.writerow(headers)
                        writer.writerows(rows)
    except Exception as e:
        print(f"Error syncing update with CSV report: {e}", flush=True)
        
    return True


