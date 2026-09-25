<template>
  <el-card shadow="never" class="analysis-panel">
    <template #header>🧠 AI 分析结果</template>
    <div v-if="analysis" class="analysis-content">
      <el-row :gutter="16">
        <el-col :span="8">
          <div class="info-block">
            <div class="info-label">意图识别</div>
            <el-tag :type="tagType" size="large">{{ intentLabel }}</el-tag>
            <div class="confidence">置信度: {{ (analysis.intent_confidence * 100).toFixed(0) }}%</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="info-block">
            <div class="info-label">情感分析</div>
            <div class="sentiment">{{ sentimentEmoji }} {{ sentimentLabel }}</div>
            <el-progress :percentage="sentimentPercent" :color="sentimentColor" :stroke-width="8" />
          </div>
        </el-col>
        <el-col :span="8">
          <div class="info-block">
            <div class="info-label">优先级</div>
            <el-tag :type="priorityType" size="large">{{ priorityLabel }}</el-tag>
          </div>
        </el-col>
      </el-row>
      <el-divider />
      <div class="keywords">
        <span class="info-label">关键词：</span>
        <el-tag v-for="kw in analysis.keywords" :key="kw" size="small" style="margin: 2px">{{ kw }}</el-tag>
      </div>
      <div class="strategy" v-if="analysis.strategy">
        <span class="info-label">策略建议：</span>
        <span>{{ analysis.strategy.action }}</span>
        <div class="tips">💡 {{ analysis.strategy.tips }}</div>
      </div>
    </div>
    <el-empty v-else description="等待弹幕分析..." />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AnalysisResult } from '@/types'

const props = defineProps<{ analysis: AnalysisResult | null }>()

const labelMap: Record<string, string> = { purchase: '购买意向', question: '产品疑问', price: '价格疑虑', negative: '负面情绪', interaction: '互动闲聊', other: '其他' }
const tagTypeMap: Record<string, string> = { purchase: 'success', question: 'primary', price: 'warning', negative: 'danger', interaction: 'info', other: 'info' }
const sentimentEmojiMap: Record<string, string> = { positive: '😊', neutral: '😐', negative: '😞' }
const sentimentLabelMap: Record<string, string> = { positive: '积极', neutral: '中性', negative: '消极' }
const priorityTypeMap: Record<string, string> = { high: 'danger', medium: 'warning', low: 'info' }
const priorityLabelMap: Record<string, string> = { high: '高优先级', medium: '中优先级', low: '低优先级' }

const tagType = computed(() => tagTypeMap[props.analysis?.intent || 'other'] || 'info')
const intentLabel = computed(() => labelMap[props.analysis?.intent || 'other'] || '其他')
const sentimentEmoji = computed(() => sentimentEmojiMap[props.analysis?.sentiment || 'neutral'] || '😐')
const sentimentLabel = computed(() => sentimentLabelMap[props.analysis?.sentiment || 'neutral'] || '中性')
const sentimentPercent = computed(() => Math.round(((props.analysis?.sentiment_score || 0.5) + 1) / 2 * 100))
const sentimentColor = computed(() => {
  const s = props.analysis?.sentiment
  return s === 'positive' ? '#67c23a' : s === 'negative' ? '#f56c6c' : '#e6a23c'
})
const priorityType = computed(() => priorityTypeMap[props.analysis?.priority || 'low'] || 'info')
const priorityLabel = computed(() => priorityLabelMap[props.analysis?.priority || 'low'] || '低优先级')
</script>

<style scoped>
.analysis-panel { height: 100%; }
.info-block { text-align: center; }
.info-label { font-size: 12px; color: #909399; margin-bottom: 8px; }
.confidence { font-size: 12px; color: #67c23a; margin-top: 4px; }
.sentiment { font-size: 24px; margin-bottom: 8px; }
.keywords { margin: 12px 0; }
.strategy { margin-top: 12px; }
.tips { color: #e6a23c; font-size: 13px; margin-top: 4px; }
</style>
