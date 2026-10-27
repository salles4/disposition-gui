import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import base64
import json
import xml.etree.ElementTree as ET
import threading
from datetime import datetime, timedelta
from flask import send_from_directory, request
from flask_socketio import join_room

from scripts.app_context import app, socketio
from scripts.config import GLOBAL_CONFIG, load_config, save_config
from scripts.state import (
    queue_lock, connected_terminals, sim_stats, logs_history,
    pending_reconciliations, reconciliation_lock, daily_reconciliation_history, process_and_buffer_data,
    all_time_stats, unregistered_cameras
)
from scripts.logging_reporter import log_event
from scripts.payment_handler import sync_and_process_parked_vehicles
from scripts.camera_ws import websocket_listener
from scripts.utils import format_plate
from scripts.api_metrics import set_broadcast_callback, get_all_metrics, reset_metrics

set_broadcast_callback(lambda data: socketio.emit('api_metrics_update', data, to='admin_room'))

def emit_unregistered_cameras(to='admin_room'):
    cams = sorted(unregistered_cameras.values(), key=lambda c: c["last_seen"], reverse=True)
    socketio.emit('unregistered_cameras', cams, to=to)

# =========================================================
# 🌐 SOCKET ROUTING & ADMIN COMMANDS
# =========================================================
@socketio.on('register_terminal')
def handle_registration(data):
    role, gate = data.get('role', 'entry'), data.get('gate', 1)
    room_name = f"{role}_{gate}" if role != 'admin' else 'admin_room'
    join_room(room_name)
    
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    if not ip:
        ip = "unknown"
        
    connected_terminals[request.sid] = {"role": role, "gate": gate, "ip": ip}
    
    if role == 'admin':
        from scripts.state import load_recent_detections
        load_recent_detections()
        
        socketio.emit('config_sync', GLOBAL_CONFIG, to=request.sid)
        socketio.emit('stats_update', sim_stats, to=request.sid)
        socketio.emit('logs_history', logs_history, to=request.sid)
        socketio.emit('reconciliation_history_response', daily_reconciliation_history, to=request.sid)
        socketio.emit('all_time_reconciliation_stats_response', all_time_stats, to=request.sid)
        
        from scripts.state import recent_detections, is_hcp_connected, get_available_reconciliation_dates
        from scripts.logging_reporter import load_manual_verification_history
        socketio.emit('recent_detections', recent_detections, to=request.sid)
        socketio.emit('hcp_status_update', {'connected': is_hcp_connected}, to=request.sid)
        socketio.emit('available_reconciliation_dates_response', get_available_reconciliation_dates(), to=request.sid)
        
        manual_history = load_manual_verification_history()
        socketio.emit('manual_verification_history', manual_history, to=request.sid)
        socketio.emit('api_metrics_update', get_all_metrics(), to=request.sid)
        emit_unregistered_cameras(to=request.sid)

    log_event(f"Terminal Connected: {role.upper()} GATE {gate} (IP: {ip}).", "SYSTEM")

@socketio.on('get_detection_images')
def handle_get_detection_images(data):
    det_id = data.get("id")
    plate_no = data.get("plate_no")
    timestamp = data.get("timestamp")
    
    from scripts.state import enrich_detection_images
    dummy_det = {
        "plate_image_front": "",
        "plate_image_back": "",
        "plate_no": plate_no,
        "timestamp": timestamp
    }
    enriched = enrich_detection_images(dummy_det)
    
    socketio.emit('detection_images_response', {
        "id": det_id,
        "front_plate_image": enriched.get("front_plate_image") or "",
        "front_vehicle_image": enriched.get("front_vehicle_image") or "",
        "back_plate_image": enriched.get("back_plate_image") or "",
        "back_vehicle_image": enriched.get("back_vehicle_image") or ""
    }, to=request.sid)

