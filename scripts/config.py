import os
import json

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

API_BASE_URL = os.environ.get("API_BASE_URL", "http://103.93.223.103:9075")
TERMINAL_ID = "HaH-B5-02-00055"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjowLCJ1c2VyX25hbWUiOiJBRE1JTiIsInR5cGUiOiJBRE1JTiIsInRlcm1pbmFsSUQiOm51bGwsImp0aSI6ImNhMGM4ODNlLWZmOGEtNDYwMC05OTI2LTVjYWI4NDk2OWNkNSIsImlhdCI6MTc4MzAzODYxNSwiZXhwIjoxNzgzNjQzNDE1fQ.NW8QOMZJTgdBVlYU7HruUMh2_UG8iKvvero438PJrVE"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Accept": "application/json"}

ADMIN_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjowLCJ1c2VyX25hbWUiOiJBRE1JTiIsInR5cGUiOiJBRE1JTiIsInRlcm1pbmFsSUQiOm51bGwsImp0aSI6ImNhMGM4ODNlLWZmOGEtNDYwMC05OTI2LTVjYWI4NDk2OWNkNSIsImlhdCI6MTc4MzAzODYxNSwiZXhwIjoxNzgzNjQzNDE1fQ.NW8QOMZJTgdBVlYU7HruUMh2_UG8iKvvero438PJrVE"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json", "Accept": "application/json"}

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
    "camera_mapping": {}
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config(log_callback=None):
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded = json.load(f)
                GLOBAL_CONFIG.update(loaded)
                if log_callback:
                    log_callback("Simulation configuration loaded from config.json", "SYSTEM")
        except Exception as e:
            if log_callback:
                log_callback(f"Error loading config: {e}", "ERROR")

def save_config(log_callback=None):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(GLOBAL_CONFIG, f, indent=4)
    except Exception as e:
        if log_callback:
            log_callback(f"Error saving config: {e}", "ERROR")
