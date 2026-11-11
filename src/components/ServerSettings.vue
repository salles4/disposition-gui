<template>
  <div class="admin-card server-card">
    <h2><span class="mdi mdi-server-network heading-icon"></span> Server Connection</h2>
    <p class="card-subtitle">Where this app finds the core API, and which ports it listens on.</p>

    <form @submit.prevent="save" novalidate>
      <div class="field-row">
        <div class="form-group grow">
          <label for="srv-api-host" class="label-with-info">
            Core API Server IP:
            <span class="tooltip-container">
              <span class="mdi mdi-information-outline info-icon"></span>
              <span class="tooltip-content">
                <span class="tooltip-title">Core API Server</span>
                <span>The parking backend this app calls for billing, payments, exits and the live disposition stream. Applies immediately: the stream reconnects and the teller service is updated.</span>
                <span class="tech-tooltip"><strong>Technical:</strong> Saved as <code>servers.api_base_url</code> in <code>data/config.json</code> (not tracked by git, so pulls never overwrite it). Add <code>https://</code> in front of the IP if the API uses HTTPS.</span>
              </span>
            </span>
          </label>
          <input id="srv-api-host" v-model.trim="form.apiHost" type="text" placeholder="e.g. 192.168.0.13" class="compact-input" autocomplete="off" spellcheck="false">
        </div>
        <div class="form-group port">
          <label for="srv-api-port">API Port:</label>
          <input id="srv-api-port" v-model.trim="form.apiPort" type="text" inputmode="numeric" placeholder="9080" class="compact-input">
        </div>
      </div>

      <div class="field-row">
        <div class="form-group grow">
          <label for="srv-app-port" class="label-with-info">
            App Port:
            <span class="tooltip-container">
              <span class="mdi mdi-information-outline info-icon"></span>
              <span class="tooltip-content">
                <span class="tooltip-title">App Port</span>
                <span>The port this dashboard and the camera webhooks are served on. Takes effect after the app is restarted; open the dashboard on the new port afterwards.</span>
                <span class="tech-tooltip"><strong>Technical:</strong> Saved as <code>servers.app_port</code>; overrides <code>PORT</code> in <code>.env</code>. In dev mode the frontend still connects using <code>VITE_WS_PORT</code>.</span>
              </span>
            </span>
          </label>
          <input id="srv-app-port" v-model.trim="form.appPort" type="text" inputmode="numeric" placeholder="5015" class="compact-input">
        </div>
        <div class="form-group grow">
          <label for="srv-teller-port" class="label-with-info">
            Teller Port:
            <span class="tooltip-container">
              <span class="mdi mdi-information-outline info-icon"></span>
              <span class="tooltip-content">
                <span class="tooltip-title">Teller Port</span>
                <span>The port of the local teller service used for real device payments. Restart the teller service after changing it.</span>
                <span class="tech-tooltip"><strong>Technical:</strong> Saved as <code>servers.teller_port</code>.</span>
              </span>
            </span>
          </label>
          <input id="srv-teller-port" v-model.trim="form.tellerPort" type="text" inputmode="numeric" placeholder="5010" class="compact-input">
        </div>
      </div>

      <p class="current-line">Currently using <code>{{ servers.api_base_url || '—' }}</code></p>

      <p v-if="result" :class="['result-msg', result.ok ? (result.restart_needed ? 'warn' : 'ok') : 'error']" role="status">
        <span :class="['mdi', result.ok ? (result.restart_needed ? 'mdi-restart-alert' : 'mdi-check-circle') : 'mdi-alert-circle']"></span>
        {{ result.message }}
      </p>

      <div class="actions">
        <button type="button" class="btn btn-secondary" :disabled="!isDirty || saving" @click="resetForm">Reset</button>
        <button type="submit" class="btn btn-success" :disabled="!isDirty || saving">
          <span :class="['mdi', saving ? 'mdi-loading mdi-spin' : 'mdi-content-save']"></span>
          {{ saving ? 'Saving…' : 'Save Server Settings' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  socket: { type: Object, required: true },
  servers: { type: Object, required: true }
})

// Split the saved URL into the IP and port boxes; keep https:// on the IP so it isn't lost on save
const fromServers = (s) => {
  let apiHost = ''
  let apiPort = ''
  try {
    const u = new URL(s.api_base_url)
    apiHost = (u.protocol === 'https:' ? 'https://' : '') + u.hostname
    apiPort = u.port || (u.protocol === 'https:' ? '443' : '80')
  } catch { /* no saved URL yet */ }
  return {
    apiHost,
    apiPort,
    appPort: s.app_port != null ? String(s.app_port) : '',
    tellerPort: s.teller_port != null ? String(s.teller_port) : ''
  }
}

