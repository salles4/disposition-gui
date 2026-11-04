import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts.disposition import decide_disposition

# Path allocation configuration
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
# date_str = datetime.now().strftime("%Y-%m-%d")
target_file = os.path.join(LOG_DIR, f"reconciliation_log_2026-06-20.json")

def normalize_camera_vehicle_type(raw_type):
    """Unified binary normalization rule."""
    if not raw_type: 
        return "CAR"
        
    clean_type = str(raw_type).strip().upper().replace("/", "").replace("-", "")
    
    motorcycle_keywords = [
        "TWOWHEELER", 
        "MOTORCYCLE", 
        "MOTORBIKE", 
        "BIKE", 
        "TWOWHEELVEHICLE"
    ]
    
    if clean_type in motorcycle_keywords: 
        return "MOTORCYCLE"
        
    return "CAR"

def repair_today_json_matrix():
    if not os.path.exists(target_file):
        print(f"Today's log file does not exist yet: {target_file}")
        return

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception as e:
        print(f"Read error or empty log file: {e}")
        return

    print(f"Scanning {len(records)} records for retroactive matrix re-calculation...")
    repaired_count = 0

    for row in records:
        # Re-evaluate Front Camera
        if row.get("front_camera"):
            row["front_camera"]["vehicle_type"] = normalize_camera_vehicle_type(row["front_camera"].get("raw_type_received"))
        
        # Re-evaluate Back Camera
        if row.get("back_camera"):
            row["back_camera"]["vehicle_type"] = normalize_camera_vehicle_type(row["back_camera"].get("raw_type_received"))

        # Re-evaluate HCP Node
        if row.get("hikcentral"):
            row["hikcentral"]["vehicleType"] = normalize_camera_vehicle_type(row["hikcentral"].get("raw_type_received"))

        # Re-calculate the decision
        decision = decide_disposition(row)
        if any(row.get(k) != v for k, v in decision.items()):
            row.update(decision)
            repaired_count += 1

    # Overwrite repaired JSON array back to file
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4, ensure_ascii=False)

    print(f"Success! Re-calculated matrix execution. Corrected {repaired_count} entries to match the flowchart.")

if __name__ == "__main__":
    repair_today_json_matrix()