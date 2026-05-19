<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  step: number | string
  title: string
  description?: string
  collapsible?: boolean
  defaultOpen?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  description: '',
  collapsible: true,
  defaultOpen: true,
})

const open = ref(props.defaultOpen)
</script>

<template>
  <div class="rounded-xl shadow-md border border-[var(--color-parchment-darker)] bg-white overflow-hidden">
    <button
      v-if="collapsible"
      class="w-full flex items-center gap-3 px-4 sm:px-5 py-4 text-left transition-colors hover:bg-[var(--color-surface-muted)]"
      :class="open ? 'bg-[var(--color-surface-muted)]' : 'bg-white'"
      @click="open = !open"
      type="button"
    >
      <span
        class="flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center text-sm font-bold text-white shadow-sm"
        style="background: linear-gradient(135deg, var(--color-leather), var(--color-leather-light))"
      >
        {{ step }}
      </span>
      <div class="flex-1 min-w-0">
        <h3 class="font-semibold text-[var(--color-ink)] truncate">{{ title }}</h3>
        <p v-if="description" class="text-xs text-[var(--color-ink-light)] mt-0.5 line-clamp-1">
          {{ description }}
        </p>
      </div>
      <svg
        class="flex-shrink-0 w-4 h-4 text-[var(--color-leather)] transition-transform"
        :class="open ? 'rotate-180' : ''"
        fill="none" stroke="currentColor" viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <div
      v-else
      class="flex items-center gap-3 px-4 sm:px-5 py-4 bg-[var(--color-surface-muted)]"
    >
      <span
        class="flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center text-sm font-bold text-white"
        style="background: linear-gradient(135deg, var(--color-leather), var(--color-leather-light))"
      >
        {{ step }}
      </span>
      <div>
        <h3 class="font-semibold text-[var(--color-ink)]">{{ title }}</h3>
        <p v-if="description" class="text-xs text-[var(--color-ink-light)] mt-0.5">{{ description }}</p>
      </div>
    </div>

    <Transition name="slide">
      <div v-if="!collapsible || open" class="px-4 sm:px-5 py-4 border-t border-[var(--color-parchment-darker)]">
        <slot />
      </div>
    </Transition>
  </div>
</template>
