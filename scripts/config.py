import os
import json
import shutil
from datetime import datetime

def load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().strip('"').strip("'")
                        os.environ[key] = val
        except Exception as e:
            print(f"[ENV ERROR] Failed to load .env: {e}")

load_env_file()

# Core API address. Set from the dashboard (config.json "servers"); .env / these defaults are only the starting values.
# Read it as config.API_BASE_URL at call time (not "from config import API_BASE_URL") so dashboard changes apply live.
API_BASE_URL = os.environ.get("API_BASE_URL", "http://192.168.0.13:9080")
TERMINAL_ID = "PoR-B1-02-00001"
TOKEN = os.environ.get("API_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjowLCJ1c2VyX25hbWUiOiJybmRzdXBlcmFkbWluIiwidHlwZSI6IkFETUlOIiwidGVybWluYWxJRCI6bnVsbCwianRpIjoiMWQxNmU0ZmQtNGU3NS00M2Q0LWEwNTYtMGQ3ZDZjM2Y2MWExIiwiaWF0IjoxNzkzMDY1MzY5LCJleHAiOjE3OTM2NzAxNjl9.81uCRZHRbT40jOrSpOpwGN1LaFk6mQNxzTDSWEw83WE")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Accept": "application/json"}

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjowLCJ1c2VyX25hbWUiOiJybmRzdXBlcmFkbWluIiwidHlwZSI6IkFETUlOIiwidGVybWluYWxJRCI6bnVsbCwianRpIjoiMWQxNmU0ZmQtNGU3NS00M2Q0LWEwNTYtMGQ3ZDZjM2Y2MWExIiwiaWF0IjoxNzkzMDY1MzY5LCJleHAiOjE3OTM2NzAxNjl9.81uCRZHRbT40jOrSpOpwGN1LaFk6mQNxzTDSWEw83WE")
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json", "Accept": "application/json"}

# Sent as the first message on the backend WebSocket ({"type":"auth","token":...}); server replies with "auth-ok".
WS_TOKEN = os.environ.get("WS_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjowLCJ1c2VyX25hbWUiOiJSTkRTVVBFUkFETUlOIiwidHlwZSI6IkFETUlOIiwidGVybWluYWxJRCI6bnVsbCwianRpIjoiYjczMjAxMjUtNTdjNC00NTlmLWE3YmEtZDNkNzRmZTQ3ZGZkIiwiaWF0IjoxNzkzMTQ5NDAxLCJleHAiOjE3OTM3NTQyMDF9.xBPkD1DZLw-EV-AHkqlpkhb91kRU9t6JaO_YkzJeUVw")

# ---------------------------------------------------------------------------
# EXIT GATE CONFIGURATION
# Change this list to match the active physical exit gates in your facility.
# The auto-exit will round-robin through these gates.
# ---------------------------------------------------------------------------
EXIT_GATES = [8]

GLOBAL_CONFIG = {
    "entry_interval_seconds": 5, 
    "pay_delay_seconds": 60,
    "exit_delay_seconds": 20,
    "mock_mode": False,
    "detection_mode": "camera",
    "auto_generate_plates": False,
    "camera_auto_exit_only": True,
    "real_device_payment": False,
    "teller_process_delay_seconds": 2,
    "teller_cooldown_seconds": 3,
    # LPR cameras: terminals -> gates (entry/exit) -> front/back camera IPs. Edited on the dashboard.
    "terminals": [],
    # Disposition table: separate Exit plate column, optionally with exit rows right-aligned
    "split_exit_layout": True,
    "exit_rows_right_aligned": True,
    # Keep the images LPR cameras send. Off: rows still get the plate reads, with no camera images stored or shown.
    "include_images": True,
    # Server addresses (editable on the dashboard). Ports only take effect after a restart.
    "servers": {
        "api_base_url": API_BASE_URL,
        "app_port": int(os.environ.get("PORT", 5015)),
        "teller_port": int(os.environ.get("TELLER_PORT", 5010))
    }
}

