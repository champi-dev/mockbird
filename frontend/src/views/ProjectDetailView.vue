<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useProjectsStore } from '../stores/projects'
import { useEndpointsStore } from '../stores/endpoints'
import client, { API_BASE } from '../api/client'
import AiGenerateModal from '../components/AiGenerateModal.vue'
import ImportOpenApiModal from '../components/ImportOpenApiModal.vue'
import EndpointForm from '../components/EndpointForm.vue'
import MockTester from '../components/MockTester.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import EndpointRow from '../components/EndpointRow.vue'
import LogsTable from '../components/LogsTable.vue'
import CopyButton from '../components/CopyButton.vue'

const props = defineProps({ id: { type: String, required: true } })

const projects = useProjectsStore()
const store = useEndpointsStore()

const tab = ref('endpoints')
const editing = ref(null)
const showForm = ref(false)
const showAi = ref(false)
const aiBusy = ref(false)
const aiModal = ref(null)
const testing = ref(null)
const showImport = ref(false)
const importBusy = ref(false)
const importModal = ref(null)
const live = ref(false)
let eventSource = null

const project = computed(() =>
  projects.projects.find((p) => p.id === Number(props.id)),
)
const baseUrl = computed(() =>
  project.value ? `${API_BASE}/m/${project.value.slug}` : '',
)

onMounted(async () => {
  if (!projects.projects.length) await projects.fetchProjects()
  await store.fetchEndpoints(props.id)
})

function edit(ep) {
  editing.value = ep
  showForm.value = true
}

async function save(payload) {
  if (editing.value) {
    await store.updateEndpoint(props.id, editing.value.id, payload)
  } else {
    await store.createEndpoint(props.id, payload)
  }
  showForm.value = false
  editing.value = null
}

const aiProgress = ref({ percent: 0, text: '' })
let progressTimer = null

async function pollProgress() {
  try {
    const { data } = await client.get(
      `/projects/${props.id}/generate/progress/`,
    )
    if (data && typeof data.percent === 'number') aiProgress.value = data
  } catch {
    /* progress is cosmetic — never break generation over it */
  }
}

async function generate(description) {
  aiBusy.value = true
  aiProgress.value = { percent: 0, text: '' }
  progressTimer = setInterval(pollProgress, 1200)
  try {
    await store.generateEndpoints(props.id, description)
    showAi.value = false
  } catch (e) {
    const status = e.response?.status
    aiModal.value?.setError(
      status === 429
        ? 'Rate limit reached — try again later.'
        : e.response?.data?.detail || 'Generation failed. Try again.',
    )
  } finally {
    clearInterval(progressTimer)
    aiBusy.value = false
  }
}

async function importSpec(spec) {
  importBusy.value = true
  try {
    await store.importOpenapi(props.id, spec)
    showImport.value = false
  } catch (e) {
    importModal.value?.setError(
      e.response?.data?.spec?.[0] || 'Import failed. Check the spec.',
    )
  } finally {
    importBusy.value = false
  }
}

function openLogs() {
  tab.value = 'logs'
  store.fetchLogs(props.id)
  startStream()
}

function startStream() {
  if (eventSource) return
  const token = localStorage.getItem('access')
  eventSource = new EventSource(
    `${API_BASE}/api/projects/${props.id}/logs/stream/?token=${token}`,
  )
  eventSource.onopen = () => (live.value = true)
  eventSource.onmessage = (event) => {
    store.logs.unshift(JSON.parse(event.data))
  }
  eventSource.onerror = () => {
    live.value = false
    stopStream()
  }
}

function stopStream() {
  eventSource?.close()
  eventSource = null
  live.value = false
}

onUnmounted(stopStream)

function openState() {
  tab.value = 'state'
  stopStream()
  store.fetchResources(props.id)
}

function openEndpoints() {
  tab.value = 'endpoints'
  stopStream()
}
</script>

<template>
  <main class="container">
    <transition name="rise" appear>
      <div v-if="project">
        <div class="spread head">
          <div>
            <h1>{{ project.name }}</h1>
            <div class="row url">
              <code>{{ baseUrl }}</code>
              <CopyButton :text="baseUrl" />
            </div>
          </div>
          <div class="row">
            <router-link
              class="btn btn-ghost"
              :to="{ name: 'docs', params: { slug: project.slug } }"
              target="_blank"
            >
              📄 Docs
            </router-link>
            <button class="btn btn-ghost" @click="showImport = true">
              ⇪ Import spec
            </button>
            <button class="btn btn-ghost" @click="showAi = true">
              ✨ Generate with AI
            </button>
            <button
              class="btn btn-primary"
              @click="((editing = null), (showForm = true))"
            >
              + New endpoint
            </button>
          </div>
        </div>

        <nav class="tabs row">
          <button
            :class="['tab', { active: tab === 'endpoints' }]"
            @click="openEndpoints"
          >
            Endpoints
          </button>
          <button
            :class="['tab', { active: tab === 'state' }]"
            @click="openState"
          >
            State
          </button>
          <button
            :class="['tab', { active: tab === 'logs' }]"
            @click="openLogs"
          >
            Request log
          </button>
        </nav>

        <section v-if="tab === 'endpoints'">
          <p v-if="store.loading" class="muted">Loading…</p>
          <p
            v-else-if="!store.endpoints.length"
            class="muted empty"
          >
            No endpoints yet — add one to bring this mock API to life.
          </p>
          <transition-group name="list" tag="div" class="stack">
            <EndpointRow
              v-for="ep in store.endpoints"
              :key="ep.id"
              :endpoint="ep"
              :base-url="baseUrl"
              @edit="edit(ep)"
              @delete="store.deleteEndpoint(id, ep.id)"
              @test="testing = ep"
            />
          </transition-group>
        </section>

        <ResourcePanel
          v-else-if="tab === 'state'"
          :resources="store.resources"
          @reset="(rid) => store.resetResource(id, rid)"
          @refresh="store.fetchResources(id)"
        />

        <LogsTable
          v-else
          :logs="store.logs"
          :live="live"
          @refresh="store.fetchLogs(id)"
        />

        <MockTester
          v-if="testing"
          :endpoint="testing"
          :base-url="baseUrl"
          @close="testing = null"
        />

        <ImportOpenApiModal
          v-if="showImport"
          ref="importModal"
          :busy="importBusy"
          @import="importSpec"
          @close="showImport = false"
        />

        <AiGenerateModal
          v-if="showAi"
          ref="aiModal"
          :busy="aiBusy"
          :progress="aiProgress"
          @generate="generate"
          @close="showAi = false"
        />

        <EndpointForm
          v-if="showForm"
          :endpoint="editing"
          @save="save"
          @close="showForm = false"
        />
      </div>
    </transition>
  </main>
</template>

<style scoped>
.head {
  margin-bottom: 1rem;
}

h1 {
  font-size: 1.6rem;
  margin-bottom: 0.4rem;
}

.url code {
  font-size: 0.78rem;
  color: var(--text-soft);
}

.tabs {
  border-bottom: 1px solid var(--border);
  margin-bottom: 1.25rem;
  gap: 0;
}

.tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 0.6rem 1rem;
  font: 600 0.875rem 'Inter', sans-serif;
  color: var(--text-soft);
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s;
}

.tab.active {
  color: var(--brand);
  border-color: var(--brand);
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.empty {
  text-align: center;
  padding: 3rem 0;
}
</style>
