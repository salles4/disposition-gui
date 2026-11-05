# Event Data Reference

What this project receives from outside systems, what it uses from each event, and where that data ends up. Use it as context when planning changes to event handling.

Last checked: 2026-11-05.

**How far to trust each section**

- **Captured:** based on a real payload.
- **From code:** based only on what the code reads. The sender may include more, and field formats are unconfirmed.

Sample values below are real except plates, device serials and IDs, which are replaced or shortened. Dashboard Socket.IO traffic and the teller service are internal, so they aren't covered.

## Overview

| Source | Route | Format | Handled by | Row field | Basis |
|---|---|---|---|---|---|
| LPR camera | `POST /api/webhooks/camera` | Multipart: XML + JPEGs | `camera_webhook_receiver`, `analyze_camera_payload` (`scripts/engine.py`) | `front_camera` / `back_camera` | Captured |
| HCP (HikCentral) | `POST /api/webhooks/camera` | JSON: `OnEventNotify` | `process_hcp_notification` (`scripts/camera_ws.py`) | `hikcentral` | Captured |
| Backend WebSocket: HCP | `disposition` message, `payload.hcp` | JSON | `on_ws_message`, `merge_hcp_events` | `hikcentral` | From code |
| Backend WebSocket: admin | `disposition` message, `payload.admin` | JSON | `on_ws_message` | `core_event` | From code |
| Backend WebSocket: barrier | `disposition` message, `payload.barrier` | JSON | `apply_barrier_open` (`scripts/state.py`) | `barrier` | From code |
| Backend WebSocket: spaces | `available-space` message | JSON | `on_ws_message` | None (see below) | From code |
| Backend REST (we request it) | `POST /api/payment/plate-no` | JSON | `lookup_plate_on_server` (`scripts/state.py`) | `server_record`, `server_saved` | From code |
| Backend REST (we request it) | `GET /api/reports/payment` | JSON | `lookup_exit_on_server` (`scripts/state.py`) | `server_record`, `server_saved` | Sample reply |

The webhook is served on the app port: `servers.app_port`, default 5015. The captured logs show port 5000.

## LPR camera (ISAPI XML)

**Basis: captured.** Full sample: [`anpr.xml`](../anpr.xml). Its first line is a console header, not XML.

Each event is a multipart POST containing an `EventNotificationAlert` XML file and JPEG attachments.

**Fields used**

| XML tag | Sample | Used for |
|---|---|---|
| `licensePlate` | `ABC1234` | Plate read |
| `vehicleType` | `vehicle` | Normalized to `MOTORCYCLE` or `CAR` |
| `confidenceLevel` | `99` | Read confidence, used by the disposition logic |
| `ipAddress` | `192.168.0.152` | Looks up terminal, gate, direction and front/back role in `terminals` config |
| `macAddress` | `08:3b:c1:...` | Unregistered camera list |
| `channelName` | `Camera 01` | Unregistered camera list |

**Attachments**

| Filename | Stored as |
|---|---|
| `licensePlatePicture.jpg` | Plate image |
| `detectionPicture.jpg` | Scene image |
| `vehiclePicture.jpg` | Scene image (whichever scene file is processed last wins) |

**Behaviour to know**

- Direction comes from `terminals` config. The XML's own `<direction>` (`forward`) isn't used.
- The row's time is when the event was processed. The XML's `<dateTime>` isn't used.
- The camera lookup uses the IP inside the XML, not the sender's IP. The sender's IP only sets the `CAMERA` / `NON-CAMERA` console label.
- Unregistered IPs get no row. They're listed on the dashboard for registration.
- With `include_images: false`, images are discarded on arrival but rows are still created.
- Images are stored separately in `logs/media/<date>/<plate_key>.json`, not in the reconciliation log.

**Received but unused:** `dateTime`, `eventType`, `deviceID`, `plateCharBelieve`, `plateColor`, `plateType`, `detectDir`, `barrierGateCtrlType`, image regions, vehicle logo and model codes, and the behaviour flags (`helmet`, `smoking`, etc., all `unknown` in the sample).

## HCP webhook (`OnEventNotify`)

**Basis: captured** (5 posts from one sender, `192.168.0.8`, 2026-11-05). All had `ability: event_veh` and `eventType: 131688`.

### Post types

| Type | How to recognize it | Handling |
|---|---|---|
| Details | Plate present, `isAttachPic: 0`, image empty | First post of an `eventId` is used |
| Details + image | Same `eventId`, `isAttachPic: 1`, `frontImage` set | Skipped as a repeat |
| Image only | Own `eventId`, empty plate, most values `-1` or empty, `backimage` set | Skipped (no plate) |

Repeat tracking is held in memory for 10 minutes, so it resets on restart.

### Entry vs exit

| Field | Entry | Exit |
|---|---|---|
| `laneInfo.direction` | `1` | `2` |
| Time field | `timeIn` | `timeOut` |
| `passagewayName` | `TERMINAL 3-ENT` | `TERMINAL 3-EXIT` |
| `srcIndex` / `gateNumber` | `3` | `4` |
| `allowType` / `allowResult` / `allowedReason` | `2` / `1` / `193` | `3` / `2` / `29` |

