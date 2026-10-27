<template>
  <div class="testing-container">
    <!-- Header -->
    <div class="testing-header">
      <div class="header-title-section">
        <router-link to="/admin" class="back-link">
          <span class="mdi mdi-arrow-left"></span> Back to Command Center
        </router-link>
        <h1>
          <span class="mdi mdi-shield-check-outline text-purple animate-pulse"></span>
          Manual Camera Verification
        </h1>
      </div>
      <div class="header-badge" :class="{ 'connected': isConnected }">
        <span class="mdi mdi-circle" :class="isConnected ? 'text-green animate-blink' : 'text-red'"></span>
        {{ isConnected ? 'Camera Connected' : 'Camera Disconnected' }}
      </div>
    </div>

    <!-- Main Workspace -->
    <div class="workspace-layout">
      <!-- Active Detection Workspace -->
      <div class="workspace-main">
        <div class="workspace-card">
          <div class="card-header">
            <span class="mdi mdi-focus-field text-purple"></span> Active Verification Desk
            <span v-if="activeDet" class="active-badge">ID: {{ activeDet.id }}</span>
          </div>

          <div class="swipe-container" :class="transitionClass">
            <div v-if="activeDet" class="active-workspace-content">
              <!-- Left Side: Images Panel (65% width) -->
              <div class="images-panel">
                <div class="image-box" style="height: 100%;">
                  <div class="image-toggle-header">
                    <div class="image-label">
                      <span class="mdi" :class="activeView === 'front' ? 'mdi-camera-front' : 'mdi-camera-rear'"></span>
                      Vehicle View ({{ activeView === 'front' ? 'Front' : 'Back' }} - {{ activeImageType === 'vehicle' ? 'Whole' : 'Plate' }})
                    </div>
                    <div class="toggle-buttons" style="display: flex; gap: 8px;">
                      <!-- Camera View Group -->
                      <div class="toggle-group" style="display: flex; gap: 4px;">
                        <button 
                          class="btn-toggle-view" 
                          :class="{ active: activeView === 'front' }"
                          @click="activeView = 'front'"
                          :disabled="!activeDet.plate_image_front && !activeDet.front_vehicle_image"
                        >
                          Front View
                        </button>
                        <button 
                          class="btn-toggle-view" 
                          :class="{ active: activeView === 'back' }"
                          @click="activeView = 'back'"
                          :disabled="!activeDet.plate_image_back && !activeDet.back_vehicle_image"
                        >
                          Back View
                        </button>
                      </div>

                      <!-- Image Mode Group -->
                      <div class="toggle-group" style="display: flex; gap: 4px; border-left: 1px solid rgba(255, 255, 255, 0.15); padding-left: 8px;">
                        <button 
                          class="btn-toggle-view" 
                          :class="{ active: activeImageType === 'vehicle' }"
                          @click="activeImageType = 'vehicle'"
                          :disabled="activeView === 'front' ? !activeDet.front_vehicle_image : !activeDet.back_vehicle_image"
                        >
                          Whole Vehicle
                        </button>
                        <button 
                          class="btn-toggle-view" 
                          :class="{ active: activeImageType === 'plate' }"
                          @click="activeImageType = 'plate'"
                          :disabled="activeView === 'front' ? !activeDet.plate_image_front : !activeDet.plate_image_back"
                        >
                          Plate Crop
                        </button>
                      </div>
                    </div>
                  </div>

                  <div class="image-wrapper single-image-wrapper">
                    <img 
                      v-if="getCurrentImageUrl()" 
                      :src="getCurrentImageUrl()" 
                      alt="Camera Capture" 
                      class="camera-image"
                      @click="openFullscreenImage(getCurrentImageUrl())"
                    />
                    <div v-else class="image-placeholder">
                      <span class="mdi mdi-image-off"></span> No Image Received for Selection
                    </div>
                  </div>
                </div>
              </div>

              <!-- Right Side: Controls and Form (35% width) -->
              <div class="controls-panel-desk">
                <!-- Compact Session Stats -->
                <div class="compact-stats-section">
                  <div class="stats-title-row">
                    <h3>Session Stats</h3>
                    <div class="toggle-not-detected-container">
                      <span class="switch-label">Include Not Detected</span>
                      <label class="switch">
                        <input type="checkbox" v-model="includeNotDetected" />
                        <span class="slider"></span>
                      </label>
                    </div>
                  </div>
                  <div class="compact-stats-grid-box">
                    <div class="compact-stat-card border-purple-compact">
                      <div class="compact-stat-header">
                        <span class="mdi mdi-camera-burst text-purple"></span>
                        <span class="compact-stat-title">Logged</span>
                      </div>
                      <div class="compact-stat-num">{{ recentDetections.length }}</div>
                      <div class="compact-stat-sub">{{ pendingDetectionsCount }} pending</div>
                    </div>

                    <div class="compact-stat-card border-green-compact">
                      <div class="compact-stat-header">
                        <span class="mdi mdi-check-circle-outline text-green"></span>
                        <span class="compact-stat-title">Accuracy</span>
                      </div>
                      <div class="compact-stat-num text-green">{{ accuracyStats.accuracy }}</div>
                      <div class="compact-stat-sub">{{ accuracyStats.correct }}/{{ accuracyStats.total }} ok</div>
                    </div>

                    <div class="compact-stat-card border-red-compact">
                      <div class="compact-stat-header">
                        <span class="mdi mdi-alert-circle-outline text-red"></span>
                        <span class="compact-stat-title">Incorrect</span>
                      </div>
                      <div class="compact-stat-num text-red">{{ accuracyStats.incorrect }}</div>
                      <div class="compact-stat-sub">{{ accuracyStats.errorRate }} rate</div>
                    </div>

                    <div class="compact-stat-card border-cyan-compact">
                      <div class="compact-stat-header">
                        <span class="mdi mdi-car-cog text-cyan"></span>
                        <span class="compact-stat-title">V-Type</span>
                      </div>
                      <div class="compact-stat-num text-cyan">{{ accuracyStats.vtypeMatchRate }}</div>
                      <div class="compact-stat-sub">{{ accuracyStats.vtypeMatches }} matches</div>
                    </div>
                  </div>
                </div>

                <!-- Info Box -->
                <div class="detected-info-panel">
                  <h3>Camera Detection Details</h3>
                  <div class="info-grid">
                    <div class="info-field">
                      <div class="info-label">Timestamp</div>
                      <div class="info-val">{{ activeDet.timestamp }}</div>
                    </div>
                    <div class="info-field">
                      <div class="info-label">Source Gate</div>
                      <div class="info-val text-yellow">{{ activeDet.gate }}</div>
                    </div>
                    <div class="info-field">
                      <div class="info-label">Detected Plate</div>
                      <div class="info-val plate-box">{{ activeDet.plate_no }}</div>
                    </div>
                    <div class="info-field">
                      <div class="info-label">Detected Vehicle Type</div>
                      <div class="info-val">
                        <span class="vtype-badge" :class="'badge-' + activeDet.vehicle_type.toLowerCase()">
                          {{ activeDet.vehicle_type }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Verification Form -->
                <div class="decision-form-panel">
                  <h3>Verify Accuracy</h3>
                  
                  <!-- Decision Buttons (Always shown) -->
                  <div class="accuracy-selection-row">
                    <button 
                      class="btn-decision btn-correct" 
                      :class="{ active: verificationForm.status === 'CORRECT' }"
                      :disabled="verificationForm.status === 'INCORRECT' || verificationForm.status === 'NOT_DETECTED'"
                      @click="setFormStatus('CORRECT', $event)"
                    >
                      <span class="mdi mdi-check-circle"></span> Correct
                    </button>
                    <button 
                      class="btn-decision btn-incorrect" 
                      :class="{ active: verificationForm.status === 'INCORRECT' }"
                      :disabled="verificationForm.status === 'NOT_DETECTED'"
                      @click="setFormStatus('INCORRECT', $event)"
                    >
                      <span class="mdi mdi-close-circle"></span> Incorrect
                    </button>
                    <button 
                      class="btn-decision btn-not-detected" 
                      :class="{ active: verificationForm.status === 'NOT_DETECTED' }"
                      :disabled="verificationForm.status === 'INCORRECT'"
                      @click="setFormStatus('NOT_DETECTED', $event)"
                    >
                      <span class="mdi mdi-eye-off"></span> Not Detected
                    </button>
                  </div>

                  <!-- Edit Inputs (Shown only if Incorrect or Not Detected selected) -->
                  <div v-if="verificationForm.status === 'INCORRECT' || verificationForm.status === 'NOT_DETECTED'" class="incorrect-edit-section">
                    <div class="correction-mode-badge" :class="{ 'badge-warn': verificationForm.status === 'NOT_DETECTED' }">
                      <span class="mdi" :class="verificationForm.status === 'NOT_DETECTED' ? 'mdi-eye-off' : 'mdi-alert-circle-outline'"></span>
                      <span>{{ verificationForm.status === 'NOT_DETECTED' ? 'Not Detected Mode' : 'Input Actual Details' }}</span>
                    </div>
                    <div class="form-row">
                      <div class="form-group">
                        <label>Actual Plate Number</label>
                        <input 
                          type="text" 
                          v-model="verificationForm.actualPlate" 
                          class="input-text plate-input"
                          placeholder="Enter ground truth plate..."
                        />
                      </div>
                      <div class="form-group">
                        <label>Actual Vehicle Type</label>
                        <select v-model="verificationForm.actualVehicleType" class="input-select">
                          <option value="CAR">CAR</option>
                          <option value="MOTORCYCLE">MOTORCYCLE</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  <!-- Remarks -->
                  <div class="form-group remarks-group">
                    <label>Remarks / Comments</label>
                    <textarea 
                      v-model="verificationForm.remarks" 
                      class="input-textarea"
                      placeholder="Add remarks or comments..."
                      rows="5"
                    ></textarea>
                  </div>

                  <!-- Action Buttons Row -->
                  <div class="form-actions-row">
                    <button 
                    class="btn-submit-verification" 
                    :disabled="isSubmitting"
                    @click="submitVerification"
                    >
                    <span v-if="isSubmitting" class="mdi mdi-loading mdi-spin"></span>
                    <span v-else class="mdi mdi-content-save-check"></span>
                    {{ verificationForm.status === 'INCORRECT' ? 'Submit Correction' : (verificationForm.status === 'NOT_DETECTED' ? 'Submit Not Detected' : 'Submit Verification') }}
                  </button>
                  <button 
                    v-if="verificationForm.status === 'INCORRECT' || verificationForm.status === 'NOT_DETECTED'"
                    class="btn-cancel-correction" 
                    @click="cancelCorrection"
                  >
                    Cancel
                  </button>
                  </div>
                </div>
              </div>
            </div>
            
            <div v-else class="empty-workspace-state">
              <span class="mdi mdi-camera-off empty-icon animate-pulse"></span>
              <h3>No Vehicle Selected</h3>
              <p>Select a pending vehicle from the queue to start manual verification.</p>
              <button 
                v-if="pendingDetections.length > 0" 
                class="btn-primary-testing" 
                @click="selectFirstPending"
              >
                Start Verification Queue
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Grid: Queue and Report -->
    <div class="bottom-layout-grid">
      <!-- Left Side: Queue Sidebar (1fr) -->
      <div class="queue-card-wrapper">
        <div class="workspace-card sidebar-card">
          <div class="card-header justify-between">
            <span>
              <span class="mdi mdi-playlist-play text-purple"></span>
              Verification Queue
            </span>
            <span class="count-badge">
              {{ queueVehicleTypeFilter === 'ALL' ? pendingDetections.length + ' Pending' : filteredQueue.length + ' / ' + pendingDetections.length + ' Pending' }}
            </span>
          </div>

          <!-- Queue Filter Bar -->
          <div class="queue-filter-bar">
            <span class="mdi mdi-filter-variant text-purple"></span>
            <select v-model="queueVehicleTypeFilter" class="queue-filter-select">
              <option value="ALL">ALL VEHICLES</option>
              <option value="CAR">CAR ONLY</option>
              <option value="MOTORCYCLE">MOTORCYCLE ONLY</option>
            </select>
          </div>

          <div class="queue-list-container">
            <div 
              v-for="det in filteredQueue" 
              :key="det.id"
              class="queue-item"
              :class="{ 
                active: activeDet && activeDet.id === det.id
              }"
              @click="selectDetection(det)"
            >
              <div class="queue-item-meta">
                <span class="queue-item-time">{{ formatTimeOnly(det.timestamp) }}</span>
                <span class="queue-item-gate">{{ det.gate }}</span>
              </div>
              <div class="queue-item-main">
                <span class="queue-item-plate">{{ det.plate_no }}</span>
                <span class="vtype-badge badge-sm" :class="'badge-' + det.vehicle_type.toLowerCase()">
                  {{ det.vehicle_type }}
                </span>
              </div>
            </div>

            <div v-if="filteredQueue.length === 0" class="empty-queue-state">
              <span class="mdi mdi-tray-arrow-down text-muted"></span>
              <p v-if="pendingDetections.length > 0">No pending vehicles match the type filter.</p>
              <p v-else>Waiting for live camera entry events...</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Side: Accuracy Report (3fr) -->
      <div class="report-card-wrapper">
        <div class="report-card">
          <div class="accuracy-header">
          <h2>
            <span class="mdi mdi-file-table-box text-purple" style="margin-right: 8px;"></span>
            Manual Ground-Truth Accuracy Report
          </h2>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-warning btn-sm" @click="exportCSV">
              <span class="mdi mdi-download"></span> Export CSV
            </button>
            <button class="btn btn-secondary btn-sm" @click="clearManualReport">
              <span class="mdi mdi-refresh"></span> Reset Data
            </button>
          </div>
        </div>

        <!-- Filters Row -->
        <div class="filters-row">
          <div class="filter-group">
            <label>Filter Result</label>
            <select v-model="filters.status" class="filter-select">
              <option value="ALL">ALL RESULTS</option>
              <option value="CORRECT">CORRECT</option>
              <option value="INCORRECT">INCORRECT</option>
            </select>
          </div>
          <div class="filter-group">
            <label>Filter Vehicle Type</label>
            <select v-model="filters.type" class="filter-select">
              <option value="ALL">ALL VEHICLES</option>
              <option value="CAR">CAR</option>
              <option value="MOTORCYCLE">MOTORCYCLE</option>
            </select>
          </div>
          <div class="filter-group" style="flex: 2 1 250px;">
            <label>Search Plate Numbers</label>
            <div class="search-input-wrapper">
              <span class="mdi mdi-magnify search-icon"></span>
              <input type="text" v-model="filters.search" placeholder="Search detected or actual plate..." class="search-input" />
            </div>
          </div>
        </div>

        <!-- Table -->
        <div class="table-container">
          <table class="report-table">
            <thead>
              <tr>
                <th>Verification Time</th>
                <th>Gate</th>
                <th>Detected Details</th>
                <th>Actual Details</th>
                <th>QA Result</th>
                <th>Remarks / Reason</th>
                <th>Front Image</th>
                <th>Back Image</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="filteredHistory.length === 0">
                <td colspan="8" class="placeholder-row">
                  No ground-truth records found.
                </td>
              </tr>
              <tr 
                v-else 
                v-for="(record, idx) in filteredHistory" 
                :key="idx" 
                :class="{ 'row-pass': record.status === 'CORRECT', 'row-fail': record.status === 'INCORRECT', 'row-warn': record.status === 'NOT_DETECTED' }"
              >
                <td>{{ record.ts }}</td>
                <td>{{ record.gate }}</td>
                <td>
                  <div class="plate-code">{{ record.det_plate }}</div>
                  <span class="vtype-badge badge-sm" :class="'badge-' + record.det_type.toLowerCase()">
                    {{ record.det_type }}
                  </span>
                </td>
                <td>
                  <div class="plate-code text-green">{{ record.act_plate }}</div>
                  <span class="vtype-badge badge-sm" :class="'badge-' + record.act_type.toLowerCase()">
                    {{ record.act_type }}
                  </span>
                </td>
                <td>
                  <button 
                    @click="openEditModal(record)" 
                    class="btn-edit-record" 
                    :class="'badge-' + (record.status === 'CORRECT' ? 'pass' : (record.status === 'INCORRECT' ? 'fail' : 'warn'))"
                  >
                    <span class="mdi" :class="record.status === 'CORRECT' ? 'mdi-check' : (record.status === 'INCORRECT' ? 'mdi-close' : 'mdi-eye-off')"></span>
                    {{ record.status === 'NOT_DETECTED' ? 'NOT DETECTED' : record.status }}
                  </button>
                </td>
                <td class="remarks-cell">{{ record.remarks || '-' }}</td>
                <td>
                  <button 
                    v-if="record.img_front"
                    class="btn-img-view"
                    @click="viewHistoryImage(record, 'front')"
                  >
                    View Front
                  </button>
                  <span v-else class="text-muted">-</span>
                </td>
                <td>
                  <button 
                    v-if="record.img_back"
                    class="btn-img-view"
                    @click="viewHistoryImage(record, 'back')"
                  >
                    View Back
                  </button>
                  <span v-else class="text-muted">-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

    <!-- Image Fullscreen Overlay Modal -->
    <div v-if="fullscreenImageSrc" class="fullscreen-overlay" @click="fullscreenImageSrc = null">
      <div class="fullscreen-modal-container">
        <button class="close-overlay-btn" @click="fullscreenImageSrc = null">
          <span class="mdi mdi-close"></span>
        </button>
        <img :src="fullscreenImageSrc" alt="Fullscreen camera capture" class="fullscreen-image" @click.stop />
      </div>
    </div>

    <!-- Edit Record Modal -->
    <div v-if="editModalRecord" class="fullscreen-overlay" @click="closeEditModal">
      <div class="edit-modal-card" @click.stop>
        <div class="card-header justify-between">
          <span><span class="mdi mdi-pencil-box-outline text-purple"></span> Edit Verification Record</span>
          <button class="close-modal-btn" @click="closeEditModal">
            <span class="mdi mdi-close"></span>
          </button>
        </div>
        
        <div class="modal-body">
          <div class="modal-info-bar">
            <div><strong>Timestamp:</strong> {{ editModalRecord.ts }}</div>
            <div><strong>Detected:</strong> <span class="plate-code text-purple">{{ editModalRecord.det_plate }}</span> ({{ editModalRecord.det_type }})</div>
          </div>

          <!-- Vehicle Images Preview Row -->
          <div v-if="getEditModalImageUrl('front') || getEditModalImageUrl('back')" class="modal-images-row">
            <div v-if="getEditModalImageUrl('front')" class="modal-img-container">
              <div class="modal-img-label">Front Image</div>
              <img 
                :src="getEditModalImageUrl('front')" 
                alt="Front Plate Capture" 
                class="modal-preview-image"
                @click="openFullscreenImage(getEditModalImageUrl('front'))"
              />
            </div>
            <div v-if="getEditModalImageUrl('back')" class="modal-img-container">
              <div class="modal-img-label">Back Image</div>
              <img 
                :src="getEditModalImageUrl('back')" 
                alt="Back Plate Capture" 
                class="modal-preview-image"
                @click="openFullscreenImage(getEditModalImageUrl('back'))"
              />
            </div>
          </div>

          <div class="form-group" style="margin-top: 15px;">
            <label>QA Result</label>
            <div class="accuracy-selection-row">
              <button 
                class="btn-decision btn-correct" 
                :class="{ active: editModalForm.status === 'CORRECT' }"
                @click="editModalForm.status = 'CORRECT'"
              >
                <span class="mdi mdi-check-circle"></span> Correct
              </button>
              <button 
                class="btn-decision btn-incorrect" 
                :class="{ active: editModalForm.status === 'INCORRECT' }"
                @click="editModalForm.status = 'INCORRECT'"
              >
                <span class="mdi mdi-close-circle"></span> Incorrect
              </button>
              <button 
                class="btn-decision btn-not-detected" 
                :class="{ active: editModalForm.status === 'NOT_DETECTED' }"
                @click="editModalForm.status = 'NOT_DETECTED'"
              >
                <span class="mdi mdi-eye-off"></span> Not Detected
              </button>
            </div>
          </div>

          <!-- Edit Inputs (Shown only if Incorrect or Not Detected selected) -->
          <div v-if="editModalForm.status === 'INCORRECT' || editModalForm.status === 'NOT_DETECTED'" class="incorrect-edit-section" style="margin-top: 15px;">
            <div class="correction-mode-badge" :class="{ 'badge-warn': editModalForm.status === 'NOT_DETECTED' }">
              <span class="mdi" :class="editModalForm.status === 'NOT_DETECTED' ? 'mdi-eye-off' : 'mdi-alert-circle-outline'"></span>
              <span>{{ editModalForm.status === 'NOT_DETECTED' ? 'Not Detected Mode' : 'Input Actual Details' }}</span>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Actual Plate Number</label>
                <input 
                  type="text" 
                  v-model="editModalForm.actPlate" 
                  class="input-text plate-input"
                  placeholder="Enter actual plate..."
                />
              </div>
              <div class="form-group">
                <label>Actual Vehicle Type</label>
                <select v-model="editModalForm.actVehicleType" class="input-select">
                  <option value="CAR">CAR</option>
                  <option value="MOTORCYCLE">MOTORCYCLE</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-group" style="margin-top: 15px;">
            <label>Remarks / Comments</label>
            <textarea 
              v-model="editModalForm.remarks" 
              class="input-textarea"
              placeholder="Add remarks or comments..."
              rows="3"
            ></textarea>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn-cancel-correction" @click="closeEditModal">Cancel</button>
          <button class="btn-submit-verification" @click="saveEditModal">
            <span class="mdi mdi-content-save-check"></span> Save Changes
          </button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { io } from 'socket.io-client'

