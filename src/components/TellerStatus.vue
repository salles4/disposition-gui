<template>
  <div class="admin-card teller-status-card">
    <div class="status-header">
      <h2>
        <span class="mdi mdi-calculator-variant heading-icon"></span>
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
              <span class="mdi mdi-information-outline insufficient-icon"></span>
              <span>Awaiting telemetry data for <strong>{{ activeChartTerminal }}</strong> (requires at least 2 logs to graph).</span>
            </div>
            <template v-else>
              <div class="svg-container">
                <span class="y-label top-label">{{ maxMemoryVal }} MB</span>
                <span class="y-label bottom-label">{{ minMemoryVal }} MB</span>
                <svg class="live-chart-svg" viewBox="0 0 500 150" preserveAspectRatio="none">
                  <!-- Grid Lines -->
                  <line x1="0" y1="37.5" x2="500" y2="37.5" class="grid-line" />
                  <line x1="0" y1="75" x2="500" y2="75" class="grid-line" />
                  <line x1="0" y1="112.5" x2="500" y2="112.5" class="grid-line" />

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
.admin-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 24px; box-sizing: border-box; box-shadow: var(--shadow); min-width: 0; }
.teller-status-card { display: flex; flex-direction: column; min-height: 300px; }
.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--border-soft);
  padding-bottom: 12px;
  margin-bottom: 15px;
}
.status-header h2 {
  margin: 0;
  font-size: 1.15rem;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.heading-icon { color: var(--c-yellow); }

.connection-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
  font-weight: bold;
  color: var(--c-red);
  background: rgba(220, 53, 69, 0.1);
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid rgba(220, 53, 69, 0.25);
}
.connection-indicator.online {
  color: var(--c-green);
  background: rgba(40, 167, 69, 0.1);
  border-color: rgba(40, 167, 69, 0.25);
}
.connection-indicator .dot { width: 8px; height: 8px; border-radius: 50%; background-color: var(--c-red); }
.connection-indicator.online .dot { background-color: var(--c-green); animation: pulse 1.5s infinite; }

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
  color: var(--text-muted);
}
.offline-icon { font-size: 2.5rem; color: var(--c-red); margin-bottom: 10px; }
.cmd-snippet {
  background: var(--code-bg);
  color: var(--c-yellow);
  padding: 8px 12px;
  border-radius: 4px;
  font-family: monospace;
  margin-top: 10px;
  border: 1px solid var(--border);
}

.stats-mini-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px; }
.mini-stat-card {
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 10px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-label { font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.stat-val { font-size: 1.1rem; font-weight: bold; }
.text-primary { color: var(--c-purple); }
.text-info { color: var(--c-cyan); }
.text-success { color: var(--c-green); }

.section-title {
  font-size: 0.82rem;
  text-transform: uppercase;
  color: var(--text-2);
  margin-top: 15px;
  margin-bottom: 10px;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 6px;
  border-left: 2px solid var(--c-yellow);
  padding-left: 6px;
}

.no-data-placeholder {
  background: var(--surface-2);
  padding: 12px;
  border-radius: 6px;
  color: var(--text-faint);
  font-size: 0.85rem;
  font-style: italic;
  text-align: center;
}

.terminals-list { display: flex; flex-direction: column; gap: 10px; max-height: 150px; overflow-y: auto; padding-right: 4px; }
.terminals-list::-webkit-scrollbar { width: 6px; }
.terminals-list::-webkit-scrollbar-track { background: transparent; }
.terminals-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
.terminals-list::-webkit-scrollbar-thumb:hover { background: var(--border-strong); }

.terminal-item {
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.terminal-item.offline { opacity: 0.65; }
.term-main { display: flex; justify-content: space-between; align-items: center; }
.term-id { font-family: monospace; font-weight: bold; font-size: 0.9rem; }

.badge { font-size: 0.7rem; padding: 2px 8px; border-radius: 10px; font-weight: bold; text-transform: uppercase; }
.badge-idle { background: var(--surface-3); color: var(--text-muted); }
.badge-waiting { background: #ffc107; color: #111; }
.badge-success { background: var(--btn-ok-bg); color: #fff; }
.badge-failed { background: #dc3545; color: #fff; }
.badge-offline { background: var(--surface-3); color: var(--text-faint); }

.term-details { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: var(--text-muted); }
.detail-row { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.ram-limit, .ram-separator { color: var(--text-faint); }
.ram-separator { margin: 0 4px; }

.ram-bar-container { display: flex; background: var(--surface-3); height: 4px; border-radius: 2px; overflow: hidden; }
.ram-bar { height: 100%; }
.ram-bar.device-bar { background: #17a2b8; }
.ram-bar.app-bar { background: #a855f7; }
.ram-bar-container.critical .ram-bar.device-bar { background: #dc3545; animation: alarm-pulse 1s infinite alternate; }

@keyframes alarm-pulse {
  from { opacity: 0.6; }
  to { opacity: 1; }
}

.transactions-flex { display: flex; flex-wrap: wrap; gap: 6px; }
.plate-tag { background: #2563eb; color: #fff; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-weight: bold; font-size: 0.8rem; }
.plate-tag.blinking { animation: text-blink 1.5s ease-in-out infinite; }

@keyframes text-blink {
  0% { opacity: 0.85; }
  50% { opacity: 0.45; }
  100% { opacity: 0.85; }
}

.spin-icon { animation: spin 2s linear infinite; }

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.ram-chart-container { margin-top: 15px; }
.chart-section-title { display: flex !important; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; width: 100%; }
.chart-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.chart-tabs { display: flex; background: var(--surface-3); border-radius: 4px; padding: 2px; border: 1px solid var(--border); }
.chart-tab-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 0.65rem;
  font-weight: bold;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
  font-family: inherit;
}
.chart-tab-btn:hover { color: var(--text); }
.chart-tab-btn.active { background: var(--surface); color: var(--c-yellow); box-shadow: var(--shadow); }

.chart-select {
  background: var(--input-bg);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}
.chart-select:hover { border-color: var(--c-yellow); }

.btn-download-logs {
  background: var(--surface-3);
  border: 1px solid var(--border);
  color: var(--text-muted);
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
  font-family: inherit;
}
.btn-download-logs:hover { color: var(--c-yellow); border-color: var(--c-yellow); }

.ram-chart-card {
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.svg-container { position: relative; width: 100%; }
.y-label {
  position: absolute;
  left: 6px;
  font-size: 0.6rem;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border-soft);
  padding: 1px 4px;
  border-radius: 2px;
  pointer-events: none;
  z-index: 2;
}
.y-label.top-label { top: 6px; }
.y-label.bottom-label { bottom: 6px; }
.live-chart-svg {
  width: 100%;
  height: 100px;
  background: var(--console-bg);
  border-radius: 4px;
  border: 1px solid var(--border-soft);
  overflow: visible;
}
.grid-line { stroke: var(--border-soft); stroke-width: 1; }

.chart-insufficient-data {
  height: 100px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-faint);
  font-size: 0.75rem;
  text-align: center;
  background: var(--console-bg);
  border: 1px solid var(--border-soft);
  border-radius: 4px;
  gap: 6px;
  padding: 10px;
}
.insufficient-icon { font-size: 1.5rem; color: var(--text-faint); }
.chart-insufficient-data strong { color: var(--text-muted); }

.chart-legend { display: flex; gap: 12px; font-size: 0.7rem; justify-content: flex-end; }
.legend-item { display: flex; align-items: center; gap: 5px; color: var(--text-muted); }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
</style>
