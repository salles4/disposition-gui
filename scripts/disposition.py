"""
Automated Disposition
=====================
Pure logic, no I/O. Same flow as disposition.py in vermosa-parking-disposition,
which follows the Parking Disposition flowchart. The HCP step is skipped for now.

UNKNOWN reads count as no read. Only UNKNOWN reads -> Ignored. No camera read -> NA.

The camera that read the plate first decides the branch, using its vehicle type.
A read is high score at min_confidence or above; a missing score is low.

Car: check the first camera, then the other one. The first high score read goes
to the format check. No high score read -> Ticket.

Motorcycle: only the back read counts.
- Back camera first: high score goes to the format check, low -> Ticket.
- Front camera first: high score -> Ticket, low -> use the back read as above.

A front read with vehicle type motorcycle and a high score is always a Ticket
when it's reached, including on the car branch.

Format check: the plate must fit the read's vehicle type. Car format on a car
-> Car LP, motorcycle format on a motorcycle -> Motor LP, otherwise Ticket.
"""

import re

# Below this a read is a low vehicle score, per the flowchart.
DEFAULT_MIN_CONFIDENCE = 80

MOTORCYCLE_PATTERNS = [
    re.compile(r"^\d{4}[A-Z]{2}$"),       # Legacy MC (e.g., 2724SO)
    re.compile(r"^[A-Z]{2}\d{5}$"),       # 2 Letters, 5 Numbers (AB12345)
    re.compile(r"^[A-Z]{3}\d{5}$"),       # 3 Letters, 5 Numbers (ABC12345)
    re.compile(r"^[A-Z]\d{5}[A-Z]$"),     # 1 Letter, 5 Numbers, 1 Letter (N12345A)
    re.compile(r"^\d{3}[A-Z]{3}$"),       # 3 Numbers, 3 Letters (123ABC)
    re.compile(r"^[A-Z]\d{3}[A-Z]{2}$"),  # A 123 BC
    re.compile(r"^[A-Z]{2}\d{3}[A-Z]$"),  # AB 123 C
    re.compile(r"^\d[A-Z]{3}\d{2}$"),     # 1 ABC 23
    re.compile(r"^[A-Z]\d{4}[A-Z]$"),     # A 1234 C
    re.compile(r"^[A-Z]\d[A-Z]\d{3}$"),   # A 1 C 234
    re.compile(r"^[A-Z]\d{2}[A-Z]\d{2}$"),  # A 12 C 34
]

CAR_PATTERNS = [
    # Standard 4-Wheel MV Formats
    re.compile(r"^[A-Z]{3}\d{4}$"),       # 3 Letters, 4 Numbers (ABC1234)
    re.compile(r"^[A-Z]{3}\d{3}$"),       # 3 Letters, 3 Numbers (WFU799)
    re.compile(r"^[A-Z]{2}\d{4}$"),       # 2 Letters, 4 Numbers (Government/Electric/Conduction SE1234)
    # Conduction Stickers & Temporary Plates
    re.compile(r"^[A-Z]\d{4}$"),          # 1 Letter, 4 Numbers (Legacy Conduction)
    # LTO MV File Numbers (Temporary registrations)
    re.compile(r"^\d{11}$"),              # 11-Digit Pure Numerical File Block
    re.compile(r"^\d{10}$"),              # 10-Digit Pure Numerical File Block
    # Protocol & Diplomatic Formats
    re.compile(r"^\d{1,2}$"),             # 1 to 2 Digit Government Protocol Keys
    re.compile(r"^\d{7}$"),               # 7-Digit Diplomatic Plates
]


def _matches(plate, patterns):
    clean = re.sub(r"[\s-]+", "", plate or "").upper()
    return any(p.match(clean) for p in patterns)


def _safe_confidence(value):
    """Missing/unparseable confidence counts as the lowest possible score."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1.0


def _is_unknown(read):
    return (read.get("plate") or "").replace(" ", "").upper() in ("", "UNKNOWN")


def _first_camera(record, reads):
    first = record.get("first_camera")
    if reads.get(first):
        return first
    # Rows saved before first_camera existed: fall back to the read times
    return min(reads, key=lambda s: str(reads[s].get("timestamp") or ""))


def _result(disposition, routing, source, plate, reason, short=None):
    return {
        "disposition": disposition,
        "routing_decision": routing,
        "chosen_camera": source,
        "chosen_plate": plate,
        "decision_reason": reason,
        "decision_reason_short": short,
    }


def _format_check(source, read):
    plate = read.get("plate")
    is_car_plate = _matches(plate, CAR_PATTERNS)
    is_motorcycle_plate = _matches(plate, MOTORCYCLE_PATTERNS)

    if read.get("vehicle_type") == "MOTORCYCLE":
        if is_motorcycle_plate:
            return _result("Motor LP", "SYSTEM", source, plate, "Valid Format and Type")
        if is_car_plate:
            return _result("Ticket", "TICKET", source, plate, "Type Mismatch (Car plate on Motorcycle)", "Type mismatch")
        return _result("Ticket", "TICKET", source, plate,
                       "Invalid Motorcycle Format (Expected: AB12345, 123ABC, A12C34, A1C234, A1234C, etc.)", "Wrong plate format")

    if is_car_plate:
        return _result("Car LP", "SYSTEM", source, plate, "Valid Format and Type")
    if is_motorcycle_plate:
        return _result("Ticket", "TICKET", source, plate, "Type Mismatch (Motorcycle plate on Car)", "Type mismatch")
    return _result("Ticket", "TICKET", source, plate, "Invalid Car Format (Expected: ABC1234, WFU799, SE1234, etc.)", "Wrong plate format")


def decide_disposition(record, min_confidence=DEFAULT_MIN_CONFIDENCE):
    """
    record: dict with optional "front_camera" / "back_camera" reads (plate,
    vehicle_type normalized to CAR/MOTORCYCLE, confidence, timestamp), plus
    "first_camera" ("front" | "back") naming which camera read first.

    Returns the fields to store on the record, see _result.
    """
    front = record.get("front_camera")
    back = record.get("back_camera")
    if not front and not back:
        return _result("NA", "NA", None, None, "No Camera Read")

    reads = {s: r for s, r in (("front", front), ("back", back)) if r and not _is_unknown(r)}
    if not reads:
        return _result("Ignored", "IGNORED", "front" if front else "back", "UNKNOWN", "UNKNOWN Plate From All Cameras", "Unknown plate")

    first = _first_camera(record, reads)
    back_only = first == "back" and reads[first].get("vehicle_type") == "MOTORCYCLE"
    available = [s for s in ([first] if back_only else [first, "back" if first == "front" else "front"]) if s in reads]

    for source in available:
        read = reads[source]
        if _safe_confidence(read.get("confidence")) >= min_confidence:
            if source == "front" and read.get("vehicle_type") == "MOTORCYCLE":
                return _result("Ticket", "TICKET", source, read.get("plate"), "Motorcycle Read by the Front Camera", "Front motorcycle")
            return _format_check(source, read)

    # No high score read: a Ticket, reporting the best plate we saw.
    source = max(available, key=lambda s: _safe_confidence(reads[s].get("confidence")))
    score = reads[source].get("confidence")
    score_text = "no score" if score is None else f"{score}%"
    return _result("Ticket", "TICKET", source, reads[source].get("plate"), f"Low Camera Confidence ({score_text})", f"Low score ({score_text})")
