<template>
  <div class="live-room">
    <el-row :gutter="20" style="height: 100%">
      <!-- 左侧：主播选择 + 弹幕列表 -->
      <el-col :span="8" style="height: 100%">
        <el-card shadow="never" class="panel danmaku-panel">
          <template #header>
            <span>💬 实时弹幕</span>
          </template>
          <!-- 主播选择区 -->
          <div class="anchor-bar">
            <!-- 抖音集成 -->
            <div class="douyin-bar">
              <el-tag :type="douyinLoggedIn ? 'success' : 'info'" size="small" effect="plain">
                {{ douyinLoggedIn ? '抖音已登录' : '抖音未登录' }}
              </el-tag>
              <div class="douyin-actions">
                <el-button
                  v-if="!douyinLoggedIn"
                  type="danger"
                  size="small"
                  :loading="douyinLoginLoading"
                  @click="handleDouyinLogin"
                >登录抖音</el-button>
                <template v-else>
                  <el-button
                    type="success"
                    size="small"
                    :loading="syncLoading"
                    :disabled="cooldownSeconds > 0"
                    @click="handleSyncFollowing"
                  >
                    {{ cooldownSeconds > 0 ? `冷却中 ${formatCooldown(cooldownSeconds)}` : '同步关注列表' }}
                  </el-button>
                  <el-button size="small" @click="handleDouyinLogout">退出</el-button>
                </template>
              </div>
            </div>

            <el-select
              v-model="selectedAnchorId"
              placeholder="选择主播（可选）"
              size="small"
              style="width: 100%"
              clearable
              @change="onAnchorChange"
            >
              <el-option
                v-for="a in anchors"
                :key="a.id"
                :label="`${a.is_live ? '🟢 ' : ''}${a.name}（${a.platform}）`"
                :value="a.id"
              />
            </el-select>
            <div class="anchor-actions">
              <el-button type="primary" size="small" link @click="showCreateAnchor = true">+ 新建主播</el-button>
              <el-button type="info" size="small" link @click="store.loadAnchors()">刷新</el-button>
            </div>
            <div v-if="selectedAnchor" class="anchor-info">
              <div class="anchor-name-row">
                <span class="anchor-name">{{ selectedAnchor.name }}</span>
                <span v-if="selectedAnchor.is_live" class="live-badge">直播中</span>
              </div>
              <a v-if="selectedAnchor.is_live && selectedAnchor.room_url" :href="selectedAnchor.room_url" target="_blank" class="room-url live-url">
                🔴 直播中 — 打开主播主页观看
              </a>
              <a v-else-if="selectedAnchor.room_url" :href="selectedAnchor.room_url" target="_blank" class="room-url">
                {{ selectedAnchor.room_url }}
              </a>
              <el-button
                v-if="selectedAnchor.is_live"
                :type="capturing ? 'danger' : 'warning'"
                size="small"
                :loading="captureLoading"
                @click="toggleCapture"
              >
                {{ capturing ? '停止采集弹幕' : '开始采集弹幕' }}
              </el-button>
            </div>
          </div>
          <el-divider style="margin: 8px 0" />
          <!-- 弹幕输入 -->
          <el-input v-model="testInput" placeholder="输入测试弹幕..." size="small" @keyup.enter="sendTestDanmaku">
            <template #append><el-button @click="sendTestDanmaku">发送</el-button></template>
          </el-input>
          <div class="danmaku-list">
            <div v-for="(dm, idx) in danmakuList" :key="idx" class="danmaku-item">
              <div class="dm-header">
                <span class="dm-user">{{ dm.username || '观众' }}</span>
                <span v-if="getAnchorName(dm.anchor_id)" class="dm-anchor">
                  📺 {{ getAnchorName(dm.anchor_id) }}
                </span>
              </div>
              <span class="dm-content">{{ dm.content }}</span>
            </div>
            <el-empty v-if="danmakuList.length === 0" description="暂无弹幕" />
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：分析和话术 -->
      <el-col :span="16" style="height: 100%">
        <el-row :gutter="20" style="height: 50%">
          <el-col :span="24" style="height: 100%">
            <AnalysisPanel :analysis="latestAnalysis" />
          </el-col>
        </el-row>
        <el-row :gutter="20" style="height: 50%; margin-top: 20px">
          <el-col :span="24" style="height: 100%">
            <ScriptRecommend :analysis="latestAnalysis" />
          </el-col>
        </el-row>
      </el-col>
    </el-row>

    <!-- 新建主播对话框 -->
    <el-dialog v-model="showCreateAnchor" title="新建主播" width="420px" append-to-body :close-on-click-modal="false">
      <el-form :model="newAnchor" label-width="80px">
        <el-form-item label="主播名称">
          <el-input v-model="newAnchor.name" placeholder="请输入主播名称" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="newAnchor.platform" placeholder="选择平台" style="width: 100%" teleported>
            <el-option label="抖音" value="douyin" />
            <el-option label="淘宝" value="taobao" />
            <el-option label="快手" value="kuaishou" />
            <el-option label="视频号" value="wechat" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="直播间地址">
          <el-input v-model="newAnchor.room_url" placeholder="https://..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateAnchor = false">取消</el-button>
        <el-button type="primary" @click="submitCreateAnchor">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMainStore } from '@/stores'
