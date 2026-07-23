<script setup>
// Floating "install this app" button. It wires up the PWA install flow:
//
//   - Chromium (Android/desktop) fires `beforeinstallprompt`. We stash that
//     event and, on click, call its .prompt() to trigger the native install.
//   - iOS Safari never fires that event, so on iOS we instead reveal a short
//     "Add to Home Screen" hint (the only way to install there).
//   - Once installed (or already running standalone) the button hides itself.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const deferredPrompt = ref(null) // the saved beforeinstallprompt event
const installed = ref(false)
const showIosHint = ref(false)

// Running as an installed app already? Then there's nothing to offer.
const isStandalone =
  window.matchMedia('(display-mode: standalone)').matches ||
  window.navigator.standalone === true

const isIos = /iphone|ipad|ipod/i.test(window.navigator.userAgent)

// Show the button when we have a real install prompt, or on iOS where we can
// at least guide the user. Never once it's installed / already standalone.
const canShow = computed(
  () => !installed.value && !isStandalone && (!!deferredPrompt.value || isIos)
)

function onBeforeInstallPrompt(e) {
  e.preventDefault() // stop Chrome's mini-infobar; we drive the flow ourselves
  deferredPrompt.value = e
}

function onInstalled() {
  installed.value = true
  deferredPrompt.value = null
  showIosHint.value = false
}

async function install() {
  if (deferredPrompt.value) {
    deferredPrompt.value.prompt()
    try {
      await deferredPrompt.value.userChoice
    } finally {
      // A prompt can only be used once.
      deferredPrompt.value = null
    }
    return
  }
  if (isIos) showIosHint.value = !showIosHint.value
}

onMounted(() => {
  window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  window.addEventListener('appinstalled', onInstalled)
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  window.removeEventListener('appinstalled', onInstalled)
})
</script>

<template>
  <div v-if="canShow" class="install-wrap">
    <!-- iOS instructions popover -->
    <div v-if="showIosHint" class="ios-hint" role="dialog" aria-label="Install instructions">
      <button class="ios-hint-close" aria-label="Close" @click="showIosHint = false">×</button>
      <p class="ios-hint-title">Install Mockbird</p>
      <p class="ios-hint-body">
        Tap the <strong>Share</strong> icon, then choose
        <strong>“Add to Home Screen”</strong>.
      </p>
    </div>

    <button
      class="install-btn"
      type="button"
      aria-label="Install Mockbird app"
      title="Install Mockbird app"
      @click="install"
    >
      <!-- download / install-to-device glyph -->
      <svg class="install-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 3v10m0 0 4-4m-4 4-4-4" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round" />
        <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor"
              stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span class="install-label">Install app</span>
    </button>
  </div>
</template>

<style scoped>
.install-wrap {
  position: fixed;
  right: max(1rem, env(safe-area-inset-right));
  bottom: max(1rem, env(safe-area-inset-bottom));
  z-index: 50;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.5rem;
}

.install-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  height: 48px;
  padding: 0 1.1rem 0 0.95rem;
  border: none;
  border-radius: 999px;
  background: var(--brand);
  color: #fff;
  font-weight: 700;
  font-size: 0.95rem;
  cursor: pointer;
  box-shadow: 0 8px 22px -6px rgb(79 70 229 / 0.55);
  transition: background 0.2s, transform 0.15s, box-shadow 0.2s;
}
.install-btn:hover {
  background: var(--brand-dark);
  transform: translateY(-1px);
  box-shadow: 0 12px 26px -6px rgb(79 70 229 / 0.6);
}
.install-btn:active { transform: translateY(0); }
.install-btn:focus-visible { outline: 3px solid var(--brand-soft); outline-offset: 2px; }

.install-icon { width: 22px; height: 22px; flex-shrink: 0; }

/* On narrow screens collapse to a round icon-only button. */
@media (max-width: 560px) {
  .install-btn { padding: 0; width: 48px; justify-content: center; }
  .install-label { display: none; }
}

.ios-hint {
  position: relative;
  max-width: 260px;
  background: #fff;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.85rem 1rem;
  box-shadow: 0 16px 40px -12px rgb(15 23 42 / 0.3);
}
.ios-hint-title { margin: 0 0 0.25rem; font-weight: 700; }
.ios-hint-body { margin: 0; font-size: 0.9rem; color: var(--text-soft); line-height: 1.4; }
.ios-hint-close {
  position: absolute;
  top: 0.25rem;
  right: 0.45rem;
  border: none;
  background: none;
  font-size: 1.3rem;
  line-height: 1;
  color: var(--text-soft);
  cursor: pointer;
}
</style>
