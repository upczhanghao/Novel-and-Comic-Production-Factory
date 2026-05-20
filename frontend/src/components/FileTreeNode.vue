<script setup lang="ts">
export interface FileTreeNode {
  name: string
  path: string
  type: 'dir' | 'file'
  size?: number
  mtime?: number
  children?: FileTreeNode[]
}

const props = withDefaults(defineProps<{
  node: FileTreeNode
  expanded: Set<string>
  checked: Set<string>
  selectedPath: string
  depth?: number
}>(), { depth: 0 })

const emit = defineEmits<{
  (e: 'toggle', path: string): void
  (e: 'check', path: string): void
  (e: 'open', path: string): void
  (e: 'delete', path: string): void
  (e: 'download', path: string): void
}>()

</script>

<template>
  <div>
    <div
      class="fb-row"
      :class="{ selected: node.type === 'file' && node.path === selectedPath }"
      :style="{ paddingLeft: `${(props.depth ?? 0) * 12 + 4}px` }"
    >
      <span
        v-if="node.type === 'dir'"
        class="fb-twisty"
        @click="emit('toggle', node.path)"
      >{{ expanded.has(node.path) ? '▾' : '▸' }}</span>
      <input
        v-else
        type="checkbox"
        :checked="checked.has(node.path)"
        class="fb-check"
        @change="emit('check', node.path)"
      />
      <span
        class="fb-label"
        @click="node.type === 'dir' ? emit('toggle', node.path) : emit('open', node.path)"
      >{{ node.type === 'dir' ? `📂 ${node.name}` : `📄 ${node.name}` }}</span>
      <span v-if="node.type === 'file'" class="fb-actions">
        <button type="button" class="fb-act" title="下载" @click.stop="emit('download', node.path)">⬇</button>
        <button type="button" class="fb-act danger" title="删除" @click.stop="emit('delete', node.path)">🗑</button>
      </span>
    </div>
    <template v-if="node.type === 'dir' && expanded.has(node.path) && node.children?.length">
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :expanded="expanded"
        :checked="checked"
        :selected-path="selectedPath"
        :depth="(props.depth ?? 0) + 1"
        @toggle="(p) => emit('toggle', p)"
        @check="(p) => emit('check', p)"
        @open="(p) => emit('open', p)"
        @delete="(p) => emit('delete', p)"
        @download="(p) => emit('download', p)"
      />
    </template>
  </div>
</template>

<style scoped>
.fb-row { display: flex; align-items: center; gap: 4px; padding: 2px 4px; font-size: 13px; cursor: default; user-select: none; }
.fb-row:hover { background: var(--color-parchment); }
.fb-row.selected { background: var(--color-parchment); font-weight: 600; }
.fb-twisty { display: inline-block; width: 14px; color: var(--color-ink-light); cursor: pointer; user-select: none; text-align: center; }
.fb-check { margin: 0 2px; }
.fb-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
.fb-actions { display: none; gap: 2px; }
.fb-row:hover .fb-actions { display: inline-flex; }
.fb-act { padding: 1px 6px; font-size: 11px; border-radius: 4px; border: 1px solid var(--color-parchment-darker); background: white; cursor: pointer; }
.fb-act.danger { color: #b91c1c; border-color: #fca5a5; background: #fef2f2; }
</style>
