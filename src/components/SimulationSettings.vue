<template>
  <div class="admin-card settings-card">
    <h2>Simulation Settings</h2>
    <p>Control the master clock and operational engine modes.</p>

    <!-- Settings Switch Panel -->
    <div class="settings-panel">
      <!-- Auto-Exit -->
      <div class="settings-row" :class="{ 'auto-exit-active': config.camera_auto_exit_only }">
        <div class="settings-info">
          <span class="label-with-info">
            Auto-Exit Mode:
            <div class="tooltip-container">
              <span class="mdi mdi-information-outline info-icon"></span>
              <div class="tooltip-content">
                <p class="tooltip-title">Auto-Exit Mode</p>
                <p><strong></strong> Payment still happens automatically after entry. When enabled, the exit gate animation is also triggered automatically by the camera detecting the car leave — no extra configuration needed.</p>
                <p class="tech-tooltip"><strong>Technical:</strong> Controls <code>camera_auto_exit_only</code>. Payment runs normally via <code>process_camera_vehicle</code>. When ON, exit WebSocket broadcast events from the LPR camera directly trigger <code>play_exit</code> and update stats, instead of requiring a manual simulation exit event.</p>
              </div>
            </div>
          </span>
          <span class="settings-subtext">{{ config.camera_auto_exit_only ? 'Auto-Exit Camera On' : 'Auto-Exit Camera Off' }}</span>
        </div>
        <label class="switch">
          <input type="checkbox" :checked="config.camera_auto_exit_only" @change="emit('toggle-camera-auto-exit-only')">
          <span class="slider round"></span>
        </label>
      </div>

      <!-- Real Device Payment Mode -->
      <div class="settings-row" :class="{ 'real-device-active': config.real_device_payment }">
        <div class="settings-info">
          <span class="label-with-info">
            Real Device Payment Mode:
            <div class="tooltip-container">
              <span class="mdi mdi-information-outline info-icon"></span>
              <div class="tooltip-content">
                <p class="tooltip-title">Real Device Payment Mode</p>
                <p><strong></strong> Routes payments through a physical teller terminal device registered with the system, instead of clearing them automatically.</p>
                <p class="tech-tooltip"><strong>Technical:</strong> Controls <code>real_device_payment</code>. When enabled, the payment script calls the teller script's <code>/add-to-queue</code> endpoint at <code>http://localhost:5010</code> and polls the backend database until the payment is cleared by the device.</p>
              </div>
            </div>
          </span>
          <span class="settings-subtext">{{ config.real_device_payment ? 'Real Device Payment On' : 'Automatic Payment On' }}</span>
        </div>
        <label class="switch">
          <input type="checkbox" :checked="config.real_device_payment" @change="emit('toggle-real-device-payment')">
          <span class="slider round"></span>
        </label>
      </div>

      <!-- Real Device Timing Sub-settings -->
      <div v-if="config.real_device_payment" class="real-device-sub-settings">
        <div class="sub-form-group">
          <label>Teller Scan Delay (s):</label>
          <input type="number" v-model="config.teller_process_delay_seconds" min="0" class="compact-input">
        </div>
        <div class="sub-form-group">
          <label>Teller Queue Cooldown (s):</label>
          <input type="number" v-model="config.teller_cooldown_seconds" min="0" class="compact-input">
        </div>
      </div>
      <!-- Automatic Payment Mode -->
      <div class="settings-row" :class="{ 'auto-pay-active': config.enable_automatic_payment }">
        <div class="settings-info">
          <span class="label-with-info">
            Automatic Payment Mode:
            <div class="tooltip-container">
              <span class="mdi mdi-information-outline info-icon"></span>
              <div class="tooltip-content">
                <p class="tooltip-title">Automatic Payment Mode</p>
                <p><strong></strong> Automatically processes payments for vehicles (when real device payment is off).</p>
                <p class="tech-tooltip"><strong>Technical:</strong> Controls <code>enable_automatic_payment</code>. When disabled, automatic payments are skipped entirely.</p>
              </div>
            </div>
          </span>
          <span class="settings-subtext">{{ config.enable_automatic_payment ? 'Auto-Pay On' : 'Auto-Pay Off' }}</span>
        </div>
        <label class="switch">
          <input type="checkbox" :checked="config.enable_automatic_payment" @change="emit('toggle-automatic-payment')">
          <span class="slider round"></span>
        </label>
      </div>
    </div>
    
    <!-- Timer Settings -->

    <div class="form-group">
      <label class="label-with-info">
        Time until Payment API fires:
        <div class="tooltip-container">
          <span class="mdi mdi-information-outline info-icon"></span>
          <div class="tooltip-content">
            <p class="tooltip-title">Payment API Delay</p>
            <p><strong></strong> The delay (in seconds) after entry before the system automatically queries the bill and executes payment (in automated simulation mode).</p>
            <p class="tech-tooltip"><strong>Technical:</strong> Controls <code>pay_delay_seconds</code>. The sleep interval between receiving an entry LPR camera event and firing the billing API request.</p>
          </div>
        </div>
      </label>
      <input type="number" v-model="config.pay_delay_seconds">
    </div>

    <div class="form-group">
      <label class="label-with-info">
        Time until Exit Animation (After Pay):
        <div class="tooltip-container">
          <span class="mdi mdi-information-outline info-icon"></span>
          <div class="tooltip-content">
            <p class="tooltip-title">Exit Animation Delay</p>
            <p><strong></strong> The delay (in seconds) between clearing a vehicle's payment and triggering the exit animation at the gate.</p>
            <p class="tech-tooltip"><strong>Technical:</strong> Controls <code>exit_delay_seconds</code>. The sleep interval between registering a successful payment and emitting the <code>play_exit</code> animation event.</p>
          </div>
        </div>
      </label>
      <input type="number" v-model="config.exit_delay_seconds">
    </div>
    
    <button class="btn btn-success w-100" @click="emit('save-timers')">
      <span class="mdi mdi-content-save-cog"></span> Sync Settings to Engine
    </button>
  </div>
