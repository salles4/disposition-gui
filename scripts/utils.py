import re
import random

def is_token_rejection(status_code, body_text):
    """True when the backend refused the bearer token (expired, revoked or invalid)."""
    if status_code == 401:
        return True
    if status_code == 403:
        text = (body_text or "").lower()
        return any(k in text for k in ["token", "jwt", "expired", "revoked", "unauthorized"])
    return False

# Admin vehicle type codes: 1/2 is the current format, 11/12 kept for older events
ADMIN_CAR_CODES = {"1", "11"}
ADMIN_MOTORCYCLE_CODES = {"2", "12"}

def sanitize_vehicle_type(raw_type):
    if not raw_type:
        return "car"
    val = str(raw_type).lower().strip()
    if val in ADMIN_MOTORCYCLE_CODES or "motor" in val:
        return "motorcycle"
    if val in ADMIN_CAR_CODES or "car" in val:
        return "car"
    return "car"

def clean_gate_id(raw_gate):
    if raw_gate is None:
        return 1
    if isinstance(raw_gate, int):
        return raw_gate
    cleaned = re.sub(r'\D', '', str(raw_gate))
    if cleaned:
        return int(cleaned)
    return 1

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

def generate_random_plate():
    v_type = random.choices(['car', 'motorcycle'], weights=[0.5, 0.5])[0]
    if v_type == 'motorcycle':
        if random.random() > 0.5:
            letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
            numbers = "".join(random.choices("0123456789", k=5))
            return f"{letters} {numbers}", 'motorcycle'
        else:
            numbers = "".join(random.choices("0123456789", k=3))
            letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3))
            return f"{numbers} {letters}", 'motorcycle'
    else:
        letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3))
        numbers = "".join(random.choices("0123456789", k=4))
        return f"{letters} {numbers}", 'car'

def format_plate(raw_plate, explicit_type=None):
    if not raw_plate: return "", "car"
    cleaned = raw_plate.strip().upper()
    
    if explicit_type:
        v_type = sanitize_vehicle_type(explicit_type)
    else:
        v_type = "motorcycle" if len(cleaned.replace("-", "").replace(" ", "")) < 6 else "car"
    
    if v_type == "motorcycle": 
        return cleaned.replace("-", "").replace(" ", ""), v_type
    else: 
        cleaned = " ".join(cleaned.replace("-", " ").split())
        if " " not in cleaned: cleaned = re.sub(r'^([A-Z]+)(\d+)$', r'\1 \2', cleaned)
        return cleaned, v_type

def get_random_gate(role):
    from scripts.state import connected_terminals
    import random
    active = [t['gate'] for t in connected_terminals.values() if t['role'] == role]
    return random.choice(active) if active else 1


MOTORCYCLE_PATTERNS = [
    re.compile(r"^\d{4}[A-Z]{2}$"),            # Legacy MC (e.g., 2724SO)
    re.compile(r"^[A-Z]{2}\d{5}$"),            # 2 Letters, 5 Numbers (AB12345)
    re.compile(r"^[A-Z]{3}\d{5}$"),            # 3 Letters, 5 Numbers (ABC12345)
    re.compile(r"^[A-Z]\d{5}[A-Z]$"),          # 1 Letter, 5 Numbers, 1 Letter (N12345A)
    re.compile(r"^\d{3}[A-Z]{3}$"),            # 3 Numbers, 3 Letters (123ABC)
    re.compile(r"^[A-Z]\d{3}[A-Z]{2}$"),       # A 123 BC
    re.compile(r"^[A-Z]{2}\d{3}[A-Z]$"),       # AB 123 C
    re.compile(r"^\d[A-Z]{3}\d{2}$"),          # 1 ABC 23
    re.compile(r"^[A-Z]\d{4}[A-Z]$"),          # A 1234 C
    re.compile(r"^[A-Z]\d[A-Z]\d{3}$"),        # A 1 C 234
    re.compile(r"^[A-Z]{2}\d{2}[A-Z]\d{2}$"),  # A 12 C 34
]

CAR_PATTERNS = [
    re.compile(r"^[A-Z]{3}\d{4}$"),            # 3 Letters, 4 Numbers (ABC1234)
    re.compile(r"^[A-Z]{3}\d{3}$"),            # 3 Letters, 3 Numbers (WFU799)
    re.compile(r"^[A-Z]{2}\d{4}$"),            # 2 Letters, 4 Numbers (SE1234)
    re.compile(r"^[A-Z]\d{4}$"),               # 1 Letter, 4 Numbers (Legacy Conduction)
    re.compile(r"^\d{11}$"),                   # 11-Digit MV File Number
    re.compile(r"^\d{10}$"),                   # 10-Digit MV File Number
    re.compile(r"^\d{1,2}$"),                  # 1 to 2 Digit Government Protocol Keys
    re.compile(r"^\d{7}$"),                    # 7-Digit Diplomatic Plates
]

def is_valid_plate_format(plate: str) -> bool:
    """Accepts a plate number string (with or without spaces/hyphens) and returns True if valid."""
    if not plate or not isinstance(plate, str):
        return False
    clean = re.sub(r"[\s-]+", "", plate).strip().upper()
    if not clean:
        return False
    return any(p.match(clean) for p in MOTORCYCLE_PATTERNS) or any(p.match(clean) for p in CAR_PATTERNS)


