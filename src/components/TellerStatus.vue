<template>
  <div class="admin-card teller-status-card flex-card">
    <div class="status-header">
      <h2>
        <span class="mdi mdi-calculator-variant" style="color: #ffc107; margin-right: 8px;"></span>
        Teller Service Status
      </h2>
      <div class="connection-indicator" :class="{ online: isOnline }">
        <span class="dot"></span>
        <span class="text">{{ isOnline ? `ONLINE (Port ${tellerPort || 5010})` : 'OFFLINE' }}</span>
      </div>
    </div>

    <div class="status-body">
      <!-- Loader or Offline placeholder -->
      <div v-if="!isOnline" class="status-placeholder">
        <span class="mdi mdi-alert-circle-outline offline-icon"></span>
        <p>Unable to connect to Teller Service. Ensure the service is running in your VS Code terminal tab.</p>
        <code class="cmd-snippet">python3.13 scripts/teller_service.py</code>
      </div>

      <div v-else class="status-content">
        <!-- Summary Stats grid -->
        <div class="stats-mini-grid">
          <div class="mini-stat-card">
            <span class="stat-label">Queue Size</span>
            <span class="stat-val text-primary">{{ statusData.queue_size || 0 }}</span>
          </div>
          <div class="mini-stat-card">
            <span class="stat-label">Uptime</span>
            <span class="stat-val text-info">{{ formatUptime(statusData.uptime_seconds) }}</span>
          </div>
          <div class="mini-stat-card">
            <span class="stat-label">Total Revenue</span>
            <span class="stat-val text-success">P{{ (statusData.total_collected || 0).toFixed(2) }}</span>
          </div>
        </div>

        <!-- Connected Terminals -->
        <div class="section-title">
          <span class="mdi mdi-cellphone-link-off" v-if="!statusData.active_terminals?.length"></span>
          <span class="mdi mdi-cellphone-link" v-else></span>
          Connected Devices ({{ statusData.active_terminals?.length || 0 }})
        </div>
        <div v-if="!statusData.active_terminals?.length" class="no-data-placeholder">
          No teller devices currently connected.
        </div>
        <div v-else class="terminals-list">
          <div v-for="term in statusData.active_terminals" :key="term.terminal_id" class="terminal-item" :class="{ offline: !term.is_active }">
            <div class="term-main">
              <span class="term-id">{{ term.terminal_id }}</span>
              <span class="badge" :class="'badge-' + term.status.toLowerCase()">{{ term.status }}</span>
            </div>
            
            <div class="term-details">
              <div class="detail-row">
                <span>Transactions: <strong>{{ term.tx_count }}</strong></span>
                <span v-if="term.latest_telemetry?.app_used_mb">
                  {{ term.is_active ? 'RAM:' : 'Last RAM:' }} <strong>{{ term.latest_telemetry.app_used_mb }}MB</strong>
                  <span class="ram-separator"> | </span>
                  <strong>{{ term.latest_telemetry.device_total_mb - term.latest_telemetry.device_avail_mb }}MB</strong>
                  <span class="ram-limit">/{{ term.latest_telemetry.device_total_mb }}MB</span>
                </span>
              </div>
              <!-- Memory Bar (Other Device RAM + App RAM) -->
              <div v-if="term.latest_telemetry?.app_used_mb" class="ram-bar-container" :class="{ critical: term.latest_telemetry.is_memory_critical }">
                <div class="ram-bar device-bar" :style="{ width: calculateOtherDeviceRamPercentage(term.latest_telemetry) + '%' }"></div>
                <div class="ram-bar app-bar" :style="{ width: calculateAppRamPercentage(term.latest_telemetry) + '%' }"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Live Memory Chart -->
        <div v-if="availableTerminalsForChart.length > 0" class="ram-chart-container">
          <div class="section-title chart-section-title">
            <span style="display: flex; align-items: center; gap: 6px;">
              <span class="mdi mdi-chart-line"></span>
              Memory Usage History
            </span>
            <div class="chart-controls">
              <!-- X-Axis Zoom (points limit) -->
              <div class="chart-tabs limit-tabs">
                <button 
                  v-for="l in [20, 50, 100, 250, 'all']" 
                  :key="l"
                  @click="selectedPointLimit = l" 
                  class="chart-tab-btn" 
                  :class="{ active: selectedPointLimit === l }"
                  :title="'Show last ' + l + ' data points'"
                >
                  {{ l === 'all' ? 'All' : l + 'p' }}
                </button>
              </div>
              <!-- Dataset tabs to select what is scaled on Y-axis -->
              <div class="chart-tabs">
                <button 
                  @click="selectedDataset = 'app'" 
                  class="chart-tab-btn" 
                  :class="{ active: selectedDataset === 'app' }"
                >
                  App
                </button>
                <button 
                  @click="selectedDataset = 'device'" 
                  class="chart-tab-btn" 
                  :class="{ active: selectedDataset === 'device' }"
                >
                  Device
                </button>
              </div>
              <select v-model="selectedTerminalId" class="chart-select" v-if="availableTerminalsForChart.length > 1">
                <option v-for="t in availableTerminalsForChart" :key="t" :value="t">{{ t }}</option>
              </select>
              <button @click="downloadLogs" class="btn-download-logs" title="Download CSV Logs">
                <span class="mdi mdi-download"></span> CSV
              </button>
            </div>
          </div>
          <div class="ram-chart-card">
            <div v-if="filteredRamHistory.length < 2" class="chart-insufficient-data">
              <span class="mdi mdi-information-outline" style="font-size: 1.5rem; color: #555;"></span>
              <span>Awaiting telemetry data for <strong>{{ activeChartTerminal }}</strong> (requires at least 2 logs to graph).</span>
            </div>
            <template v-else>
              <div class="svg-container">
                <span class="y-label top-label">{{ maxMemoryVal }} MB</span>
                <span class="y-label bottom-label">{{ minMemoryVal }} MB</span>
                <svg class="live-chart-svg" viewBox="0 0 500 150" preserveAspectRatio="none">
                  <!-- Grid Lines -->
                  <line x1="0" y1="37.5" x2="500" y2="37.5" stroke="#1c1c1c" stroke-width="1" />
                  <line x1="0" y1="75" x2="500" y2="75" stroke="#1c1c1c" stroke-width="1" />
                  <line x1="0" y1="112.5" x2="500" y2="112.5" stroke="#1c1c1c" stroke-width="1" />

                  <!-- Active Segment Area & Line -->
                  <path :d="activeAreaPath" :fill="activeFillColor" />
                  <path :d="activeLinePath" fill="none" :stroke="activeColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </div>
              <div class="chart-legend">
                <span class="legend-item">
                  <span class="legend-dot" :style="{ backgroundColor: activeColor, boxShadow: '0 0 4px ' + activeColor }"></span>
                  {{ selectedDataset === 'app' ? 'App RAM' : 'Device Used RAM' }}
                </span>
              </div>
            </template>
          </div>
        </div>

        <!-- Active Transactions -->
        <div class="section-title">
          <span class="mdi mdi-sync spin-icon" v-if="statusData.active_transactions?.length"></span>
          <span class="mdi mdi-sync" v-else></span>
          Active Transactions ({{ statusData.active_transactions?.length || 0 }})
        </div>
        <div v-if="!statusData.active_transactions?.length" class="no-data-placeholder">
          No plates currently being processed by tellers.
        </div>
        <div v-else class="transactions-flex">
          <span v-for="plate in statusData.active_transactions" :key="plate" class="plate-tag blinking">
            {{ plate }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  // From the dashboard's Server Connection settings (servers.teller_port)
  tellerPort: { type: [Number, String], default: null }
})
const tellerBase = computed(() => `http://${window.location.hostname}:${props.tellerPort || 5010}`)

