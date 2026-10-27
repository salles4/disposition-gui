# Parking Reconciliation Pipeline & LPR Verification Documentation

This documentation covers the architecture, data structures, and pipeline features of the **Parking LPR Reconciliation & Manual Verification System**.

---

## 1. System Architecture

The pipeline synchronizes plate recognition events across multiple sources (HikCentral, local cameras, and core ticketing systems) to decide whether to route a transaction to the **Ticketing System** or the **Camera LPR System**.

```
                           +----------------------+
                           |  HikCentral LPR WS   |
                           +-----------+----------+
                                       |
                                       v
+------------------+       +-----------+----------+       +------------------+
|  Local Camera WS | ----> |   State Manager      | <---- | Core Event Logs  |
+------------------+       |   (state.py)         |       +------------------+
                           +-----------+----------+
                                       |
                                       v
                           +-----------+----------+
                           |  Truth Table Engine  |
                           +-----------+----------+
                                       |
                  +--------------------+--------------------+
                  |                                         |
                  v                                         v
         +--------+--------+                       +--------+--------+
         |  Camera System  |                       | Ticket Routing  |
         |  (Car/Motor LP) |                       | (Barcode/Paper) |
         +-----------------+                       +-----------------+
```

---

## 2. Automated Disposition Truth Table

The system reconciles front/back camera captures to assign a **Disposition** status. If a camera reads a plate or identifies a motorcycle, it is represented as a boolean value in a 4-digit tuple:

$$\text{Key} = (\text{Front Plate Detected}, \text{Front is Motorcycle}, \text{Back Plate Detected}, \text{Back is Motorcycle})$$

### Mapping Matrix

| Front Plate | Front Motor | Back Plate | Back Motor | Disposition Target | Routing Decision |
| :---: | :---: | :---: | :---: | :---: | :---: |
| `0` | `0` | `0` | `0` | `NA` | Default / Review |
| `0` | `0` | `0` | `1` | `Ticket` | **TICKET** |
| `0` | `0` | `1` | `0` | `Car LP` | **SYSTEM** |
| `0` | `0` | `1` | `1` | `Motor LP` | **SYSTEM** |
| `0` | `1` | `0` | `0` | `Ticket` | **TICKET** |
| `0` | `1` | `0` | `1` | `Ticket` | **TICKET** |
| `0` | `1` | `1` | `0` | `Ticket` | **TICKET** |
| `0` | `1` | `1` | `1` | `Motor LP` | **SYSTEM** |
| `1` | `0` | `0` | `0` | `Car LP` | **SYSTEM** |
| `1` | `0` | `0` | `1` | `Car LP` | **SYSTEM** |
| `1` | `0` | `1` | `0` | `Car LP` | **SYSTEM** |
| `1` | `0` | `1` | `1` | `Car LP` | **SYSTEM** |
| `1` | `1` | `0` | `0` | `NA` | Default / Review |
| `1` | `1` | `0` | `1` | `NA` | Default / Review |
| `1` | `1` | `1` | `0` | `NA` | Default / Review |
| `1` | `1` | `1` | `1` | `NA` | Default / Review |

---

## 3. Vehicle Plate Formats & Routing Decisions

