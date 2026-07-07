<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<template>
  <div class="auth-wrap">
    <transition name="rise" appear>
      <div class="card auth-card">
        <div class="brand">
          <span class="logo-mark">◆</span> Mockbird
        </div>
        <h1>{{ title }}</h1>
        <p v-if="subtitle" class="muted">{{ subtitle }}</p>
        <slot />
      </div>
    </transition>
  </div>
</template>

<style scoped>
.auth-wrap {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(60rem 30rem at 80% -10%, #eef2ff, transparent),
    radial-gradient(50rem 25rem at 0% 110%, #f0fdfa, transparent),
    var(--bg);
  padding: 1.5rem;
}

.auth-card {
  width: 100%;
  max-width: 400px;
  padding: 2.5rem;
}

.brand {
  font-weight: 800;
  margin-bottom: 1.5rem;
}

.logo-mark {
  color: var(--brand);
}

h1 {
  font-size: 1.5rem;
  margin-bottom: 0.25rem;
}

p {
  margin: 0 0 1.5rem;
}
</style>
