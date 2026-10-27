<template>
  <div class="tracker-grid">
    <div class="tracker-card">
      <h3>Queued to Enter</h3>
      <div class="number text-yellow">{{ stats.queued }}</div>
    </div>
    <div class="tracker-card">
      <h3>Parked (Unpaid)</h3>
      <div class="number text-cyan">{{ stats.parked }}</div>
    </div>
    <div class="tracker-card">
      <h3>Paid (Queued to Exit)</h3>
      <div class="number text-magenta">{{ stats.paid }}</div>
    </div>
    <div class="tracker-card">
      <h3>Successfully Exited</h3>
      <div class="number text-green">{{ stats.exited }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  stats: {
    type: Object,
    required: true
  }
})
</script>

<style scoped>
.tracker-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
.tracker-card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; text-align: center; }
.tracker-card h3 { margin: 0 0 10px 0; font-size: 0.9rem; color: #888; text-transform: uppercase; }
.tracker-card .number { font-size: 3rem; font-weight: bold; font-family: monospace; }
.text-yellow { color: #ffc107; }
.text-cyan { color: #17a2b8; }
.text-magenta { color: #e83e8c; }
.text-green { color: #28a745; }
</style>
