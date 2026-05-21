#!/usr/bin/env node
// A12: 禁用 alert() / confirm() / window.confirm() —— 全部使用 stores/confirm.ts 中的 confirmDialog()
// 这个脚本在 `npm run build` 前运行；扫描 frontend/src/ 下的 .vue 和 .ts 文件。

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SRC = join(__dirname, '..', 'src')

const ALLOW = new Set([
  'src/stores/confirm.ts',
  'src/components/ConfirmDialog.vue',
])

const FORBIDDEN = [
  { re: /(?<![\w.])alert\s*\(/, name: 'alert()' },
  { re: /(?<![\w.])(?:window\.)?confirm\s*\(/, name: 'confirm()' },
]

const violations = []

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) walk(full)
    else if (/\.(vue|ts|tsx|js)$/.test(entry)) scan(full)
  }
}

function scan(file) {
  const rel = relative(join(__dirname, '..'), file).replace(/\\/g, '/')
  if (ALLOW.has(rel)) return
  const text = readFileSync(file, 'utf8')
  text.split('\n').forEach((line, i) => {
    // skip comments
    const stripped = line.replace(/\/\/.*$/, '').replace(/\/\*.*?\*\//g, '')
    for (const f of FORBIDDEN) {
      if (f.re.test(stripped)) {
        violations.push({ file: rel, line: i + 1, snippet: line.trim(), name: f.name })
      }
    }
  })
}

walk(SRC)

if (violations.length) {
  console.error('\n❌ Forbidden blocking dialog usage detected. Use confirmDialog() from @/stores/confirm instead.\n')
  for (const v of violations) {
    console.error(`  ${v.file}:${v.line}  [${v.name}]  ${v.snippet}`)
  }
  console.error(`\n  Total: ${violations.length} violation(s).\n`)
  process.exit(1)
}

console.log('✓ No forbidden alert()/confirm() usage.')