// Socket.io initialization
const socket = io(import.meta.env.DEV ? `http://${window.location.hostname}:${import.meta.env.VITE_WS_PORT || '5015'}` : window.location.origin)

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://103.93.223.103:9075'

// State variables
const recentDetections = ref([])
const verificationHistory = ref([])
const activeDet = ref(null)
const activeView = ref('front') // 'front' or 'back'
const activeImageType = ref('vehicle') // 'vehicle' (whole image) or 'plate' (plate crop)
const isSubmitting = ref(false)
const toast = ref('')
const fullscreenImageSrc = ref(null)
const isConnected = ref(socket.connected)
const includeNotDetected = ref(localStorage.getItem('include_not_detected') === 'true')
watch(includeNotDetected, (newVal) => {
  localStorage.setItem('include_not_detected', newVal)
})
const queueVehicleTypeFilter = ref('ALL')

// Animations & Swiping State
const isTransitioning = ref(false)
const transitionClass = ref('')

// Verification Form State
const verificationForm = reactive({
  status: 'CORRECT',
  actualPlate: '',
  actualVehicleType: 'CAR',
  remarks: ''
})

// Filters
const filters = reactive({
  status: 'ALL',
  type: 'ALL',
  search: ''
})

// Utility functions
const showToast = (msg) => {
  toast.value = msg
  setTimeout(() => toast.value = '', 3000)
}