# Live settings live in data/config.json, which git ignores, so a git pull can never replace or delete them.
# scripts/config.json is the old, git-tracked location: it is copied over once (first start) and then left alone.
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "config.json")
LEGACY_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def migrate_legacy_config():
    """First start after the move: carry the existing settings over from scripts/config.json."""
    if os.path.exists(CONFIG_FILE) or not os.path.exists(LEGACY_CONFIG_FILE):
        return
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        # Per-process temp name: the engine and teller service may both start at once
        tmp_file = f"{CONFIG_FILE}.{os.getpid()}.tmp"
        shutil.copyfile(LEGACY_CONFIG_FILE, tmp_file)
        os.replace(tmp_file, CONFIG_FILE)
        print(f"[CONFIG] Copied existing settings from {LEGACY_CONFIG_FILE} to {CONFIG_FILE}", flush=True)
    except Exception as e:
        print(f"[CONFIG] Could not copy existing settings from {LEGACY_CONFIG_FILE}: {e}", flush=True)

def migrate_camera_mapping():
    """
    Older configs keep a flat {ip: {gate, direction, camera}} camera_mapping, where one "gate"
    number covered both its entry and exit lanes. Each old gate becomes a terminal, and each of
    its directions a gate under it (gate ids numbered in order). The converted layout is written
    out on the next dashboard save.
    """
    old_mapping = GLOBAL_CONFIG.pop("camera_mapping", None)
    if not old_mapping or GLOBAL_CONFIG.get("terminals"):
        return
    terminals = {}
    for ip, info in old_mapping.items():
        terminal_id = int(info.get("gate", 1))
        direction = info.get("direction", "entry")
        terminal = terminals.setdefault(terminal_id, {"id": terminal_id, "name": f"Terminal {terminal_id}", "gates": {}})
        gate = terminal["gates"].setdefault(direction, {"direction": direction, "cameras": {}})
        gate["cameras"][info.get("camera", "front")] = ip
    next_gate_id = 1
    result = []
    for terminal_id in sorted(terminals):
        terminal = terminals[terminal_id]
        gates = []
        for direction in sorted(terminal["gates"]):  # entry before exit
            gates.append({"id": next_gate_id, "number": next_gate_id, **terminal["gates"][direction]})
            next_gate_id += 1
        result.append({**terminal, "gates": gates})
    GLOBAL_CONFIG["terminals"] = result
    print(f"[CONFIG] Converted camera_mapping into {len(result)} terminal(s).", flush=True)

def gate_number(gate):
    """The number shown for a gate. Only a label: several gates may share it. Older configs have none, so their id was shown."""
    try:
        number = int(gate.get("number"))
    except (TypeError, ValueError):
        return gate["id"]
    return number if number >= 1 else gate["id"]

def sanitize_terminals(raw):
    """Keep only well-formed terminals/gates/cameras from a dashboard save.
    A gate's "id" is its internal identifier and must be unique; its "number" is the label people see and may repeat."""
    terminals = []
    used_gate_ids = set()
    pending_gates = []  # gates whose id was missing or taken, given a fresh one once every valid id is known
    for t in raw or []:
        try:
            terminal_id = int(t["id"])
        except (KeyError, TypeError, ValueError):
            continue
        gates = []
        for g in t.get("gates") or []:
            try:
                gate_id = int(g["id"])
            except (KeyError, TypeError, ValueError):
                gate_id = None
            if gate_id is not None and (gate_id < 1 or gate_id in used_gate_ids):
                gate_id = None
            cameras = {
                role: str(ip).strip()
                for role, ip in (g.get("cameras") or {}).items()
                if role in ("front", "back") and ip and str(ip).strip()
            }
            direction = g.get("direction") if g.get("direction") in ("entry", "exit") else "entry"
            gate = {"id": gate_id, "number": g.get("number"), "direction": direction, "cameras": cameras}
            if gate_id is None:
                pending_gates.append(gate)
            else:
                used_gate_ids.add(gate_id)
            gates.append(gate)
        name = str(t.get("name") or "").strip() or f"Terminal {terminal_id}"
        terminals.append({"id": terminal_id, "name": name, "gates": gates})
    next_id = max(used_gate_ids, default=0) + 1
    for gate in pending_gates:
        gate["id"] = next_id
        next_id += 1
    for terminal in terminals:
        for gate in terminal["gates"]:
            gate["number"] = gate_number(gate)
    return terminals