const isOnline = ref(false)
const statusData = ref({})
let pollInterval = null

const fetchStatus = async () => {
  try {
    const res = await fetch(`${tellerBase.value}/get-status`)
    if (res.ok) {
      statusData.value = await res.json()
      isOnline.value = true
    } else {
      isOnline.value = false
    }
  } catch {
    isOnline.value = false
  }
}

const formatUptime = (seconds) => {
  if (!seconds) return '00:00:00'
  const h = Math.floor(seconds / 3600).toString().padStart(2, '0')
  const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0')
  const s = Math.floor(seconds % 60).toString().padStart(2, '0')
  return `${h}:${m}:${s}`
}

const calculateAppRamPercentage = (telemetry) => {
  if (!telemetry.device_total_mb || !telemetry.app_used_mb) return 0
  return Math.min(100, Math.max(0, Math.round((telemetry.app_used_mb / telemetry.device_total_mb) * 100)))
}

const calculateOtherDeviceRamPercentage = (telemetry) => {
  if (!telemetry.device_total_mb || telemetry.device_avail_mb === undefined || !telemetry.app_used_mb) return 0
  const otherUsed = Math.max(0, telemetry.device_total_mb - telemetry.device_avail_mb - telemetry.app_used_mb)
  return Math.min(100, Math.max(0, Math.round((otherUsed / telemetry.device_total_mb) * 100)))
}