const formatTimeOnly = (tsStr) => {
  if (!tsStr) return ''
  // Expects 'YYYY-MM-DD HH:MM:SS'
  const parts = tsStr.split(' ')
  return parts.length > 1 ? parts[1] : tsStr
}

// Socket Registration
let lastRegisteredSocketId = null
const registerTerminal = () => {
  if (!socket.connected) return
  if (socket.id === lastRegisteredSocketId) return
  socket.emit('register_terminal', { role: 'admin', gate: 0 })
  lastRegisteredSocketId = socket.id
}

// Selection helpers
const pendingDetections = computed(() => {
  return recentDetections.value.filter(d => !d.verified)
})

const filteredQueue = computed(() => {
  return pendingDetections.value.filter(d => {
    if (queueVehicleTypeFilter.value === 'ALL') return true
    return d.vehicle_type === queueVehicleTypeFilter.value
  })
})

const pendingDetectionsCount = computed(() => {
  return pendingDetections.value.length
})

const selectDetection = (det) => {
  if (isTransitioning.value) return
  if (activeDet.value && activeDet.value.id === det.id) return

  isTransitioning.value = true
  transitionClass.value = 'swipe-out'

  setTimeout(() => {
    activeDet.value = det
    
    // Choose available view
    if (det.front_vehicle_image || det.plate_image_front) {
      activeView.value = 'front'
      activeImageType.value = det.front_vehicle_image ? 'vehicle' : 'plate'
    } else if (det.back_vehicle_image || det.plate_image_back) {
      activeView.value = 'back'
      activeImageType.value = det.back_vehicle_image ? 'vehicle' : 'plate'
    } else {
      activeView.value = 'front'
      activeImageType.value = 'vehicle'
    }
    
    // Set form initial values
    verificationForm.status = 'CORRECT'
    verificationForm.actualPlate = det.plate_no
    verificationForm.actualVehicleType = det.vehicle_type
    verificationForm.remarks = ''

    // Emit on-demand image request for the selected detection
    socket.emit('get_detection_images', { id: det.id, plate_no: det.plate_no, timestamp: det.timestamp })

    transitionClass.value = 'swipe-in'
    setTimeout(() => {
      transitionClass.value = ''
      isTransitioning.value = false
    }, 100)
  }, 100)
}

