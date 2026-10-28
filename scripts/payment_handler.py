import time
import random
import threading
import requests
from datetime import datetime, timedelta

sync_lock = threading.Lock()

from scripts.app_context import socketio
from scripts.config import API_BASE_URL, TERMINAL_ID, HEADERS, ADMIN_HEADERS, GLOBAL_CONFIG, EXIT_GATES
from scripts.state import sim_stats, queue_lock
from scripts.logging_reporter import log_event
from scripts.utils import format_plate, get_random_gate

def execute_payment(plate_no, v_type):
    # CONDITION 1: Handle Real Device Payment
    if GLOBAL_CONFIG.get("real_device_payment"):
        log_event(f"[{plate_no}] Real device payment enabled. Sending to Teller Service...", "PAY")
        entry_time_str = None
        try:
            bill = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate_no, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=10)
            bill_json = bill.json()
            if bill_json.get("success"):
                bill_data = bill_json.get("data")
                if bill_data:
                    entry_time_str = bill_data.get("time_in") or bill_data.get("entry_time") or bill_data.get("created_at")
        except Exception as e:
            log_event(f"Failed to query entry time for [{plate_no}] from API: {e}", "WARN")

        if not entry_time_str:
            entry_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            add_res = requests.post(
                "http://localhost:5010/add-to-queue",
                json={"plate_no": plate_no, "time_in": entry_time_str},
                timeout=5
            )
            if add_res.status_code == 200:
                log_event(f"Vehicle [{plate_no}] added to Teller Service queue.", "PAY")
            else:
                log_event(f"Teller Service addition failed for [{plate_no}]: {add_res.text}", "WARN")
        except Exception as e:
            log_event(f"Failed to communicate with Teller Service for [{plate_no}]: {e}", "ERROR")

        log_event(f"Waiting for payment on [{plate_no}] via real device...", "PAY")
        start_poll = time.time()
        payment_cleared = False
        while (time.time() - start_poll) < 180:
            time.sleep(3)
            try:
                bill_chk = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate_no, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=5)
                if bill_chk.status_code != 200:
                    err_text = bill_chk.text.lower()
                    if "already paid" in err_text or "payment successful" in err_text or "enter park" in err_text:
                        payment_cleared = True
                        break
                    if "not inside" in err_text or "exited" in err_text or "no transaction" in err_text:
                        payment_cleared = True
                        break
                else:
                    bill_json = bill_chk.json()
                    if not bill_json.get("success"):
                        msg = (bill_json.get("message") or "").lower()
                        if "already paid" in msg or "payment successful" in msg or "enter park" in msg:
                            payment_cleared = True
                            break
                        if "not inside" in msg or "exited" in msg or "no transaction" in msg:
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
            log_event(f"[{plate_no}] Payment confirmed cleared via real device.", "PAY")
            socketio.emit('payment_success', {'plate': plate_no, 'amount': 0.0, 'vType': v_type}, to='admin_room')
            return True
        else:
            log_event(f"[{plate_no}] Real device payment timed out or failed.", "ERROR")
            return False

    if not GLOBAL_CONFIG.get("enable_automatic_payment", True):
        log_event(f"[{plate_no}] Automatic payment disabled (Real Device Payment and Auto-Pay are both OFF).", "PAY")
        return False

    # CONDITION 3: Handle Production Environment (Live API Mode Enabled)
    log_event(f"Executing live production API sequence for [{plate_no}]...", "SYSTEM")
    try:
        bill = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate_no, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=10)
        try:
            bill_json = bill.json()
        except Exception:
            bill_json = {}
        if not bill_json.get("success"):
            err_msg = bill_json.get("message") or bill_json.get("error") or bill_json.get("msg") or bill.text
            log_event(f"Billing Retrieval Failed for [{plate_no}]: {err_msg}", "ERROR")
            return False
            
        ref_no = bill_json.get("reference_no")
        bill_data = bill_json.get("data")
        if not bill_data or not ref_no:
            log_event(f"Billing Error: Missing total amount or reference number for [{plate_no}].", "ERROR")
            return False
            
        total = float(bill_data.get("total_amount", "0"))
        
        pay = requests.post(f"{API_BASE_URL}/api/payment/cash", json={"amount_paid": total, "licence_plate_no": plate_no, "reference_no": ref_no, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=10)
        
        try:
            pay_json = pay.json()
        except Exception:
            pay_json = {}
        
        if pay_json.get("success"):
            log_event(f"[{plate_no}] LIVE API Payment Cleared (P{total:.2f}).", "PAY")
            socketio.emit('payment_success', {'plate': plate_no, 'amount': total, 'vType': v_type}, to='admin_room')
            return True
        else:
            err_msg = pay_json.get("message") or pay_json.get("error") or pay_json.get("msg") or pay.text
            log_event(f"Cash Payment API Failed for [{plate_no}]: {err_msg}", "ERROR")
    except Exception as e:
        log_event(f"Live Network Failure for [{plate_no}]: {str(e)}", "ERROR")
    return False

def sync_and_process_parked_vehicles():
    if not sync_lock.acquire(blocking=False):
        log_event("Sync process is already running. Skipping concurrent request.", "WARN")
        return
    try:
        # 1. Fetch active (unpaid) vehicles
        res_active = requests.get(f"{API_BASE_URL}/api/parked/active", headers=ADMIN_HEADERS, timeout=10)
        active_list = []
        if res_active.status_code == 200 and res_active.json().get("success"):
            active_list = res_active.json().get("data", [])
            log_event(f"Retrieved {len(active_list)} active (unpaid) parked vehicles.", "SYSTEM")
        else:
            log_event(f"Failed to fetch active parked list: {res_active.text}", "ERROR")
            
        # 2. Fetch cleared (paid) vehicles
        res_cleared = requests.get(f"{API_BASE_URL}/api/parked/cleared", headers=ADMIN_HEADERS, timeout=10)
        cleared_list = []
        if res_cleared.status_code == 200 and res_cleared.json().get("success"):
            cleared_list = res_cleared.json().get("data", [])
            log_event(f"Retrieved {len(cleared_list)} cleared (paid) parked vehicles.", "SYSTEM")
        else:
            log_event(f"Failed to fetch cleared parked list: {res_cleared.text}", "ERROR")

        # 2b. Fetch flagged parked vehicles (over 24 hours)
        res_flagged = requests.get(f"{API_BASE_URL}/api/parked/flagged", headers=ADMIN_HEADERS, timeout=10)
        flagged_list = []
        if res_flagged.status_code == 200 and res_flagged.json().get("success"):
            flagged_list = res_flagged.json().get("data", [])
            log_event(f"Retrieved {len(flagged_list)} flagged parked vehicles.", "SYSTEM")
        else:
            log_event(f"Failed to fetch flagged parked list: {res_flagged.text}", "ERROR")

        processed_plates = set()

        # 3. Process Cleared (Paid) Vehicles: Exit Immediately via LPR API
        for vehicle in cleared_list:
            plate = vehicle.get("plate_no", "").strip().upper()
            if not plate:
                continue
            processed_plates.add(plate)
            
            raw_v_type = vehicle.get("vehicle_type", "CAR")
            plate, v_type = format_plate(plate, raw_v_type)
            
            assigned_exit = EXIT_GATES[sim_stats.get("exited", 0) % len(EXIT_GATES)]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                exit_res = requests.post(
                    f"{API_BASE_URL}/api/lpr",
                    json={
                        "gate_id": assigned_exit,
                        "plate_no": plate,
                        "vehicle_type": v_type,
                        "created_at": now_str,
                        "timestamp": now_str,
                        "time_out": now_str
                    },
                    headers=HEADERS,
                    timeout=10
                )
                exit_json = exit_res.json()
                if exit_res.status_code == 200 and exit_json.get("success"):
                    log_event(f"[SYNC] Already Paid: Vehicle [{plate}] exited Gate {assigned_exit} via LPR API.", "EXIT")
                else:
                    log_event(f"[SYNC] Already Paid exit LPR non-success for [{plate}]: {exit_json.get('message', exit_res.text)}", "WARN")
            except Exception as ex:
                log_event(f"[SYNC] Already Paid exit LPR error for [{plate}]: {ex}", "ERROR")
            
            socketio.emit('play_exit', {'plate': plate, 'vType': v_type}, to=f"exit_{assigned_exit}")
            with queue_lock:
                sim_stats["exited"] += 1
            socketio.emit('stats_update', sim_stats, to='admin_room')

        # Combine active and flagged lists, avoiding duplicates and already cleared plates
        unpaid_list = []
        for vehicle in active_list + flagged_list:
            raw_plate = vehicle.get("plate_no", "").strip().upper()
            raw_v_type = vehicle.get("vehicle_type", "CAR")
            fmt_plate, _ = format_plate(raw_plate, raw_v_type)
            if fmt_plate and fmt_plate not in processed_plates:
                processed_plates.add(fmt_plate)
                unpaid_list.append(vehicle)

        # 4. Process Active & Flagged (Unpaid) Vehicles: Pay & Exit
        for vehicle in unpaid_list:
            plate = vehicle.get("plate_no", "").strip().upper()
            raw_v_type = vehicle.get("vehicle_type", "CAR")
            
            plate, v_type = format_plate(plate, raw_v_type)

            # --- REAL DEVICE PAYMENT HANDLING ---
            if GLOBAL_CONFIG.get("real_device_payment"):
                entry_time_str = None
                try:
                    bill = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=10)
                    bill_json = bill.json()
                    if bill_json.get("success"):
                        bill_data = bill_json.get("data")
                        if bill_data:
                            entry_time_str = bill_data.get("time_in") or bill_data.get("entry_time") or bill_data.get("created_at")
                except Exception as e:
                    log_event(f"Failed to query entry time for [{plate}]: {e}", "WARN")

                if not entry_time_str:
                    entry_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                try:
                    add_res = requests.post(
                        "http://localhost:5010/add-to-queue",
                        json={"plate_no": plate, "time_in": entry_time_str},
                        timeout=5
                    )
                    if add_res.status_code == 200:
                        log_event(f"[SYNC] Active vehicle [{plate}] sent to Teller Service.", "PAY")
                    else:
                        log_event(f"[SYNC] Teller Service queue addition failed for [{plate}]: {add_res.text}", "WARN")
                except Exception as e:
                    log_event(f"[SYNC] Failed to communicate with Teller Service: {e}", "ERROR")

                log_event(f"[SYNC] Waiting for payment on [{plate}] via real device...", "PAY")
                start_poll = time.time()
                payment_cleared = False
                while (time.time() - start_poll) < 180:
                    time.sleep(3)
                    try:
                        bill_chk = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=5)
                        if bill_chk.status_code != 200:
                            err_text = bill_chk.text.lower()
                            if "already paid" in err_text or "payment successful" in err_text or "enter park" in err_text:
                                payment_cleared = True
                                break
                            if "not inside" in err_text or "exited" in err_text or "no transaction" in err_text:
                                payment_cleared = True
                                break
                        else:
                            bill_json = bill_chk.json()
                            if not bill_json.get("success"):
                                msg = (bill_json.get("message") or "").lower()
                                if "already paid" in msg or "payment successful" in msg or "enter park" in msg:
                                    payment_cleared = True
                                    break
                                if "not inside" in msg or "exited" in msg or "no transaction" in msg:
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
                    log_event(f"[SYNC] Payment confirmed for active vehicle [{plate}] via real device.", "PAY")
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
                        exit_res = requests.post(
                            f"{API_BASE_URL}/api/lpr",
                            json={
                                "gate_id": assigned_exit,
                                "plate_no": plate,
                                "vehicle_type": v_type,
                                "created_at": now_str,
                                "timestamp": now_str,
                                "time_out": now_str
                            },
                            headers=HEADERS,
                            timeout=10
                        )
                        exit_json = exit_res.json()
                        if exit_res.status_code == 200 and exit_json.get("success"):
                            log_event(f"[SYNC] Vehicle [{plate}] exited Gate {assigned_exit} via LPR API.", "EXIT")
                        else:
                            log_event(f"[SYNC] Exit LPR non-success for [{plate}]: {exit_json.get('message', exit_res.text)}", "WARN")
                    except Exception as ex:
                        log_event(f"[SYNC] Exit LPR error for [{plate}]: {ex}", "ERROR")
                    
                    socketio.emit('play_exit', {'plate': plate, 'vType': v_type}, to=f"exit_{assigned_exit}")
                    with queue_lock:
                        sim_stats["parked"] = max(0, sim_stats["parked"] - 1)
                        sim_stats["paid"] = max(0, sim_stats["paid"] - 1)
                        sim_stats["exited"] += 1
                    socketio.emit('stats_update', sim_stats, to='admin_room')
                else:
                    log_event(f"[SYNC] Real device payment timed out or failed for [{plate}].", "ERROR")
                time.sleep(0.5)
                continue

            if not GLOBAL_CONFIG.get("enable_automatic_payment", True):
                log_event(f"[SYNC] Active vehicle [{plate}] skipped (Real Device Payment and Auto-Pay are both OFF).", "PAY")
                continue

            # --- LIVE PRODUCTION API HANDLING ---
            log_event(f"[SYNC] Fetching bill details for active vehicle [{plate}]...", "SYSTEM")
            bill = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": plate, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=10)
            try:
                bill_json = bill.json()
            except Exception:
                bill_json = {}
            
            if not bill_json.get("success"):
                err_msg = bill_json.get("message") or bill_json.get("error") or bill_json.get("msg") or bill.text
                log_event(f"[SYNC] Billing Retrieval Failed for [{plate}]: {err_msg}", "ERROR")
                continue
                
            bill_data = bill_json.get("data")
            ref_no = bill_json.get("reference_no")
            
            if not bill_data or not ref_no:
                log_event(f"[SYNC] Billing Error: Missing total amount or reference number for [{plate}].", "ERROR")
                continue
                
            total = float(bill_data.get("total_amount", "0"))
            log_event(f"[SYNC] Settle bill for active vehicle [{plate}] (P{total:.2f})...", "PAY")
            
            pay_payload = {
                "amount_paid": total,
                "licence_plate_no": plate,
                "reference_no": ref_no,
                "terminal": TERMINAL_ID
            }
            pay = requests.post(f"{API_BASE_URL}/api/payment/cash", json=pay_payload, headers=HEADERS, timeout=10)
            pay_json = pay.json()
            
            if pay_json.get("success"):
                log_event(f"[SYNC] LIVE API Payment Cleared for [{plate}] (P{total:.2f}).", "PAY")
                socketio.emit('payment_success', {'plate': plate, 'amount': total, 'vType': v_type}, to='admin_room')
                
                with queue_lock:
                    sim_stats["parked"] += 1
                    sim_stats["paid"] += 1
                socketio.emit('stats_update', sim_stats, to='admin_room')
                
                exit_delay = 0.1 if not GLOBAL_CONFIG.get("real_device_payment") else GLOBAL_CONFIG.get("exit_delay_seconds", 5)
                time.sleep(exit_delay)
                
                assigned_exit = EXIT_GATES[sim_stats.get("exited", 0) % len(EXIT_GATES)]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    exit_res = requests.post(
                        f"{API_BASE_URL}/api/lpr",
                        json={
                            "gate_id": assigned_exit,
                            "plate_no": plate,
                            "vehicle_type": v_type,
                            "created_at": now_str,
                            "timestamp": now_str,
                            "time_out": now_str
                        },
                        headers=HEADERS,
                        timeout=10
                    )
                    exit_json = exit_res.json()
                    if exit_res.status_code == 200 and exit_json.get("success"):
                        log_event(f"[SYNC] Vehicle [{plate}] exited Gate {assigned_exit} via LPR API.", "EXIT")
                    else:
                        log_event(f"[SYNC] Exit LPR non-success for [{plate}]: {exit_json.get('message', exit_res.text)}", "WARN")
                except Exception as ex:
                    log_event(f"[SYNC] Exit LPR error for [{plate}]: {ex}", "ERROR")
                
                socketio.emit('play_exit', {'plate': plate, 'vType': v_type}, to=f"exit_{assigned_exit}")
                with queue_lock:
                    sim_stats["parked"] = max(0, sim_stats["parked"] - 1)
                    sim_stats["paid"] = max(0, sim_stats["paid"] - 1)
                    sim_stats["exited"] += 1
                socketio.emit('stats_update', sim_stats, to='admin_room')
            else:
                err_msg = pay_json.get("message") or pay_json.get("error") or pay_json.get("msg") or pay.text
                log_event(f"[SYNC] Cash Payment API Failed for [{plate}]: {err_msg}", "ERROR")
                
            time.sleep(0.1 if not GLOBAL_CONFIG.get("real_device_payment") else 0.5)

        socketio.emit('admin_sync_complete', {"success": True}, to='admin_room')
        log_event("Parked vehicles synchronization process completed.", "ADMIN")
        
    except Exception as e:
        log_event(f"Failed to sync parked vehicles: {str(e)}", "ERROR")
        socketio.emit('admin_sync_complete', {"success": False, "error": str(e)}, to='admin_room')
    finally:
        sync_lock.release()


