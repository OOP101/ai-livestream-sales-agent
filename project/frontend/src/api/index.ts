import axios from 'axios'
import type { AnalysisResult, ScriptTemplate, Stats, Anchor } from '@/types'

const api = axios.create({ baseURL: '/api', timeout: 10000 })

export async function analyzeDanmaku(content: string, sessionId: string = 'default') {
  const { data } = await api.post<{ code: number; data: AnalysisResult }>(
    '/danmaku/analyze', { content }, { params: { session_id: sessionId } }
  )
  return data.data
}

export async function getSessionStats(sessionId: string, anchorId?: number) {
  const { data } = await api.get<{ code: number; data: Stats }>(
    `/analysis/stats/${sessionId}`, { params: { anchor_id: anchorId } }
  )
  return data.data
}

export async function getRecentAnalysis(sessionId: string, limit: number = 20, anchorId?: number) {
  const { data } = await api.get<{ code: number; data: AnalysisResult[] }>(
    `/analysis/recent/${sessionId}`, { params: { limit, anchor_id: anchorId } }
  )
  return data.data
}

export async function getScriptTemplates(category?: string) {
  const { data } = await api.get<{ code: number; data: ScriptTemplate[] }>(
    '/scripts/templates', { params: { category } }
  )
  return data.data
}

// ============ 主播管理 ============
export async function listAnchors() {
  const { data } = await api.get<{ code: number; data: Anchor[] }>('/anchors')
  return data.data
}

export async function createAnchor(payload: { name: string; platform?: string; room_url?: string }) {
  const { data } = await api.post<{ code: number; data: Anchor }>('/anchors', payload)
  return data.data
}

export async function updateAnchor(id: number, payload: { name?: string; platform?: string; room_url?: string }) {
  const { data } = await api.put<{ code: number; data: Anchor }>(`/anchors/${id}`, payload)
  return data.data
}

export async function deleteAnchor(id: number) {
  await api.delete(`/anchors/${id}`)
}

// ============ 抖音集成 ============
export async function getDouyinLoginStatus() {
  const { data } = await api.get<{ code: number; data: { logged_in: boolean; cooldown_seconds: number } }>('/douyin/login/status')
  return data.data
}

export async function douyinLogin() {
  const { data } = await api.post<{ code: number; message: string; data: { logged_in: boolean } }>('/douyin/login', {}, { timeout: 900000 })
  return data
}

export async function syncDouyinFollowing() {
  const { data } = await api.post<{
    code: number; message: string;
    data: { total: number; live_count: number; added: number; updated: number; items: any[] }
  }>('/douyin/following/sync', {}, { timeout: 300000 })
  return data
}

export async function douyinLogout() {
  await api.post('/douyin/logout')
}

// ============ 直播间弹幕采集 ============
export async function startDanmakuCapture(anchorId: number, sessionId = 'default') {
  const { data } = await api.post<{ code: number; message: string; data: { capturing: boolean } }>(
    `/douyin/live/${anchorId}/capture/start?session_id=${sessionId}`, {}, { timeout: 60000 }
  )
  return data
}

export async function stopDanmakuCapture() {
  const { data } = await api.post<{ code: number; message: string; data: { capturing: boolean } }>('/douyin/live/capture/stop')
  return data
}

export async function getCaptureStatus() {
  const { data } = await api.get<{ code: number; data: { capturing: boolean } }>('/douyin/live/capture/status')
  return data.data
}
