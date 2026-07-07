<script setup>
import { API_BASE } from '../api/client'
import CopyButton from './CopyButton.vue'

const props = defineProps({
  project: { type: Object, required: true },
})

defineEmits(['delete'])

const baseUrl = `${API_BASE}/m/${props.project.slug}`
</script>

<template>
  <div class="card card-hover">
    <div class="spread">
      <router-link
        class="name"
        :to="{ name: 'project', params: { id: project.id } }"
      >
        {{ project.name }}
      </router-link>
      <button
        class="btn btn-danger sm"
        aria-label="Delete project"
        @click="$emit('delete')"
      >
        ✕
      </button>
    </div>
    <p class="muted">
      {{ project.endpoint_count }} endpoint{{
        project.endpoint_count === 1 ? '' : 's'
      }}
    </p>
    <div class="url row">
      <code>{{ baseUrl }}</code>
      <CopyButton :text="baseUrl" />
    </div>
  </div>
</template>

<style scoped>
.name {
  font-weight: 700;
  font-size: 1.05rem;
  color: var(--text);
  text-decoration: none;
}

.name:hover {
  color: var(--brand);
}

.sm {
  padding: 0.25rem 0.55rem;
}

.url {
  margin-top: 0.75rem;
  background: var(--bg);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
}

.url code {
  font-size: 0.72rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
</style>
