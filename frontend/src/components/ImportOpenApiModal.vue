<script setup>
import { ref } from 'vue'

defineProps({ busy: { type: Boolean, default: false } })
const emit = defineEmits(['import', 'close'])

const spec = ref('')
const error = ref('')

defineExpose({ setError: (msg) => (error.value = msg) })

function submit() {
  if (!spec.value.trim()) return
  error.value = ''
  emit('import', spec.value)
}

async function onFile(event) {
  const file = event.target.files?.[0]
  if (file) spec.value = await file.text()
}
</script>

<template>
  <transition name="fade" appear>
    <div class="overlay" @click.self="$emit('close')">
      <transition name="rise" appear>
        <form class="card modal" @submit.prevent="submit">
          <h2>Import OpenAPI spec</h2>
          <p class="muted">
            Paste a Swagger / OpenAPI 3.x spec (YAML or JSON) — or
            pick a file — and every operation becomes a mock
            endpoint, examples included.
          </p>
          <div class="field">
            <label for="specfile">Spec file</label>
            <input
              id="specfile"
              type="file"
              accept=".yaml,.yml,.json"
              @change="onFile"
            />
          </div>
          <div class="field">
            <label for="spec">Or paste it</label>
            <textarea
              id="spec"
              v-model="spec"
              spellcheck="false"
              placeholder="openapi: 3.0.0&#10;paths:&#10;  /pets: ..."
            />
          </div>
          <p v-if="error" class="error-text">{{ error }}</p>
          <div class="row actions">
            <button
              type="button"
              class="btn btn-ghost"
              @click="$emit('close')"
            >
              Cancel
            </button>
            <button class="btn btn-primary" :disabled="busy">
              {{ busy ? 'Importing…' : 'Import' }}
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
  padding: 1.5rem;
}

.modal {
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
}

h2 {
  font-size: 1.2rem;
  margin-bottom: 0.5rem;
}

p {
  margin: 0 0 1rem;
}

textarea {
  min-height: 180px;
}

.actions {
  justify-content: flex-end;
}
</style>
