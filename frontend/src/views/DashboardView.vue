<script setup>
import { onMounted, ref } from 'vue'
import { useProjectsStore } from '../stores/projects'
import ProjectCard from '../components/ProjectCard.vue'

const store = useProjectsStore()
const newName = ref('')
const creating = ref(false)

onMounted(() => store.fetchProjects())

async function create() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    await store.createProject(newName.value.trim())
    newName.value = ''
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <main class="container">
    <transition name="rise" appear>
      <div>
        <div class="spread head">
          <div>
            <h1>Projects</h1>
            <p class="muted">
              Each project gets its own live mock base URL.
            </p>
          </div>
        </div>

        <form class="card create-bar row" @submit.prevent="create">
          <input
            v-model="newName"
            placeholder="New project name — e.g. checkout-api"
            aria-label="New project name"
          />
          <button class="btn btn-primary" :disabled="creating">
            + Create
          </button>
        </form>

        <p v-if="store.loading" class="muted">Loading projects…</p>
        <p
          v-else-if="!store.projects.length"
          class="muted empty"
        >
          No projects yet. Create your first mock API above.
        </p>

        <transition-group name="list" tag="div" class="grid">
          <ProjectCard
            v-for="p in store.projects"
            :key="p.id"
            :project="p"
            @delete="store.deleteProject(p.id)"
          />
        </transition-group>
      </div>
    </transition>
  </main>
</template>

<style scoped>
.head {
  margin-bottom: 1.5rem;
}

h1 {
  font-size: 1.75rem;
}

.create-bar {
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.create-bar input {
  flex: 1;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: 10px;
  font: 400 0.9rem 'Inter', sans-serif;
}

.create-bar input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgb(79 70 229 / 0.15);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.empty {
  text-align: center;
  padding: 3rem 0;
}
</style>
