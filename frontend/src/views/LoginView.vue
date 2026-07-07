<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthCard from '../components/AuthCard.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.login(username.value, password.value)
    router.push({ name: 'dashboard' })
  } catch {
    error.value = 'Invalid username or password.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthCard title="Welcome back" subtitle="Sign in to manage your mocks.">
    <form @submit.prevent="submit">
      <div class="field">
        <label for="username">Username</label>
        <input id="username" v-model="username" required autofocus />
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          v-model="password"
          type="password"
          required
        />
      </div>
      <p v-if="error" class="error-text">{{ error }}</p>
      <button class="btn btn-primary full" :disabled="busy">
        {{ busy ? 'Signing in…' : 'Sign in' }}
      </button>
    </form>
    <p class="muted switch">
      No account?
      <router-link :to="{ name: 'register' }">Create one</router-link>
    </p>
  </AuthCard>
</template>

<style scoped>
.full {
  width: 100%;
  justify-content: center;
}

.switch {
  margin: 1.25rem 0 0;
  text-align: center;
}

.switch a {
  color: var(--brand);
  font-weight: 600;
}
</style>
