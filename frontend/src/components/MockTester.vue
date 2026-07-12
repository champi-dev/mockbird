<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  endpoint: { type: Object, required: true },
  baseUrl: { type: String, required: true },
})

defineEmits(['close'])

const hasBody = props.endpoint.method !== 'GET'

const paramNames = [...props.endpoint.path.matchAll(/\{(\w+)\}/g)].map(
  (m) => m[1],
)
const paramValues = ref(
  Object.fromEntries(paramNames.map((name) => [name, ''])),
)

const path = computed(() =>
  paramNames.reduce(
    (p, name) =>
      p.replace(`{${name}}`, paramValues.value[name] || `{${name}}`),
    props.endpoint.path,
  ),
)

const query = ref(
  new URLSearchParams(
    props.endpoint.request_example?.query_params ?? {},
  ).toString(),
)
const body = ref(
  JSON.stringify(props.endpoint.request_example?.body ?? {}, null, 2),
)

const busy = ref(false)
const result = ref(null)
const error = ref('')

const url = computed(() => {
  const qs = query.value.trim()
  return `${props.baseUrl}${path.value}${qs ? '?' + qs : ''}`
})

const ready = computed(() =>
  paramNames.every((name) => paramValues.value[name].trim()),
)

async function send() {
  busy.value = true
  error.value = ''
  result.value = null
  const started = performance.now()
  try {
    const res = await fetch(url.value, {
      method: props.endpoint.method,
      headers: hasBody ? { 'Content-Type': 'application/json' } : {},
      body: hasBody ? body.value : undefined,
    })
    const text = await res.text()
    let pretty = text
    try {
      pretty = JSON.stringify(JSON.parse(text), null, 2)
    } catch {
      /* leave as-is */
    }
    result.value = {
      status: res.status,
      ok: res.ok,
      ms: Math.round(performance.now() - started),
      body: pretty,
    }
  } catch (e) {
    error.value = `Request failed: ${e.message}`
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <transition name="fade" appear>
    <div class="overlay" @click.self="$emit('close')">
      <transition name="rise" appear>
        <div class="card modal">
          <h2>
            <span :class="['badge', `badge-${endpoint.method}`]">
              {{ endpoint.method }}
            </span>
            Test endpoint
          </h2>
          <p v-if="endpoint.description" class="muted">
            {{ endpoint.description }}
          </p>
          <code class="url mono">{{ url }}</code>

          <div v-if="paramNames.length" class="params">
            <div
              v-for="name in paramNames"
              :key="name"
              class="field"
            >
              <label :for="`param-${name}`">
                Path param: <code>{{ name }}</code>
              </label>
              <input
                :id="`param-${name}`"
                v-model="paramValues[name]"
                :placeholder="`value for {${name}}`"
              />
            </div>
          </div>

          <div class="field">
            <label for="qs">Query string</label>
            <input id="qs" v-model="query" placeholder="page=1&limit=10" />
          </div>

          <div v-if="hasBody" class="field">
            <label for="tbody">Request body (JSON)</label>
            <textarea id="tbody" v-model="body" spellcheck="false" />
          </div>

          <div class="row actions">
            <button class="btn btn-ghost" @click="$emit('close')">
              Close
            </button>
            <button
              class="btn btn-primary"
              :disabled="busy || !ready"
              :title="ready ? '' : 'Fill in the path params first'"
              @click="send"
            >
              {{ busy ? 'Sending…' : '▶ Send request' }}
            </button>
          </div>

          <p v-if="error" class="error-text">{{ error }}</p>

          <transition name="rise">
            <div v-if="result" class="result">
              <div class="row meta">
                <span :class="['status', result.ok ? 'good' : 'bad']">
                  {{ result.status }}
                </span>
                <span class="muted">{{ result.ms }} ms</span>
              </div>
              <pre class="mono">{{ result.body }}</pre>
            </div>
          </transition>
        </div>
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
  font-size: 1.15rem;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

p {
  margin: 0 0 0.75rem;
}

.url {
  display: block;
  font-size: 0.75rem;
  background: var(--bg);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 1rem;
  word-break: break-all;
}

textarea {
  min-height: 90px;
}

.actions {
  justify-content: flex-end;
  margin-bottom: 0.75rem;
}

.result {
  border-top: 1px solid var(--border);
  padding-top: 0.75rem;
}

.meta {
  margin-bottom: 0.5rem;
}

.status {
  font-weight: 700;
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  font-size: 0.8rem;
}

.good {
  background: #ecfdf5;
  color: var(--success);
}

.bad {
  background: #fef2f2;
  color: var(--danger);
}

pre {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 10px;
  padding: 1rem;
  font-size: 0.78rem;
  overflow-x: auto;
  margin: 0;
  max-height: 300px;
}
</style>
