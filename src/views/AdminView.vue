<template>
  <div class="admin-container">
    <div class="admin-header-row">
      <h1 style="color: #ffc107; display: flex; align-items: center; gap: 10px;">
        <span class="mdi mdi-cogs"></span>
        Simulation Command Center
      </h1>
      <div class="launcher-actions">
        <router-link to="/comparison" class="btn btn-launcher btn-comparison-launcher">
          <span class="mdi mdi-table-eye"></span> Data Comparison
        </router-link>
        <router-link to="/testing" class="btn btn-launcher btn-testing-launcher">
          <span class="mdi mdi-check-decagram"></span> Verification Page
        </router-link>
      </div>
    </div>
    
    <TrackerGrid :stats="stats" />

    <div class="split-layout">
      <!-- Left Column: Console & Teller -->
      <div class="console-column">
        <LogConsole 
          :logs="logs" 
          @clear-logs="clearLogs" 
        />
        <TellerStatus />
      </div>

      <!-- Right Column: Settings & Live Actions -->
      <div class="settings-column">
        <SimulationSettings 
          :config="config" 
          @toggle-camera-auto-exit-only="toggleCameraAutoExitOnly"
          @toggle-real-device-payment="toggleRealDevicePayment"
          @toggle-automatic-payment="toggleAutomaticPayment"
          @save-timers="saveTimers" 
        />

        <!-- LPR Dynamic Camera Mapping Configuration Card -->
        <div class="live-actions-card camera-mapping-card" style="margin-top: 0px;">
          <h2>
            <span class="mdi mdi-ip-network" style="color: #00bcd4;"></span>
            LPR Camera Mappings
          </h2>
          <p class="card-subtitle">Map IP cameras to gates and roles dynamically for multi-gate configuration.</p>

          <!-- Cameras sending detections that are not mapped yet -->
          <div v-if="unregisteredCameras.length" class="unregistered-panel">
            <div class="unregistered-title">
              <span class="mdi mdi-alert-outline"></span>
              Detected but not registered ({{ unregisteredCameras.length }})
            </div>
            <p class="unregistered-hint">These cameras are sending plates that are being ignored. Register them to start using their reads.</p>
            <div v-for="cam in unregisteredCameras" :key="cam.ip" class="unregistered-row">
              <div class="unregistered-info">
                <span class="unregistered-ip">{{ cam.ip }}</span>
                <span class="unregistered-meta">
                  Last plate <strong>{{ cam.last_plate }}</strong> · {{ formatSeen(cam.last_seen) }} · {{ cam.hits }} read{{ cam.hits === 1 ? '' : 's' }}
                  <template v-if="cam.mac"> · MAC {{ cam.mac }}</template>
                </span>
              </div>
              <button class="btn-register" @click="startRegister(cam.ip)">
                <span class="mdi mdi-plus"></span> Register
              </button>
              <button class="btn-dismiss" title="Dismiss" @click="dismissUnregistered(cam.ip)">
                <span class="mdi mdi-close"></span>
              </button>
            </div>
          </div>

          <!-- Add Camera Mapping Form Inline -->
          <div class="mapping-form" :class="{ 'mapping-form-editing': editingIp }" style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; background: rgba(255,255,255,0.02); padding: 12px; border-radius: 6px; border: 1px solid #2a2a2a;">
            <div v-if="editingIp" class="editing-banner">
              <span><span class="mdi mdi-pencil"></span> Editing {{ editingIp }}</span>
              <button class="btn-cancel-edit" @click="resetMappingForm">Cancel</button>
            </div>
            <div class="sub-form-group">
              <label>Camera Name (optional):</label>
              <input ref="nameInput" type="text" v-model="addMappingForm.name" :placeholder="autoCameraLabel(addMappingForm)" class="compact-input" style="height: 38px; padding: 8px 10px; background: #000; border: 1px solid #333; color: #fff; border-radius: 4px; font-size: 0.85rem; width: 100%; box-sizing: border-box;">
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
              <div class="sub-form-group">
                <label>Camera IP Address:</label>
                <input type="text" v-model="addMappingForm.ip" placeholder="e.g. 192.168.0.66" class="compact-input" style="height: 38px; padding: 8px 10px; background: #000; border: 1px solid #333; color: #fff; border-radius: 4px; font-size: 0.85rem; width: 100%; box-sizing: border-box;">
              </div>
              <div class="sub-form-group">
                <label>Gate Number:</label>
                <input type="number" v-model.number="addMappingForm.gate" min="1" class="compact-input" style="height: 38px; padding: 8px 10px; background: #000; border: 1px solid #333; color: #fff; border-radius: 4px; font-size: 0.85rem; width: 100%; box-sizing: border-box;">
              </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
              <div class="sub-form-group">
                <label>Direction:</label>
                <select v-model="addMappingForm.direction" class="compact-input" style="height: 38px; padding: 8px 10px; background: #000; border: 1px solid #333; color: #fff; border-radius: 4px; font-size: 0.85rem; width: 100%; box-sizing: border-box; cursor: pointer;">
                  <option value="entry">Entry Gate</option>
                  <option value="exit">Exit Gate</option>
                </select>
              </div>
              <div class="sub-form-group">
                <label>Camera Role:</label>
                <select v-model="addMappingForm.camera" class="compact-input" style="height: 38px; padding: 8px 10px; background: #000; border: 1px solid #333; color: #fff; border-radius: 4px; font-size: 0.85rem; width: 100%; box-sizing: border-box; cursor: pointer;">
                  <option value="front">Front Camera</option>
                  <option value="back">Back Camera</option>
                </select>
              </div>
            </div>
            
            <button class="btn btn-premium btn-premium-sync w-100" @click="addCameraMapping" style="height: 38px; margin-top: 5px; background: #00bcd4; color: #000; box-shadow: 0 4px 10px rgba(0, 188, 212, 0.2); font-weight: bold; border-radius: 6px; cursor: pointer; border: none; display: flex; align-items: center; justify-content: center; gap: 6px;">
              <span :class="['mdi', editingIp ? 'mdi-content-save' : 'mdi-plus-circle']"></span> {{ editingIp ? 'Save Camera' : 'Add Camera IP' }}
            </button>
          </div>
          
          <!-- Mappings List Table -->
          <div class="mappings-list" style="max-height: 320px; overflow-y: auto;">
            <div v-if="Object.keys(cameraMapping).length === 0" style="text-align: center; color: #666; padding: 20px; font-size: 0.9rem;">
              No cameras mapped yet. Click add to register one.
            </div>
            <table v-else style="width: 100%; border-collapse: collapse; font-size: 0.825rem; text-align: left;">
              <thead>
                <tr style="border-bottom: 1px solid #333; color: #888;">
                  <th style="padding: 6px;">Camera</th>
                  <th style="padding: 6px;">Gate Info</th>
                  <th style="padding: 6px;">Role</th>
                  <th style="padding: 6px; text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="[ip, info] in sortedMappings" :key="ip" :class="{ 'mapping-row-editing': editingIp === ip }" style="border-bottom: 1px solid #222; color: #eee;">
                  <td style="padding: 8px 6px;">
                    <div class="mapping-name">{{ info.name || autoCameraLabel(info) }}</div>
                    <div class="mapping-ip">{{ ip }}</div>
                  </td>
                  <td style="padding: 8px 6px;">
                    <span style="background: rgba(255,255,255,0.06); padding: 2px 5px; border-radius: 3px; font-weight: bold;">Gate {{ info.gate }}</span>
                    <span :style="{
                      background: info.direction === 'entry' ? 'rgba(40,167,69,0.1)' : 'rgba(23,162,184,0.1)',
                      color: info.direction === 'entry' ? '#28a745' : '#17a2b8',
                      marginLeft: '4px',
                      padding: '2px 5px',
                      borderRadius: '3px',
                      fontSize: '0.725rem',
                      fontWeight: 'bold',
                      textTransform: 'uppercase'
                    }">{{ info.direction }}</span>
                  </td>
                  <td style="padding: 8px 6px; text-transform: capitalize;">{{ info.camera }}</td>
                  <td style="padding: 8px 6px; text-align: right; white-space: nowrap;">
                    <button @click="startEdit(ip)" title="Edit" style="background: none; border: none; color: #00bcd4; cursor: pointer; font-size: 1rem; padding: 2px 4px;">
                      <span class="mdi mdi-pencil-outline"></span>
                    </button>
                    <button @click="removeCameraMapping(ip)" title="Remove" style="background: none; border: none; color: #dc3545; cursor: pointer; font-size: 1rem; padding: 2px 4px;">
                      <span class="mdi mdi-delete-outline"></span>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        
        <div class="live-actions-card">
          <div class="card-header-with-status">
            <h2>
              <span class="mdi mdi-database-sync" style="color: #ff9800;"></span>
              Live Database Actions
            </h2>
            <span class="db-badge">
              <span class="db-dot"></span> ACTIVE ({{ apiPort }})
            </span>
          </div>
          <p class="card-subtitle">Trigger operations on active and paid vehicles in the live database.</p>
          
          <div class="actions-list">
            <!-- Sync Action -->
            <div class="action-item-card" :class="{ active: isSyncing }">
              <div class="action-item-icon-wrapper sync-icon-bg">
                <span class="mdi" :class="isSyncing ? 'mdi-sync mdi-spin' : 'mdi-database-refresh'"></span>
              </div>
              <div class="action-item-details">
                <span class="action-item-title">Sync Parked Vehicles</span>
                <span class="action-item-desc">Fetch and process latest active records from database.</span>
              </div>
              <button 
                class="btn-premium btn-premium-sync" 
                @click="syncParkedVehicles" 
                :disabled="isSyncing"
              >
                {{ isSyncing ? 'Syncing...' : 'Sync Now' }}
              </button>
            </div>

            <!-- Exit Action -->
            <div class="action-item-card" :class="{ active: isExitingPaid }">
              <div class="action-item-icon-wrapper exit-icon-bg">
                <span class="mdi" :class="isExitingPaid ? 'mdi-logout-variant mdi-spin' : 'mdi-logout-variant'"></span>
              </div>
              <div class="action-item-details">
                <span class="action-item-title">Exit Paid Vehicles</span>
                <span class="action-item-desc">Raise gates for all fully paid license plates.</span>
              </div>
              <button 
                class="btn-premium btn-premium-exit" 
                @click="exitAllPaid" 
                :disabled="isExitingPaid || isSyncing"
              >
                {{ isExitingPaid ? 'Exiting...' : 'Exit All' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <ApiMetrics :metrics="apiMetrics" @reset-metrics="resetApiMetrics" style="margin-top: 20px;" />

    <div v-if="toast" class="toast">{{ toast }}</div>
    <TokenPrompt :socket="socket" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'
import TokenPrompt from '@/components/TokenPrompt.vue'

// Import Sub-components
import TrackerGrid from '@/components/TrackerGrid.vue'
import LogConsole from '@/components/LogConsole.vue'
import TellerStatus from '@/components/TellerStatus.vue'
import SimulationSettings from '@/components/SimulationSettings.vue'
import ApiMetrics from '@/components/ApiMetrics.vue'

const socket = io(import.meta.env.DEV ? `http://${window.location.hostname}:${import.meta.env.VITE_WS_PORT || '5015'}` : window.location.origin)

const apiPort = computed(() => {
  const url = import.meta.env.VITE_API_BASE_URL || 'http://103.93.223.103:9075'
  try {
    const parsed = new URL(url)
    return parsed.port || '80'
  } catch (e) {
    return '9075'
  }
})

let lastRegisteredSocketId = null
const registerTerminal = () => {
  if (!socket.connected) return
  if (socket.id === lastRegisteredSocketId) return
  socket.emit('register_terminal', { role: 'admin', gate: 0 })
  lastRegisteredSocketId = socket.id
}

const stats = reactive({ queued: 0, parked: 0, paid: 0, exited: 0 })
const config = reactive({ pay_delay_seconds: 60, exit_delay_seconds: 20, camera_auto_exit_only: true, real_device_payment: false, enable_automatic_payment: true, teller_process_delay_seconds: 2, teller_cooldown_seconds: 3 })

const cameraMapping = ref({})
const unregisteredCameras = ref([])
const editingIp = ref(null)
const nameInput = ref(null)
const addMappingForm = reactive({
  ip: '',
  name: '',
  gate: 1,
  direction: 'entry',
  camera: 'front'
})

const capitalize = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : ''

// Readable fallback label, e.g. "Gate 2 Exit Back"
const autoCameraLabel = (info) => `Gate ${info.gate} ${capitalize(info.direction)} ${capitalize(info.camera)}`

// Group mappings by gate, then entry before exit, then front before back
const sortedMappings = computed(() => {
  return Object.entries(cameraMapping.value).sort(([, a], [, b]) => {
    return (a.gate - b.gate) || (a.direction || '').localeCompare(b.direction || '') || (b.camera || '').localeCompare(a.camera || '')
  })
})

const resetMappingForm = () => {
  editingIp.value = null
  addMappingForm.ip = ''
  addMappingForm.name = ''
}

const focusNameInput = () => {
  nameInput.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  nameInput.value?.focus()
}

const startRegister = (ip) => {
  resetMappingForm()
  addMappingForm.ip = ip
  focusNameInput()
}

const startEdit = (ip) => {
  const info = cameraMapping.value[ip]
  editingIp.value = ip
  addMappingForm.ip = ip
  addMappingForm.name = info.name || ''
  addMappingForm.gate = info.gate
  addMappingForm.direction = info.direction
  addMappingForm.camera = info.camera
  focusNameInput()
}

const dismissUnregistered = (ip) => {
  socket.emit('dismiss_unregistered_camera', { ip })
}

const formatSeen = (iso) => {
  if (!iso) return '—'
  const secs = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return new Date(iso).toLocaleTimeString()
}

const addCameraMapping = () => {
  const ip = addMappingForm.ip.trim()
  if (!ip) {
    showToast('IP address cannot be empty.')
    return
  }
  const ipPattern = /^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/
  if (!ipPattern.test(ip)) {
    showToast('Invalid IP address format.')
    return
  }
  if (cameraMapping.value[ip] && ip !== editingIp.value) {
    showToast(`IP address ${ip} is already mapped.`)
    return
  }
  if (editingIp.value && editingIp.value !== ip) {
    delete cameraMapping.value[editingIp.value]
  }
  const entry = {
    gate: addMappingForm.gate,
    direction: addMappingForm.direction,
    camera: addMappingForm.camera
  }
  const name = addMappingForm.name.trim()
  if (name) entry.name = name
  cameraMapping.value[ip] = entry

  const wasEditing = editingIp.value
  saveTimers()
  showToast(wasEditing ? `Updated camera ${name || ip}.` : `Successfully added camera mapping for IP ${ip}!`)
  resetMappingForm()
}

const removeCameraMapping = (ip) => {
  const label = cameraMapping.value[ip]?.name || ip
  if (confirm(`Are you sure you want to remove mapping for ${label}?`)) {
    delete cameraMapping.value[ip]
    if (editingIp.value === ip) resetMappingForm()
    saveTimers()
    showToast(`Successfully removed camera mapping for ${label}.`)
  }
}

const toast = ref('')
const logs = ref([])
const apiMetrics = ref([])
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
    camera_mapping: cameraMapping.value
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

const resetApiMetrics = () => {
  socket.emit('reset_api_metrics')
  showToast('Reset API query latency metrics.')
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
    cameraMapping.value = newConfig.camera_mapping || {}
  })

  socket.on('stats_update', (newStats) => {
    stats.queued = newStats.queued
    stats.parked = newStats.parked
    stats.paid = newStats.paid
    stats.exited = newStats.exited
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

  socket.on('api_metrics_update', (data) => {
    apiMetrics.value = data
  })

  socket.on('unregistered_cameras', (cams) => {
    unregisteredCameras.value = cams || []
  })
})

onUnmounted(() => {
  socket.off('connect')
  socket.off('config_sync')
  socket.off('stats_update')
  socket.off('logs_history')
  socket.off('new_log')
  socket.off('admin_sync_complete')
  socket.off('admin_exit_all_paid_complete')
  socket.off('api_metrics_update')
  socket.off('unregistered_cameras')
})
</script>

<style scoped>
.admin-container { flex: 1; background-color: #111; padding: 40px; color: white; overflow-y: auto; height: 100%; box-sizing: border-box;}

/* Unregistered camera alerts */
.unregistered-panel { margin-bottom: 16px; padding: 12px; border-radius: 6px; border: 1px solid rgba(255, 193, 7, 0.35); background: rgba(255, 193, 7, 0.06); }
.unregistered-title { color: #ffc107; font-weight: bold; font-size: 0.9rem; display: flex; align-items: center; gap: 6px; }
.unregistered-hint { color: #999; font-size: 0.78rem; margin: 4px 0 10px; }
.unregistered-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-top: 1px solid rgba(255, 193, 7, 0.15); }
.unregistered-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.unregistered-ip { font-family: monospace; font-size: 0.9rem; color: #fff; }
.unregistered-meta { font-size: 0.75rem; color: #aaa; overflow-wrap: anywhere; }
.unregistered-meta strong { color: #ffc107; font-family: monospace; }
.btn-register { background: #ffc107; color: #000; border: none; border-radius: 4px; padding: 6px 10px; font-weight: bold; font-size: 0.8rem; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.btn-register:hover { background: #ffcd38; }
.btn-dismiss { background: none; border: none; color: #888; cursor: pointer; font-size: 1rem; padding: 2px 4px; }
.btn-dismiss:hover { color: #fff; }

/* Camera mapping names & editing */
.mapping-name { font-weight: bold; color: #eee; }
.mapping-ip { font-family: monospace; font-size: 0.75rem; color: #888; margin-top: 2px; }
.mapping-row-editing { background: rgba(0, 188, 212, 0.08); }
.mapping-form-editing { border-color: rgba(0, 188, 212, 0.5) !important; }
.editing-banner { display: flex; justify-content: space-between; align-items: center; color: #00bcd4; font-size: 0.85rem; font-weight: bold; }
.btn-cancel-edit { background: none; border: 1px solid #444; color: #ccc; border-radius: 4px; padding: 3px 10px; font-size: 0.78rem; cursor: pointer; }
.btn-cancel-edit:hover { border-color: #888; color: #fff; }

.admin-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
  flex-wrap: wrap;
  gap: 15px;
}

.launcher-actions {
  display: flex;
  gap: 12px;
}

.btn-launcher {
  text-decoration: none;
  font-size: 0.95rem;
  padding: 10px 18px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  font-weight: bold;
}

.btn-comparison-launcher {
  background: rgba(23, 162, 184, 0.15);
  color: #17a2b8;
  border-color: rgba(23, 162, 184, 0.3);
}

.btn-comparison-launcher:hover {
  background: #17a2b8;
  color: #111;
}

.btn-testing-launcher {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
  border-color: rgba(168, 85, 247, 0.3);
}

.btn-testing-launcher:hover {
  background: #a855f7;
  color: #fff;
}

.btn-entry-launcher {
  background: rgba(255, 193, 7, 0.15);
  color: #ffc107;
  border-color: rgba(255, 193, 7, 0.3);
}

.btn-entry-launcher:hover {
  background: #ffc107;
  color: #111;
}

.btn-exit-launcher {
  background: rgba(40, 167, 69, 0.15);
  color: #28a745;
  border-color: rgba(40, 167, 69, 0.3);
}

.btn-exit-launcher:hover {
  background: #28a745;
  color: #fff;
}

.split-layout {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  width: 100%;
}

.console-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 2 1 380px;
}

@media (max-width: 1200px) {
  .split-layout > * {
    flex: 1 1 100% !important;
  }
}

.toast { position: fixed; bottom: 20px; right: 20px; background: #28a745; color: white; padding: 10px 20px; border-radius: 4px; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.5); z-index: 200;}

/* Live actions styling */
.settings-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1 1 320px;
}

.live-actions-card {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 25px;
  box-sizing: border-box;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  transition: border-color 0.3s ease;
}

.live-actions-card:hover {
  border-color: #444;
}

.card-header-with-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 10px;
}

.live-actions-card h2 {
  font-size: 1.2rem;
  color: #ff9800;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.db-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: bold;
  color: #28a745;
  background: rgba(40, 167, 69, 0.1);
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid rgba(40, 167, 69, 0.2);
}

.db-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #28a745;
  box-shadow: 0 0 8px #28a745;
  animation: db-pulse 1.8s infinite;
}

@keyframes db-pulse {
  0% { transform: scale(0.95); opacity: 1; }
  50% { transform: scale(1.25); opacity: 0.5; }
  100% { transform: scale(0.95); opacity: 1; }
}

.card-subtitle {
  font-size: 0.85rem;
  color: #888;
  margin-top: 0;
  margin-bottom: 20px;
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
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 14px;
  gap: 14px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.action-item-card:hover {
  border-color: #444;
  background: rgba(255, 255, 255, 0.04);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.action-item-card.active {
  border-color: #ff9800;
  background: rgba(255, 152, 0, 0.02);
}

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

.sync-icon-bg {
  background: rgba(23, 162, 184, 0.1);
  color: #17a2b8;
  border: 1px solid rgba(23, 162, 184, 0.2);
}

.exit-icon-bg {
  background: rgba(40, 167, 69, 0.1);
  color: #28a745;
  border: 1px solid rgba(40, 167, 69, 0.2);
}

.action-item-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-grow: 1;
  text-align: left;
}

.action-item-title {
  font-size: 0.95rem;
  font-weight: bold;
  color: #eee;
}

.action-item-desc {
  font-size: 0.78rem;
  color: #777;
}

.btn-premium {
  border: none;
  padding: 10px 18px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: bold;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 105px;
}

.btn-premium:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn-premium:active:not(:disabled) {
  transform: translateY(0);
}

.btn-premium-sync {
  background: #17a2b8;
  color: #000;
  box-shadow: 0 4px 10px rgba(23, 162, 184, 0.2);
}

.btn-premium-sync:hover:not(:disabled) {
  background: #1bc3dd;
  box-shadow: 0 4px 14px rgba(23, 162, 184, 0.4);
}

.btn-premium-exit {
  background: #28a745;
  color: #fff;
  box-shadow: 0 4px 10px rgba(40, 167, 69, 0.2);
}

.btn-premium-exit:hover:not(:disabled) {
  background: #2ebd4e;
  box-shadow: 0 4px 14px rgba(40, 167, 69, 0.4);
}

.btn-premium:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  transform: none !important;
  box-shadow: none !important;
}
</style>