</template>

<script setup>
defineProps({
  config: {
    type: Object,
    required: true
  }
})

const emit = defineEmits([
  'toggle-camera-auto-exit-only',
  'toggle-real-device-payment',
  'toggle-automatic-payment',
  'save-timers'
])
</script>

<style scoped>
.settings-card { flex: 1 1 300px; }
.admin-card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 25px; box-sizing: border-box; }

/* Settings Switch Panel */
.settings-panel {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid #333;
  border-radius: 6px;
  padding: 10px 15px;
  margin-bottom: 25px;
}

.settings-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid #2a2a2a;
}

.settings-row:last-of-type {
  border-bottom: none;
}

.settings-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-subtext {
  font-size: 0.78rem;
  color: #666;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  transition: color 0.3s ease;
}

/* Color codes when toggles are active */
.mock-active .settings-subtext {
  color: #ffe082;
}
.camera-active .settings-subtext {
  color: #a5d6a7;
}
.endless-active .settings-subtext {
  color: #ffe082;
}
.auto-exit-active .settings-subtext {
  color: #9eccff;
}
.real-device-active .settings-subtext {
  color: #d1c4e9;
}

.label-with-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.9rem;
  font-weight: 500;
  color: #ddd;
}

/* Slide Switch Styling */
.switch {
  position: relative;
  display: inline-block;
  width: 46px;
  height: 24px;
  flex-shrink: 0;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #2c2c2c;
  transition: .25s ease-in-out;
  border: 1px solid #444;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: #888;
  transition: .25s ease-in-out;
  box-shadow: 0 2px 4px rgba(0,0,0,0.4);
}

input:checked + .slider {
  background-color: #333;
}

input:checked + .slider:before {
  background-color: white;
  transform: translateX(22px);
}

/* Custom slider accents for active states */
.mock-active input:checked + .slider {
  background-color: rgba(255, 193, 7, 0.2);
  border-color: #ffc107;
}
.mock-active input:checked + .slider:before {
  background-color: #ffc107;
}

