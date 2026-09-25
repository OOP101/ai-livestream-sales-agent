import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { AnalysisResult, Stats, Anchor, Danmaku } from '@/types'
import { WebSocketClient } from '@/utils/websocket'
import { listAnchors } from '@/api'

export const useMainStore = defineStore('main', () => {
  const sessionId = ref('default')
  const isConnected = ref(false)
  const latestAnalysis = ref<AnalysisResult | null>(null)
  const stats = ref<Stats | null>(null)
  const danmakuList = ref<Danmaku[]>([])
  const anchors = ref<Anchor[]>([])
  const selectedAnchorId = ref<number | null>(null)
  let wsClient: WebSocketClient | null = null

  const intentDistribution = computed(() => stats.value?.intent_distribution || {})
  const sentimentDistribution = computed(() => stats.value?.sentiment_distribution || {})
  const selectedAnchor = computed(() => anchors.value.find(a => a.id === selectedAnchorId.value) || null)

  /**
   * 建立实时通道。
   * 把 WS 客户端的响应式状态直接接到 store 上（推送即更新），不再用定时器轮询；
   * 同一 session 重复调用是幂等的，避免 App 与页面各自 connect 时叠加出多条连接。
   */
  function connect(sessionIdStr: string = 'default') {
    // 幂等只对"还活着的连接"成立：sessionId 没变但连接已断时必须重建，
    // 否则断线后再没有任何入口能把它拉回来
    if (wsClient && sessionId.value === sessionIdStr && wsClient.isAlive()) return
    disconnect()
    sessionId.value = sessionIdStr
    const client = new WebSocketClient(sessionIdStr)
    wsClient = client
    watch(client.connected, v => { isConnected.value = v }, { immediate: true })
    watch(client.latestAnalysis, v => { latestAnalysis.value = v }, { immediate: true })
    // 统计快照只在后端推来新值时覆盖，避免断线瞬间把已有看板数据清空
    watch(client.stats, v => { if (v) stats.value = v }, { immediate: true })
    watch(client.danmakuList, v => { danmakuList.value = [...v] }, { deep: true, immediate: true })
    client.connect()
  }

  function sendDanmaku(content: string, username: string = '测试用户') {
    wsClient?.sendDanmaku(content, username, selectedAnchorId.value ?? undefined)
  }

  async function loadAnchors() {
    try { anchors.value = await listAnchors() } catch (e) { console.error(e) }
  }

  function selectAnchor(id: number | null) {
    selectedAnchorId.value = id
  }

  function disconnect() {
    wsClient?.disconnect()
    wsClient = null
    isConnected.value = false
  }

  return { sessionId, isConnected, latestAnalysis, stats, danmakuList, anchors, selectedAnchorId, selectedAnchor, intentDistribution, sentimentDistribution, connect, sendDanmaku, loadAnchors, selectAnchor, disconnect }
})