const selectFirstPending = () => {
  if (filteredQueue.value.length > 0) {
    selectDetection(filteredQueue.value[0])
  } else if (pendingDetections.value.length > 0) {
    selectDetection(pendingDetections.value[0])
  }
}

const getCurrentImageUrl = () => {
  if (!activeDet.value) return ''
  if (activeView.value === 'front') {
    if (activeImageType.value === 'vehicle' && activeDet.value.front_vehicle_image) {
      return activeDet.value.front_vehicle_image
    }
    const img = activeDet.value.plate_image_front || activeDet.value.front_plate_image
    if (!img || img === 'front_image_available' || img === 'back_image_available') return ''
    return img.startsWith('data:') ? img : `${apiBaseUrl}/anpr/${img}`
  } else {
    if (activeImageType.value === 'vehicle' && activeDet.value.back_vehicle_image) {
      return activeDet.value.back_vehicle_image
    }
    const img = activeDet.value.plate_image_back || activeDet.value.back_plate_image
    if (!img || img === 'front_image_available' || img === 'back_image_available') return ''
    return img.startsWith('data:') ? img : `${apiBaseUrl}/anpr/${img}`
  }
}

const getEditModalImageUrl = (type) => {
  if (!editModalRecord.value) return ''
  if (type === 'front') {
    if (editModalRecord.value.front_vehicle_image) return editModalRecord.value.front_vehicle_image
    const img = editModalRecord.value.img_front
    if (!img || img === 'front_image_available' || img === 'back_image_available') return ''
    return img.startsWith('data:') ? img : `${apiBaseUrl}/anpr/${img}`
  } else {
    if (editModalRecord.value.back_vehicle_image) return editModalRecord.value.back_vehicle_image
    const img = editModalRecord.value.img_back
    if (!img || img === 'front_image_available' || img === 'back_image_available') return ''
    return img.startsWith('data:') ? img : `${apiBaseUrl}/anpr/${img}`
  }
}

const viewHistoryImage = (record, type) => {
  const imgKey = type === 'front' ? 'img_front' : 'img_back'
  const imgUrl = record[imgKey]
  
  if (!imgUrl) return
  
  // If the image is already a base64 string or an absolute HTTP URL, view it directly!
  if (imgUrl.startsWith('data:') || imgUrl.startsWith('http')) {
    openFullscreenImage(imgUrl)
    return
  }
  
  // Otherwise, request the real base64 images from the backend on demand!
  showToast("Loading image...")
  
  const handleResponse = (res) => {
    if (res.id === (record.det_id || record.ts)) {
      socket.off('detection_images_response', handleResponse)
      const loadedImg = type === 'front' 
        ? (res.front_vehicle_image || res.front_plate_image) 
        : (res.back_vehicle_image || res.back_plate_image)
        
      if (loadedImg) {
        record[imgKey] = loadedImg
        openFullscreenImage(loadedImg)
      } else {
        showToast("Image not found on media server")
      }
    }
  }
  
  socket.on('detection_images_response', handleResponse)
  socket.emit('get_detection_images', { 
    id: record.det_id || record.ts, 
    plate_no: record.det_plate, 
    timestamp: record.ts 
  })
}

const cancelCorrection = () => {
  verificationForm.status = 'CORRECT'
  if (activeDet.value) {
    verificationForm.actualPlate = activeDet.value.plate_no
    verificationForm.actualVehicleType = activeDet.value.vehicle_type
  }
  verificationForm.remarks = ''
}

