export type IntentType = 'purchase' | 'question' | 'price' | 'negative' | 'interaction' | 'other'
export type SentimentType = 'positive' | 'neutral' | 'negative'

export interface Danmaku {
  id?: number
  content: string
  user_id?: string
  username?: string
  type?: string
  created_at?: string
}

export interface AnalysisResult {
  intent: IntentType
  intent_confidence: number
  sentiment: SentimentType
  sentiment_score: number
  keywords: string[]
  recommended_script: string
  script_category: string
  rag_sources: { title: string; score: number }[]
  strategy: { priority: string; action: string; tips: string }
  priority: string
  timestamp: string
}

export interface WSMessage {
  type: 'analysis_result' | 'danmaku' | 'stats'
  danmaku?: Danmaku
  analysis?: AnalysisResult
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
