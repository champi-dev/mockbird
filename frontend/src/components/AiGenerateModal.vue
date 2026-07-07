<script setup>
import { ref } from 'vue'

defineProps({ busy: { type: Boolean, default: false } })
const emit = defineEmits(['generate', 'close'])

const description = ref('')
const error = ref('')

defineExpose({ setError: (msg) => (error.value = msg) })

function submit() {
  if (!description.value.trim()) return
  error.value = ''
  emit('generate', description.value.trim())
}
</script>

<template>
  <transition name="fade" appear>
    <div class="overlay" @click.self="$emit('close')">
      <transition name="rise" appear>
        <form class="card modal" @submit.prevent="submit">
          <h2>✨ Generate endpoints with AI</h2>
          <p class="muted">
            Describe the API you wish existed — resources, fields,
            behaviour — and get ready-made mock endpoints.
          </p>
          <div class="field">
            <label for="desc">Description</label>
            <textarea
              id="desc"
              v-model="description"
              spellcheck="false"
              placeholder="A todo API: list todos with title and done
flag, get one by id, create, and delete. Deleting a missing todo
returns 404."
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
              {{ busy ? 'Generating…' : 'Generate' }}
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
  max-width: 520px;
}

h2 {
  font-size: 1.2rem;
  margin-bottom: 0.5rem;
}

p {
  margin: 0 0 1rem;
}

textarea {
  min-height: 140px;
}

.actions {
  justify-content: flex-end;
}
</style>
