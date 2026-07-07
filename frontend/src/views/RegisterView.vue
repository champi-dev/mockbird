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
    await auth.register(username.value, password.value)
    router.push({ name: 'dashboard' })
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.username?.[0] ||
      data?.password?.[0] ||
      'Registration failed. Try a different username.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthCard
    title="Create your account"
    subtitle="Spin up live mock APIs in seconds."
  >
    <form @submit.prevent="submit">
      <div class="field">
        <label for="username">Username</label>
        <input id="username" v-model="username" required autofocus />
      </div>
      <div class="field">
        <label for="password">Password (8+ characters)</label>
        <input
          id="password"
          v-model="password"
          type="password"
          minlength="8"
          required
        />
      </div>
      <p v-if="error" class="error-text">{{ error }}</p>
      <button class="btn btn-primary full" :disabled="busy">
        {{ busy ? 'Creating…' : 'Create account' }}
      </button>
    </form>
    <p class="muted switch">
      Already registered?
      <router-link :to="{ name: 'login' }">Sign in</router-link>
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
