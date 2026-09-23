import { ref } from 'vue'
import type { WSMessage, Danmaku, AnalysisResult } from '@/types'

export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  public connected = ref(false)
  public messages = ref<WSMessage[]>([])
  public latestAnalysis = ref<AnalysisResult | null>(null)
  public danmakuList = ref<Danmaku[]>([])

  constructor(sessionId: string = 'default') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = `${protocol}//${window.location.hostname}:8000/api/danmaku/ws/${sessionId}`
  }

  connect() {
    this.ws = new WebSocket(this.url)
    this.ws.onopen = () => { this.connected.value = true }
    this.ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)
        this.messages.value.push(message)
        if (message.type === 'analysis_result' && message.analysis) {
          this.latestAnalysis.value = message.analysis
        }
        if (message.danmaku) {
          this.danmakuList.value.unshift(message.danmaku)
          if (this.danmakuList.value.length > 100) this.danmakuList.value.pop()
        }
      } catch (e) { console.error('消息解析失败:', e) }
    }
    this.ws.onclose = () => {
      this.connected.value = false
      setTimeout(() => this.connect(), 3000)
    }
  }

  sendDanmaku(content: string, username: string = '观众', anchorId?: number) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ content, username, user_id: `user_${Date.now()}`, type: 'comment', anchor_id: anchorId ?? null }))
    }
  }

  disconnect() { this.ws?.close() }
}
