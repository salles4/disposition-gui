<template>
  <div :class="['admin-container', { light: isLightMode }]" ref="pageScroller" @scroll.passive="updateBackToTop">
    <div class="admin-header-row">
      <h1 class="page-title" style="color: #17a2b8; display: flex; align-items: center; gap: 10px;">
        <span class="mdi mdi-table-eye"></span>
        Disposition Module
      </h1>
      <div class="launcher-actions">
        <button
          type="button"
          class="btn btn-launcher btn-theme-toggle"
          :aria-pressed="isLightMode"
          :title="isLightMode ? 'Switch to dark mode' : 'Switch to light mode'"
          @click="toggleLightMode"
        >
          <span :class="['mdi', isLightMode ? 'mdi-weather-night' : 'mdi-weather-sunny']"></span>
          {{ isLightMode ? 'Dark' : 'Light' }}
        </button>
        <router-link to="/admin" class="btn btn-launcher btn-admin-launcher">
          <span class="mdi mdi-arrow-left"></span> Back to Dashboard
        </router-link>
      </div>
    </div>

    <div class="reconcile-summary-row">
      <div class="system-status-badges">
        <div class="db-badge">
          <span class="db-dot animate-pulse-slow"></span> AUDITOR ACTIVE
        </div>
        <div :class="['connection-badge', isSocketConnected ? 'online' : 'offline']">
          <span class="pulse-ping" v-if="isSocketConnected"></span>
          <span class="db-dot" v-else></span>
          {{ wsPort }}: {{ isSocketConnected ? 'ONLINE' : 'OFFLINE' }}
        </div>
        <div :class="['connection-badge', isHcpConnected ? 'online' : 'offline']">
          <span class="pulse-ping" v-if="isHcpConnected"></span>
          <span class="db-dot" v-else></span>
          {{ apiPort }}: {{ isHcpConnected ? 'ONLINE' : 'OFFLINE' }}
        </div>
      </div>
      <!-- Labels show as a popup on hover/focus (data-tip) to keep the KPI row compact -->
      <div class="summary-stats-cards">
        <div
          v-for="kpi in kpiCards"
          :key="kpi.key"
          :class="['stat-card', kpi.cls]"
          :data-tip="kpi.tip"
          :aria-label="`${kpi.tip}: ${kpi.value}`"
          tabindex="0"
        >
          <span :class="['mdi', kpi.icon, 'icon']"></span>
          <div class="stat-details">
            <span class="stat-value">{{ kpi.value }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="live-actions-card">
      <div class="card-header-with-status">
        <h2>
          <span class="mdi mdi-matrix" style="color: #ff9800;"></span>
          Detected Vehicles
        </h2>
        <button @click="toggleFilters" :class="['btn-filter-toggle', { open: showFilters }]">
          <span class="mdi mdi-filter-variant"></span>
          {{ showFilters ? 'Hide Filters' : 'Show Filters' }}
          <span v-if="activeFilterCount" class="filter-count-badge">{{ activeFilterCount }} active</span>
          <span :class="['mdi', showFilters ? 'mdi-chevron-up' : 'mdi-chevron-down']"></span>
        </button>
      </div>

      <div v-show="showFilters" class="filter-controls-row">
        <!-- Left Section: Dropdowns -->
        <div class="filter-left-section">
          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-calendar"></span> Date:</span>
            <select v-model="selectedDate" @change="fetchHistory" class="select-premium">
              <option value="today">Today</option>
              <option value="all">All Dates</option>
              <option v-for="d in availableDates" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>

          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-filter-variant"></span> Status:</span>
            <select v-model="selectedResult" class="select-premium">
              <option value="ALL">All Results</option>
              <option value="MATCHED">Matched</option>
              <option value="RESOLVED">Resolved</option>
              <option value="MISMATCH">Mismatch</option>
              <option value="PARTIAL">Partial</option>
            </select>
          </div>

          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-swap-vertical"></span> Direction:</span>
            <select v-model="selectedDirection" class="select-premium">
              <option value="ALL">Entry &amp; Exit</option>
              <option value="entry">Entry Only</option>
              <option value="exit">Exit Only</option>
            </select>
          </div>

          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-boom-gate-outline"></span> Gate:</span>
            <select v-model="selectedGate" class="select-premium">
              <option value="ALL">All Gates</option>
              <option v-for="g in availableGates" :key="g" :value="g">{{ g }}</option>
            </select>
          </div>

          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-eye-off-outline"></span> Missing:</span>
            <select v-model="selectedMissing" class="select-premium">
              <option value="ALL">Any</option>
              <option value="FRONT">No Front Camera</option>
              <option value="BACK">No Back Camera</option>
              <option value="HCP">No HikCentral</option>
              <option value="ADMIN">No Admin Read</option>
              <option value="COMPLETE">All Sources Present</option>
            </select>
          </div>

          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-car"></span> Type:</span>
            <select v-model="selectedVehicleType" class="select-premium">
              <option value="ALL">All Types</option>
              <option value="CAR">Car</option>
              <option value="MOTORCYCLE">Motorcycle</option>
            </select>
          </div>

          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-percent"></span> Confidence:</span>
            <select v-model="selectedConfidence" class="select-premium">
              <option value="ALL">Any Confidence</option>
              <option value="90">≥ 90%</option>
              <option value="80">≥ 80%</option>
              <option value="50">≥ 50%</option>
              <option value="LOW">&lt; 50%</option>
            </select>
          </div>

          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-signpost-direction"></span> Process:</span>
            <select v-model="selectedRouting" class="select-premium">
              <option value="ALL">All Processes</option>
              <option value="SYSTEM">System</option>
              <option value="TICKET">Ticket</option>
            </select>
          </div>

          <div class="filter-group">
            <span class="filter-label"><span class="mdi mdi-sort-clock-descending"></span> Sort Time:</span>
            <select v-model="sortOrderTime" class="select-premium">
              <option value="DESC">Newest First</option>
              <option value="ASC">Oldest First</option>
            </select>
          </div>

          <div class="filter-group select-premium-checkbox" style="display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; align-self: center; margin-left: 5px; height: 38px;">
            <input type="checkbox" id="excludeUnknownCheckbox" v-model="excludeUnknown" style="cursor: pointer; width: 16px; height: 16px;" />
            <label for="excludeUnknownCheckbox" class="exclude-unknown-label" style="cursor: pointer; font-size: 0.85rem; font-weight: 500; color: #cbd5e1; margin-bottom: 0;">Exclude UNKNOWN</label>
          </div>
        </div>

        <!-- Right Section: Search & Export Actions -->
        <div class="filter-right-section">
          <div class="search-box-wrapper">
            <span class="mdi mdi-magnify search-icon"></span>
            <input 
              type="text" 
              v-model="searchQuery" 
              placeholder="Search Target Plate..." 
              class="search-input"
            />
            <button v-if="searchQuery" @click="searchQuery = ''" class="clear-search-btn">&times;</button>
          </div>

          <button @click="exportToExcel" class="btn-export">
            <span class="mdi mdi-microsoft-excel text-green"></span>
            Export Excel
          </button>
        </div>
      </div>

      <div class="table-responsive">
        <table class="comparison-table">
          <thead>
            <tr>
              <th><span class="mdi mdi-clock-outline"></span> Timestamp</th>
              <th><span class="mdi mdi-key-variant"></span> {{ splitExitLayout ? 'Entry Plate Key' : 'Target Plate Key' }}</th>
              <th class="col-header-front"><span class="mdi mdi-camera"></span> Front Camera</th>
              <th class="col-header-back"><span class="mdi mdi-camera-rear"></span> Back Camera</th>
              <th class="col-header-hik"><span class="mdi mdi-server-network"></span> HikCentral Data</th>
              <th class="col-header-ops"><span class="mdi mdi-account-shield"></span> Admin Read</th>
              <th class="col-header-ops"><span class="mdi mdi-swap-horizontal"></span> Disposition</th>
              <!-- Hidden for now: Process / Validation columns
              <th class="col-header-decision"><span class="mdi mdi-swap-horizontal-bold"></span> Process</th>
              <th style="text-align: center;"><span class="mdi mdi-list-status"></span> Validation</th>
              -->
              <th v-if="splitExitLayout" class="col-header-exit" :style="{ textAlign: exitRowsRightAligned ? 'right' : 'left' }"><span class="mdi mdi-key-variant"></span> Exit Plate Key</th>
            </tr>
          </thead>
          <!-- Rows slide in, and glide into place when new ones are inserted or filters change -->
          <TransitionGroup tag="tbody" name="row">
            <tr v-if="visibleComparisonList.length === 0" key="__empty__">
              <td :colspan="splitExitLayout ? 8 : 7" class="no-data-row">
                <span v-if="searchQuery" class="mdi mdi-database-search" style="margin-right: 6px;"></span>
                <span v-else class="mdi mdi-loading mdi-spin" style="margin-right: 6px;"></span>
                {{ searchQuery ? 'No records match search filter' : 'Awaiting vehicle streaming payloads...' }}
              </td>
            </tr>
            <tr 
              v-for="(row, index) in visibleComparisonList" 
              :key="row.plate_key || index" 
              :class="['clickable-row', getRowClass(row), { 'row-align-right': splitExitLayout && exitRowsRightAligned && getRowDirection(row) === 'exit' }]"
              :style="{ '--row-i': Math.min(index, 12) }"
              @click="openDetailModal(row)"
            >
              <td class="text-muted">{{ formatTime(row.first_seen) }}</td>
              
              <td class="text-bold text-highlight">
                <template v-if="!splitExitLayout || getRowDirection(row) !== 'exit'">
                <div class="plate-code-display" style="font-size: 1.05rem;">{{ displayPlate(row.plate_key) }}</div>
                <div style="margin-top: 5px; display: flex; gap: 4px; flex-wrap: wrap;">
                  <span class="badge-sm badge-gate" style="background: rgba(255,255,255,0.06); color: #cbd5e1; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase;">
                    {{ row.gate || 'GATE 1' }}
                  </span>
                  <span :class="['badge-sm', (row.direction || 'entry') === 'entry' ? 'badge-dir-entry' : 'badge-dir-exit']" :style="{
                    background: (row.direction || 'entry') === 'entry' ? 'rgba(40,167,69,0.15)' : 'rgba(23,162,184,0.15)',
                    color: (row.direction || 'entry') === 'entry' ? '#2ebd4e' : '#00bcd4',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '0.7rem',
                    fontWeight: '700',
                    textTransform: 'uppercase'
                  }">
                    {{ row.direction || 'entry' }}
                  </span>
                </div>
                </template>
              </td>

              <td class="col-cell-front">
                <Transition name="cell-fade" mode="out-in">
                <div v-if="row.front_camera" class="source-cell-block">
                  <div :class="['plate-badge', 'badge-front', { 'badge-chosen': getHigherConfidenceCamera(row) === 'front' }]">{{ row.front_camera.plate || displayPlate(row.plate_key) }}</div>
                  <div class="nested-type-row">
                    <span class="type-text">{{ row.front_camera.vehicle_type }}</span>
                    <span :class="['conf-text', getConfidenceClass(row.front_camera.confidence)]">({{ row.front_camera.confidence }}%)</span>
                  </div>
                  <div class="cell-timestamp text-muted">
                    <span class="mdi mdi-clock-outline"></span> {{ formatTime(row.front_camera.timestamp) }}
                  </div>
                </div>
                <span v-else class="text-muted">— Missing —</span>
                </Transition>
              </td>
              
              <td class="col-cell-back">
                <Transition name="cell-fade" mode="out-in">
                <div v-if="row.back_camera" class="source-cell-block">
                  <div :class="['plate-badge', 'badge-back', { 'badge-chosen': getHigherConfidenceCamera(row) === 'back' }]">{{ row.back_camera.plate || displayPlate(row.plate_key) }}</div>
                  <div class="nested-type-row">
                    <span class="type-text">{{ row.back_camera.vehicle_type }}</span>
                    <span :class="['conf-text', getConfidenceClass(row.back_camera.confidence)]">({{ row.back_camera.confidence }}%)</span>
                  </div>
                  <div class="cell-timestamp text-muted">
                    <span class="mdi mdi-clock-outline"></span> {{ formatTime(row.back_camera.timestamp) }}
                  </div>
                </div>
                <span v-else class="text-muted">— Missing —</span>
                </Transition>
              </td>
              
              <td class="col-cell-hik">
                <Transition name="cell-fade" mode="out-in">
                <div v-if="row.hikcentral" class="source-cell-block">
                  <div class="plate-badge badge-hik">{{ row.hikcentral.plate || 'EMPTY' }}</div>
                  <div class="nested-type-row">
                    <span class="type-text text-orange">{{ row.hikcentral.vehicleType }}</span>
                  </div>
                  <div class="cell-timestamp text-muted">
                    <span class="mdi mdi-clock-outline"></span> {{ formatTime(row.hikcentral.timestamp) }}
                  </div>
                </div>
                <span v-else class="text-muted">— Missing —</span>
                </Transition>
              </td>

              <td class="col-cell-ops">
                <Transition name="cell-fade" mode="out-in">
                <div v-if="row.core_event" class="source-cell-block">
                  <div class="plate-badge badge-admin">{{ row.core_event.plate_no || displayPlate(row.plate_key) }}</div>
                  <div class="nested-type-row">
                    <span class="type-text text-purple">{{ row.core_event.vehicle_type_code }}</span>
                  </div>
                  <div class="cell-timestamp text-muted">
                    <span class="mdi mdi-clock-outline"></span> {{ formatTime(row.core_event.timestamp) }}
                  </div>
                </div>
                <span v-else class="text-muted">— Pending —</span>
                </Transition>
              </td>

              <td class="col-cell-ops" style="vertical-align: middle;">
                <Transition name="cell-fade" mode="out-in">
                <span :key="row.disposition || 'NA'" :class="['dispo-tag', (row.disposition || 'NA').toLowerCase().replace(' ', '_')]">
                  {{ row.disposition || 'NA' }}
                </span>
                </Transition>
              </td>

              <td v-if="splitExitLayout" class="col-cell-exit text-bold text-highlight">
                <template v-if="getRowDirection(row) === 'exit'">
                  <div class="plate-code-display" style="font-size: 1.05rem;">{{ displayPlate(row.plate_key) }}</div>
                  <div style="margin-top: 5px; display: flex; gap: 4px; flex-wrap: wrap;">
                    <span class="badge-sm badge-gate" style="background: rgba(255,255,255,0.06); color: #cbd5e1; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase;">
                      {{ row.gate || 'GATE 1' }}
                    </span>
                    <span class="badge-sm badge-dir-exit" style="background: rgba(23,162,184,0.15); color: #00bcd4; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase;">
                      exit
                    </span>
                  </div>
                </template>
              </td>

              <!-- Hidden for now: Process / Validation columns (v-if instead of a comment, since the cell already contains one) -->
              <template v-if="false">
              <td class="col-cell-decision" style="vertical-align: middle;">
                <span :class="['decision-tag', getTicketingDecision(row).toLowerCase()]">
                  {{ getTicketingDecision(row) === 'TICKET' ? 'Ticket' : 'System' }}
                </span>
              </td>
              
              <td style="text-align: center; vertical-align: middle;">
                <div class="validation-container">
                  <span :class="['status-tag', getValidationInfo(row).status]">
                    <span v-if="getValidationInfo(row).status === 'matched'" class="mdi mdi-check-circle animate-check"></span>
                    <span v-else-if="getValidationInfo(row).status === 'corrected'" class="mdi mdi-alert-decagram animate-pulse-slow"></span>
                    <span v-else-if="getValidationInfo(row).status === 'mismatch'" class="mdi mdi-alert-circle animate-shake"></span>
                    <span v-else class="mdi mdi-help-circle"></span>
                    {{ getValidationInfo(row).text }}
                  </span>
                  <div v-if="getValidationInfo(row).status === 'corrected'" class="correction-details">
                    <span class="mdi mdi-arrow-right-bold"></span>
                    <span class="plate-mini">{{ getValidationInfo(row).correctData.plate }}</span>
                    <span class="source-mini">({{ getValidationInfo(row).correctSource }})</span>
                  </div>
                  <!-- <div v-else class="validation-details-text">
                    {{ getValidationInfo(row).details }}
                  </div> -->
                </div>
              </td>
              </template>
            </tr>
          </TransitionGroup>
        </table>
        <div v-if="filteredComparisonList.length > displayLimit" class="load-more-container">
          <button @click="displayLimit += 200" class="btn-load-more">
            <span class="mdi mdi-loading mdi-spin text-orange"></span>
            Loading More Records (Showing {{ displayLimit }} of {{ filteredComparisonList.length }})
          </button>
        </div>
        <!-- Inside the scrolling table box so infinite scroll follows the table's own scroll -->
        <div ref="loadMoreTrigger" style="height: 10px; margin-top: 10px;"></div>
      </div>
    </div>

    <Transition name="back-to-top">
      <button v-if="showBackToTop" class="btn-back-to-top" @click="scrollToTop" aria-label="Back to top" title="Back to top">
        <span class="mdi mdi-arrow-up"></span>
      </button>
    </Transition>

    <Transition name="modal">
      <div class="modal-overlay" v-if="selectedVehicle" @click.self="closeModal">
        <div class="modal-card">
          <div class="modal-header">
            <h3>
              <span class="mdi mdi-image-multiple" style="color: #17a2b8;"></span>
              Deep Audit Profile Explorer: <span class="modal-plate-title" style="color: #ffc107;">{{ displayPlate(selectedVehicle.plate_key) }}</span>
            </h3>
            <button class="close-btn" @click="closeModal">&times;</button>
          </div>
          
          <div class="meta-summary-footer">
            <div class="meta-item">
              <strong>Evaluation Match Integrity Status:</strong>
              <span :class="['status-tag', getValidationInfo(selectedVehicle).status]" style="margin-left: 8px;">
                {{ getValidationInfo(selectedVehicle).text }}
              </span>
            </div>
            <div class="meta-item" v-if="getValidationInfo(selectedVehicle).status === 'corrected'">
              <strong>Resolution:</strong>
              <span class="text-highlight">Use {{ getValidationInfo(selectedVehicle).correctSource }} ({{ getValidationInfo(selectedVehicle).correctData.plate }} - {{ getValidationInfo(selectedVehicle).correctData.vehicleType }})</span>
            </div>
            <div class="meta-item">
              <strong>Calculated Automated System Disposition:</strong> <span class="text-warn">{{ selectedVehicle.disposition || 'NA' }}</span>
            </div>
            <div class="meta-item">
              <strong>Process Mode:</strong>
              <span :class="['decision-tag', getTicketingDecision(selectedVehicle).toLowerCase()]" style="margin-left: 8px;">
                {{ getTicketingDecision(selectedVehicle) === 'TICKET' ? 'Ticket' : 'System' }}
              </span>
              <span class="text-dim" style="margin-left: 8px;" v-if="getTicketingRecommendation(selectedVehicle).reason">
                ({{ getTicketingRecommendation(selectedVehicle).reason }})
              </span>
            </div>
          </div>

          <div class="modal-body">
            <div class="modal-split-layout">
              
              <div class="media-gallery-pane">
                
                <div class="camera-gallery-section section-front">
                  <h3><span class="mdi mdi-camera"></span> Front Camera Media Frames (192.168.0.64)</h3>
                  <div class="frames-split-row" v-if="!mediaLoading">
                    <div class="gallery-image-wrapper image-crop">
                      <h5>Plate Text Crop</h5>
                      <img v-if="loadedMedia.front_plate_image" :src="loadedMedia.front_plate_image" />
                      <div v-else class="no-img-box">No Frame Buffer</div>
                    </div>
                    <div class="gallery-image-wrapper image-scene">
                      <h5>Context Scene Capture (detectionPicture.jpg)</h5>
                      <img v-if="loadedMedia.front_vehicle_image" :src="loadedMedia.front_vehicle_image" />
                      <div v-else class="no-img-box">No Scene Frame Buffer</div>
                    </div>
                  </div>
                  <div v-else class="media-loader-box"><span class="mdi mdi-loading mdi-spin"></span> Lazy loading base64 images from disk...</div>
                </div>

                <div class="camera-gallery-section section-back">
                  <h3><span class="mdi mdi-camera-rear"></span> Back Camera Media Frames (192.168.0.65)</h3>
                  <div class="frames-split-row" v-if="!mediaLoading">
                    <div class="gallery-image-wrapper image-crop">
                      <h5>Plate Text Crop</h5>
                      <img v-if="loadedMedia.back_plate_image" :src="loadedMedia.back_plate_image" />
                      <div v-else class="no-img-box">No Frame Buffer</div>
                    </div>
                    <div class="gallery-image-wrapper image-scene">
                      <h5>Context Scene Capture (detectionPicture.jpg)</h5>
                      <img v-if="loadedMedia.back_vehicle_image" :src="loadedMedia.back_vehicle_image" />
                      <div v-else class="no-img-box">No Scene Frame Buffer</div>
                    </div>
                  </div>
                  <div v-else class="media-loader-box"><span class="mdi mdi-loading mdi-spin"></span> Lazy loading base64 images from disk...</div>
                </div>

                <div class="camera-gallery-section section-admin-http" v-if="selectedVehicle.core_event && selectedVehicle.core_event.image_url">
                  <h3 style="color: #a855f7;"><span class="mdi mdi-web"></span> Core System Static HTTP Image Source</h3>
                  <div class="gallery-image-wrapper image-scene-full">
                    <h5>HCP Back Image Target Endpoint Link</h5>
                    <img :src="selectedVehicle.core_event.image_url" alt="Admin Socket Target HTTP View" />
                    <div class="http-link-label">{{ selectedVehicle.core_event.image_url }}</div>
                  </div>
                </div>
              </div>

              <div class="telemetry-data-pane">
                <div class="data-block-card">
                  <h4><span class="mdi mdi-text-box-search"></span> Source Telemetry Metadata</h4>
                  <div class="telemetry-scroll-box">
                    
                    <h5 class="sub-header-purple">Admin Read (Core Display)</h5>
                    <div v-if="selectedVehicle.core_event" class="telemetry-group">
                      <div class="data-row"><span class="label">Time:</span><span class="val text-dim">{{ selectedVehicle.core_event.timestamp }}</span></div>
                      <div class="data-row"><span class="label">Plate:</span><span class="val highlight-text">{{ selectedVehicle.core_event.plate_no }}</span></div>
                      <div class="data-row"><span class="label">Normalized Category:</span><span class="val">{{ selectedVehicle.core_event.vehicle_type_code }}</span></div>
                      <div class="data-row"><span class="label">Raw Code Received:</span><span class="val text-orange">{{ selectedVehicle.core_event.raw_type_received }}</span></div>
                      <div class="data-row"><span class="label">Gate ID Node:</span><span class="val">Gate {{ selectedVehicle.core_event.gate_id }}</span></div>
                      <div class="data-row"><span class="label">Percentage Factor:</span><span class="val" v-if="selectedVehicle.core_event.percentage">{{ selectedVehicle.core_event.percentage }}%</span><span class="val" v-else>N/A</span></div>
                    </div>
                    <div v-else class="no-data-msg">No entries logged.</div>

                    <h5 class="sub-header-cyan">Front Camera Read</h5>
                    <div v-if="selectedVehicle.front_camera" class="telemetry-group">
                      <div class="data-row"><span class="label">Time:</span><span class="val text-dim">{{ formatTime(selectedVehicle.front_camera.timestamp) }}</span></div>
                      <div class="data-row"><span class="label">Plate:</span><span class="val highlight-text">{{ selectedVehicle.front_camera.plate }}</span></div>
                      <div class="data-row"><span class="label">Normalized Category:</span><span class="val">{{ selectedVehicle.front_camera.vehicle_type }}</span></div>
                      <div class="data-row"><span class="label">Raw String Type:</span><span class="val text-orange">{{ selectedVehicle.front_camera.raw_type_received }}</span></div>
                      <div class="data-row"><span class="label">OCR Confidence:</span><span class="val">{{ selectedVehicle.front_camera.confidence }}%</span></div>
                    </div>
                    <div v-else class="no-data-msg">No entry stream received.</div>

                    <h5 class="sub-header-green">Back Camera Read</h5>
                    <div v-if="selectedVehicle.back_camera" class="telemetry-group">
                      <div class="data-row"><span class="label">Time:</span><span class="val text-dim">{{ formatTime(selectedVehicle.back_camera.timestamp) }}</span></div>
                      <div class="data-row"><span class="label">Plate:</span><span class="val highlight-text">{{ selectedVehicle.back_camera.plate }}</span></div>
                      <div class="data-row"><span class="label">Normalized Category:</span><span class="val">{{ selectedVehicle.back_camera.vehicle_type }}</span></div>
                      <div class="data-row"><span class="label">Raw String Type:</span><span class="val text-orange">{{ selectedVehicle.back_camera.raw_type_received }}</span></div>
                      <div class="data-row"><span class="label">OCR Confidence:</span><span class="val">{{ selectedVehicle.back_camera.confidence }}%</span></div>
                    </div>
                    <div v-else class="no-data-msg">No entry stream received.</div>

                    <h5 class="sub-header-orange">HikCentral Server</h5>
                    <div v-if="selectedVehicle.hikcentral" class="telemetry-group">
                      <div class="data-row"><span class="label">Time:</span><span class="val text-dim">{{ selectedVehicle.hikcentral.timestamp }}</span></div>
                      <div class="data-row"><span class="label">Plate:</span><span class="val highlight-text">{{ selectedVehicle.hikcentral.plate }}</span></div>
                      <div class="data-row"><span class="label">Normalized Category:</span><span class="val">{{ selectedVehicle.hikcentral.vehicleType }}</span></div>
                      <div class="data-row"><span class="label">Raw String Type:</span><span class="val text-orange">{{ selectedVehicle.hikcentral.raw_type_received }}</span></div>
                      <div class="data-row"><span class="label">Lane Node Name:</span><span class="val">{{ selectedVehicle.hikcentral.gateName }}</span></div>
                    </div>
                    <div v-else class="no-data-msg">No entry stream received.</div>

                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>
    </Transition>

    <TokenPrompt :socket="socket" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'
