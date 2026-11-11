<template>
  <div class="admin-card console-card">
    <div class="console-header">
      <h2>
        <span class="mdi mdi-console-line heading-icon"></span>
        Live System Engine Logs
        <span class="port-chip">Port: {{ wsPort }}</span>
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
.admin-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 24px; box-sizing: border-box; box-shadow: var(--shadow); min-width: 0; }
.console-card { display: flex; flex-direction: column; }
.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--border-soft);
  padding-bottom: 12px;
  margin-bottom: 15px;
}
.console-header h2 {
  margin: 0;
  font-size: 1.15rem;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.heading-icon { color: var(--c-yellow); }
.port-chip {
  font-size: 0.75rem;
  background: rgba(255, 193, 7, 0.12);
  color: var(--c-yellow);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 193, 7, 0.3);
  font-family: monospace;
  font-weight: bold;
}
.btn-secondary {
  background: var(--btn-neutral-bg);
  border: 1px solid var(--border);
  padding: 6px 12px;
  font-size: 0.85rem;
  border-radius: 4px;
  cursor: pointer;
  color: var(--btn-neutral-text);
  font-weight: bold;
  font-family: inherit;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.btn-secondary:hover { border-color: var(--border-strong); }
/* Fills the card's height (set by the row) without its own content stretching the row */
.console-body {
  flex: 1 1 auto;
  height: 0;
  min-height: 320px;
  background-color: var(--console-bg);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 15px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.88rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  scroll-behavior: smooth;
}
.console-body::-webkit-scrollbar { width: 8px; }
.console-body::-webkit-scrollbar-track { background: transparent; }
.console-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
.console-body::-webkit-scrollbar-thumb:hover { background: var(--border-strong); }
.console-placeholder {
  color: var(--text-faint);
  text-align: center;
  margin: auto 0;
  font-style: italic;
}
.console-line { display: flex; gap: 10px; line-height: 1.4; word-break: break-all; }
.console-ts { color: var(--text-faint); user-select: none; flex-shrink: 0; }
.console-level { font-weight: bold; user-select: none; min-width: 65px; display: inline-block; flex-shrink: 0; }
.level-entry { color: var(--c-yellow); }
.level-exit { color: var(--c-green); }
.level-pay { color: var(--c-pink); }
.level-admin { color: var(--c-cyan); }
.level-system { color: var(--c-cyan); }
.level-error { color: var(--c-red); }
.level-info { color: var(--c-violet); }
.console-msg { color: var(--console-text); }
</style>
