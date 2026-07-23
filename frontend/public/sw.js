/*
 * Mockbird service worker — offline app shell + runtime asset caching.
 * Hand-written (no build-time PWA plugin) so the Vite pipeline stays untouched.
 * Bump CACHE when the shell/asset strategy changes to force a clean rollover.
 */
const CACHE = 'mockbird-v1';

// Minimal app shell precached on install. Hashed JS/CSS are cached at runtime
// (their names aren't known at build time here).
const SHELL = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/pwa-192.png',
  '/pwa-512.png',
  '/pwa-maskable-512.png',
  '/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Let the page tell a waiting worker to take over immediately.
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

// Never intercept the dynamic backend — mock endpoints, API, admin, and the
// SSE log stream must always hit the network directly.
function isBackend(url) {
  return url.pathname.startsWith('/api/') ||
         url.pathname.startsWith('/m/') ||
         url.pathname.startsWith('/admin/');
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || isBackend(url)) return;

  // SPA navigations: network-first so users get fresh HTML, falling back to the
  // cached shell when offline so the app still boots.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put('/index.html', copy));
          return res;
        })
        .catch(() => caches.match('/index.html').then((r) => r || caches.match('/')))
    );
    return;
  }

  // Static assets (hashed JS/CSS/images/fonts): cache-first, then fill the cache.
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((res) => {
        if (res.ok && (res.type === 'basic' || res.type === 'default')) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
        }
        return res;
      });
    })
  );
});
