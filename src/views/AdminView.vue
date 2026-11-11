<template>
  <div :class="['admin-container', { dark: !isLight }]">
    <header class="admin-header-row">
      <h1 class="page-title">
        <span class="mdi mdi-cogs"></span>
        Simulation Command Center
      </h1>
      <div class="launcher-actions">
        <button
          type="button"
          class="btn-launcher btn-theme-toggle"
          :aria-pressed="!isLight"
          :title="isLight ? 'Switch to dark mode' : 'Switch to light mode'"
          @click="toggleTheme"
        >
          <span :class="['mdi', isLight ? 'mdi-weather-night' : 'mdi-weather-sunny']"></span>
          {{ isLight ? 'Dark' : 'Light' }}
        </button>
        <router-link to="/comparison" class="btn-launcher btn-comparison-launcher">
          <span class="mdi mdi-table-eye"></span> Data Comparison
        </router-link>
        <router-link to="/testing" class="btn-launcher btn-testing-launcher">
          <span class="mdi mdi-check-decagram"></span> Verification Page
        </router-link>
      </div>
    </header>

    <!-- Row 1: settings beside the terminal/camera map -->
    <section class="top-row">
      <SimulationSettings
        :config="config"
        @toggle-camera-auto-exit-only="toggleCameraAutoExitOnly"
        @toggle-real-device-payment="toggleRealDevicePayment"
        @toggle-automatic-payment="toggleAutomaticPayment"
        @toggle-split-exit-layout="toggleSplitExitLayout"
        @toggle-exit-rows-right-aligned="toggleExitRowsRightAligned"
        @save-timers="saveTimers"
      />

      <div class="stack">
        <ServerSettings :socket="socket" :servers="servers" />

        <div class="live-actions-card">
          <div class="card-header-with-status">
            <h2>
              <span class="mdi mdi-database-sync heading-icon"></span>
              Live Database Actions
            </h2>
            <span class="db-badge">
              <span class="db-dot"></span> ACTIVE ({{ apiPort }})
            </span>
          </div>
          <p class="card-subtitle">Trigger operations on active and paid vehicles in the live database.</p>

          <div class="actions-list">
            <div class="action-item-card" :class="{ active: isSyncing }">
              <div class="action-item-icon-wrapper sync-icon-bg">
                <span class="mdi" :class="isSyncing ? 'mdi-sync mdi-spin' : 'mdi-database-refresh'"></span>
              </div>
              <div class="action-item-details">
                <span class="action-item-title">Sync Parked Vehicles</span>
                <span class="action-item-desc">Fetch and process latest active records from database.</span>
              </div>
              <button class="btn-premium btn-premium-sync" @click="syncParkedVehicles" :disabled="isSyncing">
                {{ isSyncing ? 'Syncing...' : 'Sync Now' }}
              </button>
            </div>

            <div class="action-item-card" :class="{ active: isExitingPaid }">
              <div class="action-item-icon-wrapper exit-icon-bg">
                <span class="mdi" :class="isExitingPaid ? 'mdi-logout-variant mdi-spin' : 'mdi-logout-variant'"></span>
              </div>
              <div class="action-item-details">
                <span class="action-item-title">Exit Paid Vehicles</span>
                <span class="action-item-desc">Raise gates for all fully paid license plates.</span>
              </div>
              <button class="btn-premium btn-premium-exit" @click="exitAllPaid" :disabled="isExitingPaid || isSyncing">
                {{ isExitingPaid ? 'Exiting...' : 'Exit All' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <TerminalSettings
        class="terminals-panel"
        :socket="socket"
        :terminals="terminals"
        :unregistered-cameras="unregisteredCameras"
        @notify="showToast"
      />
    </section>

    <!-- Row 2: engine logs beside the payment (teller) service -->
    <section class="bottom-row">
      <LogConsole :logs="logs" :app-port="servers.app_port" @clear-logs="clearLogs" />
      <TellerStatus :teller-port="servers.teller_port" />
    </section>

    <div v-if="toast" class="toast" role="status">{{ toast }}</div>
    <TokenPrompt :socket="socket" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'
import TokenPrompt from '@/components/TokenPrompt.vue'
import LogConsole from '@/components/LogConsole.vue'
import TellerStatus from '@/components/TellerStatus.vue'
import SimulationSettings from '@/components/SimulationSettings.vue'
import ServerSettings from '@/components/ServerSettings.vue'
import TerminalSettings from '@/components/TerminalSettings.vue'
import { useTheme } from '@/composables/useTheme'

const { isLight, toggleTheme } = useTheme()

const socket = io(import.meta.env.DEV ? `http://${window.location.hostname}:${import.meta.env.VITE_WS_PORT || '5015'}` : window.location.origin)

// Server addresses come from the backend config (servers section, editable in the Server Connection card)
const servers = ref({})
const apiPort = computed(() => {
  try {
    const parsed = new URL(servers.value.api_base_url)
    return parsed.port || (parsed.protocol === 'https:' ? '443' : '80')
  } catch {
    return '—'
  }
})

let lastRegisteredSocketId = null
const registerTerminal = () => {
  if (!socket.connected) return
  if (socket.id === lastRegisteredSocketId) return
  socket.emit('register_terminal', { role: 'admin', gate: 0 })
  lastRegisteredSocketId = socket.id
}

const config = reactive({ pay_delay_seconds: 60, exit_delay_seconds: 20, camera_auto_exit_only: true, real_device_payment: false, enable_automatic_payment: true, teller_process_delay_seconds: 2, teller_cooldown_seconds: 3, split_exit_layout: true, exit_rows_right_aligned: true })

const terminals = ref([])
const unregisteredCameras = ref([])

const toast = ref('')
const logs = ref([])
const isSyncing = ref(false)
const isExitingPaid = ref(false)

const showToast = (msg) => {
  toast.value = msg
  setTimeout(() => toast.value = '', 3000)
}

const saveTimers = () => {
  socket.emit('admin_update_config', {
    pay: config.pay_delay_seconds,
    exit: config.exit_delay_seconds,
    camera_auto_exit_only: config.camera_auto_exit_only,
    real_device_payment: config.real_device_payment,
    enable_automatic_payment: config.enable_automatic_payment,
    teller_process_delay: config.teller_process_delay_seconds,
    teller_cooldown: config.teller_cooldown_seconds,
    split_exit_layout: config.split_exit_layout,
    exit_rows_right_aligned: config.exit_rows_right_aligned
  })
  showToast('Settings successfully synced globally.')
}

const toggleCameraAutoExitOnly = () => {
  config.camera_auto_exit_only = !config.camera_auto_exit_only
  saveTimers()
}

const toggleRealDevicePayment = () => {
  config.real_device_payment = !config.real_device_payment
  saveTimers()
}

const toggleAutomaticPayment = () => {
  config.enable_automatic_payment = !config.enable_automatic_payment
  saveTimers()
}

const toggleSplitExitLayout = () => {
  config.split_exit_layout = !config.split_exit_layout
  saveTimers()
}

const toggleExitRowsRightAligned = () => {
  config.exit_rows_right_aligned = !config.exit_rows_right_aligned
  saveTimers()
}

const syncParkedVehicles = () => {
  if (isSyncing.value) return
  isSyncing.value = true
  socket.emit('admin_sync_parked_vehicles')
  showToast('Parked vehicles sync process started.')
}

const exitAllPaid = () => {
  if (isExitingPaid.value) return
  isExitingPaid.value = true
  socket.emit('admin_exit_all_paid')
  showToast('Exit sequence for paid vehicles started.')
}

const clearLogs = () => {
  logs.value = []
}

onMounted(() => {
  socket.on('connect', () => {
    registerTerminal()
  })

  if (socket.connected) {
    registerTerminal()
  }

  socket.on('config_sync', (newConfig) => {
    config.pay_delay_seconds = newConfig.pay_delay_seconds
    config.exit_delay_seconds = newConfig.exit_delay_seconds
    config.camera_auto_exit_only = newConfig.camera_auto_exit_only !== false
    config.real_device_payment = newConfig.real_device_payment === true
    config.enable_automatic_payment = newConfig.enable_automatic_payment !== false
    config.teller_process_delay_seconds = newConfig.teller_process_delay_seconds || 2
    config.teller_cooldown_seconds = newConfig.teller_cooldown_seconds || 3
    config.split_exit_layout = newConfig.split_exit_layout !== false
    config.exit_rows_right_aligned = newConfig.exit_rows_right_aligned !== false
    servers.value = newConfig.servers || {}
    terminals.value = newConfig.terminals || []
  })

  socket.on('logs_history', (history) => {
    logs.value = history
  })

  socket.on('new_log', (logEntry) => {
    logs.value.push(logEntry)
    if (logs.value.length > 100) {
      logs.value.shift()
    }
  })

  socket.on('admin_sync_complete', (res) => {
    isSyncing.value = false
    if (res.success) {
      showToast('Synchronization of parked vehicles completed!')
    } else {
      showToast('Sync failed: ' + (res.error || 'Unknown error'))
    }
  })

  socket.on('admin_exit_all_paid_complete', (res) => {
    isExitingPaid.value = false
    if (res.success) {
      showToast(`Successfully exited ${res.count} paid vehicles!`)
    } else {
      showToast('Exit failed: ' + (res.error || 'Unknown error'))
    }
  })

  socket.on('unregistered_cameras', (cams) => {
    unregisteredCameras.value = cams || []
  })
})

onUnmounted(() => {
  socket.off('connect')
  socket.off('config_sync')
  socket.off('logs_history')
  socket.off('new_log')
  socket.off('admin_sync_complete')
  socket.off('admin_exit_all_paid_complete')
  socket.off('unregistered_cameras')
})
</script>

<style scoped>
/* Color tokens for this page and its panels. Light is the default; .dark swaps them. */
.admin-container {
  --bg: #eef1f4;
  --surface: #ffffff;
  --surface-2: #f6f8fa;
  --surface-3: #e9edf1;
  --input-bg: #ffffff;
  --border: #d8dde3;
  --border-soft: #e6e9ed;
  --border-strong: #b8c0c9;
  --text: #111827;
  --text-2: #374151;
  --text-muted: #6b7280;
  --text-faint: #9ca3af;
  --console-bg: #f8fafc;
  --console-text: #1f2937;
  --tooltip-bg: #ffffff;
  --code-bg: #f1f3f5;
  --btn-neutral-bg: #e5e8ec;
  --btn-neutral-text: #111827;
  --shadow: 0 1px 3px rgba(16, 24, 40, 0.06), 0 1px 2px rgba(16, 24, 40, 0.04);
  --shadow-pop: 0 8px 24px rgba(16, 24, 40, 0.14);
  /* Accents tuned to stay readable as text on the surface color */
  --c-yellow: #b45309;
  --c-orange: #c2410c;
  --c-cyan: #0e7490;
  --c-sky: #0369a1;
  --c-green: #15803d;
  --c-blue: #1d4ed8;
  --c-purple: #7e22ce;
  --c-violet: #6d28d9;
  --c-red: #b91c1c;
  --c-pink: #be185d;
  --c-rose: #be123c;
  --btn-ok-bg: #15803d;
  color-scheme: light;
}

.admin-container.dark {
  --bg: #111111;
  --surface: #1a1a1a;
  --surface-2: #151515;
  --surface-3: #222222;
  --input-bg: #000000;
  --border: #333333;
  --border-soft: #2a2a2a;
  --border-strong: #444444;
  --text: #f1f1f1;
  --text-2: #dddddd;
  --text-muted: #888888;
  --text-faint: #666666;
  --console-bg: #050505;
  --console-text: #e0e0e0;
  --tooltip-bg: #222222;
  --code-bg: #111111;
  --btn-neutral-bg: #333333;
  --btn-neutral-text: #ffffff;
  --shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  --shadow-pop: 0 4px 15px rgba(0, 0, 0, 0.5);
  --c-yellow: #ffc107;
  --c-orange: #ff9800;
  --c-cyan: #17a2b8;
  --c-sky: #00bcd4;
  --c-green: #28a745;
  --c-blue: #4d9fff;
  --c-purple: #a855f7;
  --c-violet: #9f7aea;
  --c-red: #dc3545;
  --c-pink: #e83e8c;
  --c-rose: #f43f5e;
  --btn-ok-bg: #28a745;
  color-scheme: dark;
}

.admin-container {
  flex: 1;
  background-color: var(--bg);
  color: var(--text);
  padding: 32px 40px 40px;
  overflow-y: auto;
  height: 100%;
  box-sizing: border-box;
}

.admin-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 15px;
}

.page-title {
  color: var(--c-yellow);
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 1.8rem;
}

.launcher-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.btn-launcher {
  text-decoration: none;
  font-size: 0.92rem;
  padding: 9px 16px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-weight: bold;
  font-family: inherit;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.btn-theme-toggle:hover { border-color: var(--border-strong); }
.btn-comparison-launcher { color: var(--c-cyan); }
.btn-comparison-launcher:hover { background: var(--c-cyan); border-color: var(--c-cyan); color: var(--surface); }
.btn-testing-launcher { color: var(--c-purple); }
.btn-testing-launcher:hover { background: var(--c-purple); border-color: var(--c-purple); color: var(--surface); }

/* Row 1: Simulation | Server + Live actions | Terminals & Cameras */
.top-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
  align-items: start;
  margin-bottom: 20px;
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

/* Row 2: Logs | Payment service, equal height */
.bottom-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  align-items: stretch;
}

@media (max-width: 1400px) {
  .top-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .terminals-panel { grid-column: 1 / -1; }
}

@media (max-width: 900px) {
  .admin-container { padding: 20px 16px 32px; }
  .top-row, .bottom-row { grid-template-columns: minmax(0, 1fr); }
}

.toast { position: fixed; bottom: 20px; right: 20px; background: var(--btn-ok-bg); color: #fff; padding: 10px 20px; border-radius: 4px; font-weight: bold; box-shadow: var(--shadow-pop); z-index: 200; }

/* Live database actions card */
.live-actions-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 24px;
  box-sizing: border-box;
  box-shadow: var(--shadow);
}

.card-header-with-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: wrap;
  gap: 10px;
}

