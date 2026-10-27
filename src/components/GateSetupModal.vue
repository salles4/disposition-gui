<template>
  <div v-if="show" class="setup-modal-overlay" @click="handleBackdropClick">
    <div class="setup-modal-card" @click.stop>
      <div class="setup-modal-header">
        <h2 class="setup-modal-title">
          <span class="mdi mdi-cog setup-title-icon"></span>
          Terminal Setup
        </h2>
        <button v-if="isDismissible" class="setup-close-btn" @click="emit('close')">
          <span class="mdi mdi-close"></span>
        </button>
      </div>

      <div class="setup-modal-body">
        <div class="setup-form-group">
          <label class="setup-label">Gate Type</label>
          <div class="setup-select-wrapper">
            <select v-model="gateType" class="setup-select">
              <option value="entry">Entry Gate</option>
              <option value="exit">Exit Gate</option>
            </select>
            <span class="mdi mdi-chevron-down setup-select-arrow"></span>
          </div>
        </div>

        <div class="setup-form-group">
          <label class="setup-label">Gate Number</label>
          <input 
            type="number" 
            v-model.number="gateNumber" 
            min="1" 
            placeholder="e.g. 1, 2, 3" 
            class="setup-input"
            @keyup.enter="handleSave"
          >
        </div>

        <div class="setup-form-group">
          <label class="setup-label">Camera View</label>
          <div class="setup-select-wrapper">
            <select v-model="cameraView" class="setup-select">
              <option value="front">Front Camera (Vehicle Front)</option>
              <option value="back">Back Camera (Vehicle Rear)</option>
            </select>
            <span class="mdi mdi-chevron-down setup-select-arrow"></span>
          </div>
        </div>

        <div v-if="validationError" class="setup-error-msg">
          <span class="mdi mdi-alert-circle"></span>
          {{ validationError }}
        </div>
      </div>

      <div class="setup-modal-footer">
        <button class="setup-btn setup-btn-success" @click="handleSave">
          <span class="mdi mdi-check-circle-outline"></span>
          Save & Connect
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  initialType: {
    type: String,
    default: 'entry'
  },
  initialNumber: {
    type: [Number, String],
    default: 1
  },
  initialCamera: {
    type: String,
    default: 'front'
  },
  isDismissible: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['save', 'close'])

const gateType = ref(props.initialType)
const gateNumber = ref(props.initialNumber)
const cameraView = ref(props.initialCamera)
const validationError = ref('')

// Sync props if they change
watch(() => props.show, (newVal) => {
  if (newVal) {
    gateType.value = props.initialType
    gateNumber.value = props.initialNumber
    cameraView.value = props.initialCamera
    validationError.value = ''
  }
})

const handleBackdropClick = () => {
  if (props.isDismissible) {
    emit('close')
  }
}

const handleSave = () => {
  if (!gateNumber.value || parseInt(gateNumber.value) < 1) {
    validationError.value = 'Please enter a valid gate number (1 or higher).'
    return
  }
  validationError.value = ''
  emit('save', {
    type: gateType.value,
    number: parseInt(gateNumber.value),
    camera: cameraView.value
  })
}
</script>

<style scoped>
/* Glassmorphic Overlay */
.setup-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

/* Premium Card Design */
.setup-modal-card {
  width: 100%;
  max-width: 400px;
  background: #141414;
  border: 1px solid #2d2d2d;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 
              0 0 40px rgba(0, 123, 255, 0.05);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: modalReveal 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modalReveal {
  from {
    transform: scale(0.95) translateY(10px);
    opacity: 0;
  }
  to {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
}

/* Header */
.setup-modal-header {
  padding: 18px 24px;
  border-bottom: 1px solid #222;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.setup-modal-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 10px;
}

.setup-title-icon {
  color: #ffc107;
  font-size: 1.4rem;
}

.setup-close-btn {
  background: none;
  border: none;
  color: #777;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.setup-close-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}

/* Body */
.setup-modal-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.setup-form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.setup-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Input Styles */
.setup-input {
  width: 100%;
  padding: 12px 16px;
  background: #0b0b0b;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  color: #ffffff;
  font-size: 1rem;
  font-weight: 500;
  box-sizing: border-box;
  transition: all 0.2s ease;
}

.setup-input:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.15);
  background: #0d0d0d;
}

/* Dropdown Styles */
.setup-select-wrapper {
  position: relative;
  width: 100%;
}

.setup-select {
  width: 100%;
  padding: 12px 16px;
  padding-right: 40px;
  background: #0b0b0b;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  color: #ffffff;
  font-size: 1rem;
  font-weight: 500;
  box-sizing: border-box;
  appearance: none;
  -webkit-appearance: none;
  transition: all 0.2s ease;
  cursor: pointer;
}

.setup-select:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.15);
  background: #0d0d0d;
}

.setup-select-arrow {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  color: #777;
  font-size: 1.2rem;
  pointer-events: none;
}

/* Error message */
.setup-error-msg {
  color: #dc3545;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(220, 53, 69, 0.08);
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid rgba(220, 53, 69, 0.2);
}

/* Footer & Buttons */
.setup-modal-footer {
  padding: 18px 24px;
  border-top: 1px solid #222;
  display: flex;
  justify-content: flex-end;
}

.setup-btn {
  border: none;
  padding: 12px 24px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}

.setup-btn-success {
  background: #28a745;
  color: #ffffff;
  width: 100%;
  justify-content: center;
}

.setup-btn-success:hover {
  background: #218838;
}

.setup-btn-success:active {
  background: #1e7e34;
}
</style>
