export type TemplateKind = 'llm' | 'embedding' | 'image'

export interface RecommendedTemplate {
  id: string
  kind: TemplateKind
  label: string
  description: string
  icon: string
  preset: Record<string, unknown>
}

export const TEMPLATES: RecommendedTemplate[] = [
  {
    id: 'deepseek',
    kind: 'llm',
    label: 'DeepSeek',
    description: '便宜、中文质量好；支持 OpenAI 兼容协议',
    icon: '🐋',
    preset: {
      config_name: 'DeepSeek V3',
      interface_format: 'DeepSeek',
      base_url: 'https://api.deepseek.com/v1',
      model_name: 'deepseek-chat',
      temperature: 0.7,
      max_tokens: 4096,
      timeout: 600,
      enable_streaming: true,
    },
  },
  {
    id: 'openai',
    kind: 'llm',
    label: 'OpenAI',
    description: '官方 GPT 系列；推荐用 gpt-4.1 或 gpt-4.1-mini',
    icon: '✨',
    preset: {
      config_name: 'GPT 4.1 Mini',
      interface_format: 'OpenAI',
      base_url: 'https://api.openai.com/v1',
      model_name: 'gpt-4.1-mini',
      temperature: 0.7,
      max_tokens: 8192,
      enable_streaming: true,
    },
  },
  {
    id: 'gemini',
    kind: 'llm',
    label: 'Gemini',
    description: 'Google Gemini 2.5；上下文长，多模态',
    icon: '💎',
    preset: {
      config_name: 'Gemini 2.5 Pro',
      interface_format: 'Gemini',
      base_url: 'https://generativelanguage.googleapis.com',
      model_name: 'gemini-2.5-pro',
      temperature: 0.7,
      enable_streaming: true,
    },
  },
  {
    id: 'mirrorstages',
    kind: 'llm',
    label: 'MirrorStages',
    description: '多模型聚合中转，国内可直连',
    icon: '🌐',
    preset: {
      config_name: 'MirrorStages-LLM',
      interface_format: 'MirrorStages',
      base_url: 'https://api.mirrorstages.com/openai/v1',
      model_name: 'gpt-4o-mini',
      enable_streaming: true,
    },
  },
  {
    id: 'ollama',
    kind: 'llm',
    label: 'Ollama 本地',
    description: '本机 Ollama；无需 API Key',
    icon: '🏠',
    preset: {
      config_name: 'Ollama-Local',
      interface_format: 'Ollama',
      base_url: 'http://localhost:11434',
      api_key: 'ollama',
      model_name: 'qwen2.5:14b',
      enable_streaming: true,
    },
  },
  {
    id: 'openai-emb',
    kind: 'embedding',
    label: 'OpenAI Embedding',
    description: 'text-embedding-3-large，质量高',
    icon: '✨',
    preset: {
      config_name: 'OpenAI-Embedding',
      interface_format: 'OpenAI',
      base_url: 'https://api.openai.com/v1',
      model_name: 'text-embedding-3-large',
      retrieval_k: 4,
    },
  },
  {
    id: 'openai-image',
    kind: 'image',
    label: 'OpenAI Images',
    description: 'gpt-image-1，1024x1536',
    icon: '🎨',
    preset: {
      config_name: 'OpenAI-Images',
      provider: 'openai',
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-image-1',
      size: '1024x1536',
      quality: 'medium',
      output_format: 'png',
    },
  },
  {
    id: 'mirrorstages-image',
    kind: 'image',
    label: 'MirrorStages Images',
    description: '中转图片接口；走 OpenAI 协议',
    icon: '🌐',
    preset: {
      config_name: 'MirrorStages-Images',
      provider: 'mirrorstages',
      base_url: 'https://api.mirrorstages.com/openai/v1',
      model: 'gpt-image-1',
      size: '1024x1536',
      quality: 'medium',
      output_format: 'png',
    },
  },
]