def exit_all_paid_vehicles():
    try:
        # 1. Fetch cleared (paid) vehicles
        res_cleared = requests.get(f"{API_BASE_URL}/api/parked/cleared", headers=ADMIN_HEADERS, timeout=10)
        cleared_list = []
        if res_cleared.status_code == 200 and res_cleared.json().get("success"):
            cleared_list = res_cleared.json().get("data", [])
            log_event(f"Retrieved {len(cleared_list)} cleared (paid) parked vehicles for exit processing.", "SYSTEM")
        else:
            log_event(f"Failed to fetch cleared parked list: {res_cleared.text}", "ERROR")

        # 2. Fetch flagged parked vehicles (over 24 hours)
        res_flagged = requests.get(f"{API_BASE_URL}/api/parked/flagged", headers=ADMIN_HEADERS, timeout=10)
        flagged_list = []
        if res_flagged.status_code == 200 and res_flagged.json().get("success"):
            flagged_list = res_flagged.json().get("data", [])
            log_event(f"Retrieved {len(flagged_list)} flagged parked vehicles for exit processing check.", "SYSTEM")
        else:
            log_event(f"Failed to fetch flagged parked list for exit check: {res_flagged.text}", "WARN")

        processed_plates = set()
        vehicles_to_exit = []

        # Add all cleared vehicles
        for vehicle in cleared_list:
            raw_plate = vehicle.get("plate_no", "").strip().upper()
            raw_v_type = vehicle.get("vehicle_type", "CAR")
            fmt_plate, _ = format_plate(raw_plate, raw_v_type)
            if fmt_plate and fmt_plate not in processed_plates:
                processed_plates.add(fmt_plate)
                vehicles_to_exit.append(vehicle)

        # Check flagged vehicles for payment status
        for vehicle in flagged_list:
            raw_plate = vehicle.get("plate_no", "").strip().upper()
            raw_v_type = vehicle.get("vehicle_type", "CAR")
            fmt_plate, _ = format_plate(raw_plate, raw_v_type)
            if not fmt_plate or fmt_plate in processed_plates:
                continue

            v_status = str(vehicle.get("status", "")).lower()
            v_pay_status = str(vehicle.get("payment_status", "")).lower()
            is_paid_flag = vehicle.get("is_paid") is True or vehicle.get("paid") is True
            
            is_paid = is_paid_flag or v_status in ["cleared", "paid"] or v_pay_status in ["cleared", "paid"]

            if not is_paid:
                try:
                    bill_chk = requests.post(f"{API_BASE_URL}/api/payment/plate-no", json={"licence_plate_no": fmt_plate, "terminal": TERMINAL_ID}, headers=HEADERS, timeout=5)
                    err_text = bill_chk.text.lower()
                    if bill_chk.status_code != 200:
                        if any(k in err_text for k in ["already paid", "payment successful", "enter park", "exited", "not inside", "no transaction"]):
                            is_paid = True
                    else:
                        bill_json = bill_chk.json()
                        if not bill_json.get("success"):
                            msg = (bill_json.get("message") or "").lower()
                            if any(k in msg for k in ["already paid", "payment successful", "enter park", "exited", "not inside", "no transaction"]):
                                is_paid = True
                        else:
                            fee = float(bill_json.get("data", {}).get("total_amount", 0.0))
                            if fee <= 0:
                                is_paid = True
                except Exception:
                    pass

            if is_paid:
                processed_plates.add(fmt_plate)
                vehicles_to_exit.append(vehicle)

        if not vehicles_to_exit:
            log_event("No paid vehicles (cleared or paid-flagged) to exit.", "SYSTEM")
            socketio.emit('admin_exit_all_paid_complete', {"success": True, "count": 0}, to='admin_room')
            return

        exited_count = 0
        for vehicle in vehicles_to_exit:
            plate = vehicle.get("plate_no", "").strip().upper()
            raw_v_type = vehicle.get("vehicle_type", "CAR")
            plate, v_type = format_plate(plate, raw_v_type)
            
            assigned_exit = EXIT_GATES[sim_stats.get("exited", 0) % len(EXIT_GATES)]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                exit_res = requests.post(
                    f"{API_BASE_URL}/api/lpr",
                    json={
                        "gate_id": assigned_exit,
                        "plate_no": plate,
                        "vehicle_type": v_type,
                        "created_at": now_str,
                        "timestamp": now_str,
                        "time_out": now_str
                    },
                    headers=HEADERS,
                    timeout=10
                )
                exit_json = exit_res.json()
                if exit_res.status_code == 200 and exit_json.get("success"):
                    log_event(f"[EXIT ALL PAID] Vehicle [{plate}] exited Gate {assigned_exit} via LPR API.", "EXIT")
                    exited_count += 1
                else:
                    log_event(f"[EXIT ALL PAID] Exit LPR non-success for [{plate}]: {exit_json.get('message', exit_res.text)}", "WARN")
            except Exception as ex:
                log_event(f"[EXIT ALL PAID] Exit LPR error for [{plate}]: {ex}", "ERROR")
            
            socketio.emit('play_exit', {'plate': plate, 'vType': v_type}, to=f"exit_{assigned_exit}")
            with queue_lock:
                sim_stats["exited"] += 1
            socketio.emit('stats_update', sim_stats, to='admin_room')
            time.sleep(0.2)

        socketio.emit('admin_exit_all_paid_complete', {"success": True, "count": exited_count}, to='admin_room')
        log_event(f"Exited {exited_count} paid vehicles successfully (cleared & paid-flagged).", "ADMIN")
    except Exception as e:
        log_event(f"Failed to exit paid vehicles: {str(e)}", "ERROR")
        socketio.emit('admin_exit_all_paid_complete', {"success": False, "error": str(e)}, to='admin_room')

