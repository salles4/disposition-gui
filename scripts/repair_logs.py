import os
import json
from datetime import datetime

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

    # FIXED TRUTH TABLE CONFIGURATION MATRIX
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
        (1, 1, 0, 0): "NA",        # Fixed Line 13 from "Car LP" to "NA"
        (1, 1, 0, 1): "NA",
        (1, 1, 1, 0): "NA",
        (1, 1, 1, 1): "NA"
    }

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

        # Re-calculate binary states
        flp = 1 if (row.get("front_camera") and row["front_camera"].get("plate")) else 0
        fvt = 1 if (row.get("front_camera") and row["front_camera"].get("vehicle_type") == "MOTORCYCLE") else 0
        blp = 1 if (row.get("back_camera") and row["back_camera"].get("plate")) else 0
        bvt = 1 if (row.get("back_camera") and row["back_camera"].get("vehicle_type") == "MOTORCYCLE") else 0

        new_dispo = truth_table.get((flp, fvt, blp, bvt), "NA")
        if row.get("disposition") != new_dispo:
            row["disposition"] = new_dispo
            repaired_count += 1

    # Overwrite repaired JSON array back to file
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4, ensure_ascii=False)

    print(f"Success! Re-calculated matrix execution. Corrected {repaired_count} entries to match the whiteboard.")

if __name__ == "__main__":
    repair_today_json_matrix()