The direction meaning is inferred from these samples. The allow codes differ, but their meaning is unknown.

### Sample: exit, first post

```json
{
  "method": "OnEventNotify",
  "params": {
    "sendTime": "2026-11-05T09:06:56+08:00",
    "ability": "event_veh",
    "events": [{
      "eventId": "FD834A16...",
      "srcIndex": "4",
      "srcType": "passageway",
      "srcName": "TERMINAL 3-EXIT",
      "eventType": 131688,
      "status": 0,
      "happenTime": "2026-11-05T09:06:56+08:00",
      "data": {
        "guid": "FD834A16...",
        "parkingLotInfo": { "parkingLotIndexCode": "1", "parkingLotName": "PARKING IQ1", "buildingId": "B1" },
        "passagewayInfo": { "passagewayIndexCode": "4", "passagewayName": "TERMINAL 3-EXIT" },
        "laneInfo": { "laneIndexCode": "21", "laneName": "Lane 4 TICKET and ANPR", "direction": 2, "cameraIndexCode": "388", "gateNumber": "4" },
        "enterExitControlDevList": [{ "ip": "192.168.0.170", "name": "TERMINAL 3-EXIT", "serialNo": "DS-TMT202-..." }],
        "personInfo": { "ticketNo": "", "ownerName": "", "ownerPhoneNum": "" },
        "carInfo": { "plate": "ABC123", "vehicleType": "Two-Wheeler", "frontImage": "" },
        "captureInfoList": [{ "backimage": "" }],
        "timeOut": "2026-11-05T09:06:56+08:00",
        "allowType": 3,
        "allowResult": 2,
        "allowedReason": 29,
        "durationTime": 0,
        "isAttachPic": 0
      }
    }]
  },
  "isHistory": 0
}
```

### Sample: image-only post

```json
{
  "eventId": "FACABCAD...",
  "srcIndex": "3",
  "srcType": "passageway",
  "srcName": "",
  "eventType": 131688,
  "status": 0,
  "happenTime": "",
  "data": {
    "guid": "FACABCAD...",
    "parkingLotInfo": { "parkingLotIndexCode": "-1", "parkingLotName": "", "buildingId": "" },
    "passagewayInfo": { "passagewayIndexCode": "3", "passagewayName": "" },
    "laneInfo": { "laneIndexCode": "-1", "laneName": "", "direction": -1, "cameraIndexCode": "-1", "gateNumber": "" },
    "personInfo": { "ticketNo": "", "ownerName": "", "ownerPhoneNum": "" },
    "carInfo": { "plate": "", "vehicleType": "", "frontImage": "" },
    "captureInfoList": [{ "backimage": "Vsm://PHQG#20261105#...:553628" }],
    "allowType": -1,
    "allowResult": -1,
    "allowedReason": -1,
    "durationTime": -1,
    "isAttachPic": 0
  }
}
```

### What gets stored

| Source field | `hikcentral` field | Sample |
|---|---|---|
| `carInfo.plate` (uppercased) | `plate` | `ABC123` |
| `carInfo.vehicleType` | `raw_type_received` | `Two-Wheeler` |
| `carInfo.vehicleType`, normalized | `vehicleType` | `MOTORCYCLE` |
| `passagewayName` + `laneName` | `gateName` | `TERMINAL 3-EXIT - Lane 4 TICKET and ANPR` |
| `timeOut`, or `timeIn` if there's no `timeOut` | `timestamp` | `2026-11-05T09:06:56+08:00` |
| `laneInfo.direction` | Row's `direction`, only if it has none | `exit` |

**Behaviour to know**

- `Unknown` plates count as no plate, so they create no row. They're still printed as `[HCP EVENT]`.
- HCP rows match other rows by exact plate within 120 seconds, and not across opposite directions.
- `frontImage` and `backimage` are `Vsm://` references, not images. Nothing can fetch them yet, and they aren't stored on the row.

**Received but unused:** `eventType`, `status`, `happenTime`, `sendTime`, `isHistory`, `srcIndex`, `gateNumber`, `laneIndexCode`, `cameraIndexCode`, `parkingLotInfo`, `enterExitControlDevList`, `personInfo`, `allowType`, `allowResult`, `allowedReason`, `durationTime`, `isAttachPic`.

`durationTime` was `0` even on the exit sample, so it doesn't appear to give parking time.

## Backend WebSocket

**Basis: from code.** There's no captured sample of these messages yet.

On connect, the script sends `{"type": "auth", "token": "..."}`. The backend replies with `{"event": "auth-ok", "action": "auth-ok"}`, and the connection only counts as live after that.

### `disposition`

```json
{
  "event": "disposition",
  "action": "disposition",
  "payload": {
    "barrier": { },
    "hcp": { "guid": "...", "events": [ ] },
    "admin": { "events": [ ] }
  }
}
```

The HCP and admin reads in one message are saved to the same row. Only the first admin read is paired with HCP. Further admin reads get their own rows.