def find_camera(ip):
    """Where a camera IP is installed: terminal, gate, direction and front/back role, or None if unregistered."""
    for terminal in GLOBAL_CONFIG.get("terminals", []):
        for gate in terminal.get("gates", []):
            for role, cam_ip in (gate.get("cameras") or {}).items():
                if cam_ip == ip:
                    return {
                        "terminal_id": terminal["id"],
                        "terminal_name": terminal.get("name") or f"Terminal {terminal['id']}",
                        "gate_id": gate["id"],
                        "gate_number": gate_number(gate),
                        "direction": gate.get("direction", "entry"),
                        "camera": role,
                    }
    return None

def get_servers():
    return GLOBAL_CONFIG["servers"]

def teller_url(path):
    """URL of the local teller service, e.g. teller_url('/add-to-queue')."""
    return f"http://localhost:{get_servers()['teller_port']}{path}"

def apply_server_settings():
    """Push the 'servers' section into the module-level values the rest of the code reads."""
    global API_BASE_URL
    API_BASE_URL = get_servers()["api_base_url"].rstrip("/")

def load_config(log_callback=None):
    global GLOBAL_CONFIG
    migrate_legacy_config()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded = json.load(f)
                # Merge "servers" key by key so a config.json without it (older format) keeps the .env defaults
                loaded_servers = loaded.pop("servers", None) or {}
                GLOBAL_CONFIG.update(loaded)
                GLOBAL_CONFIG["servers"].update(loaded_servers)
                migrate_camera_mapping()
                if log_callback:
                    log_callback(f"Simulation configuration loaded from {CONFIG_FILE}", "SYSTEM")
        except Exception as e:
            print(f"[CONFIG] Failed to read {CONFIG_FILE}: {e}", flush=True)
            if log_callback:
                log_callback(f"Error loading config: {e}", "ERROR")
            # Set the unreadable file aside so the next save doesn't overwrite what's left of it
            try:
                corrupt_file = f"{CONFIG_FILE}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                os.replace(CONFIG_FILE, corrupt_file)
                print(f"[CONFIG] Moved unreadable settings to {corrupt_file}", flush=True)
            except Exception as move_err:
                print(f"[CONFIG] Could not set aside unreadable settings: {move_err}", flush=True)
    apply_server_settings()

def save_env_value(key, value):
    """Set or replace KEY=value in the project .env so it survives restarts."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.read().splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().split("=", 1)[0].strip() == key:
            lines[i] = f"{key}={value}"
            replaced = True
    if not replaced:
        lines.append(f"{key}={value}")
    with open(env_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.environ[key] = value

def set_api_token(token):
    """Swap the REST API token in place so modules holding HEADERS/ADMIN_HEADERS see it immediately."""
    global TOKEN, ADMIN_TOKEN
    TOKEN = ADMIN_TOKEN = token
    HEADERS["Authorization"] = f"Bearer {token}"
    ADMIN_HEADERS["Authorization"] = f"Bearer {token}"
    save_env_value("API_TOKEN", token)
    save_env_value("ADMIN_TOKEN", token)

def save_config(log_callback=None):
    try:
        # Temp file + swap so a crash mid-write can't wipe the camera mapping / server settings
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        tmp_file = f"{CONFIG_FILE}.{os.getpid()}.tmp"
        with open(tmp_file, "w") as f:
            json.dump(GLOBAL_CONFIG, f, indent=4)
        os.replace(tmp_file, CONFIG_FILE)
    except Exception as e:
        if log_callback:
            log_callback(f"Error saving config: {e}", "ERROR")

# Load data/config.json on import so every process (engine and the separate teller service) sees the saved settings
load_config()