@socketio.on('submit_manual_verification')
def handle_submit_manual_verification(data):
    det_id = data.get("id")
    actual_plate = data.get("actual_plate", "").strip().upper()
    actual_type = data.get("actual_vehicle_type", "").strip().upper()
    status = data.get("status", "CORRECT").strip().upper()
    remarks = data.get("remarks", "").strip()
    
    from scripts.state import recent_detections, save_recent_detections, detections_lock, enrich_detection_images
    from scripts.logging_reporter import log_manual_verification, load_manual_verification_history
    
    target_det = None
    with detections_lock:
        for det in recent_detections:
            if det.get("id") == det_id:
                det["verified"] = True
                det["verification_details"] = {
                    "actual_plate": actual_plate,
                    "actual_vehicle_type": actual_type,
                    "status": status,
                    "remarks": remarks,
                    "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                target_det = det
                break
        if target_det:
            save_recent_detections()
            
    if target_det:
        # Save verification log to history json file
        history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "manual_verification_history.json")
        try:
            history_data = []
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
            
            history_entry = {
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "det_id": det_id,
                "det_plate": target_det.get("plate_no"),
                "det_type": target_det.get("vehicle_type"),
                "act_plate": actual_plate,
                "act_type": actual_type,
                "status": status,
                "remarks": remarks,
                "img_front": target_det.get("plate_image_front") or "",
                "img_back": target_det.get("plate_image_back") or ""
            }
            history_data.insert(0, history_entry)
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving verification history: {e}", flush=True)
            
        # Log to CSV ONLY if status is CORRECT (meaning image and detected plate are the same)
        if status == "CORRECT":
            # Retrieve base64 images from media if available
            enriched_det = enrich_detection_images(target_det)
            
            log_manual_verification(
                stage=target_det.get("stage", "ENTRY"),
                gate=target_det.get("gate", "GATE 1").replace("GATE ", ""),
                det_plate=target_det.get("plate_no", ""),
                det_type=target_det.get("vehicle_type", "CAR"),
                act_plate=actual_plate,
                act_type=actual_type,
                status=status,
                remarks=remarks,
                img_front=enriched_det.get("front_vehicle_image") or enriched_det.get("plate_image_front") or "",
                img_back=enriched_det.get("back_vehicle_image") or enriched_det.get("plate_image_back") or ""
            )
            
        socketio.emit('recent_detections', recent_detections, to='admin_room')
        manual_history = load_manual_verification_history()
        socketio.emit('manual_verification_history', manual_history, to='admin_room')
        log_event(f"Manual verification submitted for detection ID {det_id}. Status: {status}.", "ADMIN")

@socketio.on('update_manual_verification_record')
def handle_update_manual_verification_record(data):
    ts = data.get("ts")
    det_plate = data.get("det_plate")
    new_status = data.get("status", "").strip().upper()
    act_plate = data.get("act_plate", "").strip().upper()
    act_type = data.get("act_type", "").strip().upper()
    remarks = data.get("remarks", "").strip()
    
    if not ts or not det_plate or not new_status:
        return
        
    from scripts.logging_reporter import update_manual_verification_record, load_manual_verification_history
    from scripts.state import recent_detections, detections_lock, save_recent_detections
    
    success = update_manual_verification_record(ts, det_plate, new_status, act_plate, act_type, remarks)
    if success:
        with detections_lock:
            for det in recent_detections:
                if det.get("plate_no") == det_plate and det.get("verified"):
                    if det.get("verification_details"):
                        det["verification_details"]["status"] = new_status
                        det["verification_details"]["actual_plate"] = act_plate
                        det["verification_details"]["actual_vehicle_type"] = act_type
                        det["verification_details"]["remarks"] = remarks
                        save_recent_detections()
                        break
                        
        history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "manual_verification_history.json")
        try:
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
                updated = False
                for entry in history_data:
                    if entry.get("det_plate") == det_plate:
                        entry["status"] = new_status
                        entry["act_plate"] = act_plate
                        entry["act_type"] = act_type
                        entry["remarks"] = remarks
                        updated = True
                if updated:
                    with open(history_file, "w", encoding="utf-8") as f:
                        json.dump(history_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error updating verification history JSON: {e}", flush=True)
            
        socketio.emit('recent_detections', recent_detections, to='admin_room')
        manual_history = load_manual_verification_history()
        socketio.emit('manual_verification_history', manual_history, to='admin_room')
        log_event(f"Manual verification record updated for {det_plate} ({ts}).", "ADMIN")

@socketio.on('clear_manual_history')
def handle_clear_manual_history():
    from scripts.logging_reporter import clear_manual_verification_report
    from scripts.state import recent_detections, detections_lock, save_recent_detections
    
    clear_manual_verification_report()
    history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "manual_verification_history.json")
    if os.path.exists(history_file):
        try:
            os.remove(history_file)
        except Exception:
            pass
            
    with detections_lock:
        for det in recent_detections:
            det["verified"] = False
            det["verification_details"] = None
        save_recent_detections()
        
    socketio.emit('recent_detections', recent_detections, to='admin_room')
    socketio.emit('manual_verification_history', [], to='admin_room')
    log_event("Manual verification report CSV and JSON wiped. Queue preserved and reset to pending.", "ADMIN")

