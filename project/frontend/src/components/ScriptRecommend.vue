<template>
  <el-card shadow="never" class="script-panel">
    <template #header>
      <span>💡 话术推荐</span>
      <el-button v-if="analysis?.recommended_script" size="small" type="primary" @click="copyScript" style="float: right">
        📋 复制话术
      </el-button>
    </template>
    <div v-if="analysis?.recommended_script" class="script-content">
      <div class="script-text">{{ analysis.recommended_script }}</div>
      <div class="script-meta">
        <el-tag size="small" type="info">{{ analysis.script_category }}</el-tag>
        <span class="source-count">📚 RAG来源: {{ analysis.rag_sources?.length || 0 }} 条</span>
      </div>
    </div>
    <el-empty v-else description="等待话术推荐..." />
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import type { AnalysisResult } from '@/types'

const props = defineProps<{ analysis: AnalysisResult | null }>()

function copyScript() {
  if (props.analysis?.recommended_script) {
    navigator.clipboard.writeText(props.analysis.recommended_script)
    ElMessage.success('话术已复制到剪贴板')
  }
}
</script>

<style scoped>
.script-panel { height: 100%; }
.script-content { padding: 16px; background: #f0f9eb; border-radius: 8px; }
.script-text { font-size: 16px; line-height: 1.8; color: #303133; }
.script-meta { margin-top: 12px; display: flex; align-items: center; gap: 12px; }
.source-count { font-size: 12px; color: #909399; }
</style>