.live-actions-card h2 {
  font-size: 1.15rem;
  color: var(--text);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.heading-icon { color: var(--c-orange); }

.db-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--c-green);
  background: rgba(40, 167, 69, 0.1);
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid rgba(40, 167, 69, 0.25);
}

.db-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--c-green);
  animation: db-pulse 1.8s infinite;
}

@keyframes db-pulse {
  0% { transform: scale(0.95); opacity: 1; }
  50% { transform: scale(1.25); opacity: 0.5; }
  100% { transform: scale(0.95); opacity: 1; }
}

.card-subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: 0;
  margin-bottom: 18px;
  line-height: 1.4;
  text-align: left;
}

.actions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-item-card {
  display: flex;
  align-items: center;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  padding: 14px;
  gap: 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.action-item-card:hover { border-color: var(--border-strong); }
.action-item-card.active { border-color: var(--c-orange); }

.action-item-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  font-size: 1.3rem;
  flex-shrink: 0;
}

.sync-icon-bg { background: rgba(23, 162, 184, 0.1); color: var(--c-cyan); border: 1px solid rgba(23, 162, 184, 0.25); }
.exit-icon-bg { background: rgba(40, 167, 69, 0.1); color: var(--c-green); border: 1px solid rgba(40, 167, 69, 0.25); }

.action-item-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-grow: 1;
  min-width: 0;
  text-align: left;
}

.action-item-title { font-size: 0.95rem; font-weight: bold; color: var(--text); }
.action-item-desc { font-size: 0.78rem; color: var(--text-muted); }

.btn-premium {
  border: none;
  padding: 10px 16px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: bold;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: filter 0.2s, transform 0.2s;
  min-width: 100px;
  font-family: inherit;
}

.btn-premium:hover:not(:disabled) { filter: brightness(1.1); transform: translateY(-1px); }
.btn-premium-sync { background: #17a2b8; color: #000; }
.btn-premium-exit { background: var(--btn-ok-bg); color: #fff; }
.btn-premium:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }
</style>
