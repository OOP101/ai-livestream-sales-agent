<template>
  <div class="dashboard">
    <div class="filter-bar">
      <span class="filter-label">按主播筛选：</span>
      <el-select
        v-model="filterAnchorId"
        placeholder="全部主播"
        size="default"
        clearable
        style="width: 260px"
        @change="onFilterChange"
      >
        <el-option
          v-for="a in anchors"
          :key="a.id"
          :label="`${a.name}（${a.platform}）`"
          :value="a.id"
        />
      </el-select>
    </div>

    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover"><div class="stat-value">{{ stats?.total_analysis || 0 }}</div><div class="stat-label">分析总数</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="stat-value stat-green">{{ intentDist.purchase || 0 }}</div><div class="stat-label">购买意向</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="stat-value stat-orange">{{ intentDist.question || 0 }}</div><div class="stat-label">产品疑问</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="stat-value stat-red">{{ intentDist.negative || 0 }}</div><div class="stat-label">负面情绪</div></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>📊 意图分布</template>
          <StatsChart :data="intentDist" type="pie" category="intent" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>😊 情感分布</template>
          <StatsChart :data="sentimentDist" type="bar" category="sentiment" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>🔍 最近分析</template>
      <el-table :data="recentResults" stripe>
        <el-table-column prop="intent" label="意图" width="120">
          <template #default="{ row }">
            <el-tag :type="tagType(row.intent)" size="small">{{ labelMap[row.intent] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sentiment" label="情感" width="80">
          <template #default="{ row }">{{ sentimentEmoji(row.sentiment) }}</template>
        </el-table-column>
        <el-table-column prop="recommended_script" label="推荐话术" show-overflow-tooltip />
        <el-table-column prop="strategy.action" label="策略" width="160" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMainStore } from '@/stores'
import { getRecentAnalysis } from '@/api'
import StatsChart from '@/components/StatsChart.vue'
import type { AnalysisResult } from '@/types'

const store = useMainStore()
const recentResults = ref<AnalysisResult[]>([])
const stats = computed(() => store.stats)
const intentDist = computed(() => store.intentDistribution)
const sentimentDist = computed(() => store.sentimentDistribution)
const anchors = computed(() => store.anchors)
const filterAnchorId = ref<number | null>(null)

const labelMap: Record<string, string> = { purchase: '购买意向', question: '产品疑问', price: '价格疑虑', negative: '负面情绪', interaction: '互动闲聊', other: '其他' }
const tagTypeMap: Record<string, string> = { purchase: 'success', question: 'primary', price: 'warning', negative: 'danger', interaction: 'info', other: 'info' }
const sentimentEmojiMap: Record<string, string> = { positive: '😊', neutral: '😐', negative: '😞' }
const tagType = (i: string) => tagTypeMap[i] || 'info'
const sentimentEmoji = (s: string) => sentimentEmojiMap[s] || '❓'

const REFRESH_INTERVAL = 5000
let refreshTimer: ReturnType<typeof setInterval> | null = null

function onFilterChange() {
  store.selectAnchor(filterAnchorId.value)
  refresh()
}

async function refresh() {
  try {
    await store.loadStats()
    recentResults.value = await getRecentAnalysis(store.sessionId, 20, filterAnchorId.value ?? undefined)
  } catch (e) {
    console.error('刷新看板数据失败:', e)
  }
}

onMounted(async () => {
  await store.loadAnchors()
  await refresh()
  refreshTimer = setInterval(refresh, REFRESH_INTERVAL)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.filter-bar { margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
.filter-label { font-size: 14px; color: #606266; }
.stat-cards { margin-bottom: 20px; }
.stat-value { font-size: 32px; font-weight: bold; color: #409eff; text-align: center; }
.stat-green { color: #67c23a; }
.stat-orange { color: #e6a23c; }
.stat-red { color: #f56c6c; }
.stat-label { font-size: 14px; color: #909399; text-align: center; margin-top: 8px; }
</style>