import TokenPrompt from '@/components/TokenPrompt.vue'

const displayPlate = (key) => {
  if (!key) return ''
  return key.split('_')[0]
}

const socket = io(import.meta.env.DEV ? `http://${window.location.hostname}:${import.meta.env.VITE_WS_PORT || '5015'}` : window.location.origin)

// Server addresses come from the backend config (servers section, editable on the admin dashboard)
const servers = ref({})
const wsPort = computed(() => servers.value.app_port || import.meta.env.VITE_WS_PORT || '5015')
const apiPort = computed(() => {
  try {
    const parsed = new URL(servers.value.api_base_url)
    return parsed.port || (parsed.protocol === 'https:' ? '443' : '80')
  } catch {
    return '—'
  }
})
const comparisonList = ref([])
const allTimeStats = ref({ matched: 0, corrected: 0, mismatch: 0, partial: 0, total: 0 })
const searchQuery = ref('')
const displayLimit = ref(200)
const loadMoreTrigger = ref(null)
const pageScroller = ref(null)

// Back-to-top shows once the page is scrolled well down
const BACK_TO_TOP_THRESHOLD = 400
const showBackToTop = ref(false)
const updateBackToTop = () => {
  showBackToTop.value = (pageScroller.value?.scrollTop || 0) > BACK_TO_TOP_THRESHOLD
}
const scrollToTop = () => {
  const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
  pageScroller.value?.scrollTo({ top: 0, behavior })
}
let observer = null

