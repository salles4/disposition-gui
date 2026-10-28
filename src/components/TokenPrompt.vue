<template>
  <div v-if="needsToken" class="token-prompt">
    <button v-if="minimized" class="token-pill" @click="minimized = false" title="WebSocket token expired">
      <span class="mdi mdi-key-alert"></span> Token expired
    </button>

    <div v-else class="token-card">
      <div class="token-head">
        <span class="mdi mdi-key-alert"></span>
        <span class="token-title">{{ status.auth_failed ? 'Token rejected' : 'Token expired' }}</span>
        <button class="token-min" @click="minimized = true" title="Minimize">
          <span class="mdi mdi-minus"></span>
        </button>
      </div>
      <form class="token-row" @submit.prevent="submit">
        <input
          v-model="tokenInput"
          class="token-input"
          type="text"
          placeholder="Paste new token"
          spellcheck="false"
          autocomplete="off"
        />
        <button class="token-save" type="submit" :disabled="!tokenInput.trim() || saving">
          {{ saving ? '...' : 'Save' }}
        </button>
      </form>
      <div v-if="message" class="token-msg" :class="{ error: !messageOk }">{{ message }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  socket: { type: Object, required: true }
})

const status = ref({ exp: null, auth_failed: false })
const now = ref(Date.now() / 1000)
const minimized = ref(false)
const tokenInput = ref('')
const saving = ref(false)
const message = ref('')
const messageOk = ref(false)

const needsToken = computed(() => {
  if (status.value.auth_failed) return true
  return !!status.value.exp && now.value >= status.value.exp
})

const submit = () => {
  saving.value = true
  message.value = ''
  props.socket.emit('update_ws_token', { token: tokenInput.value.trim() })
}

const onStatus = (data) => {
  status.value = data
  now.value = Date.now() / 1000
}

const onResult = (res) => {
  saving.value = false
  message.value = res.message
  messageOk.value = res.ok
  if (res.ok) tokenInput.value = ''
}

const requestStatus = () => props.socket.emit('request_token_status')

let clock = null
onMounted(() => {
  props.socket.on('token_status', onStatus)
  props.socket.on('token_update_result', onResult)
  props.socket.on('connect', requestStatus)
  if (props.socket.connected) requestStatus()
  clock = setInterval(() => { now.value = Date.now() / 1000 }, 30000)
})

onUnmounted(() => {
  props.socket.off('token_status', onStatus)
  props.socket.off('token_update_result', onResult)
  props.socket.off('connect', requestStatus)
  clearInterval(clock)
})
</script>

<style scoped>
.token-prompt { position: fixed; left: 16px; bottom: 16px; z-index: 9000; font-size: 0.78rem; }

.token-pill {
  display: inline-flex; align-items: center; gap: 5px; padding: 5px 10px;
  background: #1e1e1e; color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 999px; font-size: 0.75rem; cursor: pointer; opacity: 0.85;
}
.token-pill:hover { opacity: 1; }

.token-card {
  width: 250px; background: #1a1a1a; border: 1px solid #333; border-left: 3px solid #f59e0b;
  border-radius: 6px; padding: 8px 10px; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4); box-sizing: border-box;
}
.token-head { display: flex; align-items: center; gap: 6px; color: #f59e0b; margin-bottom: 6px; }
.token-title { flex: 1; font-weight: 600; }
.token-min { background: none; border: none; color: #777; cursor: pointer; padding: 0; font-size: 0.9rem; line-height: 1; }
.token-min:hover { color: #ccc; }

.token-row { display: flex; gap: 6px; }
.token-input {
  flex: 1; min-width: 0; background: #111; border: 1px solid #333; border-radius: 4px;
  color: #ddd; padding: 4px 6px; font-family: monospace; font-size: 0.72rem;
}
.token-input:focus { outline: none; border-color: #f59e0b; }
.token-save {
  background: #f59e0b; color: #111; border: none; border-radius: 4px; padding: 4px 10px;
  font-weight: 600; font-size: 0.72rem; cursor: pointer;
}
.token-save:disabled { opacity: 0.4; cursor: default; }

.token-msg { margin-top: 5px; color: #28a745; font-size: 0.7rem; }
.token-msg.error { color: #f43f5e; }
</style>
