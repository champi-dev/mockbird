<script setup>
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { API_BASE } from '../api/client'
import CopyButton from '../components/CopyButton.vue'

const props = defineProps({ slug: { type: String, required: true } })

const docs = ref(null)
const failed = ref(false)

const baseUrl = `${API_BASE}/m/${props.slug}`

onMounted(async () => {
  try {
    const { data } = await axios.get(`${API_BASE}/api/docs/${props.slug}/`)
    docs.value = data
  } catch {
    failed.value = true
  }
})

function pretty(value) {
  return JSON.stringify(value, null, 2)
}

function hasContent(value) {
  return value && Object.keys(value).length > 0
}
</script>

<template>
  <main class="container docs">
    <transition name="rise" appear>
      <div v-if="docs">
        <header class="head">
          <p class="brand"><span class="logo-mark">◆</span> Mockbird</p>
          <h1>{{ docs.name }} — API reference</h1>
          <div class="row url">
            <code class="mono">{{ baseUrl }}</code>
            <CopyButton :text="baseUrl" />
          </div>
          <p class="muted">
            Live mock API. Every route below is callable right now.
          </p>
        </header>

        <article
          v-for="ep in docs.endpoints"
          :key="ep.id"
          class="card ep"
        >
          <div class="row">
            <span :class="['badge', `badge-${ep.method}`]">
              {{ ep.method }}
            </span>
            <code class="path">{{ ep.path }}</code>
            <span class="muted">→ {{ ep.status_code }}</span>
            <span v-if="ep.mode === 'stateful'" class="badge stateful">
              stateful
            </span>
          </div>
          <p v-if="ep.description" class="muted desc">
            {{ ep.description }}
          </p>
          <div class="grid-2">
            <div v-if="hasContent(ep.request_example)">
              <span class="label">Request</span>
              <pre class="mono">{{ pretty(ep.request_example) }}</pre>
            </div>
            <div v-if="hasContent(ep.response_body)">
              <span class="label">
                {{ ep.mode === 'stateful' ? 'Seed data' : 'Response' }}
              </span>
              <pre class="mono">{{ pretty(ep.response_body) }}</pre>
            </div>
          </div>
        </article>
      </div>
      <div v-else-if="failed" class="card empty-card">
        <h1>Not found</h1>
        <p class="muted">No mock project exists at this address.</p>
      </div>
    </transition>
  </main>
</template>

<style scoped>
.docs {
  max-width: 860px;
}

.brand {
  font-weight: 800;
  margin: 0 0 1rem;
}

.logo-mark {
  color: var(--brand);
}

.head {
  margin-bottom: 2rem;
}

h1 {
  font-size: 1.6rem;
  margin-bottom: 0.5rem;
}

.url code {
  font-size: 0.85rem;
}

.ep {
  margin-bottom: 1rem;
}

.path {
  font-size: 0.9rem;
  font-weight: 500;
}

.desc {
  margin: 0.5rem 0 0;
}

.stateful {
  background: #f0fdfa;
  color: #0d9488;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 0.75rem;
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
  font-size: 0.74rem;
  margin: 0.35rem 0 0;
  overflow-x: auto;
  max-height: 260px;
}

.empty-card {
  text-align: center;
  padding: 3rem;
}
</style>
