import json
import time
import random
import requests
import threading
import websocket
from datetime import datetime

from scripts.state import process_and_buffer_data

from scripts.app_context import socketio
import base64
import scripts.config as config
from scripts.config import API_BASE_URL, TERMINAL_ID, HEADERS, GLOBAL_CONFIG, EXIT_GATES
from scripts.state import sim_stats, queue_lock, matching_lock, last_displayed_entry, last_displayed_exit
from scripts.utils import format_plate, clean_gate_id, levenshtein_distance, get_random_gate, sanitize_vehicle_type


def process_camera_vehicle(plate_no, raw_vehicle_type, gate_id):
    plate, v_type = format_plate(plate_no, raw_vehicle_type)
    socketio.emit('play_entry', {'plate': plate, 'vType': v_type}, to=f"entry_{gate_id}")
    from scripts.logging_reporter import log_event
    log_event(f"[CAMERA] Detected vehicle {plate} at Entry Gate {gate_id}.", "ENTRY")
    
    pay_delay = GLOBAL_CONFIG.get("pay_delay_seconds", 60)
    log_event(f"[CAMERA] Vehicle [{plate}] parked. Waiting {pay_delay}s until payment...", "SYSTEM")
    time.sleep(pay_delay)
    
    try:
        if GLOBAL_CONFIG.get("real_device_payment"):
            log_event(f"[CAMERA] Real device payment enabled. Sending vehicle [{plate}] to Teller Service...", "PAY")
            entry_time_str = None
            try:
                bill_res = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=5)
                if bill_res.status_code == 200 and bill_res.json().get("success"):
                    entry_time_str = bill_res.json().get("data", {}).get("time_in")
            except Exception as e:
                log_event(f"[CAMERA] Failed to query entry time for [{plate}] from API: {e}", "WARN")
            
            if not entry_time_str:
                entry_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            try:
                add_res = requests.post("http://localhost:5010/add-to-queue", json={"plate_no": plate, "time_in": entry_time_str}, timeout=5)
                if add_res.status_code == 200:
                    log_event(f"[CAMERA] Vehicle [{plate}] added to Teller Service queue.", "PAY")
                else:
                    log_event(f"[CAMERA] Teller Service addition failed for [{plate}]: {add_res.text}", "WARN")
            except Exception as e:
                log_event(f"[CAMERA] Failed to communicate with Teller Service for [{plate}]: {e}", "ERROR")
            
            log_event(f"[CAMERA] Waiting for payment on [{plate}] via real device...", "PAY")
            start_poll = time.time()
            payment_cleared = False
            while (time.time() - start_poll) < 180:
                time.sleep(3)
                try:
                    bill_chk = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=5)
                    if bill_chk.status_code != 200:
                        err_text = bill_chk.text.lower()
                        if "already paid" in err_text or "payment successful" in err_text or "enter park" in err_text or "not inside" in err_text or "exited" in err_text:
                            payment_cleared = True
                            break
                    else:
                        bill_json = bill_chk.json()
                        if not bill_json.get("success"):
                            msg = (bill_json.get("message") or "").lower()
                            if "already paid" in msg or "payment successful" in msg or "enter park" in msg or "not inside" in msg or "exited" in msg:
                                payment_cleared = True
                                break
                        else:
                            fee = float(bill_json.get("data", {}).get("total_amount", 0.0))
                            if fee <= 0:
                                payment_cleared = True
                                break
                except Exception:
                    pass
            
            if payment_cleared:
                log_event(f"[CAMERA] Payment confirmed for [{plate}] via real device.", "PAY")
                socketio.emit('payment_success', {'plate': plate, 'amount': 0.0, 'vType': v_type}, to='admin_room')
                
                with queue_lock:
                    sim_stats["parked"] += 1
                    sim_stats["paid"] += 1
                socketio.emit('stats_update', sim_stats, to='admin_room')
                
                exit_delay = GLOBAL_CONFIG.get("exit_delay_seconds", 5)
                time.sleep(exit_delay)
                
                assigned_exit = EXIT_GATES[sim_stats.get("exited", 0) % len(EXIT_GATES)]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    exit_res = requests.post(f"{API_BASE_URL}/api/lpr", json={"gate_id": assigned_exit, "plate_no": plate, "vehicle_type": v_type, "created_at": now_str, "timestamp": now_str, "time_out": now_str}, headers=HEADERS, timeout=10)
                except Exception:
                    pass
                
                with matching_lock:
                    last_displayed_exit.setdefault(assigned_exit, []).append({"plate": plate, "time": datetime.now(), "matched": False, "v_type": v_type})
                socketio.emit('play_exit', {'plate': plate, 'vType': v_type}, to=f"exit_{assigned_exit}")
                
                with queue_lock:
                    sim_stats["parked"] = max(0, sim_stats["parked"] - 1)
                    sim_stats["paid"] = max(0, sim_stats["paid"] - 1)
                    sim_stats["exited"] += 1
                socketio.emit('stats_update', sim_stats, to='admin_room')
            return

        if not GLOBAL_CONFIG.get("enable_automatic_payment", True):
            log_event(f"[CAMERA] Vehicle [{plate}] skipped (Real Device Payment and Auto-Pay are both OFF).", "SYSTEM")
            return

        log_event(f"[CAMERA] Fetching live bill details for detected vehicle [{plate}]...", "SYSTEM")
        bill_data = None
        ref_no = None
        total = 0.0
        
        for attempt in range(3):
            try:
                bill = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=10)
                bill_json = bill.json()
                if bill_json.get("success"):
                    bill_data = bill_json.get("data")
                    ref_no = bill_json.get("reference_no")
                    if bill_data and ref_no:
                        total = float(bill_data.get("total_amount", "0"))
                        break
            except Exception:
                pass
            time.sleep(2)

        if not bill_data or not ref_no:
            log_event(f"[CAMERA] Billing retrieval non-success or missing data for [{plate}]", "WARN")
            return

        pay_success = False
        pay_err = ""
        for attempt in range(3):
            try:
                pay = requests.post(f"{API_BASE_URL}/api/payment/cash", json={"amount_paid": total, "licence_plate_no": plate, "reference_no": ref_no, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=10)
                try:
                    pay_json = pay.json()
                except Exception:
                    pay_json = {}
                
                if pay_json.get("success"):
                    pay_success = True
                    break
                else:
                    pay_err = pay_json.get("message") or pay_json.get("error") or pay_json.get("msg") or pay.text
            except Exception as ex:
                pay_err = str(ex)
            time.sleep(2)

        if pay_success:
            log_event(f"[CAMERA] LIVE API Payment Cleared for [{plate}] (P{total:.2f}).", "PAY")
            socketio.emit('payment_success', {'plate': plate, 'amount': total, 'vType': v_type}, to='admin_room')
            with queue_lock:
                sim_stats["parked"] += 1
                sim_stats["paid"] += 1
            socketio.emit('stats_update', sim_stats, to='admin_room')
            
            exit_delay = GLOBAL_CONFIG.get("exit_delay_seconds", 5)
            time.sleep(exit_delay)
            assigned_exit = EXIT_GATES[sim_stats.get("exited", 0) % len(EXIT_GATES)]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                requests.post(f"{API_BASE_URL}/api/lpr", json={"gate_id": assigned_exit, "plate_no": plate, "vehicle_type": v_type, "created_at": now_str, "timestamp": now_str, "time_out": now_str}, headers=HEADERS, timeout=10)
            except Exception: pass
            
            with matching_lock:
                last_displayed_exit.setdefault(assigned_exit, []).append({"plate": plate, "time": datetime.now(), "matched": False, "v_type": v_type})
            socketio.emit('play_exit', {'plate': plate, 'vType': v_type}, to=f"exit_{assigned_exit}")
            with queue_lock:
                sim_stats["parked"] = max(0, sim_stats["parked"] - 1)
                sim_stats["paid"] = max(0, sim_stats["paid"] - 1)
                sim_stats["exited"] += 1
            socketio.emit('stats_update', sim_stats, to='admin_room')
        else:
            log_event(f"[CAMERA] Cash Payment API Failed for [{plate}]: {pay_err}", "ERROR")
    except Exception:
        pass


last_processed_events = {}

def on_ws_message(ws, message):
    from scripts.logging_reporter import log_event
    try:
        data = json.loads(message)
        if data.get("event") == "auth-ok" and data.get("action") == "auth-ok":
            print(f"[WS AUTH] Authenticated with backend stream (kind={data.get('kind')}).", flush=True)
            global _ws_authed, _ws_auth_failed
            _ws_authed = True
            _ws_auth_failed = False
            emit_token_status()
            import scripts.state as state
            state.is_hcp_connected = True
            try:
                socketio.emit('hcp_status_update', {'connected': True}, to='admin_room')
            except Exception:
                pass
            return

        if data.get("event") == "available-space" and data.get("action") == "available-space":
            display = data.get("display", {})
            status = display.get("status")
            plate_no = display.get("plate_no")
            raw_vehicle_type = display.get("vehicle_type")
            
            if GLOBAL_CONFIG.get("detection_mode") != "camera":
                return
            
            if plate_no:
                gate_id = clean_gate_id(display.get("gate_id", 1))
                if status == "entry":
                    threading.Thread(target=process_camera_vehicle, args=(plate_no, raw_vehicle_type, gate_id), daemon=True).start()
                elif status in ["exit", "cleared"]:
                    plate, v_type = format_plate(plate_no, raw_vehicle_type)
                    socketio.emit('play_exit', {'plate': plate, 'vType': v_type}, to=f"exit_{gate_id}")
                    with queue_lock:
                        sim_stats["parked"] = max(0, sim_stats["parked"] - 1)
                        sim_stats["exited"] += 1
                    socketio.emit('stats_update', sim_stats, to='admin_room')

        elif data.get("event") == "disposition" and data.get("action") == "disposition":
            payload = data.get("payload", {})
            hcp_payload = payload.get("hcp", {})
            events = hcp_payload.get("events", [])
            guid = hcp_payload.get("guid", "")
            
            merged_hcp = {
                "transactionId": guid, "plate": "", "vehicleType": "",
                "frontImage": "", "backImage": "", "gateName": "", "timestamp": ""
            }

            for ev in events:
                car_info = ev.get("carInfo", {})
                lane_info = ev.get("laneInfo", {})
                passageway_info = ev.get("passagewayInfo", {})
                capture_list = ev.get("captureInfoList", [])

                if car_info.get("plate"):
                    merged_hcp["plate"] = car_info.get("plate").strip().upper()
                if car_info.get("vehicleType"):
                    merged_hcp["vehicleType"] = car_info.get("vehicleType")
                if car_info.get("frontImage"):
                    merged_hcp["frontImage"] = car_info.get("frontImage")
                if capture_list and len(capture_list) > 0 and capture_list[0].get("backimage"):
                    merged_hcp["backImage"] = capture_list[0].get("backimage")
                if ev.get("timeIn") and str(ev.get("timeIn")) != "-1":
                    merged_hcp["timestamp"] = ev.get("timeIn")

                l_name = lane_info.get("laneName", "").strip()
                p_name = passageway_info.get("passagewayName", "").strip()
                
                # FIX: Verify text fields are not empty or invalid placeholders before committing updates
                if l_name and p_name and l_name != "-1" and p_name != "-1":
                    merged_hcp["gateName"] = f"{p_name} - {l_name}"

            if merged_hcp["plate"]:
                log_event(f"[HCP] Disposition Processed: Plate [{merged_hcp['plate']}] at {merged_hcp['gateName']}", "SYSTEM")
                
                # Pass data straight into the central state manager pipeline in a background thread to prevent blocking the WebSocket loop
                threading.Thread(
                    target=process_and_buffer_data,
                    args=("HCP", merged_hcp),
                    daemon=True
                ).start()
                
            # --- PROCESS ADMIN READ FROM DISPOSITION PAYLOAD ---
            admin_payload = payload.get("admin", {})
            admin_events = admin_payload.get("events", [])
            for admin_ev in admin_events:
                raw_plate_no = admin_ev.get("plate_no") or admin_ev.get("plate")
                raw_vehicle_type = admin_ev.get("vehicle_type")
                if raw_plate_no:
                    plate_no, _ = format_plate(raw_plate_no, raw_vehicle_type)
                    
                    # Debounce duplicate plate events within 3 seconds
                    clean_p = plate_no.replace(" ", "").strip().upper()
                    now_t = time.time()
                    if clean_p in last_processed_events and (now_t - last_processed_events[clean_p]) < 3.0:
                        continue
                    last_processed_events[clean_p] = now_t
                    
                    gate_id = clean_gate_id(admin_ev.get("gate_id", 1))
                    ts = admin_ev.get("timestamp") or admin_ev.get("time") or merged_hcp.get("timestamp") or datetime.now().isoformat()
                    
                    event_payload = {
                        "plate_no": plate_no,
                        "plate": plate_no,
                        "time": ts,
                        "gate_id": gate_id,
                        "vehicle_type": raw_vehicle_type,
                        "percentage": admin_ev.get("percentage", 100),
                        "plate_image_front": admin_ev.get("frontImage") or merged_hcp.get("frontImage", ""),
                        "plate_image_back": admin_ev.get("backImage") or merged_hcp.get("backImage", "")
                    }
                    
                    threading.Thread(
                        target=process_and_buffer_data, 
                        args=("AVAILABLE_SPACE", event_payload), 
                        daemon=True
                    ).start()

                    v_type = sanitize_vehicle_type(raw_vehicle_type).upper()
                    
                    # Construct matched plate key det_id using reconciliation key logic
                    clean_p = plate_no.replace(" ", "").strip().upper()
                    try:
                        if "T" in ts:
                            dt_obj = datetime.fromisoformat(ts.replace("Z", ""))
                        else:
                            dt_obj = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        dt_obj = datetime.now()
                    if dt_obj.tzinfo is not None:
                        dt_obj = dt_obj.replace(tzinfo=None)
                    ts_suffix = dt_obj.strftime("%H%M%S")
                    det_id = f"{clean_p}_{ts_suffix}"
                    
                    new_det = {
                        "id": det_id, "timestamp": dt_obj.strftime("%Y-%m-%d %H:%M:%S"),
                        "stage": "ENTRY", "gate": f"GATE {gate_id}",
                        "plate_no": plate_no, "vehicle_type": v_type,
                        "plate_image_front": event_payload["plate_image_front"],
                        "plate_image_back": event_payload["plate_image_back"],
                        "verified": False, "verification_details": None
                    }
                    
                    def handle_recent_admin_det(det_obj):
                        import scripts.state as state
                        det_obj = state.enrich_detection_images(det_obj)
                        with state.detections_lock:
                            clean_p = det_obj["plate_no"].replace(" ", "").strip().upper()
                            state.recent_detections = [
                                d for d in state.recent_detections 
                                if not (d.get("plate_no", "").replace(" ", "").strip().upper() == clean_p and not d.get("verified"))
                            ]
                            state.recent_detections.insert(0, det_obj)
                            if len(state.recent_detections) > 1000:
                                state.recent_detections[:] = state.recent_detections[:1000]
                            state.save_recent_detections()
                        try:
                            socketio.emit('new_camera_detection', det_obj, to='admin_room')
                        except Exception: pass

                    threading.Thread(target=handle_recent_admin_det, args=(new_det,), daemon=True).start()

                    if GLOBAL_CONFIG.get("detection_mode") == "camera":
                        threading.Thread(target=process_camera_vehicle, args=(plate_no, raw_vehicle_type, gate_id), daemon=True).start()
                
    except Exception as e:
        log_event(f"Error handling WebSocket message: {e}", "ERROR")

def on_ws_error(ws, error):
    print(f"[WS ERROR] Connection error: {error}", flush=True)
    import scripts.state as state
    state.is_hcp_connected = False
    try:
        socketio.emit('hcp_status_update', {'connected': False}, to='admin_room')
    except Exception:
        pass

def on_ws_close(ws, close_status_code, close_msg):
    print(f"[WS CLOSE] Connection closed. Code: {close_status_code}, Message: {close_msg}", flush=True)
    global _ws_auth_failed
    # Socket opened and we sent the token, but the server hung up before "auth-ok": treat as a rejected token
    if _ws_opened and not _ws_authed and not _ws_auth_failed:
        _ws_auth_failed = True
        emit_token_status()
    import scripts.state as state
    state.is_hcp_connected = False
    try:
        socketio.emit('hcp_status_update', {'connected': False}, to='admin_room')
    except Exception:
        pass

def on_ws_open(ws):
    # Authenticate first; the connection is only marked live once the server replies with "auth-ok"
    global _ws_opened, _ws_authed
    _ws_opened = True
    _ws_authed = False
    print("[WS OPEN] Connected. Sending auth message...", flush=True)
    ws.send(json.dumps({"type": "auth", "token": config.WS_TOKEN}))


# --- WS TOKEN STATUS (drives the token-expired prompt in the admin UI) ---
_current_ws = None
_ws_opened = False
_ws_authed = False
_ws_auth_failed = False

def get_token_expiry(token):
    """Return the JWT 'exp' claim (unix seconds) without verifying the signature, or None."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("exp")
    except Exception:
        return None

def get_token_status():
    return {
        "exp": get_token_expiry(config.WS_TOKEN),
        "auth_failed": _ws_auth_failed,
        "api_exp": get_token_expiry(config.TOKEN),
        "api_auth_failed": _api_auth_failed
    }

def emit_token_status(to='admin_room'):
    try:
        socketio.emit('token_status', get_token_status(), to=to)
    except Exception:
        pass

def update_ws_token(token):
    """Swap in a new WS token, persist it to .env and force a reconnect. Returns (ok, message)."""
    global _ws_auth_failed
    token = (token or "").strip()
    exp = get_token_expiry(token)
    if not exp:
        return False, "That doesn't look like a valid token."
    if exp <= time.time():
        return False, "That token is already expired."

    config.WS_TOKEN = token
    try:
        config.save_env_value("WS_TOKEN", token)
    except Exception as e:
        print(f"[WS TOKEN] Could not save token to .env: {e}", flush=True)
    _ws_auth_failed = False
    emit_token_status()

    # Closing the socket drops run_forever(); the listener loop reconnects with the new token
    if _current_ws:
        try:
            _current_ws.close()
        except Exception:
            pass
    return True, "Token updated. Reconnecting..."


# --- API TOKEN STATUS (payment, exit and parked-list REST calls) ---
_api_auth_failed = False

def note_api_response(url, response):
    """Called for every requests response; flags the API token as rejected on 401 and clears it on success."""
    global _api_auth_failed
    if not str(url).startswith(config.API_BASE_URL):
        return
    status = response.status_code
    if status == 401 or (status == 403 and any(k in response.text.lower() for k in ["token", "jwt", "expired", "unauthorized"])):
        rejected = True
    elif 200 <= status < 300:
        rejected = False
    else:
        return
    if rejected != _api_auth_failed:
        _api_auth_failed = rejected
        if rejected:
            print(f"[API TOKEN] Backend rejected the API token (HTTP {status}) on {url}", flush=True)
        emit_token_status()

def update_api_token(token):
    """Swap in a new REST API token, persist it to .env and push it to the teller service. Returns (ok, message)."""
    global _api_auth_failed
    token = (token or "").strip()
    exp = get_token_expiry(token)
    if not exp:
        return False, "That doesn't look like a valid token."
    if exp <= time.time():
        return False, "That token is already expired."

    try:
        config.set_api_token(token)
    except Exception as e:
        print(f"[API TOKEN] Could not save token to .env: {e}", flush=True)
    _api_auth_failed = False
    emit_token_status()

    # The teller service is a separate process with its own session headers
    try:
        requests.post("http://localhost:5010/update-token", json={"token": token}, timeout=3)
    except Exception:
        return True, "Token updated. Teller service not reachable; it will load the new token on restart."
    return True, "Token updated."

def websocket_listener():
    from scripts.logging_reporter import log_event
    global _current_ws, _ws_opened
    while True:
        try:
            # Explicitly log that a connection attempt is starting
            ws_url = API_BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
            print(f"[WS CONNECT] Attempting handshake with stream at {ws_url}...", flush=True)
            _ws_opened = False

            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_ws_open,
                on_message=on_ws_message,
                on_error=on_ws_error,
                on_close=on_ws_close
            )
            _current_ws = ws

            # Send a heartbeat ping every 60 seconds with 30s timeout.
            # If the server drops the connection, it triggers an instant auto-reconnect.
            ws.run_forever(ping_interval=60, ping_timeout=30)
            
        except Exception as e:
            log_event(f"[WS CRASH] WebSocket connection loop exception: {str(e)}", "ERROR")
            
        # Wait 5 seconds before trying to bind the port socket loop again
        time.sleep(5)