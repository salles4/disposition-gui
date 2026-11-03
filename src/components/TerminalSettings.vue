<template>
  <div class="live-actions-card terminal-card">
    <h2>
      <span class="mdi mdi-ip-network" style="color: #00bcd4;"></span>
      Terminals &amp; Cameras
    </h2>
    <p class="card-subtitle">Each terminal has entry and exit gates, and each gate a front and back LPR camera. Gate numbers are assigned automatically.</p>

    <!-- Cameras sending detections that are not under any gate yet -->
    <div v-if="unregisteredCameras.length" class="unregistered-panel">
      <div class="unregistered-title">
        <span class="mdi mdi-alert-outline"></span>
        Detected but not registered ({{ unregisteredCameras.length }})
      </div>
      <p class="unregistered-hint">These cameras are sending plates that are being ignored. Assign each one to a gate, then save.</p>
      <div v-for="cam in unregisteredCameras" :key="cam.ip" class="unregistered-row">
        <div class="unregistered-info">
          <span class="unregistered-ip">{{ cam.ip }}</span>
          <span class="unregistered-meta">
            Last plate <strong>{{ cam.last_plate }}</strong> · {{ formatSeen(cam.last_seen) }} · {{ cam.hits }} read{{ cam.hits === 1 ? '' : 's' }}
            <template v-if="cam.mac"> · MAC {{ cam.mac }}</template>
          </span>
        </div>
        <span v-if="isInDraft(cam.ip)" class="assigned-note"><span class="mdi mdi-check"></span> Assigned, save to apply</span>
        <select v-else-if="emptySlots.length" class="assign-select" value="" @change="assignUnregistered(cam.ip, $event)">
          <option value="" disabled>Assign to…</option>
          <option v-for="slot in emptySlots" :key="slot.key" :value="slot.key">{{ slot.label }}</option>
        </select>
        <span v-else class="assigned-note muted">Add a gate below first</span>
        <button class="btn-dismiss" title="Dismiss" @click="dismissUnregistered(cam.ip)">
          <span class="mdi mdi-close"></span>
        </button>
      </div>
    </div>

    <div v-if="!draft.length" class="empty-state">No terminals yet. Add one to start mapping cameras.</div>

    <div v-for="terminal in draft" :key="terminal.id" class="terminal-block">
      <div class="terminal-header">
        <input v-model="terminal.name" type="text" class="terminal-name-input" :placeholder="`Terminal ${terminal.id}`" :aria-label="`Name of terminal ${terminal.id}`">
        <button class="icon-btn danger" :title="`Remove ${terminal.name || 'terminal'}`" @click="removeTerminal(terminal)">
          <span class="mdi mdi-delete-outline"></span>
        </button>
      </div>

      <div v-if="!terminal.gates.length" class="empty-gates">No gates yet.</div>

      <div v-for="gate in terminal.gates" :key="gate.id" class="gate-block">
        <div class="gate-header">
          <span class="gate-label">Gate {{ gate.id }}</span>
          <select v-model="gate.direction" :class="['direction-select', gate.direction]" :aria-label="`Direction of gate ${gate.id}`">
            <option value="entry">Entry</option>
            <option value="exit">Exit</option>
          </select>
          <button class="icon-btn danger" :title="`Remove gate ${gate.id}`" @click="removeGate(terminal, gate)">
            <span class="mdi mdi-close"></span>
          </button>
        </div>
        <div class="camera-grid">
          <label v-for="role in ['front', 'back']" :key="role" class="camera-field">
            <span class="camera-role"><span :class="['mdi', role === 'front' ? 'mdi-camera' : 'mdi-camera-rear']"></span> {{ role === 'front' ? 'Front' : 'Back' }} camera IP</span>
            <input v-model.trim="gate.cameras[role]" type="text" placeholder="e.g. 192.168.0.66" :class="['compact-input', { invalid: invalidIps.has(gate.cameras[role]) }]" autocomplete="off" spellcheck="false">
          </label>
        </div>
      </div>

      <div class="add-gate-row">
        <button class="btn-add-gate" @click="addGate(terminal, 'entry')"><span class="mdi mdi-plus"></span> Entry gate</button>
        <button class="btn-add-gate" @click="addGate(terminal, 'exit')"><span class="mdi mdi-plus"></span> Exit gate</button>
      </div>
    </div>

    <button class="btn-add-terminal" @click="addTerminal"><span class="mdi mdi-plus-circle"></span> Add terminal</button>

    <ul v-if="errors.length" class="error-list" role="alert">
      <li v-for="err in errors" :key="err"><span class="mdi mdi-alert-circle"></span> {{ err }}</li>
    </ul>

    <div class="actions">
      <button type="button" class="btn btn-secondary" :disabled="!isDirty" @click="resetDraft">Reset</button>
      <button type="button" class="btn btn-save" :disabled="!isDirty" @click="save">
        <span class="mdi mdi-content-save"></span> Save Terminals
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  socket: { type: Object, required: true },
  terminals: { type: Array, required: true },
  unregisteredCameras: { type: Array, required: true }
})
const emit = defineEmits(['notify'])

