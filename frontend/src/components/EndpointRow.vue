<script setup>
import CopyButton from './CopyButton.vue'

const props = defineProps({
  endpoint: { type: Object, required: true },
  baseUrl: { type: String, required: true },
})

defineEmits(['edit', 'delete'])

const fullUrl = `${props.baseUrl}${props.endpoint.path}`
</script>

<template>
  <div class="card row ep">
    <span :class="['badge', `badge-${endpoint.method}`]">
      {{ endpoint.method }}
    </span>
    <code class="path">{{ endpoint.path }}</code>
    <span class="muted status">→ {{ endpoint.status_code }}</span>
    <span v-if="endpoint.delay_ms" class="muted">
      ⏱ {{ endpoint.delay_ms }}ms
    </span>
    <span v-if="endpoint.error_rate" class="muted err">
      ⚠ {{ endpoint.error_rate }}% errors
    </span>
    <span class="spacer" />
    <CopyButton :text="fullUrl" />
    <button class="btn btn-ghost sm" @click="$emit('edit')">Edit</button>
    <button class="btn btn-danger sm" @click="$emit('delete')">
      Delete
    </button>
  </div>
</template>

<style scoped>
.ep {
  padding: 0.8rem 1.1rem;
}

.path {
  font-size: 0.85rem;
  font-weight: 500;
}

.status {
  font-weight: 600;
}

.err {
  color: var(--warning);
}

.spacer {
  flex: 1;
}

.sm {
  padding: 0.3rem 0.7rem;
  font-size: 0.78rem;
}
</style>