.camera-active input:checked + .slider {
  background-color: rgba(40, 167, 69, 0.2);
  border-color: #28a745;
}
.camera-active input:checked + .slider:before {
  background-color: #28a745;
}

.endless-active input:checked + .slider {
  background-color: rgba(255, 193, 7, 0.2);
  border-color: #ffc107;
}
.endless-active input:checked + .slider:before {
  background-color: #ffc107;
}

.auto-exit-active input:checked + .slider {
  background-color: rgba(0, 123, 255, 0.2);
  border-color: #007bff;
}
.auto-exit-active input:checked + .slider:before {
  background-color: #007bff;
}

.auto-pay-active input:checked + .slider {
  background-color: rgba(0, 123, 255, 0.2);
  border-color: #007bff;
}
.auto-pay-active input:checked + .slider:before {
  background-color: #007bff;
}

.real-device-active input:checked + .slider {
  background-color: rgba(111, 66, 193, 0.2);
  border-color: #6f42c1;
}
.real-device-active input:checked + .slider:before {
  background-color: #6f42c1;
}

.slider.round {
  border-radius: 24px;
}

.slider.round:before {
  border-radius: 50%;
}

.real-device-sub-settings {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  padding: 14px 0 6px 0;
  border-bottom: 1px solid #2a2a2a;
}
.sub-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sub-form-group label {
  font-size: 0.78rem;
  color: #888;
}
.compact-input {
  padding: 8px 10px !important;
  background: #000 !important;
  border: 1px solid #333 !important;
  color: #fff !important;
  border-radius: 4px !important;
  font-size: 0.85rem !important;
  width: 100%;
  box-sizing: border-box;
}
.compact-input:focus {
  border-color: #6f42c1 !important;
}

.disabled-row {
  opacity: 0.45;
  pointer-events: none;
  filter: grayscale(80%);
}

.form-group { margin-bottom: 15px; }
label { display: block; font-size: 0.85rem; color: #888; margin-bottom: 5px; }
input { width: 100%; padding: 10px; background: #000; border: 1px solid #333; color: #fff; border-radius: 4px; box-sizing: border-box; }
input:focus { outline: none; border-color: #007bff; }
.btn { border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; color: white; font-size: 1rem; transition: filter 0.2s;}
.btn:hover { filter: brightness(1.2); }
.btn-success { background: #28a745; width: 100%; }

/* Beautiful Tooltips */
.tooltip-container {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.info-icon {
  color: #666;
  font-size: 0.95rem;
  cursor: pointer;
  transition: color 0.2s;
  display: inline-block;
  line-height: 1;
}
.info-icon:hover {
  color: #ffc107;
}
.tooltip-content {
  visibility: hidden;
  width: 280px;
  background-color: #222;
  color: #fff;
  text-align: left;
  border-radius: 6px;
  padding: 12px;
  position: absolute;
  z-index: 100;
  bottom: 125%; /* Position above the icon */
  left: 50%;
  transform: translateX(-50%);
  opacity: 0;
  transition: opacity 0.2s, visibility 0.2s;
  box-shadow: 0 4px 15px rgba(0,0,0,0.5);
  border: 1px solid #444;
  font-size: 0.75rem;
  line-height: 1.4;
  pointer-events: none;
}
.tooltip-content p {
  margin: 0 0 6px 0;
}
.tooltip-content p:last-child {
  margin-bottom: 0;
}
.tooltip-title {
  font-weight: bold;
  color: #ffc107;
  font-size: 0.8rem;
  border-bottom: 1px solid #333;
  padding-bottom: 4px;
  margin-bottom: 8px !important;
}
.tech-tooltip {
  color: #aaa;
  margin-top: 6px;
  border-top: 1px dashed #444;
  padding-top: 6px;
}
.tooltip-container:hover .tooltip-content {
  visibility: visible;
  opacity: 1;
}
.tooltip-content::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  margin-left: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: #222 transparent transparent transparent;
}
code {
  background: #111;
  padding: 1px 4px;
  border-radius: 3px;
  font-family: Consolas, monospace;
  color: #ffc107;
}
</style>
