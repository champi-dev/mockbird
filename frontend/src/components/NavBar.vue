<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="nav">
    <div class="nav-inner container">
      <router-link :to="{ name: 'dashboard' }" class="logo">
        <span class="logo-mark">◆</span> Mockbird
      </router-link>
      <div class="row">
        <span class="muted">{{ auth.username }}</span>
        <button class="btn btn-ghost" @click="logout">Sign out</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.nav {
  background: rgb(255 255 255 / 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
}

.logo {
  font-weight: 800;
  font-size: 1.1rem;
  color: var(--text);
  text-decoration: none;
  letter-spacing: -0.02em;
}

.logo-mark {
  color: var(--brand);
}
</style>