import { createAnchor, getDouyinLoginStatus, douyinLogin, syncDouyinFollowing, douyinLogout, startDanmakuCapture, stopDanmakuCapture, getCaptureStatus } from '@/api'
import AnalysisPanel from '@/components/AnalysisPanel.vue'
import ScriptRecommend from '@/components/ScriptRecommend.vue'

const store = useMainStore()
const testInput = ref('')
const danmakuList = computed(() => store.danmakuList)
const latestAnalysis = computed(() => store.latestAnalysis)
const anchors = computed(() => store.anchors)
const selectedAnchorId = computed({
  get: () => store.selectedAnchorId,
  set: (v: number | null) => store.selectAnchor(v),
})
const selectedAnchor = computed(() => store.selectedAnchor)

const showCreateAnchor = ref(false)
const newAnchor = ref({ name: '', platform: 'custom', room_url: '' })

// 抖音登录状态
const douyinLoggedIn = ref(false)
const douyinLoginLoading = ref(false)
const syncLoading = ref(false)
const cooldownSeconds = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null

function formatCooldown(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}分${s}秒`
}

async function checkDouyinStatus() {
  try {
    const s = await getDouyinLoginStatus()
    douyinLoggedIn.value = s.logged_in
    cooldownSeconds.value = s.cooldown_seconds || 0
    if (cooldownTimer) clearInterval(cooldownTimer)
    if (cooldownSeconds.value > 0) {
      cooldownTimer = setInterval(() => {
        cooldownSeconds.value = Math.max(0, cooldownSeconds.value - 1)
        if (cooldownSeconds.value <= 0 && cooldownTimer) {
          clearInterval(cooldownTimer)
          cooldownTimer = null
        }
      }, 1000)
    }
  } catch (e) {
    console.error(e)
  }
}

async function handleDouyinLogin() {
  douyinLoginLoading.value = true
  try {
    ElMessage.info('正在打开抖音登录窗口，请在弹出的浏览器中扫码登录...')
    const res = await douyinLogin()
    if (res.data.logged_in) {
      ElMessage.success('抖音登录成功')
      douyinLoggedIn.value = true
    } else {
      ElMessage.warning(res.message || '登录失败')
    }
  } catch (e: any) {
    ElMessage.error('登录失败：' + (e?.response?.data?.detail || e.message))
  } finally {
    douyinLoginLoading.value = false
  }
}

async function handleSyncFollowing() {
  syncLoading.value = true
  try {
    const res = await syncDouyinFollowing()
    const liveCount = res.data?.live_count ?? 0
    ElMessage.success(`${res.message}，其中 ${liveCount} 个正在直播`)
    await store.loadAnchors()
    // 同步成功后启动 1 小时冷却
    cooldownSeconds.value = 3600
    if (cooldownTimer) clearInterval(cooldownTimer)
    cooldownTimer = setInterval(() => {
      cooldownSeconds.value = Math.max(0, cooldownSeconds.value - 1)
      if (cooldownSeconds.value <= 0 && cooldownTimer) {
        clearInterval(cooldownTimer)
        cooldownTimer = null
      }
    }, 1000)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e.message
    if (detail && String(detail).includes('登录')) {
      douyinLoggedIn.value = false
      ElMessage.warning('请先登录抖音')
    } else if (e?.response?.status === 429) {
      ElMessage.warning(detail)
    } else {
      ElMessage.error('同步失败：' + detail)
    }
  } finally {
    syncLoading.value = false
  }
}

async function handleDouyinLogout() {
  try {
    await ElMessageBox.confirm('确定退出抖音登录吗？', '提示', { type: 'warning' })
    await douyinLogout()
    douyinLoggedIn.value = false
    ElMessage.success('已退出抖音登录')
  } catch {
    // 用户取消
  }
}

function onAnchorChange() {
  // selectedAnchorId 已通过 v-model 双向绑定更新
}

function getAnchorName(anchorId: number | null | undefined): string {
  if (!anchorId) return ''
  return anchors.value.find(a => a.id === anchorId)?.name || ''
}

const capturing = ref(false)
const captureLoading = ref(false)

async function toggleCapture() {
  if (!selectedAnchor.value) return
  captureLoading.value = true
  try {
    if (capturing.value) {
      await stopDanmakuCapture()
      capturing.value = false
      ElMessage.success('已停止采集弹幕')
    } else {
      await startDanmakuCapture(selectedAnchor.value.id, 'default')
      capturing.value = true
      ElMessage.success('已开始采集直播间弹幕，AI 分析将实时进行')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '操作失败')
  } finally {
    captureLoading.value = false
  }
}

async function submitCreateAnchor() {
  if (!newAnchor.value.name.trim()) {
    ElMessage.warning('请输入主播名称')
    return
  }
  try {
    const anchor = await createAnchor({
      name: newAnchor.value.name.trim(),
      platform: newAnchor.value.platform,
      room_url: newAnchor.value.room_url.trim() || undefined,
    })
    ElMessage.success(`主播「${anchor.name}」已保存`)
    await store.loadAnchors()
    store.selectAnchor(anchor.id)
    showCreateAnchor.value = false
    newAnchor.value = { name: '', platform: 'custom', room_url: '' }
  } catch (e) {
    console.error(e)
    ElMessage.error('保存主播失败')
  }
}

function sendTestDanmaku() {
  if (!testInput.value.trim()) return
  store.sendDanmaku(testInput.value)
  testInput.value = ''
}

onMounted(async () => {
  await store.loadAnchors()
  await checkDouyinStatus()
  // 恢复采集按钮状态（后端可能仍在采集中）
  try {
    const cap = await getCaptureStatus()
    capturing.value = cap.capturing
  } catch { /* 忽略 */ }
  if (!store.isConnected) store.connect('default')
})
</script>

<style scoped>
.live-room { height: 100%; }
.panel { height: 100%; display: flex; flex-direction: column; }
.danmaku-panel :deep(.el-card__body) { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
.anchor-bar { padding: 4px 0; }
.douyin-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.douyin-actions { display: flex; gap: 8px; }
.anchor-actions { display: flex; gap: 12px; margin-top: 6px; }
.anchor-info { margin-top: 8px; font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
.anchor-name-row { display: flex; align-items: center; gap: 8px; }
.anchor-name { color: #303133; font-weight: 600; }
.live-badge { color: #fff; background: #f56c6c; font-size: 11px; padding: 1px 6px; border-radius: 4px; }
.live-url { color: #f56c6c; font-weight: 600; }
.room-url { color: #409eff; word-break: break-all; font-size: 12px; }
.danmaku-list { flex: 1; overflow-y: auto; margin-top: 10px; }
.danmaku-item { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }
.dm-header { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.dm-user { color: #409eff; font-weight: bold; }
.dm-anchor { color: #909399; font-size: 12px; background: #f5f7fa; padding: 1px 6px; border-radius: 4px; }
.dm-content { color: #303133; }
</style>
