<template>
  <div class="admin-card api-metrics-card">
    <div class="metrics-header">
      <h2>
        <span class="mdi mdi-speedometer" style="color: #00e676; margin-right: 8px;"></span>
        API Query Latency Telemetry
      </h2>
      <button class="btn btn-secondary btn-sm" @click="resetMetrics">
        <span class="mdi mdi-refresh"></span> Reset Metrics
      </button>
    </div>

    <div class="metrics-body">
      <div v-if="!metrics || metrics.length === 0" class="metrics-placeholder">
        No API query metrics recorded yet. Trigger API actions to capture latency...
      </div>
      <div v-else class="table-responsive">
        <table class="metrics-table">
          <thead>
            <tr>
              <th>Endpoint</th>
              <th class="text-right">Queries</th>
              <th class="text-right">Average</th>
              <th class="text-right">Shortest</th>
              <th class="text-right">Longest</th>
              <th class="text-right">Last Query</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in metrics" :key="item.endpoint">
              <td class="endpoint-cell">
                <span class="method-badge" :class="getMethodClass(item.endpoint)">
                  {{ getMethod(item.endpoint) }}
                </span>
                <span class="path-text">{{ getPath(item.endpoint) }}</span>
              </td>
              <td class="text-right font-mono text-cyan">{{ item.count }}</td>
              <td class="text-right font-mono" :class="getLatencyClass(item.avg_ms)">
                {{ item.avg_ms }} ms
              </td>
              <td class="text-right font-mono text-green">{{ item.min_ms }} ms</td>
              <td class="text-right font-mono text-red">{{ item.max_ms }} ms</td>
              <td class="text-right font-mono text-muted">{{ item.last_ms }} ms</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  metrics: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['reset-metrics'])

const resetMetrics = () => {
  emit('reset-metrics')
}

const getMethod = (endpointStr) => {
  if (!endpointStr) return 'API'
  return endpointStr.split(' ')[0] || 'API'
}

const getPath = (endpointStr) => {
  if (!endpointStr) return ''
  const parts = endpointStr.split(' ')
  return parts.length > 1 ? parts.slice(1).join(' ') : endpointStr
}

const getMethodClass = (endpointStr) => {
  const method = getMethod(endpointStr)
  if (method === 'GET') return 'badge-get'
  if (method === 'POST') return 'badge-post'
  if (method === 'PUT') return 'badge-put'
  if (method === 'DELETE') return 'badge-delete'
  return 'badge-default'
}

const getLatencyClass = (avgMs) => {
  if (avgMs < 150) return 'text-green'
  if (avgMs < 400) return 'text-orange'
  return 'text-red'
}
</script>

<style scoped>
.admin-card {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 25px;
  box-sizing: border-box;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.api-metrics-card {
  width: 100%;
}

.metrics-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #333;
  padding-bottom: 12px;
  margin-bottom: 15px;
}

.metrics-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: #00e676;
  display: flex;
  align-items: center;
}

.btn-secondary {
  background: #2b2b2b;
  border: 1px solid #444;
  padding: 6px 12px;
  font-size: 0.85rem;
  border-radius: 4px;
  cursor: pointer;
  color: white;
  font-weight: bold;
  transition: all 0.2s ease;
}

.btn-secondary:hover {
  background: #3a3a3a;
  border-color: #555;
}

.metrics-placeholder {
  color: #666;
  text-align: center;
  padding: 30px 10px;
  font-style: italic;
  background: #0d0d0d;
  border-radius: 6px;
  border: 1px dashed #2a2a2a;
}

.table-responsive {
  overflow-x: auto;
}

.metrics-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
  text-align: left;
}

.metrics-table th {
  background: #111;
  color: #888;
  padding: 10px 14px;
  font-weight: 600;
  border-bottom: 2px solid #282828;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.5px;
}

.metrics-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #222;
  color: #ddd;
}

.metrics-table tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.endpoint-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.method-badge {
  font-size: 0.7rem;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
  letter-spacing: 0.5px;
  font-family: monospace;
}

.badge-get {
  background: rgba(13, 202, 240, 0.15);
  color: #0dcaf0;
  border: 1px solid rgba(13, 202, 240, 0.3);
}

.badge-post {
  background: rgba(40, 167, 69, 0.15);
  color: #28a745;
  border: 1px solid rgba(40, 167, 69, 0.3);
}

.badge-put {
  background: rgba(255, 193, 7, 0.15);
  color: #ffc107;
  border: 1px solid rgba(255, 193, 7, 0.3);
}

.badge-delete {
  background: rgba(220, 53, 69, 0.15);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.3);
}

.badge-default {
  background: rgba(255, 255, 255, 0.1);
  color: #ccc;
}

.path-text {
  font-family: 'Courier New', Courier, monospace;
  font-weight: 600;
  color: #f1f1f1;
}

.text-right { text-align: right; }
.font-mono { font-family: 'Courier New', Courier, monospace; font-weight: bold; }
.text-cyan { color: #17a2b8; }
.text-green { color: #00e676; }
.text-orange { color: #ff9800; }
.text-red { color: #ff5252; }
.text-muted { color: #888; }
</style>