// System status states
const isSocketConnected = ref(false)
const isHcpConnected = ref(false)
const isCameraOnline = ref(true)
const lastCameraActivity = ref(Date.now())
let cameraTimer = null

const selectedDate = ref('today')
const selectedResult = ref('ALL')
const selectedVehicleType = ref('ALL')
const selectedConfidence = ref('ALL')
const selectedRouting = ref('ALL')
const sortOrderTime = ref('DESC')
const excludeUnknown = ref(true)
const selectedDirection = ref('ALL')
const selectedGate = ref('ALL')
const selectedMissing = ref('ALL')
const availableDates = ref([])

// Filter bar is collapsed by default; remember the viewer's choice
const FILTERS_OPEN_KEY = 'comparison_filters_open'
const readFiltersOpen = () => {
  try { return localStorage.getItem(FILTERS_OPEN_KEY) === '1' } catch { return false }
}
const showFilters = ref(readFiltersOpen())
const toggleFilters = () => {
  showFilters.value = !showFilters.value
  try { localStorage.setItem(FILTERS_OPEN_KEY, showFilters.value ? '1' : '0') } catch { /* storage unavailable */ }
}

// Dashboard settings, both on by default:
// split_exit_layout = separate Exit plate column; exit_rows_right_aligned = exit rows read from the right (split only)
const splitExitLayout = ref(true)
const exitRowsRightAligned = ref(true)

// Light mode for readability in bright surroundings (remembered per browser)
const LIGHT_MODE_KEY = 'comparison_light_mode'
const readLightMode = () => {
  try { return localStorage.getItem(LIGHT_MODE_KEY) === '1' } catch { return false }
}
const isLightMode = ref(readLightMode())
const toggleLightMode = () => {
  isLightMode.value = !isLightMode.value
  try { localStorage.setItem(LIGHT_MODE_KEY, isLightMode.value ? '1' : '0') } catch { /* storage unavailable */ }
}

// Non-default filters, shown on the toggle so collapsed filters never silently hide rows
const activeFilterCount = computed(() => [
  selectedDate.value !== 'today',
  selectedResult.value !== 'ALL',
  selectedDirection.value !== 'ALL',
  selectedGate.value !== 'ALL',
  selectedMissing.value !== 'ALL',
  selectedVehicleType.value !== 'ALL',
  selectedConfidence.value !== 'ALL',
  selectedRouting.value !== 'ALL',
  !excludeUnknown.value,
  !!searchQuery.value.trim()
].filter(Boolean).length)

const fetchHistory = () => {
  socket.emit('request_reconciliation_history', { date: selectedDate.value })
}

const loadSheetJS = () => {
  return new Promise((resolve, reject) => {
    if (window.XLSX) {
      resolve(window.XLSX)
      return
    }
    const script = document.createElement('script')
    // Use xlsx-js-style library bundle for style formatting support
    script.src = 'https://cdn.jsdelivr.net/npm/xlsx-js-style@1.2.0/dist/xlsx.bundle.js'
    script.onload = () => resolve(window.XLSX)
    script.onerror = reject
    document.head.appendChild(script)
  })
}

const exportToExcel = async () => {
  try {
    const XLSX = await loadSheetJS()
    
    // Define headers
    const headers = [
      "Date & Time",
      "Front Cam Plate",
      "Front Cam Vehicle Type",
      "Back Cam Plate",
      "Back Cam Vehicle Type",
      "HCP Plate",
      "HCP Vehicle Type",
      "Admin Plate",
      "Admin Vehicle Type",
      "Disposition Result",
      "Process Mode",
      "Verification Result"
    ]
    
    const ws = {}
    
    // Header Style (Premium Dark Header)
    const headerStyle = {
      fill: {
        patternType: "solid",
        fgColor: { rgb: "1F1F1F" }
      },
      font: {
        name: "Segoe UI",
        sz: 11,
        bold: true,
        color: { rgb: "FFFFFF" }
      },
      alignment: {
        horizontal: "center",
        vertical: "center"
      },
      border: {
        bottom: { style: "medium", color: { rgb: "444444" } }
      }
    }

    // Default cell styling
    const defaultStyle = {
      font: { name: "Segoe UI", sz: 10 },
      alignment: { vertical: "center" }
    }
    
    // Set headers
    headers.forEach((header, colIdx) => {
      const cellRef = XLSX.utils.encode_cell({ r: 0, c: colIdx })
      ws[cellRef] = { v: header, t: 's', s: headerStyle }
    })
    
    // Status colors cell styling helper
    const getStatusStyle = (statusText) => {
      const baseStyle = {
        font: { name: "Segoe UI", sz: 10, bold: true },
        alignment: { horizontal: "center", vertical: "center" },
        fill: { patternType: "solid" }
      }
      
      const cleanText = (statusText || "").toUpperCase()
      if (cleanText === "MATCHED") {
        baseStyle.fill.fgColor = { rgb: "D4EDDA" } // soft green
        baseStyle.font.color = { rgb: "155724" }   // dark green
      } else if (cleanText === "RESOLVED" || cleanText === "CORRECTED") {
        baseStyle.fill.fgColor = { rgb: "D1ECF1" } // soft cyan
        baseStyle.font.color = { rgb: "0C5460" }   // dark cyan
      } else if (cleanText === "MISMATCH") {
        baseStyle.fill.fgColor = { rgb: "F8D7DA" } // soft red
        baseStyle.font.color = { rgb: "721C24" }   // dark red
      } else { // PARTIAL
        baseStyle.fill.fgColor = { rgb: "FFF3CD" } // soft yellow
        baseStyle.font.color = { rgb: "856404" }   // dark yellow
      }
      return baseStyle
    }

    // Add rows
    filteredComparisonList.value.forEach((row, rowIdx) => {
      const excelRow = rowIdx + 2 // 1-based index (row 1 is header)
      
      const colValues = [
        formatTime(row.first_seen) || "",
        row.front_camera ? (row.front_camera.plate || "") : "",
        row.front_camera ? (row.front_camera.vehicle_type || "") : "",
        row.back_camera ? (row.back_camera.plate || "") : "",
        row.back_camera ? (row.back_camera.vehicle_type || "") : "",
        row.hikcentral ? (row.hikcentral.plate || "") : "",
        row.hikcentral ? (row.hikcentral.vehicleType || "") : "",
        row.core_event ? (row.core_event.plate_no || "") : "",
        row.core_event ? (row.core_event.vehicle_type_code || "") : ""
      ]
      
      colValues.forEach((val, colIdx) => {
        const cellRef = XLSX.utils.encode_cell({ r: rowIdx + 1, c: colIdx })
        ws[cellRef] = { v: val, t: 's', s: defaultStyle }
      })
      
      // Column J: Disposition Result (index 9)
      const dispCellRef = XLSX.utils.encode_cell({ r: rowIdx + 1, c: 9 })
      ws[dispCellRef] = { v: row.disposition || "NA", t: 's', s: defaultStyle }

      // Column K: Routing Decision (index 10)
      const routeCellRef = XLSX.utils.encode_cell({ r: rowIdx + 1, c: 10 })
      ws[routeCellRef] = { v: getTicketingDecision(row), t: 's', s: defaultStyle }
      
      // Column L: Verification Result (index 11)
      const verCellRef = XLSX.utils.encode_cell({ r: rowIdx + 1, c: 11 })
      const validationText = getValidationInfo(row).text || "PARTIAL"
      ws[verCellRef] = { v: validationText, t: 's', s: getStatusStyle(validationText) }
    })
    
    // Set ref
    const maxRow = filteredComparisonList.value.length
    ws['!ref'] = XLSX.utils.encode_range({
      s: { r: 0, c: 0 },
      e: { r: maxRow, c: headers.length - 1 }
    })
    
    // Column widths
    ws['!cols'] = [
      { wch: 15 }, // Date & Time
      { wch: 18 }, // Front Cam Plate
      { wch: 22 }, // Front Cam Vehicle Type
      { wch: 18 }, // Back Cam Plate
      { wch: 22 }, // Back Cam Vehicle Type
      { wch: 15 }, // HCP Plate
      { wch: 18 }, // HCP Vehicle Type
      { wch: 15 }, // Admin Plate
      { wch: 20 }, // Admin Vehicle Type
      { wch: 20 }, // Disposition Result
      { wch: 18 }, // Process Mode
      { wch: 20 }  // Verification Result
    ]
    
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, "Reconciliation Report")
    
    const dateStr = selectedDate.value === 'today' ? new Date().toISOString().split('T')[0] : selectedDate.value
    XLSX.writeFile(wb, `Reconciliation_Report_${dateStr}.xlsx`)
  } catch (err) {
    console.error("Failed to export Excel report:", err)
    alert("Failed to load Excel library. Please check your internet connection.")
  }
}

