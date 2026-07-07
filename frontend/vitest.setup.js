// Node >= 22 defines an experimental, non-functional `localStorage`
// global that shadows jsdom's. Replace it with an in-memory shim.
if (
  typeof globalThis.localStorage === 'undefined' ||
  globalThis.localStorage === undefined
) {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  }
}