// Particle Explosion Animation (Web Animations API)
const triggerExplosion = (event) => {
  if (!event) return
  const rect = event.currentTarget.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2

  const particleContainer = document.createElement('div')
  particleContainer.style.position = 'fixed'
  particleContainer.style.top = '0'
  particleContainer.style.left = '0'
  particleContainer.style.width = '100vw'
  particleContainer.style.height = '100vh'
  particleContainer.style.pointerEvents = 'none'
  particleContainer.style.zIndex = '9999'
  document.body.appendChild(particleContainer)

  const colors = ['#28a745', '#00ff66', '#a855f7', '#ffc107', '#17a2b8', '#00f0ff']
  for (let i = 0; i < 35; i++) {
    const p = document.createElement('div')
    p.style.position = 'absolute'
    p.style.left = `${centerX}px`
    p.style.top = `${centerY}px`
    p.style.width = `${Math.random() * 8 + 6}px`
    p.style.height = p.style.width
    p.style.borderRadius = '50%'
    p.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)]
    p.style.transform = 'translate(-50%, -50%)'
    p.style.boxShadow = '0 0 8px currentColor'
    particleContainer.appendChild(p)

    const angle = Math.random() * Math.PI * 2
    const velocity = Math.random() * 150 + 100
    const dx = Math.cos(angle) * velocity
    const dy = Math.sin(angle) * velocity

    p.animate([
      { transform: 'translate(-50%, -50%) scale(1)', opacity: 1 },
      { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(0)`, opacity: 0 }
    ], {
      duration: Math.random() * 500 + 400,
      easing: 'cubic-bezier(0.1, 0.8, 0.3, 1)',
      fill: 'forwards'
    })
  }

  setTimeout(() => {
    particleContainer.remove()
  }, 1000)
}

// Set Form status and auto-trigger correct matching
const setFormStatus = (status, event) => {
  verificationForm.status = status
  if (status === 'CORRECT') {
    triggerExplosion(event)
    // Quick auto-submit delay for high efficiency matching!
    setTimeout(() => {
      submitVerification()
    }, 600)
  }
}

// Submit Verification to backend
const submitVerification = () => {
  if (!activeDet.value || isSubmitting.value) return
  isSubmitting.value = true

  const payload = {
    id: activeDet.value.id,
    actual_plate: verificationForm.status === 'CORRECT' ? activeDet.value.plate_no : verificationForm.actualPlate,
    actual_vehicle_type: verificationForm.status === 'CORRECT' ? activeDet.value.vehicle_type : verificationForm.actualVehicleType,
    status: verificationForm.status,
    remarks: verificationForm.remarks
  }

  socket.emit('submit_manual_verification', payload)
  showToast(`Vehicle verified successfully as ${payload.status}!`)

  // Automatically queue next pending vehicle with a swipe animation
  setTimeout(() => {
    isSubmitting.value = false
    
    // Find next unverified item in queue
    const remainingPending = filteredQueue.value.filter(d => d.id !== activeDet.value.id)
    if (remainingPending.length > 0) {
      selectDetection(remainingPending[0])
    } else {
      activeDet.value = null
    }
  }, 400)
}

// Reset/Clear Manual QA logs
const clearManualReport = () => {
  if (confirm("Are you sure you want to reset all manual verification logs? The vehicle queue will be preserved and reset to pending.")) {
    socket.emit('clear_manual_history')
    verificationHistory.value = []
    showToast('Manual QA history wiped. Queue reset to pending.')
  }
}

// Fullscreen image viewer
const openFullscreenImage = (src) => {
  fullscreenImageSrc.value = src
}

const editModalRecord = ref(null)
const editModalForm = reactive({
  status: 'CORRECT',
  actPlate: '',
  actVehicleType: 'CAR',
  remarks: ''
})

const openEditModal = (record) => {
  editModalRecord.value = record
  editModalForm.status = record.status
  editModalForm.actPlate = record.act_plate
  editModalForm.actVehicleType = record.act_type
  editModalForm.remarks = record.remarks || ''
  
  // Request on-demand images for edit modal preview
  socket.emit('get_detection_images', { id: record.id || record.ts, plate_no: record.det_plate, timestamp: record.ts })
}

const closeEditModal = () => {
  editModalRecord.value = null
}

const saveEditModal = () => {
  if (!editModalRecord.value) return
  
  socket.emit('update_manual_verification_record', {
    ts: editModalRecord.value.ts,
    det_plate: editModalRecord.value.det_plate,
    status: editModalForm.status,
    act_plate: editModalForm.status === 'CORRECT' ? editModalRecord.value.det_plate : editModalForm.actPlate,
    act_type: editModalForm.status === 'CORRECT' ? editModalRecord.value.det_type : editModalForm.actVehicleType,
    remarks: editModalForm.remarks
  })
  
  showToast(`Updated record for ${editModalRecord.value.det_plate} successfully.`)
  closeEditModal()
}

// Filtered records for accuracy calculations
const filteredRecordsForAccuracy = computed(() => {
  if (includeNotDetected.value) {
    return verificationHistory.value
  } else {
    return verificationHistory.value.filter(h => h.status !== 'NOT_DETECTED')
  }
})

// Computed stats calculation
const accuracyStats = computed(() => {
  const list = filteredRecordsForAccuracy.value
  const total = list.length
  const correct = list.filter(h => h.status === 'CORRECT').length
  const incorrect = total - correct
  const vtypeMatches = list.filter(h => h.det_type && h.act_type && h.det_type.toLowerCase() === h.act_type.toLowerCase()).length

  return {
    total,
    correct,
    incorrect,
    vtypeMatches,
    accuracy: total === 0 ? '100.0%' : ((correct / total) * 100).toFixed(1) + '%',
    errorRate: total === 0 ? '0.0%' : ((incorrect / total) * 100).toFixed(1) + '%',
    vtypeMatchRate: total === 0 ? '100.0%' : ((vtypeMatches / total) * 100).toFixed(1) + '%'
  }
})

// Filtered manual history
const filteredHistory = computed(() => {
  return verificationHistory.value.filter(record => {
    const statusMatch = filters.status === 'ALL' || record.status === filters.status
    const typeMatch = filters.type === 'ALL' || record.act_type === filters.type || record.det_type === filters.type
    
    const searchQuery = (filters.search || '').trim().toUpperCase()
    const searchMatch = !searchQuery || 
      (record.det_plate || '').toUpperCase().includes(searchQuery) ||
      (record.act_plate || '').toUpperCase().includes(searchQuery) ||
      (record.remarks || '').toUpperCase().includes(searchQuery)
      
    return statusMatch && typeMatch && searchMatch
  })
})

// Export ground truth report to CSV
const exportCSV = () => {
  if (verificationHistory.value.length === 0) {
    showToast('No verifications to export.')
    return
  }
  
  const headers = ['Timestamp', 'Stage', 'Gate', 'Detected Plate', 'Detected Type', 'Actual Plate', 'Actual Type', 'Result', 'Remarks', 'Image Front', 'Image Back']
  const rows = verificationHistory.value.map(record => [
    record.ts,
    record.stage,
    record.gate,
    record.det_plate,
    record.det_type,
    record.act_plate,
    record.act_type,
    record.status,
    record.remarks || '',
    record.img_front || '',
    record.img_back || ''
  ])
  
  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(val => `"${String(val).replace(/"/g, '""')}"`).join(','))
  ].join('\n')
  
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', `anpr_manual_qa_report_${new Date().toISOString().slice(0,10)}.csv`)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  
  showToast('QA CSV exported successfully.')
}

// Hook registrations
onMounted(() => {
  socket.on('connect', () => {
    isConnected.value = true
    registerTerminal()
  })

  socket.on('disconnect', () => {
    isConnected.value = false
  })

  if (socket.connected) {
    isConnected.value = true
    registerTerminal()
  }

  // Receive detections list
  socket.on('recent_detections', (list) => {
    recentDetections.value = list
    // Set active vehicle if not already selected
    if (!activeDet.value && pendingDetections.value.length > 0) {
      activeDet.value = pendingDetections.value[0]
      activeView.value = activeDet.value.plate_image_front ? 'front' : 'back'
      verificationForm.actualPlate = activeDet.value.plate_no
      verificationForm.actualVehicleType = activeDet.value.vehicle_type
      socket.emit('get_detection_images', { id: activeDet.value.id, plate_no: activeDet.value.plate_no, timestamp: activeDet.value.timestamp })
    }
  })

  // Receive on-demand images
  socket.on('detection_images_response', (res) => {
    if (activeDet.value && activeDet.value.id === res.id) {
      activeDet.value.front_plate_image = res.front_plate_image
      activeDet.value.front_vehicle_image = res.front_vehicle_image
      activeDet.value.back_plate_image = res.back_plate_image
      activeDet.value.back_vehicle_image = res.back_vehicle_image
      
      // Choose available view dynamically when images arrive
      if (res.front_vehicle_image || res.front_plate_image) {
        activeView.value = 'front'
        activeImageType.value = res.front_vehicle_image ? 'vehicle' : 'plate'
      } else if (res.back_vehicle_image || res.back_plate_image) {
        activeView.value = 'back'
        activeImageType.value = res.back_vehicle_image ? 'vehicle' : 'plate'
      }
    }
    
    if (editModalRecord.value && (editModalRecord.value.id === res.id || editModalRecord.value.ts === res.id)) {
      editModalRecord.value.front_plate_image = res.front_plate_image
      editModalRecord.value.front_vehicle_image = res.front_vehicle_image
      editModalRecord.value.back_plate_image = res.back_plate_image
      editModalRecord.value.back_vehicle_image = res.back_vehicle_image
      
      // Also bind to legacy keys for safety
      editModalRecord.value.img_front = res.front_plate_image || res.front_vehicle_image || ""
      editModalRecord.value.img_back = res.back_plate_image || res.back_vehicle_image || ""
    }
  })

  // Receive new live camera event
  socket.on('new_camera_detection', (det) => {
    // Insert at front
    recentDetections.value.unshift(det)
    // Select it if currently nothing is selected
    if (!activeDet.value) {
      activeDet.value = det
      activeView.value = det.plate_image_front ? 'front' : 'back'
      verificationForm.actualPlate = det.plate_no
      verificationForm.actualVehicleType = det.vehicle_type
      socket.emit('get_detection_images', { id: det.id, plate_no: det.plate_no, timestamp: det.timestamp })
    }
  })

  // Receive verification history
  socket.on('manual_verification_history', (history) => {
    verificationHistory.value = history
  })

  // Receive new verification log update
  socket.on('manual_verification_new', (logRecord) => {
    verificationHistory.value.unshift(logRecord)
  })
})

onUnmounted(() => {
  socket.off('connect')
  socket.off('disconnect')
  socket.off('recent_detections')
  socket.off('new_camera_detection')
  socket.off('manual_verification_history')
  socket.off('manual_verification_new')
})
</script>

