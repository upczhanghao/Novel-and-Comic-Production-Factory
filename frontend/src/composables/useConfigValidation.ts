export interface ValidationResult {
  errors: Record<string, string>
  warnings: Record<string, string>
}

const NAME_INVALID_RE = /[/\\:*?"<>|]/

function empty(): ValidationResult {
  return { errors: {}, warnings: {} }
}

function checkName(name: string, r: ValidationResult) {
  if (!name.trim()) r.errors.config_name = '配置名称不能为空'
  else if (NAME_INVALID_RE.test(name)) r.errors.config_name = '名称不能包含 / \\ : * ? " < > |'
  else if (name.length > 60) r.warnings.config_name = '名称过长（建议 ≤ 60 字符）'
}

function checkUrl(url: string, field: string, r: ValidationResult) {
  if (!url.trim()) return
  if (!/^https?:\/\//i.test(url)) r.errors[field] = '必须以 http:// 或 https:// 开头'
  else if (url.endsWith('/')) r.warnings[field] = '末尾的 / 可能导致路径拼接问题'
}

function checkApiKey(key: string, field: string, r: ValidationResult, isEdit: boolean) {
  if (!key && !isEdit) r.errors[field] = 'API Key 不能为空'
  else if (key && key.length > 0 && key.length < 8 && key !== '***') r.warnings[field] = 'Key 似乎过短'
}

export function validateLLM(form: Record<string, unknown>, isEdit = false): ValidationResult {
  const r = empty()
  checkName(String(form.config_name ?? ''), r)
  checkApiKey(String(form.api_key ?? ''), 'api_key', r, isEdit)
  checkUrl(String(form.base_url ?? ''), 'base_url', r)
  if (!String(form.model_name ?? '').trim()) r.errors.model_name = '模型名称不能为空'
  const temp = Number(form.temperature ?? 0.7)
  if (temp < 0 || temp > 2) r.errors.temperature = 'Temperature 需在 0–2 之间'
  const mt = Number(form.max_tokens ?? 4096)
  if (mt < 256) r.errors.max_tokens = 'Max Tokens 至少 256'
  const iface = String(form.interface_format ?? '')
  const baseUrl = String(form.base_url ?? '')
  if (iface === 'MirrorStages' && baseUrl && !baseUrl.includes('mirrorstages'))
    r.warnings.base_url = '接口格式为 MirrorStages 但 URL 不含 mirrorstages'
  return r
}

export function validateEmbedding(form: Record<string, unknown>, isEdit = false): ValidationResult {
  const r = empty()
  checkName(String(form.config_name ?? ''), r)
  checkApiKey(String(form.api_key ?? ''), 'api_key', r, isEdit)
  checkUrl(String(form.base_url ?? ''), 'base_url', r)
  if (!String(form.model_name ?? '').trim()) r.errors.model_name = '模型名称不能为空'
  return r
}

export function validateImage(form: Record<string, unknown>, isEdit = false): ValidationResult {
  const r = empty()
  checkName(String(form.config_name ?? ''), r)
  checkApiKey(String(form.api_key ?? ''), 'api_key', r, isEdit)
  checkUrl(String(form.base_url ?? ''), 'base_url', r)
  const size = String(form.size ?? '')
  if (size && !/^\d+x\d+$/.test(size)) r.errors.size = '尺寸格式应为 宽x高（如 1024x1536）'
  else if (size) {
    const [w, h] = size.split('x').map(Number)
    if (w < 256 || h < 256) r.warnings.size = '宽高建议 ≥ 256'
  }
  return r
}

export function validateProxy(form: { proxy_url: string; proxy_port: string }): ValidationResult {
  const r = empty()
  if (form.proxy_url && !/^(https?:\/\/)?[\w.\-]+$/i.test(form.proxy_url))
    r.warnings.proxy_url = '代理地址格式可能有误'
  const port = Number(form.proxy_port)
  if (form.proxy_port && (isNaN(port) || port < 1 || port > 65535))
    r.errors.proxy_port = '端口需在 1–65535 之间'
  return r
}
