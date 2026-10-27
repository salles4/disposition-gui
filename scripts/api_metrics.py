import os
import json
import time
import threading
import requests
from urllib.parse import urlparse

_metrics_lock = threading.RLock()
_metrics_data = {}
_broadcast_callback = None

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
METRICS_FILE = os.path.join(DATA_DIR, "api_metrics.json")

def load_metrics_from_disk():
    global _metrics_data
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    _metrics_data = loaded
        except Exception:
            pass

def save_metrics_to_disk():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(_metrics_data, f, indent=2)
    except Exception:
        pass

load_metrics_from_disk()

def set_broadcast_callback(callback):
    global _broadcast_callback
    _broadcast_callback = callback

def record_latency(method, url, duration_ms):
    parsed = urlparse(url)
    path = parsed.path or url
    key = f"{method.upper()} {path}"
    
    with _metrics_lock:
        if key not in _metrics_data:
            _metrics_data[key] = {
                "endpoint": key,
                "count": 0,
                "total_ms": 0.0,
                "avg_ms": 0.0,
                "min_ms": duration_ms,
                "max_ms": duration_ms,
                "last_ms": duration_ms
            }
        
        stat = _metrics_data[key]
        stat["count"] += 1
        stat["total_ms"] += duration_ms
        stat["avg_ms"] = round(stat["total_ms"] / stat["count"], 1)
        stat["min_ms"] = round(min(stat["min_ms"], duration_ms), 1)
        stat["max_ms"] = round(max(stat["max_ms"], duration_ms), 1)
        stat["last_ms"] = round(duration_ms, 1)
        
        save_metrics_to_disk()
        snapshot = list(_metrics_data.values())

    if _broadcast_callback:
        try:
            _broadcast_callback(snapshot)
        except Exception:
            pass

_orig_session_request = requests.Session.request

def is_successful_response(response):
    if not (200 <= response.status_code < 300):
        return False
    try:
        data = response.json()
        if isinstance(data, dict):
            if data.get("success") is False:
                return False
    except Exception:
        pass
    return True

def tracked_session_request(self, method, url, **kwargs):
    start = time.time()
    try:
        response = _orig_session_request(self, method, url, **kwargs)
        duration_ms = (time.time() - start) * 1000.0
        if is_successful_response(response):
            record_latency(method, url, duration_ms)
        return response
    except Exception as e:
        raise e

def enable_monkey_patch():
    requests.Session.request = tracked_session_request

enable_monkey_patch()

def get_all_metrics():
    with _metrics_lock:
        return list(_metrics_data.values())

def reset_metrics():
    global _metrics_data
    with _metrics_lock:
        _metrics_data = {}
        save_metrics_to_disk()
        snapshot = []
    if _broadcast_callback:
        try:
            _broadcast_callback(snapshot)
        except Exception:
            pass
    return snapshot