@socketio.on('request_reconciliation_history')
def handle_request_history(data=None):
    if not isinstance(data, dict):
        data = {}
    selected_date = data.get("date", "today")
    
    from scripts.state import get_reconciliation_history_for_date, get_available_reconciliation_dates
    history = get_reconciliation_history_for_date(selected_date)
    
    socketio.emit('reconciliation_history_response', history, to=request.sid)
    socketio.emit('all_time_reconciliation_stats_response', all_time_stats, to=request.sid)
    socketio.emit('available_reconciliation_dates_response', get_available_reconciliation_dates(), to=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    info = connected_terminals.pop(request.sid, None)
    if info:
        ip = info.get("ip", "unknown")
        log_event(f"Terminal Disconnected: {info['role'].upper()} GATE {info['gate']} (IP: {ip}).", "SYSTEM")

@socketio.on('admin_update_config')
def handle_update_config(data):
    GLOBAL_CONFIG['entry_interval_seconds'] = int(data.get('entry', 5))
    GLOBAL_CONFIG['pay_delay_seconds'] = int(data.get('pay', 60))
    GLOBAL_CONFIG['exit_delay_seconds'] = int(data.get('exit', 20))
    GLOBAL_CONFIG['mock_mode'] = False
    GLOBAL_CONFIG['detection_mode'] = 'camera'
    GLOBAL_CONFIG['auto_generate_plates'] = False
    GLOBAL_CONFIG['camera_auto_exit_only'] = bool(data.get('camera_auto_exit_only', True))
    GLOBAL_CONFIG['real_device_payment'] = bool(data.get('real_device_payment', False))
    GLOBAL_CONFIG['enable_automatic_payment'] = bool(data.get('enable_automatic_payment', True))
    GLOBAL_CONFIG['teller_process_delay_seconds'] = int(data.get('teller_process_delay', 2))
    GLOBAL_CONFIG['teller_cooldown_seconds'] = int(data.get('teller_cooldown', 3))
    if 'camera_mapping' in data:
        GLOBAL_CONFIG['camera_mapping'] = data['camera_mapping']
        for ip in list(unregistered_cameras):
            if ip in GLOBAL_CONFIG['camera_mapping']:
                unregistered_cameras.pop(ip, None)

    save_config(log_event)
    socketio.emit('config_sync', GLOBAL_CONFIG, to='admin_room')
    emit_unregistered_cameras()
    log_event(f"Config Updated.", "ADMIN")

@socketio.on('dismiss_unregistered_camera')
def handle_dismiss_unregistered_camera(data):
    unregistered_cameras.pop(data.get('ip'), None)
    emit_unregistered_cameras()

@socketio.on('admin_sync_parked_vehicles')
def handle_sync_parked_vehicles():
    log_event("Initiating synchronization of parked vehicles from live API...", "ADMIN")
    threading.Thread(target=sync_and_process_parked_vehicles, daemon=True).start()

@socketio.on('admin_exit_all_paid')
def handle_exit_all_paid():
    log_event("Initiating exit sequence for all paid vehicles...", "ADMIN")
    from scripts.payment_handler import exit_all_paid_vehicles
    threading.Thread(target=exit_all_paid_vehicles, daemon=True).start()

@socketio.on('reset_api_metrics')
def handle_reset_api_metrics():
    reset_metrics()
    log_event("API Latency Metrics reset by admin.", "ADMIN")

@socketio.on('request_vehicle_media')
def handle_request_vehicle_media(data):
    """
    On-demand lazy loading query handler. Reads heavy base64 strings from 
    the media file only when a row is actively inspected.
    """
    plate_key = data.get("plate_key")
    if not plate_key:
        return
        
    # 🟢 FIX: Import RECON_LOG_DIR from scripts.state directly inside the scope
    from scripts.state import RECON_LOG_DIR
        
    # Extract date if passed from frontend (e.g. "YYYY-MM-DD" from first_seen), otherwise fallback to today
    date_str = data.get("date")
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    # If date_str is a full ISO timestamp, extract just the YYYY-MM-DD part
    if "T" in date_str:
        date_str = date_str.split("T")[0]
        
    media_payload = {
        "plate_key": plate_key,
        "front_plate_image": "", "front_vehicle_image": "",
        "back_plate_image": "", "back_vehicle_image": ""
    }
    
    # Try the new separate file structure first
    media_dir = os.path.join(RECON_LOG_DIR, "media", date_str)
    individual_media_file = os.path.join(media_dir, f"{plate_key}.json")
    
    if os.path.exists(individual_media_file):
        try:
            with open(individual_media_file, "r", encoding="utf-8") as f:
                media_payload = json.load(f)
        except Exception as e:
            print(f"Error loading individual media file {individual_media_file}: {e}", flush=True)
    else:
        # Fallback to the old single large file method
        media_file = os.path.join(RECON_LOG_DIR, f"reconciliation_media_{date_str}.json")
        if os.path.exists(media_file):
            try:
                with open(media_file, "r", encoding="utf-8") as f:
                    media_db = json.load(f)
                    if plate_key in media_db:
                        media_payload = media_db[plate_key]
            except Exception as e:
                print(f"Error lazy loading media file {media_file}: {e}", flush=True)
    socketio.emit('vehicle_media_response', media_payload, to=request.sid)

@socketio.on('update_ticketing_decision')
def handle_update_ticketing_decision(data):
    plate_key = data.get("plate_key")
    date_str = data.get("date")
    decision = data.get("decision")  # "CAMERA" or "TICKET"
    
    if not plate_key or not decision:
        return
        
    from scripts.state import update_ticketing_decision
    updated_record = update_ticketing_decision(plate_key, date_str, decision)
    if updated_record:
        # Broadcast the updated record to all terminals in the admin_room
        socketio.emit('reconciled_vehicle_updated', updated_record, to='admin_room')

# ==============================================================================
# 🔔 MULTI-FORMAT CAMERA WEBHOOK RECEIVER (POSTMAN + PHYSICAL ANPR ALERTS)
# ==============================================================================
def analyze_camera_payload(payload_package):
    if payload_package.get("type") != "MULTIPART":
        return

    files = payload_package.get("files", {})
    xml_entry = next((f for f in files.values() if f["type"] == "XML"), None)
    if not xml_entry:
        return
        
    try:
        root = ET.fromstring(xml_entry["data"].strip())
        
        def get_xml_tag(tag_name):
            for elem in root.iter():
                if elem.tag.endswith(f"}}{tag_name}") or elem.tag == tag_name:
                    return elem.text if elem.text else ""
            return ""

        plate = get_xml_tag('licensePlate')
        v_type = get_xml_tag('vehicleType')
        confidence = get_xml_tag('confidenceLevel')
        ip_address = get_xml_tag('ipAddress')
        mac_address = get_xml_tag('macAddress')
        channel_name = get_xml_tag('channelName')

        # Extract both image contexts
        base64_plate_img = ""
        base64_scene_img = ""
        
        for file_key, file_item in files.items():
            if file_item["type"] == "IMAGE":
                b64_data = base64.b64encode(file_item["data"]).decode('utf-8')
                data_uri = f"data:image/jpeg;base64,{b64_data}"
                
                fname = file_item["filename"].lower()
                if "licenseplate" in fname:
                    base64_plate_img = data_uri
                elif "vehicle" in fname or "detection" in fname:
                    base64_scene_img = data_uri

        print(f"[CAMERA PARSED] IP: {ip_address} | Plate: {plate} | Confidence: {confidence} | VehicleType: {v_type}", flush=True)

        if plate:
            camera_data = {
                "plate": plate.strip().upper(),
                "vehicleType": v_type,
                "confidence": int(confidence) if confidence else 100,
                "plateImage": base64_plate_img,   # Smaller text snippet
                "vehicleImage": base64_scene_img, # Big structural scene frame
                "timestamp": datetime.now().isoformat()
            }
            
            mapping = GLOBAL_CONFIG.get("camera_mapping", {})
            if ip_address in mapping:
                cam_info = mapping[ip_address]
                gate_id = cam_info.get("gate", 1)
                direction = cam_info.get("direction", "entry")
                camera_role = cam_info.get("camera", "front")
                
                # Enrich camera_data with gate and direction info
                camera_data["gate_id"] = gate_id
                camera_data["direction"] = direction
                
                source_type = "FRONT_CAM" if camera_role == "front" else "BACK_CAM"
                cam_label = cam_info.get("name") or ip_address
                print(f"[CAMERA BUFFERED] {cam_label} -> {source_type} (Gate: {gate_id}, Direction: {direction})", flush=True)
                process_and_buffer_data(source_type, camera_data)
            else:
                if ip_address not in unregistered_cameras:
                    log_event(f"Unregistered LPR camera IP: {ip_address} sent detection data. Register it on the dashboard.", "SYSTEM")
                cam = unregistered_cameras.setdefault(ip_address, {"ip": ip_address, "hits": 0})
                cam.update({
                    "mac": mac_address,
                    "channel_name": channel_name,
                    "last_plate": camera_data["plate"],
                    "last_seen": camera_data["timestamp"],
                    "hits": cam["hits"] + 1
                })
                emit_unregistered_cameras()

    except Exception as e:
        print(f"[PARSER EXCEPTION] Failed parsing camera multipart: {str(e)}", flush=True)

@app.route('/api/webhooks/camera', methods=['POST'])
def camera_webhook_receiver():
    try:
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        content_type = request.content_type.lower() if request.content_type else ""
        print(f"\n[CAMERA WEBHOOK EVENT RECEIVED] From IP: {client_ip} | Content-Type: {content_type}", flush=True)

        if "multipart/form-data" in content_type:
            extracted_files = {}
            for file_key, file_obj in request.files.items():
                filename = file_obj.filename
                raw_bytes = file_obj.read()
                
                if (filename and filename.endswith('.xml')) or ('xml' in (file_obj.content_type or '')):
                    xml_str = raw_bytes.decode('utf-8', errors='ignore')
                    extracted_files[file_key] = {"filename": filename, "type": "XML", "data": xml_str}
                    print(f"--- [CAMERA XML PAYLOAD: {filename}] ---", flush=True)
                    print(xml_str, flush=True)
                    print("------------------------------------------", flush=True)
                    try:
                        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "last_camera_event.xml")
                        with open(save_path, "w", encoding="utf-8") as xf:
                            xf.write(xml_str)
                    except Exception:
                        pass
                else:
                    byte_len = len(raw_bytes)
                    extracted_files[file_key] = {"filename": filename, "type": "IMAGE", "data": raw_bytes}
                    print(f"[CAMERA ATTACHMENT: {filename or file_key}] Size: {byte_len} bytes", flush=True)

            threading.Thread(target=analyze_camera_payload, args=({"type": "MULTIPART", "files": extracted_files},), daemon=True).start()
            return {"success": True, "message": "Multipart camera buffers streamed successfully"}, 200

        # Non-multipart payloads (JSON / raw XML fallback inspection)
        raw_data = request.get_data(as_text=True)
        print(f"[CAMERA NON-MULTIPART BODY]\n{raw_data[:2000]}", flush=True)
        return {"success": False, "error": "Unsupported media type payload structure"}, 400
    except Exception as e:
        print(f"[CAMERA WEBHOOK ERROR] {e}", flush=True)
        return {"success": False, "error": str(e)}, 500

# =========================================================
# 🖥️ VUE.JS STATIC FILE SERVING
# =========================================================
@app.route('/')
def serve_vue_app():
    return send_from_directory(os.path.join(app.root_path, 'dist'), 'index.html')

@app.route('/<path:path>')
def serve_vue_routes(path):
    dist_path = os.path.join(app.root_path, 'dist')
    if os.path.exists(os.path.join(dist_path, path)): 
        return send_from_directory(dist_path, path)
    return send_from_directory(dist_path, 'index.html')

load_config(log_event)

if __name__ == "__main__":
    print("\n" + "="*50 + "\nPIPELINE TUNNEL ENGINE RUNNING\n" + "="*50 + "\n")
    
    # Start the keep-alive background worker thread
    threading.Thread(target=websocket_listener, daemon=True).start()
    
    # 🟢 FIX: Ensure use_reloader=False is set to prevent duplicate thread generation
    port = int(os.environ.get("PORT", 5015))
    host = os.environ.get("HOST", "0.0.0.0")
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False)