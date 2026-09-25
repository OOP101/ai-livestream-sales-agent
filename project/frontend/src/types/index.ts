export type IntentType = 'purchase' | 'question' | 'price' | 'negative' | 'interaction' | 'other'
export type SentimentType = 'positive' | 'neutral' | 'negative'

export interface Danmaku {
  id?: number
  content: string
  user_id?: string
  username?: string
  type?: string
  /** 弹幕归属主播，用于弹幕列表标注来源直播间 */
  anchor_id?: number | null
  created_at?: string
}

export interface RagSource {
  title: string
  score: number
  /** 命中文档所属知识库类型（doc_type）：product 商品知识库 / script 话术库 */
  type?: string
}

export interface AnalysisResult {
  intent: IntentType
  intent_confidence: number
  sentiment: SentimentType
  sentiment_score: number
  keywords: string[]
  recommended_script: string
  script_category: string
  rag_sources: RagSource[]
  strategy: { priority: string; action: string; tips: string }
  priority: string
  timestamp: string
}

export interface WSMessage {
  type: 'analysis_result' | 'danmaku' | 'stats'
  danmaku?: Danmaku
  analysis?: AnalysisResult
  /** 随 analysis_result 一并推送的统计快照，看板据此实时更新 */
  stats?: Stats
}

export interface Stats {
  total_analysis: number
  intent_distribution: Record<string, number>
  sentiment_distribution: Record<string, number>
}

export interface ScriptTemplate {
  id: number
  category: string
  title: string
  content: string
  effectiveness_score: number
}

export interface Anchor {
  id: number
  name: string
  platform: string
  room_url?: string
  sec_uid?: string | null
  is_live?: number | boolean
  room_id?: string | null
  created_at?: string
}