const getRowVehicleType = (row) => {
  if (!row) return 'UNKNOWN'
  if (row.core_event && row.core_event.vehicle_type_code) {
    return row.core_event.vehicle_type_code.toUpperCase()
  }
  // Try higher confidence camera
  const chosenCam = getHigherConfidenceCamera(row)
  if (chosenCam === 'front' && row.front_camera && row.front_camera.vehicle_type) {
    return row.front_camera.vehicle_type.toUpperCase()
  }
  if (chosenCam === 'back' && row.back_camera && row.back_camera.vehicle_type) {
    return row.back_camera.vehicle_type.toUpperCase()
  }
  if (row.front_camera && row.front_camera.vehicle_type) {
    return row.front_camera.vehicle_type.toUpperCase()
  }
  if (row.back_camera && row.back_camera.vehicle_type) {
    return row.back_camera.vehicle_type.toUpperCase()
  }
  if (row.hikcentral && row.hikcentral.vehicleType) {
    return row.hikcentral.vehicleType.toUpperCase()
  }
  return 'UNKNOWN'
}

const motorcyclePatterns = [
  /^\d{4}[A-Z]{2}$/,       // Legacy MC (e.g., 2724SO)
  /^[A-Z]{2}\d{5}$/,       // 2 Letters, 5 Numbers (AB12345)
  /^[A-Z]{3}\d{5}$/,       // 3 Letters, 5 Numbers (ABC12345)
  /^[A-Z]\d{5}[A-Z]$/,     // 1 Letter, 5 Numbers, 1 Letter (N12345A)
  /^\d{3}[A-Z]{3}$/,       // 3 Numbers, 3 Letters (123ABC)
  /^[A-Z]\d{3}[A-Z]{2}$/,  // A 123 BC
  /^[A-Z]{2}\d{3}[A-Z]$/,  // AB 123 C
  /^\d[A-Z]{3}\d{2}$/,     // 1 ABC 23
  /^[A-Z]\d{4}[A-Z]$/,     // A 1234 C
  /^[A-Z]\d[A-Z]\d{3}$/,   // A 1 C 234
  /^[A-Z]{2}\d{2}[A-Z]\d{2}$/ // A 12 C 34
]

const carPatterns = [
  // --- Standard 4-Wheel MV Formats ---
  /^[A-Z]{3}\d{4}$/,       // 3 Letters, 4 Numbers (ABC1234)
  /^[A-Z]{3}\d{3}$/,       // 3 Letters, 3 Numbers (WFU799)
  /^[A-Z]{2}\d{4}$/,       // 2 Letters, 4 Numbers (Government/Electric/Conduction SE1234)
  
  // --- Conduction Stickers & Temporary Plates ---
  /^[A-Z]\d{4}$/,          // 1 Letter, 4 Numbers (Legacy Conduction)
  
  // --- LTO MV File Numbers (Temporary registrations) ---
  /^\d{11}$/,              // 11-Digit Pure Numerical File Block (13010000123)
  /^\d{10}$/,              // 10-Digit Pure Numerical File Block
  
  // --- Protocol & Diplomatic Formats ---
  /^\d{1,2}$/,             // 1 to 2 Digit Government Protocol Keys (1 to 16)
  /^\d{7}$/                // 7-Digit Diplomatic Plates (1234567)
]

const isValidPlateFormat = (plate) => {
  if (!plate || typeof plate !== 'string') return false
  const clean = plate.replace(/[\s-]+/g, '').toUpperCase()
  if (!clean) return false
  return motorcyclePatterns.some(pattern => pattern.test(clean)) || carPatterns.some(pattern => pattern.test(clean))
}

const getTicketingRecommendation = (row) => {
  const plate = displayPlate(row.plate_key) || ''
const clean = plate.replace(/\s+/g, '').toUpperCase()

if (!clean) return { recommend: true, reason: 'Empty Read' }

const motorcyclePatterns = [
  /^\d{4}[A-Z]{2}$/,       // Legacy MC - FROM YOUR IMAGE (e.g., 2724SO)
  /^[A-Z]{2}\d{5}$/,       // 2 Letters, 5 Numbers (AB12345)
  /^[A-Z]{3}\d{5}$/,       // 3 Letters, 5 Numbers (ABC12345)
  /^[A-Z]\d{5}[A-Z]$/,     // 1 Letter, 5 Numbers, 1 Letter (N12345A)
  /^\d{3}[A-Z]{3}$/,       // 3 Numbers, 3 Letters (123ABC)
  /^[A-Z]\d{3}[A-Z]{2}$/,  // A 123 BC
  /^[A-Z]{2}\d{3}[A-Z]$/,  // AB 123 C
  /^\d[A-Z]{3}\d{2}$/,     // 1 ABC 23
  /^[A-Z]\d{4}[A-Z]$/,     // A 1234 C
  /^[A-Z]\d[A-Z]\d{3}$/,   // A 1 C 234
  /^[A-Z]\d{2}[A-Z]\d{2}$/ // A 12 C 34
]

const carPatterns = [
  // --- Standard 4-Wheel MV Formats ---
  /^[A-Z]{3}\d{4}$/,       // 3 Letters, 4 Numbers (ABC1234)
  /^[A-Z]{3}\d{3}$/,       // 3 Letters, 3 Numbers (WFU799)
  /^[A-Z]{2}\d{4}$/,       // 2 Letters, 4 Numbers (Government/Electric/Conduction SE1234)
  
  // --- Conduction Stickers & Temporary Plates ---
  /^[A-Z]\d{4}$/,          // 1 Letter, 4 Numbers (Legacy Conduction)
  
  // --- LTO MV File Numbers (Temporary registrations) ---
  /^\d{11}$/,              // 11-Digit Pure Numerical File Block (13010000123)
  /^\d{10}$/,              // 10-Digit Pure Numerical File Block
  
  // --- Protocol & Diplomatic Formats ---
  /^\d{1,2}$/,             // 1 to 2 Digit Government Protocol Keys (1 to 16)
  /^\d{7}$/                // 7-Digit Diplomatic Plates (1234567)
]

  const isMotorcyclePattern = motorcyclePatterns.some(pattern => pattern.test(clean))
  const isCarPattern = carPatterns.some(pattern => pattern.test(clean))

  if (!isMotorcyclePattern && !isCarPattern) {
    const rowType = getRowVehicleType(row)
    if (rowType === 'MOTORCYCLE') {
      return { recommend: true, reason: 'Invalid Motorcycle Format (Expected: AB12345, 123ABC, A12C34, A1C234, A1234C, etc.)' }
    } else if (rowType === 'CAR') {
      return { recommend: true, reason: 'Invalid Car Format (Expected: ABC1234, WFU799, SE1234, etc.)' }
    }
    return { recommend: true, reason: 'Invalid Format' }
  }

  const rowType = getRowVehicleType(row)
  
  if (rowType !== 'UNKNOWN') {
    if (isMotorcyclePattern && rowType === 'CAR') {
      return { recommend: true, reason: 'Type Mismatch (Motorcycle plate on Car)' }
    }
    if (isCarPattern && rowType === 'MOTORCYCLE') {
      return { recommend: true, reason: 'Type Mismatch (Car plate on Motorcycle)' }
    }
  }

  return { recommend: false, reason: 'Valid Format and Type' }
}

const getTicketingDecision = (row) => {
  if (row.ticketing_decision) {
    return row.ticketing_decision
  }
  return getTicketingRecommendation(row).recommend ? 'TICKET' : 'SYSTEM'
}

const updateTicketingDecision = (row, decision) => {
  row.ticketing_decision = decision
  socket.emit('update_ticketing_decision', {
    plate_key: row.plate_key,
    date: row.first_seen,
    decision: decision
  })
}

const getRowDirection = (row) => (row.direction || 'entry').toLowerCase()
const getRowGate = (row) => (row.gate || 'GATE 1').toUpperCase()

const availableGates = computed(() => {
  const gates = new Set(comparisonList.value.map(getRowGate))
  return [...gates].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
})

const kpiFilteredList = computed(() => {
  let list = comparisonList.value

  // 0. Filter out UNKNOWN plates if excludeUnknown is active
  if (excludeUnknown.value) {
    list = list.filter(row => {
      const pk = (row.plate_key || '').toUpperCase()
      const fPlate = (row.front_camera?.plate || '').toUpperCase()
      const bPlate = (row.back_camera?.plate || '').toUpperCase()
      const hPlate = (row.hikcentral?.plate || '').toUpperCase()
      const cPlate = (row.core_event?.plate_no || '').toUpperCase()
      
      const isPkUnknown = pk.includes('UNKNOWN') || !pk
      const isFUnknown = fPlate.includes('UNKNOWN')
      const isBUnknown = bPlate.includes('UNKNOWN')
      const isHUnknown = hPlate.includes('UNKNOWN')
      const isCUnknown = cPlate.includes('UNKNOWN')
      
      return !(isPkUnknown || isFUnknown || isBUnknown || isHUnknown || isCUnknown)
    })
  }

  // 0b. Filter by Direction / Gate (rows without a value are shown as GATE 1 / entry)
  if (selectedDirection.value !== 'ALL') {
    list = list.filter(row => getRowDirection(row) === selectedDirection.value)
  }
  if (selectedGate.value !== 'ALL') {
    list = list.filter(row => getRowGate(row) === selectedGate.value)
  }

  // 0c. Filter by missing source
  if (selectedMissing.value !== 'ALL') {
    list = list.filter(row => {
      switch (selectedMissing.value) {
        case 'FRONT': return !row.front_camera
        case 'BACK': return !row.back_camera
        case 'HCP': return !row.hikcentral
        case 'ADMIN': return !row.core_event
        case 'COMPLETE': return row.front_camera && row.back_camera && row.hikcentral && row.core_event
        default: return true
      }
    })
  }

  // 1. Filter by Vehicle Type
  if (selectedVehicleType.value !== 'ALL') {
    list = list.filter(row => {
      const vType = selectedVehicleType.value
      // Check if any of the sources have this vehicle type
      const fType = row.front_camera?.vehicle_type?.toUpperCase() || ''
      const bType = row.back_camera?.vehicle_type?.toUpperCase() || ''
      const cType = row.core_event?.vehicle_type_code?.toUpperCase() || ''
      const hType = row.hikcentral?.vehicleType?.toUpperCase() || ''
      return fType.includes(vType) || bType.includes(vType) || cType.includes(vType) || hType.includes(vType)
    })
  }

  // 2. Filter by Confidence
  if (selectedConfidence.value !== 'ALL') {
    list = list.filter(row => {
      const frontConf = parseFloat(row.front_camera?.confidence) || 0
      const backConf = parseFloat(row.back_camera?.confidence) || 0
      const maxConf = Math.max(frontConf, backConf)
      if (selectedConfidence.value === 'LOW') return maxConf < 50
      return maxConf >= parseInt(selectedConfidence.value)
    })
  }

  // 3. Filter by Routing Decision
  if (selectedRouting.value !== 'ALL') {
    list = list.filter(row => {
      const decision = getTicketingDecision(row)
      return decision === selectedRouting.value
    })
  }

  // 4. Filter by Search Query
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.trim().toUpperCase()
    list = list.filter(row => {
      const plate = (row.plate_key || '').toUpperCase()
      return plate.includes(query)
    })
  }

  return list
})

