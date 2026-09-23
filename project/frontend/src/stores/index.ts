import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AnalysisResult, Stats, Anchor } from '@/types'
import { WebSocketClient } from '@/utils/websocket'
import { getSessionStats, listAnchors } from '@/api'

export const useMainStore = defineStore('main', () => {
  const sessionId = ref('default')
  const isConnected = ref(false)
  const latestAnalysis = ref<AnalysisResult | null>(null)
  const stats = ref<Stats | null>(null)
  const danmakuList = ref<any[]>([])
  const anchors = ref<Anchor[]>([])
  const selectedAnchorId = ref<number | null>(null)
  let wsClient: WebSocketClient | null = null

  const intentDistribution = computed(() => stats.value?.intent_distribution || {})
  const sentimentDistribution = computed(() => stats.value?.sentiment_distribution || {})
  const selectedAnchor = computed(() => anchors.value.find(a => a.id === selectedAnchorId.value) || null)

  function connect(sessionIdStr: string = 'default') {
    sessionId.value = sessionIdStr
    wsClient = new WebSocketClient(sessionIdStr)
    wsClient.connect()
    setInterval(() => {
      isConnected.value = wsClient?.connected.value || false
      if (wsClient) {
        latestAnalysis.value = wsClient.latestAnalysis.value
        danmakuList.value = wsClient.danmakuList.value
      }
    }, 500)
  }

  function sendDanmaku(content: string, username: string = '测试用户') {
    wsClient?.sendDanmaku(content, username, selectedAnchorId.value ?? undefined)
  }

  async function loadStats() {
    try { stats.value = await getSessionStats(sessionId.value, selectedAnchorId.value ?? undefined) } catch (e) { console.error(e) }
  }

  async function loadAnchors() {
    try { anchors.value = await listAnchors() } catch (e) { console.error(e) }
  }

  function selectAnchor(id: number | null) {
    selectedAnchorId.value = id
  }

  function disconnect() { wsClient?.disconnect(); isConnected.value = false }

  return { sessionId, isConnected, latestAnalysis, stats, danmakuList, anchors, selectedAnchorId, selectedAnchor, intentDistribution, sentimentDistribution, connect, sendDanmaku, loadStats, loadAnchors, selectAnchor, disconnect }
})