**`payload.hcp.events[]`** uses the same fields as the webhook's `data` object, but directly on each event with no `data` wrapper. `guid` sits on `payload.hcp`. Events in one message are merged into a single read, and later values overwrite earlier ones.

**`payload.admin.events[]`**

| Field | Used for |
|---|---|
| `plate_no` or `plate` | Plate read. Repeats of a plate within 3 seconds are dropped |
| `vehicle_type` | Admin type code, mapped to `CAR`, `MOTORCYCLE` or `OTHERS` |
| `gate_id` | Gate |
| `timestamp` or `time` | Read time. Falls back to the HCP time, then the current time |
| `percentage` | Confidence, default `100` |
| `frontImage`, `backImage` | Image names. Fall back to the HCP references |

Admin reads also feed the recent detections list. In `camera` detection mode, they also start `process_camera_vehicle`.

**`payload.barrier`** is saved whole on the row as `barrier`.

| Field | Used for |
|---|---|
| `plate` or `plate_no` | Finding the row |
| `direction` | Finding the row; fills the row's direction if it has none |
| `barrier_open_at` | Open time, format `YYYY-MM-DD HH:MM:SS`. Drives the barrier time KPIs |
| `transaction_id` | Stops an earlier visit's row from being matched |

Barrier events can arrive before the plate reads, so matching tries up to 4 times, 5 seconds apart. It looks within 600 seconds, because exit barriers open after payment.

### `available-space`

```json
{
  "event": "available-space",
  "action": "available-space",
  "display": { "status": "entry", "plate_no": "...", "vehicle_type": "...", "gate_id": 1 }
}
```

This creates no row, and it's ignored unless `detection_mode` is `camera`.

| `status` | Action |
|---|---|
| `entry` | Starts `process_camera_vehicle` |
| `exit`, `cleared` | Plays the exit animation and updates the parked and exited counts |

## Backend `/plate-no` lookup

**Basis: from code.** This is a reply to our own request rather than an event. It runs 45 seconds after a row is created, for entry rows only.

Request: `{"licence_plate_no": "...", "terminal": <TERMINAL_ID>}`. It tries the plate as read, then the spaced format if that differs.

| `server_record` field | Reply field |
|---|---|
| `plate_no`, `reference_no`, `ticket_no` | Top level or `data` |
| `transaction_id`, `total_amount`, `reason` | `data` |
| `vehicle_type` | `data.vehicle_type_name` or `vehicle_info.vehicle_type` |
| `customer_type` | `data.customer_type_name` |
| `gate_id`, `entry`, `parking_duration` | Top level |
| `message` | Top level, if it's a string |

`server_saved` is `true` for a normal reply, a `payment_required: false` reply, or a message containing "already paid", "payment successful" or "enter park".

## Payment report (exit check)

**Basis: sample reply.** `GET /api/reports/payment` runs once, 45 seconds after an exit row is created.

Query: `search` (the plate), `page=1`, `per_page=15`, `limit=15`, `offset=0`, `sort_by=time_out`, `sort_order=desc`, `start_date` (00:00:00 on the `first_seen` date), `end_date` (23:59:59 on the day of the check). It tries the plate as read, then the spaced format if that differs.

`search` is a partial match, so a reply row only counts if its `plate_no` matches exactly and its `time_out` is within 10 minutes of `first_seen`. The closest row wins. `server_saved` is `false` if no row qualifies.

`server_record` keeps these reply fields under the same names: `plate_no`, `invoice_no`, `transaction_id`, `ticket_no`, `customer_type`, `vehicle_type`, `time_in`, `time_out`, `time_paid`, `entry_point`, `exit_point`, `amount_paid`, `payment_method`, `payment_channel`.

## Open questions

- **HCP codes:** what do `eventType`, `status`, `allowType`, `allowResult` and `allowedReason` mean? `direction` should also be confirmed against HCP's documentation.
- **HCP images:** how can `Vsm://` references be turned into images?
- **Image-only posts:** how does an image-only post link to its vehicle? Its `eventId` didn't match the other posts captured with it.
- **HCP gates:** how do HCP passageways map to `terminals` config? They aren't linked today, so an HCP-only row has no terminal or gate, and it only appears when the Terminal filter is set to All.
- **`isHistory`:** what does `1` mean, and should those events be treated differently?
- **WebSocket HCP:** is it still being sent? This machine's logs have no `hikcentral` rows after 2026-08-20.
- **WebSocket samples:** capture real `disposition` and `barrier` messages to replace the "from code" sections above.

## Capturing new samples

| Source | Where to find it |
|---|---|
| Camera | `logs/last_camera_event.xml` (latest only), or `[CAMERA XML PAYLOAD]` in the console |
| Other XML senders | `logs/last_non_camera_event.xml` (latest only) |
| HCP webhook | `[HCP EVENT]` in the console (not saved to a file) |
| Other JSON on the webhook | `[NON-CAMERA NON-MULTIPART BODY]` in the console, cut at 2000 characters |
| Stored rows | `logs/reconciliation_log_<date>.json` |

Remove real plates, serials and personal details before adding samples here.