const activeStats = computed(() => {
  const stats = { matched: 0, corrected: 0, mismatch: 0, partial: 0, total: 0, ticketRouted: 0 }
  kpiFilteredList.value.forEach(row => {
    const info = getValidationInfo(row)
    const status = info.status
    if (stats[status] !== undefined) {
      stats[status]++
    }
    stats.total++
    if (getTicketingDecision(row) === 'TICKET') {
      stats.ticketRouted++
    }
  })
  return stats
})

const getPercentage = (count, total) => {
  if (!total) return '0.0%'
  return ((count / total) * 100).toFixed(1) + '%'
}

const kpiCards = computed(() => {
  const s = activeStats.value
  const pct = (n) => getPercentage(n, s.total)
  return [
    { key: 'total', cls: 'stat-total', icon: 'mdi-database-outline', value: s.total, tip: 'Total Streams' },
    { key: 'matched', cls: 'stat-matched', icon: 'mdi-check-circle-outline', value: s.matched, tip: `Matched (${pct(s.matched)})` },
    { key: 'partial', cls: 'stat-partial', icon: 'mdi-clock-outline', value: s.partial, tip: `Partial (${pct(s.partial)})` },
    { key: 'corrected', cls: 'stat-corrected', icon: 'mdi-alert-decagram-outline', value: s.corrected, tip: `Auto-Resolved (${pct(s.corrected)})` },
    { key: 'mismatch', cls: 'stat-mismatch', icon: 'mdi-alert-circle-outline', value: s.mismatch, tip: `Mismatch (${pct(s.mismatch)})` },
    { key: 'ticketed', cls: 'stat-ticketed', icon: 'mdi-ticket-confirmation-outline', value: s.ticketRouted, tip: `Ticket Process (${pct(s.ticketRouted)})` },
  ]
})

const filteredComparisonList = computed(() => {
  let list = kpiFilteredList.value

  // 1. Filter by Status/Result
  if (selectedResult.value !== 'ALL') {
    list = list.filter(row => {
      const info = getValidationInfo(row)
      const statusKey = info.status.toUpperCase()
      if (selectedResult.value === 'RESOLVED') {
        return statusKey === 'CORRECTED'
      }
      return statusKey === selectedResult.value
    })
  }

  // 2. Sort by time
  list = list.slice().sort((a, b) => {
    const timeA = new Date(a.first_seen || 0).getTime()
    const timeB = new Date(b.first_seen || 0).getTime()
    return sortOrderTime.value === 'ASC' ? timeA - timeB : timeB - timeA
  })

  return list
})

const visibleComparisonList = computed(() => {
  return filteredComparisonList.value.slice(0, displayLimit.value)
})

const selectedVehicle = ref(null)
const mediaLoading = ref(false)

const loadedMedia = ref({
  front_plate_image: "", front_vehicle_image: "",
  back_plate_image: "", back_vehicle_image: ""
})

const formatTime = (isoString) => {
  if (!isoString) return '—'
  let normalized = isoString
  if (typeof isoString === 'string' && isoString.includes(' ') && !isoString.includes('T')) {
    normalized = isoString.replace(' ', 'T')
  }
  const date = new Date(normalized)
  if (isNaN(date.getTime())) return isoString
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const getHigherConfidenceCamera = (row) => {
  if (!row.front_camera && !row.back_camera) return null
  if (!row.front_camera) return 'back'
  if (!row.back_camera) return 'front'
  
  const frontConf = parseFloat(row.front_camera.confidence) || 0
  const backConf = parseFloat(row.back_camera.confidence) || 0
  return frontConf >= backConf ? 'front' : 'back'
}

const getConfidenceClass = (confidence) => {
  const conf = parseFloat(confidence) || 0
  if (conf < 85) return 'conf-low'    // red
  if (conf <= 95) return 'conf-mid'   // yellow
  return 'conf-high'                  // green
}

const getValidationInfo = (row) => {
  if (!row) {
    return {
      status: 'partial',
      text: 'PARTIAL',
      details: 'No record available'
    }
  }

  // If we don't have enough data yet
  if (!row.core_event && !row.hikcentral) {
    return {
      status: 'partial',
      text: 'PARTIAL',
      details: 'Awaiting telemetry...'
    }
  }

  // Get chosen camera plate and vehicle type
  let camPlate = null
  let camType = null
  const chosenCam = getHigherConfidenceCamera(row)
  if (chosenCam === 'front' && row.front_camera) {
    camPlate = row.front_camera.plate
    camType = row.front_camera.vehicle_type
  } else if (chosenCam === 'back' && row.back_camera) {
    camPlate = row.back_camera.plate
    camType = row.back_camera.vehicle_type
  }

  const adminPlate = row.core_event ? row.core_event.plate_no : null
  const adminType = row.core_event ? row.core_event.vehicle_type_code : null

  const hcpPlate = row.hikcentral ? row.hikcentral.plate : null
  const hcpType = row.hikcentral ? row.hikcentral.vehicleType : null

  // Normalize all plates for comparison
  const normCam = camPlate ? camPlate.replace(/\s+/g, '').toUpperCase() : null
  const normAdmin = adminPlate ? adminPlate.replace(/\s+/g, '').toUpperCase() : null
  const normHcp = hcpPlate ? hcpPlate.replace(/\s+/g, '').toUpperCase() : null

  // Gather unique plates present
  const uniquePlates = new Set([normCam, normAdmin, normHcp].filter(Boolean))
  const uniqueTypes = new Set([camType, adminType, hcpType].filter(Boolean))

  // If all three sources are present and all have different plates, it is a mismatch
  if (normCam && normAdmin && normHcp && normCam !== normAdmin && normCam !== normHcp && normAdmin !== normHcp) {
    return {
      status: 'mismatch',
      text: 'MISMATCH',
      details: 'All plate reads are different'
    }
  }

  // If all three sources are present and all have different vehicle types, it is a mismatch
  if (camType && adminType && hcpType && camType !== adminType && camType !== hcpType && adminType !== hcpType) {
    return {
      status: 'mismatch',
      text: 'MISMATCH',
      details: 'All vehicle types are different'
    }
  }

  // Check if everything matches exactly
  const allPlatesMatch = uniquePlates.size <= 1
  const allTypesMatch = uniqueTypes.size <= 1

  if (allPlatesMatch && allTypesMatch) {
    return {
      status: 'matched',
      text: 'MATCHED',
      details: 'All systems align'
    }
  }

  // Auto-Resolution Logic (e.g. Disposition correction)
  // If plates match but vehicle types mismatch, check if the disposition helps resolve it
  const dispo = (row.disposition || '').toLowerCase()
  let dispoTargetType = null
  if (dispo.includes('motor')) {
    dispoTargetType = 'MOTORCYCLE'
  } else if (dispo.includes('car')) {
    dispoTargetType = 'CAR'
  }

  if (allPlatesMatch && dispoTargetType) {
    // If Admin aligns with disposition target type
    if (adminType === dispoTargetType && hcpType !== dispoTargetType) {
      return {
        status: 'corrected',
        text: 'RESOLVED',
        details: `Using Admin Type: ${dispoTargetType}`,
        correctSource: 'Admin Read',
        correctData: { plate: adminPlate, vehicleType: adminType }
      }
    }
    // If HCP aligns with disposition target type
    if (hcpType === dispoTargetType && adminType !== dispoTargetType) {
      return {
        status: 'corrected',
        text: 'RESOLVED',
        details: `Using HCP Type: ${dispoTargetType}`,
        correctSource: 'HikCentral Data',
        correctData: { plate: hcpPlate, vehicleType: hcpType }
      }
    }
  }

  // If plates are slightly mismatched but one camera is chosen
  if (!allPlatesMatch && camPlate) {
    // If chosen camera plate matches Admin plate
    if (normCam === normAdmin) {
      return {
        status: 'corrected',
        text: 'RESOLVED',
        details: `Plate Resolved to Camera/Admin: ${camPlate}`,
        correctSource: 'Camera/Admin Choice',
        correctData: { plate: camPlate, vehicleType: camType || adminType }
      }
    }
    // If chosen camera plate matches HCP plate
    if (normCam === normHcp) {
      return {
        status: 'corrected',
        text: 'RESOLVED',
        details: `Plate Resolved to Camera/HCP: ${camPlate}`,
        correctSource: 'Camera/HCP Choice',
        correctData: { plate: camPlate, vehicleType: camType || hcpType }
      }
    }
  }

  // Otherwise, it's a mismatch
  return {
    status: 'mismatch',
    text: 'MISMATCH',
    details: 'Discrepancy detected'
  }
}

const getRowClass = (row) => {
  const info = getValidationInfo(row)
  return `row-${info.status}` + (getRowDirection(row) === 'exit' ? ' row-exit' : '')
}

const openDetailModal = (row) => {
  selectedVehicle.value = row
  mediaLoading.value = true
  
  // Clean placeholders
  loadedMedia.value = { front_plate_image: "", front_vehicle_image: "", back_plate_image: "", back_vehicle_image: "" }
  
  // Lazy load images on-demand from disk file over websockets
  socket.emit('request_vehicle_media', { 
    plate_key: row.plate_key,
    date: row.first_seen
  })
}

const closeModal = () => {
  selectedVehicle.value = null
}

onMounted(() => {
  // Check connection status
  isSocketConnected.value = socket.connected

  socket.on('connect', () => {
    isSocketConnected.value = true
    socket.emit('register_terminal', { role: 'admin', gate: 0 })
    fetchHistory()
  })

  // If already connected on mount, register and fetch immediately
  if (socket.connected) {
    socket.emit('register_terminal', { role: 'admin', gate: 0 })
    fetchHistory()
  }

  socket.on('disconnect', () => {
    isSocketConnected.value = false
  })

  socket.on('connect_error', () => {
    isSocketConnected.value = false
  })

  socket.on('hcp_status_update', (status) => {
    isHcpConnected.value = status.connected
  })

  socket.on('available_reconciliation_dates_response', (datesList) => {
    availableDates.value = datesList
  })

  socket.on('reconciliation_history_response', (historyList) => {
    comparisonList.value = [...historyList].reverse()
    
    // Find latest camera activity from history
    let latestTime = 0
    historyList.forEach(row => {
      if (row.front_camera && row.front_camera.timestamp) {
        const t = new Date(row.front_camera.timestamp).getTime()
        if (t > latestTime) latestTime = t
      }
      if (row.back_camera && row.back_camera.timestamp) {
        const t = new Date(row.back_camera.timestamp).getTime()
        if (t > latestTime) latestTime = t
      }
    })
    if (latestTime > 0) {
      lastCameraActivity.value = latestTime
      isCameraOnline.value = (Date.now() - latestTime) < 45000
    }
  })

  // Table layout is a dashboard setting, pushed to every admin page on connect and whenever it changes
  socket.on('config_sync', (cfg) => {
    splitExitLayout.value = cfg.split_exit_layout !== false
    exitRowsRightAligned.value = cfg.exit_rows_right_aligned !== false
    servers.value = cfg.servers || {}
  })

  socket.on('all_time_reconciliation_stats_response', (statsData) => {
    allTimeStats.value = statsData
  })

  socket.on('new_reconciled_vehicle', (newVehicle) => {
    if (newVehicle.front_camera || newVehicle.back_camera) {
      lastCameraActivity.value = Date.now()
      isCameraOnline.value = true
    }

    // Only append/update if selectedDate is "all" or "today" or matches the record's date
    let shouldAdd = false
    if (selectedDate.value === 'all' || selectedDate.value === 'today') {
      shouldAdd = true
    } else if (newVehicle.first_seen) {
      const vehicleDate = newVehicle.first_seen.split('T')[0]
      if (vehicleDate === selectedDate.value) {
        shouldAdd = true
      }
    }

    if (shouldAdd) {
      const existingIdx = comparisonList.value.findIndex(item => item.plate_key === newVehicle.plate_key)
      if (existingIdx !== -1) {
        comparisonList.value[existingIdx] = newVehicle
      } else {
        comparisonList.value.unshift(newVehicle)
      }
    }
  })

  socket.on('reconciled_vehicle_updated', (updatedVehicle) => {
    const existingIdx = comparisonList.value.findIndex(item => item.plate_key === updatedVehicle.plate_key)
    if (existingIdx !== -1) {
      comparisonList.value[existingIdx] = updatedVehicle
    }
  })

  // Catch the heavy lazy-loaded images response packet
  socket.on('vehicle_media_response', (mediaData) => {
    if (selectedVehicle.value && selectedVehicle.value.plate_key === mediaData.plate_key) {
      loadedMedia.value = mediaData
      mediaLoading.value = false
    }
  })

  // Start checking camera offline state every 2 seconds
  cameraTimer = setInterval(() => {
    isCameraOnline.value = (Date.now() - lastCameraActivity.value) < 45000
  }, 2000)

  // Infinite Scroll IntersectionObserver
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && filteredComparisonList.value.length > displayLimit.value) {
      displayLimit.value += 200
    }
  }, {
    root: pageScroller.value,
    rootMargin: '200px',
  })
  
  if (loadMoreTrigger.value) {
    observer.observe(loadMoreTrigger.value)
  }
})

