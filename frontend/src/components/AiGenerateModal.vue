<script setup>
import { ref } from 'vue'

defineProps({
  busy: { type: Boolean, default: false },
  progress: {
    type: Object,
    default: () => ({ percent: 0, text: '' }),
  },
})
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
          <div v-if="busy" class="progress-wrap">
            <div class="progress-track">
              <div
                class="progress-fill"
                :style="{ width: (progress.percent || 2) + '%' }"
              />
            </div>
            <p class="progress-text">
              {{ progress.text || 'Warming up the model…' }}
            </p>
          </div>
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

.progress-wrap {
  margin-bottom: 1rem;
}

.progress-track {
  height: 8px;
  border-radius: 999px;
  background: rgb(100 116 139 / 0.2);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #818cf8, #6366f1);
  transition: width 0.6s ease;
}

.progress-text {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: var(--muted, #64748b);
  animation: pulse-text 1.6s ease-in-out infinite;
}

@keyframes pulse-text {
  50% { opacity: 0.55; }
}
</style>
