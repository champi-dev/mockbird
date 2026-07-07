<script setup>
defineProps({
  resources: { type: Array, required: true },
})

defineEmits(['reset', 'refresh'])
</script>

<template>
  <section>
    <div class="spread bar">
      <p class="muted">
        Live state behind stateful endpoints. Reset restores the seed
        data.
      </p>
      <button class="btn btn-ghost" @click="$emit('refresh')">
        ↻ Refresh
      </button>
    </div>
    <p v-if="!resources.length" class="muted empty">
      No stateful resources yet — create an endpoint with mode
      "stateful" or generate with AI.
    </p>
    <div v-for="r in resources" :key="r.id" class="card res">
      <div class="spread">
        <h3>
          {{ r.name }}
          <span class="muted count">
            {{ r.items.length }} item{{
              r.items.length === 1 ? '' : 's'
            }}
          </span>
        </h3>
        <button class="btn btn-danger sm" @click="$emit('reset', r.id)">
          ⟲ Reset state
        </button>
      </div>
      <pre class="mono">{{ JSON.stringify(r.items, null, 2) }}</pre>
    </div>
  </section>
</template>

<style scoped>
.bar {
  margin-bottom: 1rem;
}

.bar p {
  margin: 0;
}

.res {
  margin-bottom: 1rem;
}

h3 {
  font-size: 1rem;
}

.count {
  font-weight: 400;
  margin-left: 0.5rem;
}

.sm {
  padding: 0.3rem 0.7rem;
  font-size: 0.78rem;
}

pre {
  background: var(--bg);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  font-size: 0.75rem;
  overflow-x: auto;
  max-height: 260px;
  margin: 0.75rem 0 0;
}

.empty {
  text-align: center;
  padding: 3rem 0;
}
</style>
