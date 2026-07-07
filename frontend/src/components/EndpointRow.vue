<script setup>
import { computed, ref } from 'vue'
import CopyButton from './CopyButton.vue'

const props = defineProps({
  endpoint: { type: Object, required: true },
  baseUrl: { type: String, required: true },
})

defineEmits(['edit', 'delete', 'test'])

const open = ref(false)
const fullUrl = `${props.baseUrl}${props.endpoint.path}`

const example = computed(() => {
  const ex = props.endpoint.request_example
  return ex && Object.keys(ex).length
    ? JSON.stringify(ex, null, 2)
    : ''
})
</script>

<template>
  <div class="card ep-card">
    <div class="row ep" @click="open = !open">
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
      <button class="btn btn-primary sm" @click.stop="$emit('test')">
        ▶ Test
      </button>
      <CopyButton :text="fullUrl" @click.stop />
      <button class="btn btn-ghost sm" @click.stop="$emit('edit')">
        Edit
      </button>
      <button class="btn btn-danger sm" @click.stop="$emit('delete')">
        Delete
      </button>
    </div>
    <transition name="rise">
      <div
        v-if="open && (endpoint.description || example)"
        class="details"
      >
        <p v-if="endpoint.description" class="muted">
          {{ endpoint.description }}
        </p>
        <div v-if="example">
          <span class="label">Expected request</span>
          <pre class="mono">{{ example }}</pre>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.ep-card {
  padding: 0;
}

.ep {
  padding: 0.8rem 1.1rem;
  cursor: pointer;
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

.details {
  border-top: 1px solid var(--border);
  padding: 0.75rem 1.1rem 1rem;
}

.details p {
  margin: 0 0 0.5rem;
}

.label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-soft);
}

pre {
  background: var(--bg);
  border-radius: 8px;
  padding: 0.6rem 0.8rem;
  font-size: 0.75rem;
  margin: 0.35rem 0 0;
  overflow-x: auto;
}
</style>
