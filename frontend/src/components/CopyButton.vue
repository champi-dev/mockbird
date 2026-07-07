<script setup>
import { ref } from 'vue'

const props = defineProps({
  text: { type: String, required: true },
})

const copied = ref(false)

async function copy() {
  await navigator.clipboard.writeText(props.text)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}
</script>

<template>
  <button class="btn btn-ghost sm" @click="copy">
    {{ copied ? '✓ Copied' : 'Copy' }}
  </button>
</template>

<style scoped>
.sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.75rem;
}
</style>