const IP_PATTERN = /^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/
const ROLES = ['front', 'back']

// Editable copy with both camera slots present, so inputs can bind to them
const toDraft = (terminals) => (terminals || []).map(t => ({
  id: t.id,
  name: t.name || '',
  gates: (t.gates || []).map(g => ({
    id: g.id,
    direction: g.direction === 'exit' ? 'exit' : 'entry',
    cameras: { front: g.cameras?.front || '', back: g.cameras?.back || '' }
  }))
}))

const draft = ref(toDraft(props.terminals))
const errors = ref([])
const snapshot = (list) => JSON.stringify(list)
const savedSnapshot = ref(snapshot(toDraft(props.terminals)))
const isDirty = computed(() => snapshot(draft.value) !== savedSnapshot.value)

// Follow saved values from the server, but never overwrite unsaved edits
watch(() => props.terminals, (terminals) => {
  const wasDirty = isDirty.value
  savedSnapshot.value = snapshot(toDraft(terminals))
  if (!wasDirty) draft.value = toDraft(terminals)
}, { deep: true })

const resetDraft = () => {
  draft.value = JSON.parse(savedSnapshot.value)
  errors.value = []
}

const allGates = computed(() => draft.value.flatMap(t => t.gates.map(g => ({ terminal: t, gate: g }))))
const nextId = (ids) => (ids.length ? Math.max(...ids) : 0) + 1

const addTerminal = () => {
  const id = nextId(draft.value.map(t => t.id))
  draft.value.push({ id, name: `Terminal ${id}`, gates: [] })
}

const addGate = (terminal, direction) => {
  const id = nextId(allGates.value.map(({ gate }) => gate.id))
  terminal.gates.push({ id, direction, cameras: { front: '', back: '' } })
}

const hasCameras = (gate) => ROLES.some(role => gate.cameras[role])

const removeGate = (terminal, gate) => {
  if (hasCameras(gate) && !confirm(`Remove gate ${gate.id} and its cameras?`)) return
  terminal.gates = terminal.gates.filter(g => g !== gate)
}

const removeTerminal = (terminal) => {
  const label = terminal.name || `Terminal ${terminal.id}`
  if (terminal.gates.length && !confirm(`Remove ${label} and its ${terminal.gates.length} gate(s)?`)) return
  draft.value = draft.value.filter(t => t !== terminal)
}

const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1)

const emptySlots = computed(() => allGates.value.flatMap(({ terminal, gate }) =>
  ROLES.filter(role => !gate.cameras[role]).map(role => ({
    key: `${gate.id}:${role}`,
    label: `${terminal.name || `Terminal ${terminal.id}`} · Gate ${gate.id} ${capitalize(gate.direction)} · ${capitalize(role)}`
  }))
))

const isInDraft = (ip) => allGates.value.some(({ gate }) => ROLES.some(role => gate.cameras[role] === ip))

