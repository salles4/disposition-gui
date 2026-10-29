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
    "camera_mapping": {},
    # Disposition table: separate Exit plate column, optionally with exit rows right-aligned
    "split_exit_layout": True,
    "exit_rows_right_aligned": True,
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