<style scoped>
/* Custom Scrollbars */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: #060606;
}
::-webkit-scrollbar-thumb {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: #2a2a2a;
}
* {
  scrollbar-width: thin;
  scrollbar-color: #1a1a1a #060606;
}

.testing-container {
  flex: 1;
  background-color: #0d0d0d;
  padding: 30px;
  color: #e0e0e0;
  overflow-y: auto;
  height: 100vh;
  box-sizing: border-box;
  font-family: 'Segoe UI', -apple-system, sans-serif;
}

/* Header styling */
.testing-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
  border-bottom: 1px solid #222;
  padding-bottom: 15px;
}
.header-title-section {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.back-link {
  color: #a855f7;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: opacity 0.2s;
}
.back-link:hover {
  opacity: 0.8;
}
.testing-header h1 {
  margin: 0;
  font-size: 1.6rem;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 10px;
}
.text-purple {
  color: #a855f7 !important;
}
.text-green {
  color: #28a745 !important;
}
.text-red {
  color: #dc3545 !important;
}
.text-cyan {
  color: #17a2b8 !important;
}
.header-badge {
  background: rgba(220, 53, 69, 0.1);
  border: 1px solid rgba(220, 53, 69, 0.25);
  color: #dc3545;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}
.header-badge.connected {
  background: rgba(40, 167, 69, 0.1);
  border: 1px solid rgba(40, 167, 69, 0.25);
  color: #28a745;
}
.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .5; }
}
.animate-blink {
  animation: blink 1.2s infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Stats grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin-bottom: 25px;
}
.stat-card {
  background: #141414;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.border-purple { border-left: 4px solid #a855f7; }
.border-green { border-left: 4px solid #28a745; }
.border-red { border-left: 4px solid #dc3545; }
.border-cyan { border-left: 4px solid #17a2b8; }

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}
.stat-title {
  font-size: 0.78rem;
  text-transform: uppercase;
  color: #888;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.icon-lg {
  font-size: 1.2rem;
}
.stat-num {
  font-size: 2rem;
  font-weight: 800;
  font-family: monospace;
  line-height: 1.1;
  margin: 5px 0;
}
.stat-sub {
  font-size: 0.72rem;
  color: #666;
}

/* Workspace Layout */
.workspace-layout {
  display: flex;
  gap: 20px;
  margin-bottom: 25px;
  height: 770px;
}
.workspace-main {
  flex: 3;
  min-width: 0;
  height: 100%;
}
.workspace-sidebar {
  flex: 1;
  min-width: 300px;
  height: 100%;
}
.bottom-layout-grid {
  display: grid;
  grid-template-columns: 1fr 3fr;
  gap: 20px;
  margin-top: 25px;
  align-items: start;
}
.queue-card-wrapper {
  height: 100%;
}
.queue-card-wrapper .workspace-card {
  height: 600px;
}
.report-card-wrapper {
  min-width: 0;
}
.workspace-card {
  background: #141414;
  border: 1px solid #222;
  border-radius: 8px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 8px 16px rgba(0,0,0,0.2);
}
.card-header {
  background: #1a1a1a;
  border-bottom: 1px solid #2a2a2a;
  padding: 12px 18px;
  font-size: 0.9rem;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.justify-between {
  justify-content: space-between;
}
.active-badge {
  background: rgba(168, 85, 247, 0.15);
  border: 1px solid rgba(168, 85, 247, 0.3);
  color: #c084fc;
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
}
.count-badge {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  font-size: 0.7rem;
  color: #bbb;
  padding: 2px 8px;
  border-radius: 12px;
}

/* Swipe transitions */
.swipe-container {
  flex: 1;
  overflow: hidden;
  position: relative;
  height: 100%;
}
.swipe-container.swipe-out {
  transform: translateX(-80px) scale(0.98);
  opacity: 0;
  transition: transform 0.1s ease-in, opacity 0.1s ease-in;
}
.swipe-container.swipe-in {
  transform: translateX(80px) scale(0.98);
  opacity: 0;
  transition: none;
}
.swipe-container:not(.swipe-out):not(.swipe-in) {
  transform: translateX(0) scale(1);
  opacity: 1;
  transition: transform 0.1s ease-out, opacity 0.1s ease-out;
}

.active-workspace-content {
  display: flex;
  flex-direction: row;
  height: 100%;
  padding: 16px;
  box-sizing: border-box;
  gap: 20px;
}

/* Images styles */
.images-panel {
  flex: 2;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.image-toggle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.toggle-buttons {
  display: flex;
  gap: 8px;
}
.btn-toggle-view {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #aaa;
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-toggle-view:hover:not(:disabled) {
  background: rgba(168, 85, 247, 0.12);
  color: #c084fc;
  border-color: #a855f7;
}
.btn-toggle-view.active {
  background: #a855f7;
  color: #fff;
  border-color: #a855f7;
  box-shadow: 0 0 10px rgba(168, 85, 247, 0.35);
}
.btn-toggle-view:disabled {
  opacity: 0.25;
  cursor: not-allowed;
}
.single-image-wrapper {
  flex: 1;
  height: auto !important;
}
.image-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  height: 100%;
}
.image-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: #aaa;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.image-wrapper {
  flex: 1;
  background: #080808;
  border: 1px solid #222;
  border-radius: 6px;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.camera-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  cursor: zoom-in;
  transition: transform 0.2s ease;
}
.camera-image:hover {
  transform: scale(1.03);
}
.image-placeholder {
  color: #444;
  font-size: 0.8rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.image-placeholder .mdi {
  font-size: 2rem;
}

/* Verification details and decision board */
.controls-panel-desk {
  flex: 1.1;
  min-width: 320px;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
}
.controls-panel-desk h3 {
  margin: 0 0 10px 0;
  font-size: 0.8rem;
  color: #a855f7;
  text-transform: uppercase;
  letter-spacing: 1px;
  border-bottom: 1px solid #2a2a2a;
  padding-bottom: 6px;
}
.compact-stats-section {
  border-bottom: 1px solid #2a2a2a;
  padding-bottom: 12px;
  margin-bottom: 8px;
}
.compact-stats-grid-box {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.compact-stat-card {
  background: #111;
  border: 1px solid #222;
  border-radius: 6px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
}
.border-purple-compact { border-left: 3px solid #a855f7; }
.border-green-compact { border-left: 3px solid #28a745; }
.border-red-compact { border-left: 3px solid #dc3545; }
.border-cyan-compact { border-left: 3px solid #17a2b8; }

.compact-stat-header {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 2px;
}
.compact-stat-title {
  font-size: 0.65rem;
  color: #777;
  font-weight: 700;
  text-transform: uppercase;
}
.compact-stat-num {
  font-size: 1.15rem;
  font-weight: 800;
  font-family: monospace;
  line-height: 1.2;
}
.compact-stat-sub {
  font-size: 0.62rem;
  color: #555;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.detected-info-panel {
  border-bottom: 1px solid #2a2a2a;
  padding-bottom: 12px;
  margin-bottom: 5px;
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.info-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.info-label {
  font-size: 0.65rem;
  color: #777;
  text-transform: uppercase;
  font-weight: 700;
}
.info-val {
  font-size: 0.88rem;
  font-weight: 600;
  color: #ddd;
}
.plate-box {
  background: #111;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 2px 6px;
  font-family: monospace;
  font-weight: bold;
  letter-spacing: 0.5px;
  color: #ffc107 !important;
  text-align: center;
  max-width: 100px;
}

/* Decision form styling */
.decision-form-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.accuracy-selection-row {
  display: flex;
  gap: 10px;
}
.btn-decision {
  flex: 1;
  border: 1px solid #333;
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: bold;
  color: #aaa;
  background: #111;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s ease;
}
.btn-correct {
  border-color: rgba(40, 167, 69, 0.45) !important;
  color: #28a745 !important;
  background: rgba(40, 167, 69, 0.04) !important;
}
.btn-correct:hover:not(:disabled) {
  background: rgba(40, 167, 69, 0.1) !important;
  border-color: #28a745 !important;
  color: #28a745 !important;
}
.btn-correct.active {
  background: rgba(40, 167, 69, 0.18) !important;
  border-color: #28a745 !important;
  color: #28a745 !important;
  box-shadow: 0 0 12px rgba(40, 167, 69, 0.25) !important;
}
.btn-incorrect {
  border-color: rgba(220, 53, 69, 0.45) !important;
  color: #dc3545 !important;
  background: rgba(220, 53, 69, 0.04) !important;
}
.btn-incorrect:hover:not(:disabled) {
  background: rgba(220, 53, 69, 0.1) !important;
  border-color: #dc3545 !important;
  color: #dc3545 !important;
}
.btn-incorrect.active {
  background: rgba(220, 53, 69, 0.18) !important;
  border-color: #dc3545 !important;
  color: #dc3545 !important;
  box-shadow: 0 0 12px rgba(220, 53, 69, 0.25) !important;
}
.btn-not-detected {
  border-color: rgba(255, 193, 7, 0.45) !important;
  color: #ffc107 !important;
  background: rgba(255, 193, 7, 0.04) !important;
}
.btn-not-detected:hover:not(:disabled) {
  background: rgba(255, 193, 7, 0.1) !important;
  border-color: #ffc107 !important;
  color: #ffc107 !important;
}
.btn-not-detected.active {
  background: rgba(255, 193, 7, 0.18) !important;
  border-color: #ffc107 !important;
  color: #ffc107 !important;
  box-shadow: 0 0 12px rgba(255, 193, 7, 0.25) !important;
}
.btn-decision:disabled {
  opacity: 0.3 !important;
  cursor: not-allowed !important;
  background: #0d0d0d !important;
  border-color: #222 !important;
  color: #444 !important;
  box-shadow: none !important;
}
.correction-mode-badge {
  background: rgba(220, 53, 69, 0.1);
  border: 1px solid rgba(220, 53, 69, 0.25);
  color: #dc3545;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.correction-mode-badge.badge-warn {
  background: rgba(255, 193, 7, 0.1);
  border-color: rgba(255, 193, 7, 0.25);
  color: #ffc107;
}

.incorrect-edit-section {
  background: #111;
  border: 1px solid #2b2b2b;
  border-radius: 6px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  animation: slideDown 0.25s ease-out;
}
@keyframes slideDown {
  from { transform: translateY(-8px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.form-row {
  display: flex;
  gap: 10px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}
.form-group label {
  font-size: 0.65rem;
  color: #888;
  font-weight: 700;
  text-transform: uppercase;
}
.input-text, .input-select, .input-textarea {
  background: #000;
  border: 1px solid #222;
  color: #fff;
  padding: 8px 10px;
  border-radius: 4px;
  outline: none;
  font-size: 0.8rem;
  font-weight: bold;
}
.input-text:focus, .input-select:focus, .input-textarea:focus {
  border-color: #a855f7;
}
.plate-input {
  font-family: monospace;
  letter-spacing: 1px;
  color: #ffc107;
  text-transform: uppercase;
}

.remarks-group {
  margin-top: 2px;
}
.input-textarea {
  font-family: inherit;
  font-weight: normal;
  resize: none;
}

.form-actions-row {
  display: flex;
  gap: 10px;
  margin-top: 5px;
}
.btn-cancel-correction {
  background: #222;
  border: 1px solid #333;
  color: #ccc;
  padding: 10px 18px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 700;
  font-size: 0.85rem;
  transition: all 0.2s;
}
.btn-cancel-correction:hover {
  background: #333;
  color: #fff;
  border-color: #444;
}

.btn-submit-verification {
  flex: 1;
  background: #a855f7;
  border: none;
  color: white;
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 700;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 0.2s;
  box-shadow: 0 4px 6px rgba(168, 85, 247, 0.2);
}
.btn-submit-verification:hover:not(:disabled) {
  background: #c084fc;
}
.btn-submit-verification:disabled {
  background: #4a3e56;
  color: #888;
  cursor: not-allowed;
  box-shadow: none;
}

/* Empty workspace state */
.empty-workspace-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px;
  box-sizing: border-box;
  text-align: center;
}
.empty-icon {
  font-size: 4rem;
  color: #2b2b2b;
  margin-bottom: 15px;
}
.empty-workspace-state h3 {
  margin: 0 0 8px 0;
  font-size: 1.1rem;
  color: #fff;
}
.empty-workspace-state p {
  margin: 0 0 20px 0;
  color: #777;
  max-width: 300px;
  font-size: 0.85rem;
  line-height: 1.4;
}
.btn-primary-testing {
  background: rgba(168, 85, 247, 0.15);
  border: 1px solid rgba(168, 85, 247, 0.3);
  color: #a855f7;
  padding: 8px 20px;
  border-radius: 6px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-primary-testing:hover {
  background: #a855f7;
  color: #fff;
}

/* Sidebar & Queue List styles */
.sidebar-card {
  height: 100%;
}
.queue-filter-bar {
  background: #1a1a1a;
  border-bottom: 1px solid #2a2a2a;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.queue-filter-select {
  flex: 1;
  background: #000;
  border: 1px solid #222;
  color: #fff;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
  outline: none;
  cursor: pointer;
  transition: all 0.2s;
}
.queue-filter-select:focus {
  border-color: #a855f7;
}
.queue-list-container {
  flex: 1;
  overflow-y: auto;
  background: #0d0d0d;
}
.queue-item {
  padding: 12px 16px;
  border-bottom: 1px solid #1a1a1a;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 5px;
  transition: background 0.2s;
  position: relative;
}
.queue-item:hover {
  background: rgba(255, 255, 255, 0.02);
}
.queue-item.active {
  background: rgba(168, 85, 247, 0.08) !important;
  border-left: 3px solid #a855f7;
  padding-left: 13px; /* account for border-left */
}
.queue-item.verified-correct {
  background: rgba(40, 167, 69, 0.02);
}
.queue-item.verified-incorrect {
  background: rgba(220, 53, 69, 0.02);
}

.queue-item-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.68rem;
  color: #555;
  font-weight: 600;
}
.queue-item-main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.queue-item-plate {
  font-size: 0.95rem;
  font-family: monospace;
  font-weight: 800;
  color: #bbb;
}
.queue-item.active .queue-item-plate {
  color: #fff;
}

.queue-item-status {
  position: absolute;
  right: 15px;
  top: 50%;
  transform: translateY(-50%);
}
.badge-status {
  font-size: 0.65rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}
.badge-status.pending {
  background: rgba(255, 193, 7, 0.1);
  color: #ffc107;
  border: 1px solid rgba(255, 193, 7, 0.2);
}
.badge-status.correct {
  background: rgba(40, 167, 69, 0.15);
  color: #28a745;
}
.badge-status.incorrect {
  background: rgba(220, 53, 69, 0.15);
  color: #dc3545;
}
.badge-status.warning {
  background: rgba(255, 193, 7, 0.15);
  color: #ffc107;
  border: 1px solid rgba(255, 193, 7, 0.2);
}

.empty-queue-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  color: #444;
  font-size: 0.8rem;
}
.empty-queue-state .mdi {
  font-size: 2rem;
  margin-bottom: 10px;
}

/* Accuracy & V-Type Badges styling */
.vtype-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: bold;
  text-transform: uppercase;
  display: inline-block;
}
.badge-sm {
  font-size: 0.6rem;
  padding: 1px 4px;
}
.badge-car {
  background: rgba(23, 162, 184, 0.1);
  color: #17a2b8;
  border: 1px solid rgba(23, 162, 184, 0.2);
}
.badge-motorcycle {
  background: rgba(232, 62, 140, 0.1);
  color: #e83e8c;
  border: 1px solid rgba(232, 62, 140, 0.2);
}

/* Report Table Styling */
.report-section {
  width: 100%;
}
.report-card {
  background: #141414;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 25px;
  box-sizing: border-box;
}
.accuracy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #222;
  padding-bottom: 12px;
  margin-bottom: 20px;
}
.accuracy-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: #fff;
  display: flex;
  align-items: center;
}
.btn {
  border: none;
  padding: 8px 16px;
  border-radius: 5px;
  cursor: pointer;
  font-weight: bold;
  color: white;
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: filter 0.2s;
}
.btn:hover {
  filter: brightness(1.2);
}
.btn-warning {
  background: #ffc107;
  color: #111;
}
.btn-secondary {
  background: #222;
  border: 1px solid #333;
}
.btn-secondary:hover {
  background: #333;
}

/* Filters */
.filters-row {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1 1 180px;
}
.filter-group label {
  font-size: 0.75rem;
  color: #777;
  text-transform: uppercase;
  font-weight: 600;
}
.filter-select {
  background: #000;
  border: 1px solid #222;
  color: #fff;
  padding: 8px 12px;
  border-radius: 4px;
  outline: none;
  font-size: 0.85rem;
  font-weight: bold;
}
.filter-select:focus {
  border-color: #a855f7;
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}
.search-input {
  width: 100%;
  padding: 8px 12px 8px 35px;
  background: #000;
  border: 1px solid #222;
  color: #fff;
  border-radius: 4px;
  font-size: 0.85rem;
  outline: none;
  box-sizing: border-box;
}
.search-input:focus {
  border-color: #a855f7;
}
.search-icon {
  position: absolute;
  left: 10px;
  color: #555;
  font-size: 1.1rem;
  pointer-events: none;
}

/* Report Table values */
.table-container {
  max-height: 450px;
  overflow-y: auto;
  border: 1px solid #222;
  border-radius: 6px;
  background-color: #080808;
}
.report-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.88rem;
}
.report-table th, .report-table td {
  padding: 12px 15px;
  border-bottom: 1px solid #141414;
}
.report-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #111;
  color: #777;
  font-weight: 700;
  text-transform: uppercase;
  font-size: 0.72rem;
  border-bottom: 1px solid #222;
}
.placeholder-row {
  text-align: center;
  color: #444;
  font-style: italic;
  padding: 30px !important;
}
.plate-code {
  font-family: monospace;
  font-weight: bold;
  letter-spacing: 0.5px;
}
.result-badge {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
  display: inline-block;
  text-align: center;
}
.badge-pass {
  background: rgba(40, 167, 69, 0.15);
  color: #28a745;
  border: 1px solid rgba(40, 167, 69, 0.3);
}
.badge-fail {
  background: rgba(220, 53, 69, 0.15);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.3);
}
.row-pass {
  background: rgba(40, 167, 69, 0.01);
}
.row-fail {
  background: rgba(220, 53, 69, 0.01);
}
.row-warn {
  background: rgba(255, 193, 7, 0.01);
}
.toggle-not-detected-container {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.switch-label {
  font-size: 0.68rem;
  color: #888;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.switch {
  position: relative;
  display: inline-block;
  width: 38px;
  height: 20px;
  margin: 0;
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
  background-color: #1a1a1a;
  border: 1px solid #333;
  transition: .3s;
  border-radius: 20px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 12px;
  width: 12px;
  left: 3px;
  bottom: 3px;
  background-color: #888;
  transition: .3s;
  border-radius: 50%;
}

.switch input:checked + .slider {
  background-color: rgba(168, 85, 247, 0.2);
  border-color: #a855f7;
  box-shadow: 0 0 8px rgba(168, 85, 247, 0.4);
}

.switch input:checked + .slider:before {
  transform: translateX(18px);
  background-color: #c084fc;
  box-shadow: 0 0 6px #c084fc;
}

.switch:hover .slider {
  border-color: #555;
}

.switch:hover input:checked + .slider {
  border-color: #c084fc;
}

/* Edit Record Modal Styling */
.edit-modal-card {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  width: 100%;
  max-width: 550px;
  box-shadow: 0 15px 30px rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: scaleIn 0.25s cubic-bezier(0.1, 0.8, 0.3, 1);
}

@keyframes scaleIn {
  from { transform: scale(0.9) translateY(10px); opacity: 0; }
  to { transform: scale(1) translateY(0); opacity: 1; }
}

.close-modal-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-modal-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  max-height: 70vh;
  overflow-y: auto;
}

.modal-info-bar {
  background: #0d0d0d;
  border: 1px solid #222;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.82rem;
  color: #aaa;
}

.modal-info-bar strong {
  color: #eee;
}

.modal-images-row {
  display: flex;
  gap: 12px;
  width: 100%;
}

.modal-img-container {
  flex: 1;
  background: #0d0d0d;
  border: 1px solid #222;
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.modal-img-label {
  font-size: 0.65rem;
  color: #888;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.modal-preview-image {
  max-width: 100%;
  max-height: 120px;
  object-fit: contain;
  cursor: zoom-in;
  border-radius: 4px;
  border: 1px solid #1a1a1a;
  transition: all 0.2s ease;
}

.modal-preview-image:hover {
  transform: scale(1.03);
  border-color: #a855f7;
}

.modal-footer {
  background: #1a1a1a;
  border-top: 1px solid #2a2a2a;
  padding: 12px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.modal-footer .btn-submit-verification {
  flex: none;
  padding-left: 20px;
  padding-right: 20px;
}

/* Edit Record table badge button */
.btn-edit-record {
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all 0.2s ease;
  background: transparent;
  outline: none;
}

.btn-edit-record:hover {
  filter: brightness(1.2);
  transform: translateY(-1px);
}

.btn-edit-record:active {
  transform: translateY(0);
}

.badge-warn {
  background: rgba(255, 193, 7, 0.15);
  color: #ffc107;
  border: 1px solid rgba(255, 193, 7, 0.3);
}

/* Enlarged detected details specifically for the active camera detection details panel */
.detected-info-panel .plate-box {
  font-size: 1.55rem;
  padding: 6px 12px;
  max-width: 180px;
  border-radius: 6px;
  letter-spacing: 1px;
  border-color: rgba(168, 85, 247, 0.4);
  box-shadow: 0 0 10px rgba(255, 193, 7, 0.15);
}

.detected-info-panel .vtype-badge {
  font-size: 0.95rem;
  padding: 5px 12px;
  font-weight: 800;
  border-radius: 6px;
}
.remarks-cell {
  max-width: 250px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #999;
}
.btn-img-view {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #ccc;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}
.btn-img-view:hover {
  background: rgba(168, 85, 247, 0.15);
  color: #c084fc;
  border-color: #a855f7;
}

/* Fullscreen Overlay Modal */
.fullscreen-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: fadeIn 0.2s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.fullscreen-modal-container {
  position: relative;
  max-width: 90%;
  max-height: 90%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.fullscreen-image {
  max-width: 100%;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  border: 1px solid #333;
}
.close-overlay-btn {
  position: absolute;
  top: -45px;
  right: 0;
  background: none;
  border: none;
  color: white;
  font-size: 2rem;
  cursor: pointer;
  transition: color 0.2s;
}
.close-overlay-btn:hover {
  color: #dc3545;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 25px;
  right: 25px;
  background: #a855f7;
  color: white;
  padding: 12px 24px;
  border-radius: 6px;
  font-weight: bold;
  box-shadow: 0 10px 20px rgba(0,0,0,0.4);
  z-index: 99999;
  font-size: 0.9rem;
  animation: slideInUp 0.3s cubic-bezier(0.1, 0.8, 0.3, 1);
}
@keyframes slideInUp {
  from { transform: translateY(50px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* Responsiveness Media Queries */
@media (max-width: 1200px) {
  .workspace-layout {
    flex-direction: column;
    height: auto;
  }
  .workspace-main {
    width: 100%;
    height: 600px;
    flex: none;
  }
  .bottom-layout-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .active-workspace-content {
    flex-direction: column;
    overflow-y: auto;
  }
  .workspace-main {
    height: auto;
    min-height: 800px;
  }
  .images-panel {
    height: 380px;
    flex: none;
  }
  .controls-panel-desk {
    flex: none;
    min-width: 0;
    height: auto;
    overflow-y: visible;
  }
}

@media (max-width: 576px) {
  .testing-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  .accuracy-selection-row {
    flex-direction: column;
  }
}
</style>