const form = reactive(fromServers(props.servers))
const saved = ref(fromServers(props.servers))
const isDirty = computed(() => Object.keys(form).some(k => form[k] !== saved.value[k]))
const saving = ref(false)
const result = ref(null)

const resetForm = () => {
  Object.assign(form, saved.value)
  result.value = null
}

// Follow saved values from the server, but never overwrite what the user is typing
watch(() => props.servers, (s) => {
  const wasDirty = isDirty.value
  saved.value = fromServers(s)
  if (!wasDirty) Object.assign(form, saved.value)
}, { deep: true })

const save = () => {
  saving.value = true
  result.value = null
  props.socket.emit('admin_update_servers', {
    api_host: form.apiHost,
    api_port: form.apiPort,
    app_port: form.appPort,
    teller_port: form.tellerPort
  })
}

const onResult = (res) => {
  saving.value = false
  result.value = res
  if (res.ok) {
    // config_sync carries the canonical values; treat the form as saved right away
    saved.value = { ...form }
  }
}

onMounted(() => props.socket.on('servers_update_result', onResult))
onUnmounted(() => props.socket.off('servers_update_result', onResult))
</script>

<style scoped>
.admin-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 24px; box-sizing: border-box; box-shadow: var(--shadow); min-width: 0; }
.admin-card h2 { font-size: 1.15rem; color: var(--text); margin: 0 0 6px; display: flex; align-items: center; gap: 8px; }
.heading-icon { color: var(--c-cyan); }
.card-subtitle { font-size: 0.85rem; color: var(--text-muted); margin: 0 0 18px; line-height: 1.4; }

.field-row { display: flex; gap: 12px; flex-wrap: wrap; }
.form-group { margin-bottom: 14px; display: flex; flex-direction: column; }
.form-group.grow { flex: 1 1 140px; }
.form-group.port { flex: 0 0 96px; }

label { display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 5px; }
.label-with-info { display: flex; align-items: center; gap: 6px; }

.compact-input {
  padding: 9px 10px;
  background: var(--input-bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 4px;
  font-size: 0.88rem;
  width: 100%;
  box-sizing: border-box;
  font-family: Consolas, monospace;
}
.compact-input:focus { outline: none; border-color: var(--c-cyan); }

.current-line { font-size: 0.78rem; color: var(--text-muted); margin: 2px 0 12px; }
code { background: var(--code-bg); padding: 1px 4px; border-radius: 3px; font-family: Consolas, monospace; color: var(--c-yellow); }

.result-msg { display: flex; gap: 8px; align-items: flex-start; font-size: 0.82rem; padding: 10px 12px; border-radius: 6px; margin: 0 0 12px; line-height: 1.4; }
.result-msg.ok { background: rgba(40, 167, 69, 0.1); color: var(--c-green); border: 1px solid rgba(40, 167, 69, 0.3); }
.result-msg.warn { background: rgba(255, 193, 7, 0.12); color: var(--c-yellow); border: 1px solid rgba(255, 193, 7, 0.35); }
.result-msg.error { background: rgba(244, 63, 94, 0.1); color: var(--c-rose); border: 1px solid rgba(244, 63, 94, 0.3); }

.actions { display: flex; gap: 10px; }
.btn { border: none; padding: 11px 18px; border-radius: 5px; cursor: pointer; font-weight: bold; color: #fff; font-size: 0.95rem; transition: filter 0.2s, opacity 0.2s; display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-family: inherit; }
.btn:hover:not(:disabled) { filter: brightness(1.1); }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-success { background: var(--btn-ok-bg); flex: 1; }
.btn-secondary { background: var(--btn-neutral-bg); color: var(--btn-neutral-text); }

/* Tooltips (same look as Simulation Settings) */
.tooltip-container { position: relative; display: inline-flex; align-items: center; }
.info-icon { color: var(--text-faint); font-size: 0.95rem; cursor: pointer; transition: color 0.2s; line-height: 1; }
.info-icon:hover { color: var(--c-yellow); }
.tooltip-content {
  visibility: hidden; opacity: 0; pointer-events: none;
  position: absolute; z-index: 100; bottom: 125%; left: 50%; transform: translateX(-50%);
  width: 280px; background-color: var(--tooltip-bg); color: var(--text); text-align: left;
  border-radius: 6px; padding: 12px; border: 1px solid var(--border);
  box-shadow: var(--shadow-pop); font-size: 0.75rem; line-height: 1.4;
  display: flex; flex-direction: column; gap: 6px;
  transition: opacity 0.2s, visibility 0.2s;
}
.tooltip-title { font-weight: bold; color: var(--c-yellow); font-size: 0.8rem; border-bottom: 1px solid var(--border-soft); padding-bottom: 4px; }
.tech-tooltip { color: var(--text-muted); border-top: 1px dashed var(--border); padding-top: 6px; }
.tooltip-container:hover .tooltip-content { visibility: visible; opacity: 1; }
</style>
