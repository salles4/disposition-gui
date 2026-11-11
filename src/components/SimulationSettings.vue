<template>
  <div class="admin-card settings-card">
    <h2><span class="mdi mdi-tune-variant heading-icon"></span> Simulation Settings</h2>
    <p class="card-subtitle">Control the master clock and operational engine modes.</p>

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

      <!-- Disposition Table Layout -->
      <div class="settings-row" :class="{ 'split-exit-active': config.split_exit_layout }">
        <div class="settings-info">
          <span class="label-with-info">
            Split Exit Layout:
            <div class="tooltip-container">
              <span class="mdi mdi-information-outline info-icon"></span>
              <div class="tooltip-content">
                <p class="tooltip-title">Split Exit Layout</p>
                <p><strong></strong> On the Disposition table, shows entry plates in a left column and exit plates in a separate right column. When off, there is a single plate column and every row is left-aligned.</p>
                <p class="tech-tooltip"><strong>Technical:</strong> Controls <code>split_exit_layout</code>. Display only; applies live to every open Disposition page.</p>
              </div>
            </div>
          </span>
          <span class="settings-subtext">{{ config.split_exit_layout ? 'Entry Left / Exit Right' : 'Single Plate Column' }}</span>
        </div>
        <label class="switch">
          <input type="checkbox" :checked="config.split_exit_layout" @change="emit('toggle-split-exit-layout')">
          <span class="slider round"></span>
        </label>
      </div>

      <!-- Split Exit Layout sub-option -->
      <div v-if="config.split_exit_layout" class="settings-row sub-settings-row" :class="{ 'split-exit-active': config.exit_rows_right_aligned }">
        <div class="settings-info">
          <span class="label-with-info">
            Right-Align Exit Rows:
            <div class="tooltip-container">
              <span class="mdi mdi-information-outline info-icon"></span>
              <div class="tooltip-content">
                <p class="tooltip-title">Right-Align Exit Rows</p>
                <p><strong></strong> When on, exit rows are aligned to the right so they read toward the Exit Plate Key column. When off, the columns stay split but every row keeps the normal left alignment.</p>
                <p class="tech-tooltip"><strong>Technical:</strong> Controls <code>exit_rows_right_aligned</code>. Only applies while Split Exit Layout is on.</p>
              </div>
            </div>
          </span>
          <span class="settings-subtext">{{ config.exit_rows_right_aligned ? 'Exit Rows Right' : 'All Rows Left' }}</span>
        </div>
        <label class="switch">
          <input type="checkbox" :checked="config.exit_rows_right_aligned" @change="emit('toggle-exit-rows-right-aligned')">
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
  'toggle-split-exit-layout',
  'toggle-exit-rows-right-aligned',
  'save-timers'
])
</script>

<style scoped>
.admin-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 24px; box-sizing: border-box; box-shadow: var(--shadow); min-width: 0; }
.admin-card h2 { font-size: 1.15rem; color: var(--text); margin: 0 0 6px; display: flex; align-items: center; gap: 8px; }
.heading-icon { color: var(--c-blue); }
.card-subtitle { font-size: 0.85rem; color: var(--text-muted); margin: 0 0 18px; line-height: 1.4; }

/* Settings Switch Panel */
.settings-panel {
  display: flex;
  flex-direction: column;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 6px 15px;
  margin-bottom: 22px;
}

.settings-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 13px 0;
  border-bottom: 1px solid var(--border-soft);
}

.settings-row:last-of-type { border-bottom: none; }

/* Indented option that belongs to the row above it */
.sub-settings-row {
  padding: 10px 0 10px 16px;
  border-left: 2px solid var(--border);
  margin-left: 4px;
}
.sub-settings-row .label-with-info { font-size: 0.85rem; }

.settings-info { display: flex; flex-direction: column; gap: 4px; }

.settings-subtext {
  font-size: 0.75rem;
  color: var(--text-faint);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  transition: color 0.3s ease;
}