const selectedTerminalId = ref('')

const availableTerminalsForChart = computed(() => {
  const history = statusData.value.ram_history || []
  const terms = new Set()
  history.forEach(pt => {
    if (pt.terminal_id) terms.add(pt.terminal_id)
  })
  return Array.from(terms)
})

const activeChartTerminal = computed(() => {
  const list = availableTerminalsForChart.value
  if (list.length === 0) return ''
  if (!selectedTerminalId.value || !list.includes(selectedTerminalId.value)) {
    return list[0]
  }
  return selectedTerminalId.value
})

const selectedPointLimit = ref(50) // Default zoom: last 50 points

const filteredRamHistory = computed(() => {
  const termId = activeChartTerminal.value
  const history = statusData.value.ram_history || []
  if (!termId) return []
  const filtered = history.filter(pt => pt.terminal_id === termId)
  const limit = selectedPointLimit.value
  return limit === 'all' ? filtered : filtered.slice(-limit)
})

const selectedDataset = ref('app') // 'app' or 'device'

const activeKey = computed(() => {
  return selectedDataset.value === 'app' ? 'app_used_mb' : 'device_used_mb'
})

const activeColor = computed(() => {
  return selectedDataset.value === 'app' ? '#a855f7' : '#17a2b8'
})

const activeFillColor = computed(() => {
  return selectedDataset.value === 'app' ? 'rgba(168, 85, 247, 0.05)' : 'rgba(23, 162, 184, 0.05)'
})

const minMemoryVal = computed(() => {
  const history = filteredRamHistory.value
  const key = activeKey.value
  if (history.length === 0) return 0
  let minVal = Infinity
  for (const pt of history) {
    const val = pt[key] || 0
    if (val < minVal) minVal = val
  }
  const pad = minVal * 0.02 > 5 ? minVal * 0.02 : 5
  return Math.max(0, Math.floor(minVal - pad))
})

const maxMemoryVal = computed(() => {
  const history = filteredRamHistory.value
  const key = activeKey.value
  if (history.length === 0) return 100
  let maxVal = -Infinity
  for (const pt of history) {
    const val = pt[key] || 0
    if (val > maxVal) maxVal = val
  }
  const pad = maxVal * 0.02 > 5 ? maxVal * 0.02 : 5
  return Math.ceil(maxVal + pad)
})