const assignUnregistered = (ip, event) => {
  const [gateId, role] = event.target.value.split(':')
  const found = allGates.value.find(({ gate }) => String(gate.id) === gateId)
  if (found) found.gate.cameras[role] = ip
}

const dismissUnregistered = (ip) => {
  props.socket.emit('dismiss_unregistered_camera', { ip })
}

const formatSeen = (iso) => {
  if (!iso) return '—'
  const secs = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return new Date(iso).toLocaleTimeString()
}

// IPs that are malformed or used by more than one camera slot, highlighted in the inputs
const invalidIps = computed(() => {
  const seen = new Set()
  const bad = new Set()
  for (const { gate } of allGates.value) {
    for (const role of ROLES) {
      const ip = gate.cameras[role]
      if (!ip) continue
      if (!IP_PATTERN.test(ip) || seen.has(ip)) bad.add(ip)
      seen.add(ip)
    }
  }
  return bad
})

const validate = () => {
  const found = []
  const seen = new Map()
  for (const { terminal, gate } of allGates.value) {
    for (const role of ROLES) {
      const ip = gate.cameras[role]
      if (!ip) continue
      const where = `${terminal.name || `Terminal ${terminal.id}`} Gate ${gate.id} ${role}`
      if (!IP_PATTERN.test(ip)) found.push(`${where}: "${ip}" is not a valid IP address.`)
      else if (seen.has(ip)) found.push(`${ip} is used by both ${seen.get(ip)} and ${where}.`)
      else seen.set(ip, where)
    }
  }
  return found
}

const save = () => {
  errors.value = validate()
  if (errors.value.length) return
  const terminals = draft.value.map(t => ({
    id: t.id,
    name: t.name.trim() || `Terminal ${t.id}`,
    gates: t.gates.map(g => ({
      id: g.id,
      direction: g.direction,
      cameras: Object.fromEntries(ROLES.filter(role => g.cameras[role]).map(role => [role, g.cameras[role]]))
    }))
  }))
  props.socket.emit('admin_update_terminals', { terminals })
  // config_sync carries the canonical values back; treat the draft as saved right away
  savedSnapshot.value = snapshot(toDraft(terminals))
  draft.value = toDraft(terminals)
  emit('notify', 'Terminals and cameras saved.')
}
</script>