/* Color codes when toggles are active */
.auto-exit-active .settings-subtext,
.auto-pay-active .settings-subtext { color: var(--c-blue); }
.real-device-active .settings-subtext { color: var(--c-violet); }
.split-exit-active .settings-subtext { color: var(--c-cyan); }

.label-with-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-2);
}

/* Slide Switch Styling */
.switch { position: relative; display: inline-block; width: 46px; height: 24px; flex-shrink: 0; }
.switch input { opacity: 0; width: 0; height: 0; }

.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: var(--surface-3);
  transition: .25s ease-in-out;
  border: 1px solid var(--border-strong);
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: var(--text-faint);
  transition: .25s ease-in-out;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

input:checked + .slider:before { background-color: #fff; transform: translateX(22px); }
input:focus-visible + .slider { outline: 2px solid var(--c-blue); outline-offset: 2px; }

/* Accent per switch when on */
.auto-exit-active input:checked + .slider,
.auto-pay-active input:checked + .slider { background-color: #2563eb; border-color: #2563eb; }
.split-exit-active input:checked + .slider { background-color: #0e9fb5; border-color: #0e9fb5; }
.real-device-active input:checked + .slider { background-color: #6f42c1; border-color: #6f42c1; }

.slider.round { border-radius: 24px; }
.slider.round:before { border-radius: 50%; }

.real-device-sub-settings {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  padding: 12px 0 8px;
  border-bottom: 1px solid var(--border-soft);
}
.sub-form-group { display: flex; flex-direction: column; gap: 6px; }
.sub-form-group label { font-size: 0.78rem; color: var(--text-muted); margin: 0; }
.compact-input { padding: 8px 10px; font-size: 0.85rem; }
.compact-input:focus { border-color: var(--c-violet); }

.form-group { margin-bottom: 15px; }
label { display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 5px; }
input { width: 100%; padding: 10px; background: var(--input-bg); border: 1px solid var(--border); color: var(--text); border-radius: 4px; box-sizing: border-box; font-family: inherit; }
input:focus { outline: none; border-color: var(--c-blue); }
.btn { border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; color: #fff; font-size: 1rem; transition: filter 0.2s; font-family: inherit; display: inline-flex; align-items: center; justify-content: center; gap: 6px; }
.btn:hover { filter: brightness(1.1); }
.btn-success { background: var(--btn-ok-bg); width: 100%; }

/* Tooltips */
.tooltip-container { position: relative; display: inline-flex; align-items: center; justify-content: center; }
.info-icon { color: var(--text-faint); font-size: 0.95rem; cursor: pointer; transition: color 0.2s; display: inline-block; line-height: 1; }
.info-icon:hover { color: var(--c-yellow); }
.tooltip-content {
  visibility: hidden;
  width: 280px;
  background-color: var(--tooltip-bg);
  color: var(--text);
  text-align: left;
  border-radius: 6px;
  padding: 12px;
  position: absolute;
  z-index: 100;
  bottom: 125%;
  left: 50%;
  transform: translateX(-50%);
  opacity: 0;
  transition: opacity 0.2s, visibility 0.2s;
  box-shadow: var(--shadow-pop);
  border: 1px solid var(--border);
  font-size: 0.75rem;
  font-weight: normal;
  line-height: 1.4;
  pointer-events: none;
}
.tooltip-content p { margin: 0 0 6px 0; }
.tooltip-content p:last-child { margin-bottom: 0; }
.tooltip-title { font-weight: bold; color: var(--c-yellow); font-size: 0.8rem; border-bottom: 1px solid var(--border-soft); padding-bottom: 4px; margin-bottom: 8px !important; }
.tech-tooltip { color: var(--text-muted); margin-top: 6px; border-top: 1px dashed var(--border); padding-top: 6px; }
.tooltip-container:hover .tooltip-content { visibility: visible; opacity: 1; }
.tooltip-content::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  margin-left: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: var(--tooltip-bg) transparent transparent transparent;
}
code { background: var(--code-bg); padding: 1px 4px; border-radius: 3px; font-family: Consolas, monospace; color: var(--c-yellow); }
</style>