const activeLinePath = computed(() => {
  const history = filteredRamHistory.value
  if (history.length < 2) return ''
  
  const w = 500
  const h = 150
  const minVal = minMemoryVal.value
  const maxVal = maxMemoryVal.value
  const range = maxVal - minVal || 10
  
  const points = []
  history.forEach((pt, index) => {
    const x = (index / (history.length - 1)) * w
    const yVal = pt[activeKey.value] || 0
    const y = h - ((yVal - minVal) / range) * h
    points.push(`${x.toFixed(1)},${y.toFixed(1)}`)
  })
  
  return `M ${points.join(' L ')}`
})

const activeAreaPath = computed(() => {
  const line = activeLinePath.value
  if (!line) return ''
  const w = 500
  const h = 150
  return `${line} L ${w},${h} L 0,${h} Z`
})

const downloadLogs = () => {
  window.open(`${tellerBase.value}/download-ram-logs`, '_blank')
}

onMounted(() => {
  fetchStatus()
  pollInterval = setInterval(fetchStatus, 2000) // Poll status every 2 seconds
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.flex-card { display: flex; flex-direction: column; }
.teller-status-card { min-height: 300px; flex: 1 1 auto; }
.admin-card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 25px; box-sizing: border-box; }
.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #333;
  padding-bottom: 12px;
  margin-bottom: 15px;
}
.status-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: #ffc107;
  display: flex;
  align-items: center;
}

.connection-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
  font-weight: bold;
  color: #dc3545;
  background: rgba(220, 53, 69, 0.1);
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid rgba(220, 53, 69, 0.2);
}

.connection-indicator.online {
  color: #28a745;
  background: rgba(40, 167, 69, 0.1);
  border-color: rgba(40, 167, 69, 0.2);
}

.connection-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #dc3545;
}

.connection-indicator.online .dot {
  background-color: #28a745;
  box-shadow: 0 0 8px #28a745;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.9); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.6; }
  100% { transform: scale(0.9); opacity: 1; }
}

.status-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 30px 10px;
  color: #888;
}

.offline-icon {
  font-size: 2.5rem;
  color: #dc3545;
  margin-bottom: 10px;
}

.cmd-snippet {
  background: #000;
  color: #ffc107;
  padding: 8px 12px;
  border-radius: 4px;
  font-family: monospace;
  margin-top: 10px;
  border: 1px solid #333;
}

.stats-mini-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.mini-stat-card {
  background: #111;
  border: 1px solid #222;
  border-radius: 6px;
  padding: 10px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 0.75rem;
  color: #777;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-val {
  font-size: 1.1rem;
  font-weight: bold;
}

