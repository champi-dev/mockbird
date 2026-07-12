<script setup>
import { reactive, ref } from 'vue'

const props = defineProps({
  endpoint: { type: Object, default: null },
})

const emit = defineEmits(['save', 'close'])

const form = reactive({
  method: props.endpoint?.method ?? 'GET',
  path: props.endpoint?.path ?? '/',
  description: props.endpoint?.description ?? '',
  mode: props.endpoint?.mode ?? 'static',
  resource: props.endpoint?.resource ?? '',
  status_code: props.endpoint?.status_code ?? 200,
  delay_ms: props.endpoint?.delay_ms ?? 0,
  error_rate: props.endpoint?.error_rate ?? 0,
  error_status: props.endpoint?.error_status ?? 500,
})

const bodyText = ref(
  JSON.stringify(props.endpoint?.response_body ?? {}, null, 2),
)
const headersText = ref(
  JSON.stringify(props.endpoint?.headers ?? {}, null, 2),
)
const error = ref('')

function parseJson(text, label) {
  try {
    return JSON.parse(text || '{}')
  } catch {
    throw new Error(`${label} is not valid JSON.`)
  }
}

function submit() {
  error.value = ''
  try {
    emit('save', {
      ...form,
      response_body: parseJson(bodyText.value, 'Response body'),
      headers: parseJson(headersText.value, 'Headers'),
    })
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <transition name="fade" appear>
    <div class="overlay" @click.self="$emit('close')">
      <transition name="rise" appear>
        <form class="card modal" @submit.prevent="submit">
          <h2>{{ endpoint ? 'Edit endpoint' : 'New endpoint' }}</h2>

          <div class="grid-2">
            <div class="field">
              <label for="method">Method</label>
              <select id="method" v-model="form.method">
                <option v-for="m in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']"
                  :key="m" :value="m">{{ m }}</option>
              </select>
            </div>
            <div class="field">
              <label for="path">Path ({param} allowed)</label>
              <input id="path" v-model="form.path" required
                placeholder="/users/{id}" />
            </div>
          </div>

          <div class="grid-2">
            <div class="field">
              <label for="mode">Mode</label>
              <select id="mode" v-model="form.mode">
                <option value="static">Static response</option>
                <option value="stateful">Stateful CRUD</option>
              </select>
            </div>
            <div class="field">
              <label for="resource">
                Resource {{ form.mode === 'stateful' ? '' : '(n/a)' }}
              </label>
              <input id="resource" v-model="form.resource"
                :disabled="form.mode !== 'stateful'"
                placeholder="products" />
            </div>
          </div>

          <div class="field">
            <label for="desc">Description (optional)</label>
            <input id="desc" v-model="form.description"
              placeholder="What this endpoint does, expected inputs" />
          </div>

          <div class="grid-2">
            <div class="field">
              <label for="status">Status code</label>
              <input id="status" v-model.number="form.status_code"
                type="number" min="100" max="599" />
            </div>
            <div class="field">
              <label for="delay">Delay (ms)</label>
              <input id="delay" v-model.number="form.delay_ms"
                type="number" min="0" max="30000" />
            </div>
          </div>

          <div class="grid-2">
            <div class="field">
              <label for="rate">Error rate (%)</label>
              <input id="rate" v-model.number="form.error_rate"
                type="number" min="0" max="100" />
            </div>
            <div class="field">
              <label for="estatus">Error status</label>
              <input id="estatus" v-model.number="form.error_status"
                type="number" min="400" max="599" />
            </div>
          </div>

          <div class="field">
            <label for="body">Response body (JSON)</label>
            <textarea id="body" v-model="bodyText" spellcheck="false" />
          </div>

          <div class="field">
            <label for="headers">Custom headers (JSON)</label>
            <textarea id="headers" v-model="headersText"
              spellcheck="false" class="short" />
          </div>

          <p v-if="error" class="error-text">{{ error }}</p>

          <div class="row actions">
            <button type="button" class="btn btn-ghost"
              @click="$emit('close')">Cancel</button>
            <button class="btn btn-primary">
              {{ endpoint ? 'Save changes' : 'Create endpoint' }}
            </button>
          </div>
        </form>
      </transition>
    </div>
  </transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgb(15 23 42 / 0.45);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
  z-index: 50;
  padding: clamp(0.6rem, 3vw, 1.5rem);
}

.modal {
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
}

h2 {
  font-size: 1.2rem;
  margin-bottom: 1.25rem;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.short {
  min-height: 70px;
}

.actions {
  justify-content: flex-end;
  margin-top: 0.5rem;
}
</style>
