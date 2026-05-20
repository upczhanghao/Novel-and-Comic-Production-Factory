export interface ImageRecordLike {
  id: string
  path?: string
  filename?: string
  prompt?: string
  config_name?: string
  model?: string
  size?: string
  provider?: string
  source_type?: string
  source_id?: string
  created_at?: string
}

export interface PromptItemLike {
  id: string
  title: string
  prompt: string
  negative_prompt?: string
  source_type?: string
  source_id?: string
}

export interface RecordFilterCriteria {
  sourceType?: string
  chapter?: string
  keyword?: string
  configName?: string
  dateFrom?: string
}

const CHAPTER_RE = /(?:^|[_-])ch(\d+)/i
const CHAR_RE = /character[_-]([^_]+)/i

export function parseSourceMeta(id?: string | null) {
  if (!id) return { chapter: null as number | null, character: null as string | null }
  const ch = CHAPTER_RE.exec(id)
  const ca = CHAR_RE.exec(id)
  return {
    chapter: ch ? Number(ch[1]) : null,
    character: ca ? ca[1] : null,
  }
}

function recordTimestamp(r: ImageRecordLike): number {
  if (!r.created_at) return 0
  const d = new Date(r.created_at).getTime()
  return Number.isFinite(d) ? d : 0
}

export function applyRecordFilters<T extends ImageRecordLike>(
  records: T[],
  criteria: RecordFilterCriteria,
): T[] {
  const { sourceType, chapter, keyword, configName, dateFrom } = criteria
  const kwLower = keyword?.trim().toLowerCase() ?? ''
  const fromTs = dateFrom ? new Date(dateFrom).getTime() : 0
  return records.filter((r) => {
    if (sourceType && sourceType !== 'all' && (r.source_type || 'custom') !== sourceType) return false
    if (configName && configName !== 'all' && r.config_name !== configName) return false
    if (chapter) {
      const parsed = parseSourceMeta(r.source_id || '')
      if (String(parsed.chapter ?? '') !== String(chapter).replace(/^ch/i, '')) return false
    }
    if (fromTs && recordTimestamp(r) < fromTs) return false
    if (kwLower) {
      const hay = `${r.prompt ?? ''} ${r.filename ?? ''} ${r.source_id ?? ''} ${r.config_name ?? ''}`.toLowerCase()
      if (!hay.includes(kwLower)) return false
    }
    return true
  })
}

export function relativeTime(iso?: string): string {
  if (!iso) return '—'
  const d = new Date(iso).getTime()
  if (!Number.isFinite(d)) return iso
  const diff = (Date.now() - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
  return new Date(iso).toLocaleDateString()
}

export function sourceLabel(record: { source_type?: string; source_id?: string }): string {
  const st = record.source_type || 'custom'
  const sid = record.source_id || ''
  const map: Record<string, string> = {
    character: '角色',
    shot: '分镜',
    scene: '场景',
    chapter: '章节',
    custom: '自定义',
    image_module: '图片模块',
    manju_custom: '漫剧',
  }
  const tag = map[st] ?? st
  return sid ? `${tag} · ${sid}` : tag
}