.text-primary { color: #a855f7; }
.text-info { color: #17a2b8; }
.text-success { color: #28a745; }

.section-title {
  font-size: 0.85rem;
  text-transform: uppercase;
  color: #aaa;
  margin-top: 15px;
  margin-bottom: 10px;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 6px;
  border-left: 2px solid #ffc107;
  padding-left: 6px;
}

.no-data-placeholder {
  background: #111;
  padding: 12px;
  border-radius: 6px;
  color: #555;
  font-size: 0.85rem;
  font-style: italic;
  text-align: center;
}

.terminals-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 150px;
  overflow-y: auto;
  padding-right: 4px;
}

/* Custom Scrollbar for Terminals List */
.terminals-list::-webkit-scrollbar {
  width: 6px;
}
.terminals-list::-webkit-scrollbar-track {
  background: #111;
  border-radius: 3px;
}
.terminals-list::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 3px;
}
.terminals-list::-webkit-scrollbar-thumb:hover {
  background: #444;
}

.terminal-item {
  background: #111;
  border: 1px solid #222;
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.terminal-item.offline {
  opacity: 0.65;
  border-color: #2b2b2b;
  background: #0f0f0f;
}

.term-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.term-id {
  font-family: monospace;
  font-weight: bold;
  font-size: 0.9rem;
}

.badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: bold;
  text-transform: uppercase;
}

.badge-idle { background: #222; color: #aaa; }
.badge-waiting { background: #ffc107; color: #111; }
.badge-success { background: #28a745; color: #fff; }
.badge-failed { background: #dc3545; color: #fff; }
.badge-offline { background: #333; color: #888; }

.term-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8rem;
  color: #888;
}

.detail-row {
  display: flex;
  justify-content: space-between;
}

.ram-limit {
  color: #444;
}

.ram-separator {
  color: #444;
  margin: 0 4px;
}

.ram-bar-container {
  display: flex;
  background: #222;
  height: 4px;
  border-radius: 2px;
  overflow: hidden;
}

.ram-bar {
  height: 100%;
}

.ram-bar.device-bar {
  background: #17a2b8;
}

.ram-bar.app-bar {
  background: #a855f7;
}

.ram-bar-container.critical .ram-bar.device-bar {
  background: #dc3545;
  animation: alarm-pulse 1s infinite alternate;
}

@keyframes alarm-pulse {
  from { opacity: 0.6; }
  to { opacity: 1; }
}

.transactions-flex {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.plate-tag {
  background: #007bff;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-weight: bold;
  font-size: 0.8rem;
}

.plate-tag.blinking {
  animation: text-blink 1.5s ease-in-out infinite;
}

@keyframes text-blink {
  0% { opacity: 0.8; }
  50% { opacity: 0.4; }
  100% { opacity: 0.8; }
}

.spin-icon {
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.ram-chart-container {
  margin-top: 15px;
}

.chart-section-title {
  display: flex !important;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  border-left: 2px solid #ffc107;
  padding-left: 6px;
}

.chart-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart-tabs {
  display: flex;
  background: #222;
  border-radius: 4px;
  padding: 2px;
  border: 1px solid #333;
}

.chart-tab-btn {
  background: transparent;
  border: none;
  color: #888;
  font-size: 0.65rem;
  font-weight: bold;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
}

.chart-tab-btn:hover {
  color: #eee;
}

.chart-tab-btn.active {
  background: #333;
  color: #ffc107;
}

.chart-select {
  background: #222;
  border: 1px solid #333;
  color: #fff;
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}

.chart-select:hover {
  border-color: #ffc107;
}

.btn-download-logs {
  background: #222;
  border: 1px solid #333;
  color: #aaa;
  font-size: 0.7rem;
  font-weight: bold;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s ease;
  text-transform: uppercase;
}

.btn-download-logs:hover {
  background: #333;
  color: #ffc107;
  border-color: #ffc107;
}

.ram-chart-card {
  background: #111;
  border: 1px solid #222;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.svg-container {
  position: relative;
  width: 100%;
}

.y-label {
  position: absolute;
  left: 6px;
  font-size: 0.6rem;
  color: #555;
  background: rgba(13, 13, 13, 0.75);
  padding: 1px 4px;
  border-radius: 2px;
  pointer-events: none;
  z-index: 2;
}

.y-label.top-label {
  top: 6px;
  border: 1px solid rgba(255,255,255,0.03);
}

.y-label.bottom-label {
  bottom: 6px;
  border: 1px solid rgba(255,255,255,0.03);
}

.live-chart-svg {
  width: 100%;
  height: 100px;
  background: #0d0d0d;
  border-radius: 4px;
  border: 1px solid #1a1a1a;
  overflow: visible;
}

.chart-insufficient-data {
  height: 100px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #555;
  font-size: 0.75rem;
  text-align: center;
  background: #0d0d0d;
  border: 1px solid #1a1a1a;
  border-radius: 4px;
  gap: 6px;
  padding: 10px;
}

.chart-insufficient-data strong {
  color: #888;
}

.chart-legend {
  display: flex;
  gap: 12px;
  font-size: 0.7rem;
  justify-content: flex-end;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #888;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>
