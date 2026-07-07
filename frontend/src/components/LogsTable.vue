<script setup>
defineProps({
  logs: { type: Array, required: true },
})

defineEmits(['refresh'])

function fmt(iso) {
  return new Date(iso).toLocaleString()
}
</script>

<template>
  <section class="card">
    <div class="spread">
      <h2>Incoming requests</h2>
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
      <tbody>
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
      </tbody>
    </table>
  </section>
</template>

<style scoped>
h2 {
  font-size: 1.05rem;
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