To determine whether a vehicle uses the LPR **SYSTEM** or routes to a paper **TICKET**, the comparison module in [src/views/ComparisonView.vue](file:///c:/codes/parking-payment-script/src/views/ComparisonView.vue) validates parsed plate numbers against expected national LTO format regular expressions.

This logic is executed by the `getTicketingRecommendation` and `getTicketingDecision` functions in the frontend. If a plate number fails to match either pattern set, the system flags it as an **Invalid Format** and recommends routing to **TICKET**.

### Motorcycle Plate Formats (Classified as Motorcycle)

| Format Profile | Regex Pattern | Example | Description |
| :--- | :--- | :--- | :--- |
| **LL DDDDD** | `^[A-Z]{2}\d{5}$` | `AB12345` | 2 Letters, 5 Numbers |
| **DDDDD LL** | `^\d{5}[A-Z]{2}$` | `12345AB` | 5 Numbers, 2 Letters |
| **DDD LLL** | `^\d{3}[A-Z]{3}$` | `123ABC` | 3 Numbers, 3 Letters |
| **L DDD LL** | `^[A-Z]\d{3}[A-Z]{2}$` | `A123BC` | 1 Letter, 3 Numbers, 2 Letters |
| **LL DDD L** | `^[A-Z]{2}\d{3}[A-Z]$` | `AB123C` | 2 Letters, 3 Numbers, 1 Letter |
| **D LLL DD** | `^\d[A-Z]{3}\d{2}$` | `1ABC23` | 1 Number, 3 Letters, 2 Numbers |
| **L DDDD L** | `^[A-Z]\d{4}[A-Z]$` | `A1234C` | 1 Letter, 4 Numbers, 1 Letter |
| **L D L DDD** | `^[A-Z]\d[A-Z]\d{3}$` | `A1C234` | 1 Letter, 1 Number, 1 Letter, 3 Numbers |
| **L DD L DD** | `^[A-Z]\d{2}[A-Z]\d{2}$` | `A12C34` | 1 Letter, 2 Numbers, 1 Letter, 2 Numbers |

### Car Plate Formats (Classified as Car)

| Format Profile | Regex Pattern | Example | Description |
| :--- | :--- | :--- | :--- |
| **LLL DDDD** | `^[A-Z]{3}\d{4}$` | `ABC1234` | Standard MV: 3 Letters, 4 Numbers |
| **LLL DDD** | `^[A-Z]{3}\d{3}$` | `WFU799` | Legacy MV: 3 Letters, 3 Numbers |
| **LL DDDD** | `^[A-Z]{2}\d{4}$` | `SE1234` | Electric / Government: 2 Letters, 4 Numbers |
| **L DDDD** | `^[A-Z]\d{4}$` | `A1234` | Legacy Conduction: 1 Letter, 4 Numbers |
| **D11** | `^\d{11}$` | `13010000123` | LTO Temporary MV File Number (11 digits) |
| **D10** | `^\d{10}$` | `1301000123` | LTO Temporary MV File Number (10 digits) |
| **D1-D2** | `^\d{1,2}$` | `16` | Government Protocol Key (1 to 2 digits) |
| **D7** | `^\d{7}$` | `1234567` | Diplomatic Plates (7 digits) |

If a plate matches a motorcycle format but the camera detected it as a car (or vice versa), the system flags a **Type Mismatch** and recommends routing to **TICKET**.

---

## 4. Key Pipeline Features & Optimization

### ⚡ On-Demand Lazy Loading (Zero Memory Overhead)
* **Problem**: Storing and sending base64 images within the live metadata log payload bloated the server-client WebSocket pipe, triggering high latency and causing browser rendering lag.
* **Solution**: Live updates transmit only text-based metadata. When the operator selects a vehicle row in the queue or clicks an action item, the frontend emits a socket event `get_detection_images` to request base64 captures.

### ⏱️ Debouncing Duplicate LPR Events
* **Problem**: Multi-lane layouts or camera retriggers can fire duplicate packets for the same vehicle arrival.
* **Solution**: `camera_ws.py` keeps a rolling time-based sliding window debouncer:
  ```python
  if clean_p in last_processed_events and (now_t - last_processed_events[clean_p]) < 3.0:
      continue
  ```
  Any duplicate plate number detected within **3.0 seconds** of its first detection is automatically dropped, preventing identical cards from stacking in the queue.

### 🎛️ Exclude UNKNOWN Filter
* **Problem**: Failed plate reads register as `"UNKNOWN"`, which visual noise is included in statistics calculations.
* **Solution**: Added a toggle switch to **Exclude UNKNOWN** in the filters bar. Activating this strips out any plates matching `"UNKNOWN"` from both the UI tables and the KPI statistics cards.

---

## 4. Directory & File Mapping

* [scripts/config.py](file:///c:/codes/parking-payment-script/scripts/config.py): Contains global settings, API endpoints, tokens, and active exit gate lists.
* [scripts/state.py](file:///c:/codes/parking-payment-script/scripts/state.py): Reconciles inputs using the truth table, tracks connected terminals, and saves log structures.
* [scripts/camera_ws.py](file:///c:/codes/parking-payment-script/scripts/camera_ws.py): Manages WebSocket connections to the camera feed and applies the LPR event debouncer.
* [src/views/ComparisonView.vue](file:///c:/codes/parking-payment-script/src/views/ComparisonView.vue): Web UI dashboard displaying reconciliation stats, Excel export, and the UNKNOWN filter controls.
* [src/views/TestingView.vue](file:///c:/codes/parking-payment-script/src/views/TestingView.vue): Manual camera QA dashboard showing active queues, lazy-loading image previews, and correctness controls.