<style scoped>
.live-actions-card {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 25px;
  box-sizing: border-box;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  transition: border-color 0.3s ease;
}
.live-actions-card:hover { border-color: #444; }
.live-actions-card h2 { font-size: 1.2rem; color: #ff9800; margin: 0; display: flex; align-items: center; gap: 8px; }
.card-subtitle { font-size: 0.85rem; color: #888; margin-top: 8px; margin-bottom: 20px; line-height: 1.4; text-align: left; }

/* Unregistered camera alerts */
.unregistered-panel { margin-bottom: 16px; padding: 12px; border-radius: 6px; border: 1px solid rgba(255, 193, 7, 0.35); background: rgba(255, 193, 7, 0.06); }
.unregistered-title { color: #ffc107; font-weight: bold; font-size: 0.9rem; display: flex; align-items: center; gap: 6px; }
.unregistered-hint { color: #999; font-size: 0.78rem; margin: 4px 0 10px; }
.unregistered-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-top: 1px solid rgba(255, 193, 7, 0.15); flex-wrap: wrap; }
.unregistered-info { flex: 1 1 160px; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.unregistered-ip { font-family: monospace; font-size: 0.9rem; color: #fff; }
.unregistered-meta { font-size: 0.75rem; color: #aaa; overflow-wrap: anywhere; }
.unregistered-meta strong { color: #ffc107; font-family: monospace; }
.assign-select { background: #ffc107; color: #000; border: none; border-radius: 4px; padding: 6px 8px; font-weight: bold; font-size: 0.8rem; cursor: pointer; max-width: 100%; }
.assigned-note { font-size: 0.78rem; color: #5dd879; white-space: nowrap; }
.assigned-note.muted { color: #999; }
.btn-dismiss { background: none; border: none; color: #888; cursor: pointer; font-size: 1rem; padding: 2px 4px; }
.btn-dismiss:hover { color: #fff; }

.empty-state { text-align: center; color: #666; padding: 20px; font-size: 0.9rem; }

/* Terminal > gate > camera tree */
.terminal-block { border: 1px solid #2a2a2a; border-radius: 6px; background: rgba(255, 255, 255, 0.02); padding: 12px; margin-bottom: 12px; }
.terminal-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.terminal-name-input { flex: 1; min-width: 0; background: transparent; border: 1px solid transparent; border-radius: 4px; color: #fff; font-size: 1rem; font-weight: bold; padding: 4px 6px; font-family: inherit; }
.terminal-name-input:hover { border-color: #333; }
.terminal-name-input:focus { outline: none; border-color: #17a2b8; background: #000; }
.empty-gates { color: #666; font-size: 0.8rem; padding: 2px 6px 8px; }

.gate-block { border-left: 2px solid #333; padding: 8px 0 8px 10px; margin-bottom: 8px; }
.gate-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.gate-label { font-weight: bold; font-size: 0.85rem; color: #eee; background: rgba(255, 255, 255, 0.06); padding: 2px 6px; border-radius: 3px; }
.direction-select { border-radius: 3px; border: 1px solid transparent; padding: 2px 4px; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; cursor: pointer; }
.direction-select.entry { background: rgba(40, 167, 69, 0.1); color: #28a745; border-color: rgba(40, 167, 69, 0.25); }
.direction-select.exit { background: rgba(23, 162, 184, 0.1); color: #17a2b8; border-color: rgba(23, 162, 184, 0.25); }
.direction-select option { background: #1a1a1a; color: #eee; }
.gate-header .icon-btn { margin-left: auto; }

.camera-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
.camera-field { display: flex; flex-direction: column; gap: 4px; }
.camera-role { font-size: 0.75rem; color: #888; display: flex; align-items: center; gap: 4px; }
.compact-input { padding: 7px 9px; background: #000; border: 1px solid #333; color: #fff; border-radius: 4px; font-size: 0.85rem; width: 100%; box-sizing: border-box; font-family: Consolas, monospace; }
.compact-input:focus { outline: none; border-color: #17a2b8; }
.compact-input.invalid { border-color: #f43f5e; }

.icon-btn { background: none; border: none; cursor: pointer; font-size: 1rem; padding: 2px 4px; color: #888; }
.icon-btn.danger:hover { color: #dc3545; }

.add-gate-row { display: flex; gap: 8px; flex-wrap: wrap; }
.btn-add-gate { background: none; border: 1px dashed #444; color: #ccc; border-radius: 4px; padding: 5px 10px; font-size: 0.8rem; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.btn-add-gate:hover { border-color: #00bcd4; color: #00bcd4; }
.btn-add-terminal { width: 100%; background: none; border: 1px dashed #00bcd4; color: #00bcd4; border-radius: 6px; padding: 9px; font-weight: bold; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; margin-bottom: 14px; }
.btn-add-terminal:hover { background: rgba(0, 188, 212, 0.08); }

.error-list { list-style: none; padding: 10px 12px; margin: 0 0 12px; border-radius: 6px; background: rgba(244, 63, 94, 0.1); border: 1px solid rgba(244, 63, 94, 0.3); color: #ff7a8f; font-size: 0.8rem; display: flex; flex-direction: column; gap: 4px; }

.actions { display: flex; gap: 10px; }
.btn { border: none; padding: 10px 16px; border-radius: 5px; cursor: pointer; font-weight: bold; color: white; font-size: 0.9rem; transition: filter 0.2s, opacity 0.2s; display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-family: inherit; }
.btn:hover:not(:disabled) { filter: brightness(1.2); }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-save { background: #00bcd4; color: #000; flex: 1; }
.btn-secondary { background: #333; }
</style>
