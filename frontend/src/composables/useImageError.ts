export interface ClassifiedError {
  category: 'auth' | 'quota' | 'network' | 'size' | 'model' | 'moderation' | 'config' | 'unknown'
  title: string
  detail: string
  hint: string
}

const PATTERNS: Array<{ re: RegExp; cat: ClassifiedError['category']; title: string; hint: string }> = [
  { re: /401|unauthor|api[_\s]?key|apikey|incorrect[_\s]api/i, cat: 'auth', title: 'API Key 鉴权失败', hint: '请回到「模型配置」检查图片配置的 API Key 是否填写、是否过期或被吊销' },
  { re: /quota|insufficient[_\s]?(credit|balance|fund)|rate[_\s]?limit|429|too many request|余额|额度/i, cat: 'quota', title: '配额或限流', hint: '账户余额不足或触发了速率限制，稍后重试或前往服务商充值' },
  { re: /timeout|timed[_\s]?out|econnreset|network|getaddrinfo|enotfound|网络/i, cat: 'network', title: '网络连接失败', hint: '检查代理设置 / Base URL 是否能联通；如使用 Ollama 等本地服务，确认服务正在运行' },
  { re: /size|dimension|resolution|width|height|invalid[_\s]?image[_\s]?size/i, cat: 'size', title: '尺寸参数不合法', hint: '当前 size 参数可能不被该模型支持，常见可用值：1024x1024 / 1024x1536 / 1536x1024' },
  { re: /model[_\s]?not[_\s]?found|invalid[_\s]?model|deprecated|模型不存在|未授权.*模型/i, cat: 'model', title: '模型不可用', hint: '在「模型配置」检查 model 字段；某些 provider 需要先开通使用权限' },
  { re: /content[_\s]?policy|safety|moderation|审核|policy[_\s]?violation|content[_\s]filter/i, cat: 'moderation', title: '内容审核拒绝', hint: '当前提示词触发了服务商的内容安全策略，调整描述（去掉敏感主体/暴力/裸露词）后再试' },
  { re: /未找到图片生成配置|config[_\s]?not[_\s]?found|configuration/i, cat: 'config', title: '图片配置缺失', hint: '尚未选择图片配置，或所选配置已被删除。前往「模型配置」检查' },
]

export function classifyImageError(message: string): ClassifiedError {
  const msg = (message || '').toString()
  for (const p of PATTERNS) {
    if (p.re.test(msg)) {
      return { category: p.cat, title: p.title, detail: msg, hint: p.hint }
    }
  }
  return {
    category: 'unknown',
    title: '生成失败',
    detail: msg || '未知错误',
    hint: '查看返回详情，或在「运行日志」中检索更完整的报错',
  }
}
