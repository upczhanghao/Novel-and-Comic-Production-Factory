<script setup lang="ts">
defineProps<{
  name: string
  size?: number | string
}>()
</script>

<template>
  <svg
    :width="size || 18"
    :height="size || 18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="name === 'workshop'">
      <path d="M4 5h16" /><path d="M4 12h16" /><path d="M4 19h10" /><path d="M18 16l2 2-2 2" />
    </template>
    <template v-else-if="name === 'settings'">
      <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.03-1.56 1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 8a1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 3.6a1.7 1.7 0 0 0 1-1.51V2a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 8c.16.6.65 1.04 1.25 1.13H21a2 2 0 1 1 0 4h-.09A1.7 1.7 0 0 0 19.4 15Z" />
    </template>
    <template v-else-if="name === 'presets'">
      <path d="M8 6h13" /><path d="M8 12h13" /><path d="M8 18h13" /><path d="M3 6h.01" /><path d="M3 12h.01" /><path d="M3 18h.01" />
    </template>
    <template v-else-if="name === 'instructions'">
      <path d="M4 19.5V4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 1 4 17.5" /><path d="M8 7h8" /><path d="M8 11h8" /><path d="M8 15h5" />
    </template>
    <template v-else-if="name === 'styles'">
      <path d="M12 22a10 10 0 1 0-10-10c0 4 3 3 5 3h1a2 2 0 0 1 2 2v1c0 2 0 4 2 4Z" /><circle cx="7.5" cy="10.5" r=".5" /><circle cx="10.5" cy="7.5" r=".5" /><circle cx="14" cy="7.5" r=".5" /><circle cx="16.5" cy="10.5" r=".5" />
    </template>
    <template v-else-if="name === 'knowledge'">
      <path d="M12 20V4" /><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H12v16H6.5A2.5 2.5 0 0 1 4 17.5Z" /><path d="M20 6.5A2.5 2.5 0 0 0 17.5 4H12v16h5.5a2.5 2.5 0 0 0 2.5-2.5Z" />
    </template>
    <template v-else-if="name === 'check'">
      <path d="m9 12 2 2 4-5" /><circle cx="12" cy="12" r="9" />
    </template>
    <template v-else-if="name === 'brainstorm'">
      <path d="M9 18h6" /><path d="M10 22h4" /><path d="M8.5 14.5a6 6 0 1 1 7 0c-.9.7-1.5 1.7-1.5 2.5h-4c0-.8-.6-1.8-1.5-2.5Z" />
    </template>
    <template v-else-if="name === 'manju'">
      <path d="M4 5h16v14H4z" /><path d="M8 5v14" /><path d="M16 5v14" /><path d="M4 9h4" /><path d="M16 9h4" /><path d="M4 15h4" /><path d="M16 15h4" />
    </template>
    <template v-else-if="name === 'images'">
      <rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="8.5" cy="10.5" r="1.5" /><path d="m21 15-5-5L5 21" />
    </template>
    <template v-else-if="name === 'profile'">
      <circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" />
    </template>
    <template v-else-if="name === 'files'">
      <path d="M4 4h6l2 3h8v13H4z" />
    </template>
    <template v-else-if="name === 'logs'">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" /><path d="M8 13h8" /><path d="M8 17h6" />
    </template>
    <template v-else-if="name === 'reader'">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5Z" />
    </template>
    <template v-else-if="name === 'menu'">
      <path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="M18 6 6 18" /><path d="m6 6 12 12" />
    </template>
    <template v-else-if="name === 'search'">
      <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
    </template>
    <template v-else>
      <circle cx="12" cy="12" r="9" /><path d="M12 8v8" /><path d="M8 12h8" />
    </template>
  </svg>
</template>
