<template>
  <div class="admin-card flex-grow console-card flex-card">
    <div class="console-header">
      <h2>
        <span class="mdi mdi-console-line" style="color: #ffc107; margin-right: 8px;"></span>
        Live System Engine Logs
        <span style="font-size: 0.75rem; background: rgba(255, 193, 7, 0.1); color: #ffc107; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(255, 193, 7, 0.2); font-family: monospace; font-weight: bold; margin-left: 8px; vertical-align: middle;">Port: {{ wsPort }}</span>
      </h2>
      <button class="btn btn-secondary btn-sm" @click="clearLogs">
        <span class="mdi mdi-delete-sweep-outline"></span> Clear Panel
      </button>
    </div>
    
    <div class="console-body" ref="consoleRef">
      <div v-if="logs.length === 0" class="console-placeholder">
        No logs captured. Waiting for system events...
      </div>
      <div v-else v-for="(log, idx) in logs" :key="idx" class="console-line">
        <span class="console-ts">[{{ log.ts }}]</span>
        <span class="console-level" :class="'level-' + log.level.toLowerCase()">[{{ log.level }}]</span>
        <span class="console-msg">{{ log.msg }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue'

const props = defineProps({
  logs: {
    type: Array,
    required: true
  },
  // From the dashboard's Server Connection settings (servers.app_port)
  appPort: {
    type: [Number, String],
    default: null
  }
})

const wsPort = computed(() => props.appPort || import.meta.env.VITE_WS_PORT || '5015')

const emit = defineEmits(['clear-logs'])

const consoleRef = ref(null)

const clearLogs = () => {
  emit('clear-logs')
}

const scrollToBottom = () => {
  nextTick(() => {
    if (consoleRef.value) {
      consoleRef.value.scrollTop = consoleRef.value.scrollHeight
    }
  })
}

watch(() => props.logs, () => {
  scrollToBottom()
}, { deep: true })
</script>

<style scoped>
.flex-grow { flex: 2 1 380px; }
.flex-card { display: flex; flex-direction: column; }
.console-card { min-height: 380px; }
.admin-card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 25px; box-sizing: border-box; }
.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #333;
  padding-bottom: 12px;
  margin-bottom: 15px;
}
.console-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: #007bff;
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
}
.btn-secondary:hover {
  background: #3a3a3a;
  border-color: #555;
}
.console-body {
  background-color: #050505;
  border: 1px solid #222;
  border-radius: 6px;
  padding: 15px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9rem;
  height: 250px;
  overflow-y: auto;
  box-shadow: inset 0 2px 8px rgba(0,0,0,0.8);
  display: flex;
  flex-direction: column;
  gap: 6px;
  scroll-behavior: smooth;
}
.console-body::-webkit-scrollbar {
  width: 8px;
}
.console-body::-webkit-scrollbar-track {
  background: #050505;
}
.console-body::-webkit-scrollbar-thumb {
  background: #222;
  border-radius: 4px;
}
.console-body::-webkit-scrollbar-thumb:hover {
  background: #333;
}
.console-placeholder {
  color: #555;
  text-align: center;
  margin-top: 100px;
  font-style: italic;
}
.console-line {
  display: flex;
  gap: 10px;
  line-height: 1.4;
  word-break: break-all;
}
.console-ts {
  color: #666;
  user-select: none;
}
.console-level {
  font-weight: bold;
  user-select: none;
  min-width: 65px;
  display: inline-block;
}
.level-entry { color: #ffc107; }
.level-exit { color: #28a745; }
.level-pay { color: #e83e8c; }
.level-admin { color: #17a2b8; }
.level-system { color: #17a2b8; }
.level-error { color: #dc3545; }
.level-info { color: #6f42c1; }
.console-msg { color: #e0e0e0; }
</style>
