<script setup>
import NavBar from './components/NavBar.vue'
import InstallButton from './components/InstallButton.vue'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
</script>

<template>
  <NavBar v-if="auth.isAuthenticated" />
  <router-view v-slot="{ Component }">
    <transition name="fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>

  <!-- Global PWA install button — self-hides when not installable / already
       installed, so it's safe to always render (login pages included). -->
  <InstallButton />
</template>
