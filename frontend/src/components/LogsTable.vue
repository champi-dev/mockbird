<script setup>
defineProps({
  logs: { type: Array, required: true },
  live: { type: Boolean, default: false },
})

defineEmits(['refresh'])

function fmt(iso) {
  return new Date(iso).toLocaleString()
}
</script>

<template>
  <section class="card">
    <div class="spread">
      <h2>
        Incoming requests
        <span v-if="live" class="live">
          <span class="dot" /> live
        </span>
      </h2>
      <button class="btn btn-ghost" @click="$emit('refresh')">
        ↻ Refresh
      </button>
    </div>
    <p v-if="!logs.length" class="muted empty">
      No requests logged yet. Call your mock URL to see traffic here.
    </p>
    <table v-else>
      <thead>
        <tr>
          <th>Time</th>
          <th>Method</th>
          <th>Path</th>
          <th>Status</th>
          <th>Matched</th>
        </tr>
      </thead>
      <transition-group tag="tbody" name="list">
        <tr v-for="log in logs" :key="log.id">
          <td class="muted">{{ fmt(log.created_at) }}</td>
          <td>
            <span :class="['badge', `badge-${log.method}`]">
              {{ log.method }}
            </span>
          </td>
          <td><code>{{ log.path }}</code></td>
          <td>{{ log.status_code }}</td>
          <td>{{ log.matched ? '✓' : '—' }}</td>
        </tr>
      </transition-group>
    </table>
  </section>
</template>

<style scoped>
h2 {
  font-size: 1.05rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.live {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--success);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--success);
  animation: pulse 1.6s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.4;
    transform: scale(0.8);
  }
}

table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
  font-size: 0.85rem;
}

th {
  text-align: left;
  color: var(--text-soft);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
}

td {
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid var(--border);
}

code {
  font-size: 0.78rem;
}

.empty {
  text-align: center;
  padding: 2rem 0;
}
</style>