onUnmounted(() => {
  if (cameraTimer) clearInterval(cameraTimer)
  if (observer) observer.disconnect()
  socket.off('connect')
  socket.off('disconnect')
  socket.off('connect_error')
  socket.off('hcp_status_update')
  socket.off('available_reconciliation_dates_response')
  socket.off('reconciliation_history_response')
  socket.off('all_time_reconciliation_stats_response')
  socket.off('config_sync')
  socket.off('new_reconciled_vehicle')
  socket.off('reconciled_vehicle_updated')
  socket.off('vehicle_media_response')
})
</script>

<style scoped>
/* Main View Architecture */
/* Page is a full-height column: header, KPIs and filters stay put and the table fills the rest,
   so the table's own scrollbar is the only one (the page only scrolls on very short screens) */
/* No top padding here: sticky table headers stop at the scroll container's padding edge, which left a gap above
   them. The header row's margin-top supplies the same spacing instead. */
.admin-container { flex: 1; display: flex; flex-direction: column; background-color: #111; padding: 0 40px 40px; color: white; overflow-y: auto; height: 100%; box-sizing: border-box; color-scheme: dark; transition: background-color 0.25s ease, color 0.25s ease; }
.admin-header-row { display: flex; justify-content: space-between; align-items: center; margin-top: 40px; margin-bottom: 25px; flex-wrap: wrap; gap: 15px; flex-shrink: 0; }
.launcher-actions { display: flex; gap: 12px; }

.btn-launcher {
  text-decoration: none; font-size: 0.95rem; padding: 10px 18px; border-radius: 6px;
  display: inline-flex; align-items: center; gap: 8px; border: 1px solid #333;
  cursor: pointer; font-weight: bold; background: rgba(255,255,255,0.05); color: #eee;
}
.btn-launcher:hover { background: #fff; color: #111; }
.btn-theme-toggle { font-family: inherit; }

.reconcile-summary-row {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
  background: rgba(255, 255, 255, 0.01); padding: 12px 20px; border-radius: 6px; border: 1px solid #222;
  flex-shrink: 0;
}
.stat-counter { font-size: 0.9rem; font-weight: bold; color: #888; }

.db-badge {
  display: inline-flex; align-items: center; gap: 6px; font-size: 0.75rem; font-weight: bold;
  color: #17a2b8; background: rgba(23, 162, 184, 0.1); padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(23, 162, 184, 0.2);
}
.db-dot { width: 6px; height: 6px; border-radius: 50%; background-color: #17a2b8; }

/* min-width: the card grows to the table's width so the whole page scrolls sideways on narrow screens */
.live-actions-card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 25px; box-sizing: border-box; flex: 0 0 auto; min-width: fit-content; display: flex; flex-direction: column; }
.card-header-with-status h2 { font-size: 1.2rem; color: #ff9800; margin: 0; display: flex; align-items: center; gap: 8px; }
.card-subtitle { font-size: 0.85rem; color: #888; margin-top: 5px; margin-bottom: 25px; text-align: left; }

/* Grid Table Formatting (8 Clean Columns) */
/* The whole page scrolls, not the table box. overflow: clip rounds the corners without making the box a scroll
   container, so the sticky headers below pin to the top of the page. */
.table-responsive { width: 100%; border: 1px solid #2a2a2a; border-radius: 8px; background: #151515; overflow: visible; overflow: clip; box-sizing: border-box; }
.comparison-table { width: 100%; min-width: 1200px; border-collapse: separate; border-spacing: 0; text-align: left; font-size: 0.88rem; }
.comparison-table th { position: sticky; top: 0; z-index: 10; background-color: #1f1f1f; color: #aaa; font-size: 0.78rem; padding: 16px; border-bottom: 2px solid #2a2a2a; text-transform: uppercase; letter-spacing: 0.5px; box-shadow: inset 0 -2px 0 #2a2a2a; }
.comparison-table td { padding: 14px 16px; border-bottom: 1px solid #222; vertical-align: middle; }

.clickable-row { cursor: pointer; transition: background 0.2s ease; }
.clickable-row:hover { background: rgba(255, 255, 255, 0.04) !important; }

/* Condensed Nested Data blocks formatting rules */
.source-cell-block { display: flex; flex-direction: column; gap: 5px; }
.nested-type-row { display: flex; gap: 6px; align-items: center; font-size: 0.78rem; font-weight: bold; }
.type-text { color: #ccc; text-transform: capitalize; }
.text-orange { color: #ff9800 !important; font-weight: bold; }
.text-purple { color: #a855f7 !important; font-weight: bold; }
.conf-text { color: #555; }
.conf-text.conf-low { color: #ff4a5a !important; font-weight: bold; }
.conf-text.conf-mid { color: #eab308 !important; font-weight: bold; }
.conf-text.conf-high { color: #28a745 !important; font-weight: bold; }
.gate-tag { font-size: 0.72rem; color: #666; display: flex; align-items: center; gap: 4px; margin-top: 2px; }

/* Cell Tinting Shading Blocks */
.col-cell-front { border-left: 1px solid #2d2d2d; background: rgba(23, 162, 184, 0.005); }
.col-cell-back { border-left: 1px solid #2d2d2d; background: rgba(40, 167, 69, 0.005); }
.col-cell-hik { border-left: 1px solid #2d2d2d; background: rgba(255, 152, 0, 0.005); }
.col-cell-ops { border-left: 1px solid #2d2d2d; background: rgba(255, 255, 255, 0.002); }

.dispo-tag { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; text-align: center; border: 1px solid transparent; min-width: 70px; }
.dispo-tag.na { background: rgba(255,255,255,0.05); color: #777; }
.dispo-tag.ticket { background: rgba(244, 63, 94, 0.15); color: #f43f5e; border-color: rgba(244, 63, 94, 0.2); }
.dispo-tag.car_lp { background: rgba(23, 162, 184, 0.15); color: #17a2b8; border-color: rgba(23, 162, 184, 0.2); }
.dispo-tag.motor_lp { background: rgba(234, 179, 8, 0.15); color: #eab308; border-color: rgba(234, 179, 8, 0.2); }

/* Decision Column and Tags Styling */
.col-cell-decision { border-left: 1px solid #2d2d2d; background: rgba(255, 255, 255, 0.002); text-align: center; }
.col-cell-exit { border-left: 1px solid #2d2d2d; }
.decision-tag {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
  text-align: center;
  border: 1px solid transparent;
  min-width: 65px;
}
.decision-tag.system {
  background: rgba(23, 162, 184, 0.05);
  color: #17a2b8;
  border-color: rgba(23, 162, 184, 0.1);
}
.decision-tag.ticket {
  background: rgba(244, 63, 94, 0.15);
  color: #f43f5e;
  border-color: rgba(244, 63, 94, 0.2);
}

.row-mismatch { background: rgba(244, 63, 94, 0.015); }
.row-partial { background: rgba(234, 179, 8, 0.005); }

/* Exit rows: grey background so they stand apart from entries */
.comparison-table tr.row-exit { background: #1e1e1e; }
.comparison-table tr.row-exit td { border-bottom-color: #2a2a2a; }
.comparison-table tr.row-exit:hover { background: #242424 !important; }

/* Plate Badges Rules */
.plate-badge {
  display: inline-block; align-self: flex-start; background: #222; color: #fff;
  font-family: monospace; font-size: 1rem; font-weight: bold; padding: 3px 8px; border-radius: 4px; border: 1px solid #383838;
}
.badge-front { border-left: 3px solid #17a2b8; }
.badge-back { border-left: 3px solid #28a745; }
.badge-hik { border-left: 3px solid #ff9800; }
.badge-admin { border-left: 3px solid #a855f7; }
.plate-badge.badge-chosen {
  border-color: #28a745 !important;
  box-shadow: 0 0 10px rgba(40, 167, 69, 0.4);
  background: rgba(40, 167, 69, 0.1) !important;
}

.text-bold { font-weight: bold; }
.text-highlight { color: #00e5ff; }
.text-muted { color: #555; }

.status-tag { display: inline-flex; padding: 4px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: bold; min-width: 75px; justify-content: center; }
.status-tag.matched { background: rgba(40, 167, 69, 0.15); color: #28a745; border: 1px solid rgba(40, 167, 69, 0.2); }
.status-tag.mismatch { background: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.2); }
.status-tag.partial { background: rgba(234, 179, 8, 0.15); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.2); }
.no-data-row { text-align: center; color: #444; padding: 40px 0 !important; }

/* ========================================================= */
/* 📄 SPLIT-PANE MODAL VIEW DESIGN WITH DETAILED TELEMETRY   */
/* ========================================================= */
.modal-overlay {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background: rgba(0, 0, 0, 0.9); display: flex; align-items: center; justify-content: center; z-index: 999;
}
.modal-card {
  background: #161616; border: 1px solid #333; width: 1380px; max-width: 95%;
  border-radius: 8px; box-shadow: 0 15px 60px rgba(0,0,0,0.8); overflow: hidden;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px; border-bottom: 1px solid #252525; background: #202020;
}
.modal-header h3 { margin: 0; font-size: 1rem; }
.close-btn { background: none; border: none; color: #888; font-size: 1.5rem; cursor: pointer; line-height: 1; }
.close-btn:hover { color: #fff; }

.modal-body { padding: 24px; max-height: 85vh; overflow-y: auto; }

.modal-split-layout { display: flex; gap: 24px; flex-wrap: wrap; }
.media-gallery-pane { flex: 2 1 700px; display: flex; flex-direction: column; gap: 20px; }
.telemetry-data-pane { flex: 1 1 380px; }

.camera-gallery-section { background: #111; border: 1px solid #222; padding: 16px; border-radius: 6px; }
.camera-gallery-section h3 { margin-top: 0; margin-bottom: 14px; font-size: 0.88rem; letter-spacing: 0.5px; }
.section-front h3 { color: #17a2b8; }
.section-back h3 { color: #28a745; }

.frames-split-row { display: flex; gap: 16px; flex-wrap: wrap; }
.gallery-image-wrapper { background: #090909; border: 1px solid #222; border-radius: 4px; padding: 10px; display: flex; flex-direction: column; gap: 8px; width: 100%; box-sizing: border-box; }

.image-crop { flex: 1 1 180px; max-width: 220px; }
.image-scene { flex: 2 1 420px; }
.image-scene-full { width: 100%; }

.gallery-image-wrapper h5 { margin: 0; font-size: 0.74rem; color: #666; text-transform: uppercase; }
.gallery-image-wrapper img { width: 100%; height: auto; max-height: 240px; border-radius: 2px; object-fit: contain; border: 1px solid #1a1a1a; background: #030303; }
.no-img-box { height: 120px; display: flex; align-items: center; justify-content: center; color: #444; font-size: 0.78rem; font-family: monospace; border: 1px solid #1d1d1d; border-style: dashed; }
.media-loader-box { text-align: center; color: #17a2b8; font-size: 0.85rem; padding: 30px 0; font-weight: bold; font-family: monospace; }

.http-link-label { font-family: monospace; font-size: 0.72rem; color: #a855f7; background: rgba(168, 85, 247, 0.05); padding: 6px; border-radius: 4px; word-break: break-all; text-align: left; margin-top: 5px; }

/* Telemetry Card Shading Grid */
.data-block-card { background: #111; border: 1px solid #222; border-radius: 6px; padding: 20px; height: 100%; box-sizing: border-box; display: flex; flex-direction: column; }
.data-block-card h4 { margin-top: 0; margin-bottom: 15px; font-size: 0.9rem; color: #ff9800; border-bottom: 1px solid #222; padding-bottom: 10px; }
.telemetry-scroll-box { display: flex; flex-direction: column; gap: 14px; overflow-y: auto; flex-grow: 1; }

.telemetry-scroll-box h5 { margin-top: 5px; margin-bottom: 5px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; }
.sub-header-purple { color: #b388ff; }
.sub-header-cyan { color: #00e5ff; }
.sub-header-green { color: #69f0ae; }
.sub-header-orange { color: #ffd740; }

.telemetry-group { background: #090909; border: 1px solid #1f1f1f; padding: 10px 14px; border-radius: 4px; display: flex; flex-direction: column; gap: 8px; }
.data-row { display: flex; justify-content: space-between; font-size: 0.82rem; }
.data-row .label { color: #666; }
.data-row .val { color: #eee; font-weight: 500; }
.highlight-text { color: #00e5ff !important; font-weight: bold !important; font-family: monospace; font-size: 1.2rem; }
.text-dim { color: #444 !important; font-size: 0.75rem; }
.no-data-msg { font-size: 0.78rem; color: #444; font-style: italic; padding: 2px 14px; }

.meta-summary-footer { display: flex; gap: 40px; background: #202020; padding: 14px 24px; border-bottom: 1px solid #252525; font-size: 0.82rem; flex-wrap: wrap; }
.meta-item strong { color: #666; margin-right: 6px; }
.text-warn { color: #ffca28; font-weight: bold; }
.dispo-tag.car_lp { background: rgba(23, 162, 184, 0.15); color: #17a2b8; border-color: rgba(23, 162, 184, 0.2); }
.dispo-tag.motor_lp { background: rgba(234, 179, 8, 0.15); color: #eab308; border-color: rgba(234, 179, 8, 0.2); }
/* Custom row status styles */
.row-matched {
  background: rgba(40, 167, 69, 0.015);
}
.row-corrected {
  background: rgba(0, 229, 255, 0.015);
}
.status-tag.corrected {
  background: rgba(0, 229, 255, 0.15);
  color: #00e5ff;
  border: 1px solid rgba(0, 229, 255, 0.25);
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.15);
}

/* Animations & Layout for Validation details */
.validation-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.validation-details-text {
  font-size: 0.72rem;
  color: #666;
  white-space: nowrap;
}
.correction-details {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
  color: #00e5ff;
  font-weight: 600;
  animation: fadeIn 0.3s ease;
}
.plate-mini {
  font-family: monospace;
  background: rgba(0, 229, 255, 0.12);
  padding: 1px 5px;
  border-radius: 3px;
  border: 1px dashed rgba(0, 229, 255, 0.25);
}
.source-mini {
  color: #888;
  font-size: 0.68rem;
}

/* Back-to-top button */
.btn-back-to-top {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 50; /* above sticky headers, below the detail modal (999) */
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid #333;
  background: #1f1f1f;
  color: #17a2b8;
  font-size: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
}
.btn-back-to-top:hover {
  transform: translateY(-2px);
  background: #262626;
  border-color: #17a2b8;
}
.btn-back-to-top:focus-visible {
  outline: 2px solid #17a2b8;
  outline-offset: 2px;
}
.back-to-top-enter-active, .back-to-top-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.back-to-top-enter-from, .back-to-top-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

/* Table row transitions (TransitionGroup name="row") */
.row-enter-active {
  transition: opacity 0.45s cubic-bezier(0.16, 1, 0.3, 1), transform 0.45s cubic-bezier(0.16, 1, 0.3, 1);
  transition-delay: calc(var(--row-i, 0) * 25ms); /* light stagger when many rows load at once */
}
.row-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
/* Leaving rows drop out of the layout right away so the remaining rows can glide into place */
.row-leave-active {
  display: none;
}
.row-move {
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

/* Source cells fade in when a reading arrives on an existing row */
.cell-fade-enter-active, .cell-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.cell-fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.cell-fade-leave-to {
  opacity: 0;
}

/* Hover accent bar on the first cell */
.clickable-row td:first-child {
  transition: box-shadow 0.2s ease;
}
.clickable-row:hover td:first-child {
  box-shadow: inset 3px 0 0 #17a2b8;
}
.clickable-row:active {
  background: rgba(255, 255, 255, 0.07) !important;
}

/* Split exit layout: exit rows read from the right, next to the Exit Plate Key column */
.row-align-right td { text-align: right; }
.row-align-right .source-cell-block { align-items: flex-end; }
.row-align-right .plate-badge { align-self: flex-end; }
.row-align-right .nested-type-row,
.row-align-right .cell-timestamp,
.row-align-right .col-cell-exit > div { justify-content: flex-end; }
.row-align-right:hover td:first-child { box-shadow: none; }
.row-align-right:hover td:last-child { box-shadow: inset -3px 0 0 #17a2b8; }
.light .row-align-right:hover td:first-child { box-shadow: none; }
.light .row-align-right:hover td:last-child { box-shadow: inset -3px 0 0 #0e7490; }
.row-align-right td:last-child { transition: box-shadow 0.2s ease; }

@media (prefers-reduced-motion: reduce) {
  .row-enter-active, .row-move, .cell-fade-enter-active, .cell-fade-leave-active,
  .clickable-row td:first-child, .btn-back-to-top, .back-to-top-enter-active, .back-to-top-leave-active {
    transition: none;
  }
}

@keyframes pulse-slow {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.04); opacity: 0.85; }
}
.animate-pulse-slow {
  animation: pulse-slow 2s infinite ease-in-out;
  display: inline-block;
  margin-right: 4px;
}

@keyframes check-pop {
  0% { transform: scale(0.7); }
  50% { transform: scale(1.25); }
  100% { transform: scale(1); }
}
.animate-check {
  animation: check-pop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) both;
  display: inline-block;
  margin-right: 4px;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-3px); }
  40%, 80% { transform: translateX(3px); }
}
.animate-shake {
  animation: shake 0.6s ease-in-out;
  display: inline-block;
  margin-right: 4px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Modal Transition styles */
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.3s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-card, .modal-leave-active .modal-card {
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.modal-enter-from .modal-card, .modal-leave-to .modal-card {
  transform: scale(0.92) translateY(20px);
}

/* Summary Dashboard Cards */
.summary-stats-cards {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid #222;
  padding: 6px 14px;
  border-radius: 6px;
  min-width: 110px;
  transition: all 0.25s ease;
  position: relative;
  cursor: default;
  outline: none;
}
.stat-card:hover, .stat-card:focus-visible {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.04);
  z-index: 30; /* keep the popup above the sticky table headers */
}
/* Label popup (replaces the inline labels) */
.stat-card::after {
  content: attr(data-tip);
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translate(-50%, -4px);
  opacity: 0;
  pointer-events: none;
  background: #1f1f1f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  white-space: nowrap;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.stat-card:hover::after, .stat-card:focus-visible::after {
  opacity: 1;
  transform: translate(-50%, 0);
}
@media (prefers-reduced-motion: reduce) {
  .stat-card, .stat-card::after { transition: none; }
}
.stat-card .icon {
  font-size: 1.4rem;
}
.stat-details {
  display: flex;
  flex-direction: column;
}
.stat-value {
  font-size: 1.1rem;
  font-weight: bold;
}

/* Color accents for cards */
.stat-total .icon { color: #888; }
.stat-total { border-color: rgba(255, 255, 255, 0.1); }

.stat-matched .icon { color: #28a745; }
.stat-matched { border-color: rgba(40, 167, 69, 0.25); background: rgba(40, 167, 69, 0.02); }
.stat-matched:hover { border-color: rgba(40, 167, 69, 0.5); background: rgba(40, 167, 69, 0.05); }

.stat-corrected .icon { color: #00e5ff; }
.stat-corrected { border-color: rgba(0, 229, 255, 0.25); background: rgba(0, 229, 255, 0.02); }
.stat-corrected:hover { border-color: rgba(0, 229, 255, 0.5); background: rgba(0, 229, 255, 0.05); }

.stat-mismatch .icon { color: #f43f5e; }
.stat-mismatch { border-color: rgba(244, 63, 94, 0.25); background: rgba(244, 63, 94, 0.02); }
.stat-mismatch:hover { border-color: rgba(244, 63, 94, 0.5); background: rgba(244, 63, 94, 0.05); }

.stat-partial .icon { color: #eab308; }
.stat-partial { border-color: rgba(234, 179, 8, 0.25); background: rgba(234, 179, 8, 0.02); }
.stat-partial:hover { border-color: rgba(234, 179, 8, 0.5); background: rgba(234, 179, 8, 0.05); }

.stat-ticketed .icon { color: #f43f5e; }
.stat-ticketed { border-color: rgba(244, 63, 94, 0.25); background: rgba(244, 63, 94, 0.02); }
.stat-ticketed:hover { border-color: rgba(244, 63, 94, 0.5); background: rgba(244, 63, 94, 0.05); }

/* Search bar & Virtual loading controls styling */
.card-header-with-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
  margin-bottom: 5px;
}
.search-box-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}
.search-icon {
  position: absolute;
  left: 12px;
  color: #666;
  font-size: 1.1rem;
}
.search-input {
  background: #111;
  border: 1px solid #333;
  color: #fff;
  padding: 8px 35px 8px 35px;
  border-radius: 6px;
  font-size: 0.88rem;
  width: 200px;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.search-input:focus {
  outline: none;
  border-color: #ff9800;
  box-shadow: 0 0 10px rgba(255, 152, 0, 0.15);
  width: 280px;
}
.clear-search-btn {
  position: absolute;
  right: 10px;
  background: none;
  border: none;
  color: #888;
  font-size: 1.2rem;
  cursor: pointer;
  line-height: 1;
}
.clear-search-btn:hover {
  color: #fff;
}

.load-more-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
.btn-load-more {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid #2a2a2a;
  color: #ccc;
  padding: 10px 24px;
  border-radius: 6px;
  font-size: 0.88rem;
  font-weight: bold;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
}
.btn-load-more:hover {
  background: #fff;
  color: #111;
  border-color: #fff;
  transform: translateY(-1px);
}
.btn-load-more:active {
  transform: translateY(0);
}

/* System Status Badges container */
.system-status-badges {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.connection-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.75rem;
  font-weight: bold;
  padding: 4px 12px;
  border-radius: 20px;
  border: 1px solid transparent;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.connection-badge.online {
  color: #28a745;
  background: rgba(40, 167, 69, 0.1);
  border-color: rgba(40, 167, 69, 0.25);
  box-shadow: 0 0 10px rgba(40, 167, 69, 0.15);
}

.connection-badge.offline {
  color: #f43f5e;
  background: rgba(244, 63, 94, 0.1);
  border-color: rgba(244, 63, 94, 0.25);
  box-shadow: 0 0 10px rgba(244, 63, 94, 0.15);
  animation: connection-offline-pulse 2s infinite ease-in-out;
}

/* Pulsing dot for online status */
.pulse-ping {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  position: relative;
  display: inline-block;
}
.connection-badge.online .pulse-ping {
  background-color: #28a745;
}
.connection-badge.online .pulse-ping::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background-color: #28a745;
  animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes ping {
  75%, 100% {
    transform: scale(2.5);
    opacity: 0;
  }
}

@keyframes connection-offline-pulse {
  0%, 100% {
    border-color: rgba(244, 63, 94, 0.25);
    box-shadow: 0 0 5px rgba(244, 63, 94, 0.05);
  }
  50% {
    border-color: rgba(244, 63, 94, 0.6);
    box-shadow: 0 0 15px rgba(244, 63, 94, 0.3);
  }
}

.btn-filter-toggle {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-filter-toggle:hover,
.btn-filter-toggle.open { border-color: rgba(255, 152, 0, 0.4); color: #fff; }
.filter-count-badge {
  background: rgba(255, 152, 0, 0.15);
  color: #ff9800;
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 0.72rem;
  font-weight: 600;
}

/* Premium Filter Controls Layout */
.filter-controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
  margin-bottom: 22px;
  background: rgba(255, 255, 255, 0.02);
  padding: 12px 20px;
  border-radius: 8px;
  border: 1px solid #2a2a2a;
  box-sizing: border-box;
}

.filter-left-section {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.filter-right-section {
  display: flex;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-label {
  font-size: 0.82rem;
  color: #aaa;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 6px;
}

.select-premium {
  background: #111;
  border: 1px solid #333;
  color: #fff;
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  outline: none;
  font-weight: 600;
}

.select-premium:hover {
  border-color: #555;
  background: #151515;
}

.select-premium:focus {
  border-color: #ff9800;
  box-shadow: 0 0 10px rgba(255, 152, 0, 0.2);
}

.btn-export {
  background: rgba(40, 167, 69, 0.1);
  border: 1px solid rgba(40, 167, 69, 0.25);
  color: #28a745;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: bold;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  outline: none;
}

.btn-export:hover {
  background: #28a745;
  color: #fff;
  border-color: #28a745;
  box-shadow: 0 0 12px rgba(40, 167, 69, 0.3);
  transform: translateY(-1px);
}

.btn-export:active {
  transform: translateY(0);
}

.text-green {
  color: #28a745;
}

.btn-export:hover .text-green {
  color: #fff;
}

.cell-timestamp {
  font-size: 0.76rem;
  display: flex;
  align-items: center;
  gap: 3px;
  justify-content: start;
}

/* ========================================================= */
/* ☀️ LIGHT MODE (high contrast for bright / outdoor screens)  */
/* Accent colors are darkened so they stay readable on white. */
/* !important is only used where the template sets inline styles. */
/* ========================================================= */
.admin-container.light { background-color: #eef1f4; color: #111827; color-scheme: light; }

/* Header & summary */
.light .page-title { color: #0e7490 !important; }
.light .btn-launcher { background: #fff; color: #111827; border-color: #cbd2d9; }
.light .btn-launcher:hover { background: #111827; color: #fff; }
.light .reconcile-summary-row { background: #fff; border-color: #d8dde3; }
.light .db-badge { color: #0e7490; background: rgba(14, 116, 144, 0.08); border-color: rgba(14, 116, 144, 0.25); }
.light .db-dot { background-color: #0e7490; }
.light .connection-badge.online { color: #15803d; background: rgba(21, 128, 61, 0.08); }
.light .connection-badge.offline { color: #be123c; background: rgba(190, 18, 60, 0.08); }
.light .connection-badge.online .pulse-ping,
.light .connection-badge.online .pulse-ping::after { background-color: #15803d; }

/* KPI cards */
.light .stat-card { background: #fff; }
.light .stat-card:hover, .light .stat-card:focus-visible { background: #f8fafc; }
.light .stat-card::after { background: #111827; color: #fff; border-color: #111827; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.25); }
.light .stat-total { border-color: #cbd2d9; }
.light .stat-total .icon { color: #4b5563; }
.light .stat-matched .icon { color: #15803d; }
.light .stat-corrected .icon { color: #0e7490; }
.light .stat-partial .icon { color: #a16207; }
.light .stat-mismatch .icon, .light .stat-ticketed .icon { color: #be123c; }

/* Card, filters, search */
.light .live-actions-card { background: #fff; border-color: #d8dde3; }
.light .card-header-with-status h2, .light .card-header-with-status h2 .mdi { color: #c2410c !important; }
.light .btn-filter-toggle { background: #fff; border-color: #cbd2d9; color: #374151; }
.light .btn-filter-toggle:hover, .light .btn-filter-toggle.open { border-color: #c2410c; color: #111827; }
.light .filter-count-badge { background: rgba(194, 65, 12, 0.1); color: #c2410c; }
.light .filter-controls-row { background: #f8fafc; border-color: #e2e6ea; }
.light .filter-label { color: #4b5563; }
.light .exclude-unknown-label { color: #374151 !important; }
.light .select-premium, .light .search-input { background: #fff; border-color: #cbd2d9; color: #111827; }
.light .select-premium:hover { background: #f8fafc; border-color: #9ca3af; }
.light .search-icon, .light .clear-search-btn { color: #6b7280; }
.light .clear-search-btn:hover { color: #111827; }
.light .btn-export, .light .text-green { color: #15803d; }
.light .btn-export:hover .text-green { color: #fff; }

/* Table */
.light .table-responsive { background: #fff; border-color: #cbd2d9; }
.light .comparison-table th { background-color: #e5e8ec; color: #374151; border-bottom-color: #cbd2d9; box-shadow: inset 0 -2px 0 #cbd2d9; }
.light .comparison-table td { border-bottom-color: #e5e8ec; }
.light .col-cell-front, .light .col-cell-back, .light .col-cell-hik,
.light .col-cell-ops, .light .col-cell-decision, .light .col-cell-exit { border-left-color: #e5e8ec; }
.light .clickable-row:hover { background: #f1f5f9 !important; }
.light .clickable-row:active { background: #e2e8f0 !important; }
.light .clickable-row:hover td:first-child { box-shadow: inset 3px 0 0 #0e7490; }
.light .comparison-table tr.row-exit { background: #f3f4f6; }
.light .comparison-table tr.row-exit td { border-bottom-color: #e2e6ea; }
.light .comparison-table tr.row-exit:hover { background: #e9edf2 !important; }
.light .row-mismatch { background: rgba(190, 18, 60, 0.04); }
.light .row-partial { background: rgba(161, 98, 7, 0.03); }
.light .row-matched { background: rgba(21, 128, 61, 0.03); }
.light .row-corrected { background: rgba(14, 116, 144, 0.03); }
.light .no-data-row { color: #6b7280; }

.light .text-muted { color: #6b7280; }
.light .text-highlight { color: #0e7490; }
.light .text-orange { color: #c2410c !important; }
.light .text-purple { color: #7e22ce !important; }
.light .type-text { color: #374151; }
.light .conf-text { color: #6b7280; }
.light .conf-text.conf-low { color: #dc2626 !important; }
.light .conf-text.conf-mid { color: #a16207 !important; }
.light .conf-text.conf-high { color: #15803d !important; }

.light .plate-badge { background: #f3f4f6; color: #111827; border-color: #cbd2d9; }
.light .badge-front { border-left-color: #0e7490; }
.light .badge-back { border-left-color: #15803d; }
.light .badge-hik { border-left-color: #c2410c; }
.light .badge-admin { border-left-color: #7e22ce; }
.light .plate-badge.badge-chosen { border-color: #15803d !important; background: rgba(21, 128, 61, 0.1) !important; box-shadow: 0 0 0 2px rgba(21, 128, 61, 0.15); }

.light .badge-gate { background: #e5e8ec !important; color: #374151 !important; }
.light .badge-dir-entry { background: rgba(21, 128, 61, 0.12) !important; color: #15803d !important; }
.light .badge-dir-exit { background: rgba(14, 116, 144, 0.12) !important; color: #0e7490 !important; }

.light .dispo-tag.na { background: #f3f4f6; color: #4b5563; }
.light .dispo-tag.ticket, .light .decision-tag.ticket { background: rgba(190, 18, 60, 0.1); color: #be123c; border-color: rgba(190, 18, 60, 0.25); }
.light .dispo-tag.car_lp, .light .decision-tag.system { background: rgba(14, 116, 144, 0.1); color: #0e7490; border-color: rgba(14, 116, 144, 0.25); }
.light .dispo-tag.motor_lp { background: rgba(161, 98, 7, 0.1); color: #a16207; border-color: rgba(161, 98, 7, 0.25); }
.light .status-tag.matched { background: rgba(21, 128, 61, 0.1); color: #15803d; }
.light .status-tag.mismatch { background: rgba(190, 18, 60, 0.1); color: #be123c; }
.light .status-tag.partial { background: rgba(161, 98, 7, 0.1); color: #a16207; }
.light .status-tag.corrected { background: rgba(14, 116, 144, 0.1); color: #0e7490; box-shadow: none; }

.light .btn-load-more { background: #fff; border-color: #cbd2d9; color: #374151; }
.light .btn-load-more:hover { background: #111827; border-color: #111827; color: #fff; }
.light .btn-back-to-top { background: #fff; border-color: #cbd2d9; color: #0e7490; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18); }
.light .btn-back-to-top:hover { background: #f1f5f9; border-color: #0e7490; }

/* Detail modal */
.light .modal-overlay { background: rgba(15, 23, 42, 0.55); }
.light .modal-card { background: #fff; border-color: #cbd2d9; box-shadow: 0 15px 60px rgba(15, 23, 42, 0.3); }
.light .modal-header { background: #f3f4f6; border-bottom-color: #e2e6ea; }
.light .modal-plate-title { color: #b45309 !important; }
.light .close-btn { color: #6b7280; }
.light .close-btn:hover { color: #111827; }
.light .meta-summary-footer { background: #f8fafc; border-bottom-color: #e2e6ea; }
.light .meta-item strong { color: #4b5563; }
.light .text-warn { color: #b45309; }
.light .text-dim { color: #6b7280 !important; }
.light .camera-gallery-section, .light .data-block-card { background: #f8fafc; border-color: #e2e6ea; }
.light .section-front h3 { color: #0e7490; }
.light .section-back h3 { color: #15803d; }
.light .gallery-image-wrapper { background: #fff; border-color: #e2e6ea; }
.light .gallery-image-wrapper h5 { color: #6b7280; }
.light .gallery-image-wrapper img { background: #f3f4f6; border-color: #e2e6ea; }
.light .no-img-box { color: #6b7280; border-color: #cbd2d9; }
.light .media-loader-box { color: #0e7490; }
.light .http-link-label { color: #7e22ce; }
.light .data-block-card h4 { color: #c2410c; border-bottom-color: #e2e6ea; }
.light .sub-header-purple { color: #7e22ce; }
.light .sub-header-cyan { color: #0e7490; }
.light .sub-header-green { color: #15803d; }
.light .sub-header-orange { color: #b45309; }
.light .telemetry-group { background: #fff; border-color: #e2e6ea; }
.light .data-row .label { color: #6b7280; }
.light .data-row .val { color: #111827; }
.light .highlight-text { color: #0e7490 !important; }
.light .no-data-msg { color: #6b7280; }
.light .correction-details { color: #0e7490; }
.light .source-mini { color: #6b7280; }
</style>
