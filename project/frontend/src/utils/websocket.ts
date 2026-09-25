import { ref } from 'vue'
import type { WSMessage, Danmaku, AnalysisResult, Stats } from '@/types'

/** 弹幕流保留上限：超出后丢弃最旧的，避免长场次下内存无上限增长 */
const DANMAKU_LIMIT = 100
/** 断线重连间隔（毫秒） */
const RECONNECT_DELAY = 3000

export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  /** 主动断开标记：避免用户主动断开后被重连定时器又拉起来 */
  private closedByUser = false
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  public connected = ref(false)
  public messages = ref<WSMessage[]>([])
  public latestAnalysis = ref<AnalysisResult | null>(null)
  public stats = ref<Stats | null>(null)
  public danmakuList = ref<Danmaku[]>([])

  constructor(sessionId: string = 'default') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = `${protocol}//${window.location.hostname}:8000/api/danmaku/ws/${sessionId}`
  }

  /** 连接是否存活。外部判断"要不要重建"必须用它，只比 sessionId 会误判 */
  isAlive() {
    return this.ws !== null &&
      (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
  }

  connect() {
    this.closedByUser = false
    // 已连接/连接中则不重复建连，避免叠加出多条并行连接
    if (this.isAlive()) return
    // 上一次的 socket 已进入 CLOSED/CLOSING，先彻底摘掉再重建
    this.dropSocket()
    this.ws = new WebSocket(this.url)
    this.ws.onopen = () => { this.connected.value = true }
    this.ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)
        this.messages.value.push(message)
        if (this.messages.value.length > DANMAKU_LIMIT) this.messages.value.shift()
        if (message.analysis) this.latestAnalysis.value = message.analysis
        // 统计快照随分析结果一并推送，看板据此实时更新，不必自己轮询
        if (message.stats) this.stats.value = message.stats
        if (message.danmaku) {
          this.danmakuList.value.unshift(message.danmaku)
          if (this.danmakuList.value.length > DANMAKU_LIMIT) this.danmakuList.value.pop()
        }
      } catch (e) { console.error('消息解析失败:', e) }
    }
    this.ws.onclose = () => {
      this.connected.value = false
      if (this.closedByUser) return
      this.reconnectTimer = setTimeout(() => this.connect(), RECONNECT_DELAY)
    }
    // 连接出错后由 onclose 统一接管重连，这里不重复处理
    this.ws.onerror = () => {}
  }

  sendDanmaku(content: string, username: string = '观众', anchorId?: number) {
    if (this.ws?.readyState !== WebSocket.OPEN) return
    try {
      this.ws.send(JSON.stringify({ content, username, user_id: `user_${Date.now()}`, type: 'comment', anchor_id: anchorId ?? null }))
    } catch (e) {
      // 序列化失败不该把调用方（按钮点击）一起带崩
      console.error('弹幕发送失败（序列化异常）:', e)
    }
  }

  /** 摘掉监听器并释放 socket 引用，避免已关闭的连接继续被持有/触发回调 */
  private dropSocket() {
    if (!this.ws) return
    this.ws.onopen = null
    this.ws.onmessage = null
    this.ws.onclose = null
    this.ws.onerror = null
    if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
      this.ws.close()
    }
    this.ws = null
  }

  disconnect() {
    this.closedByUser = true
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null }
    this.dropSocket()
    this.connected.value = false
  }
}
