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
        <span class="source-count">📚 RAG 命中 {{ sources.length }} 条知识</span>
      </div>

      <!-- 检索来源：把「这一句话术从哪来」摊开展示，而不是只给一个条数 -->
      <el-collapse v-if="sources.length" v-model="openedPanels" class="source-collapse">
        <el-collapse-item name="sources">
          <template #title>
            <span class="source-collapse-title">检索来源（{{ sources.length }}）</span>
          </template>
          <ul class="source-list">
            <li v-for="(s, i) in sources" :key="`${s.title}-${i}`" class="source-item">
              <span class="source-index">{{ i + 1 }}</span>
              <span class="source-title">{{ s.title || '未命名文档' }}</span>
              <el-tag size="small" effect="plain" :type="docTagType(s.type)">{{ docLabel(s.type) }}</el-tag>
              <span class="source-score" title="相关度 = 1 − 向量距离">{{ s.score.toFixed(2) }}</span>
            </li>
          </ul>
          <div class="source-hint">
            相关度 = 1 − 向量距离，数值越高表示该文档与当前弹幕越接近；话术即基于以上文档生成
          </div>
        </el-collapse-item>
      </el-collapse>
      <div v-else class="source-empty">本次未命中知识库，话术由模型直接生成（兜底路径）</div>
    </div>
    <el-empty v-else description="等待话术推荐..." />
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { AnalysisResult, RagSource } from '@/types'

const props = defineProps<{ analysis: AnalysisResult | null }>()

/** 默认展开检索来源——这是本页最值得被看见的信息 */
const openedPanels = ref<string[]>(['sources'])

const sources = computed<RagSource[]>(() => props.analysis?.rag_sources || [])

/** doc_type → 知识库名称（对应后端意图路由的检索范围） */
const docLabelMap: Record<string, string> = { product: '商品知识库', script: '话术库' }
const docTagTypeMap: Record<string, string> = { product: 'primary', script: 'success' }
const docLabel = (t?: string) => (t && docLabelMap[t]) || '知识库'
const docTagType = (t?: string) => (t && docTagTypeMap[t]) || 'info'

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
.source-collapse { margin-top: 12px; border-top: 1px solid #dcdfe6; }
.source-collapse :deep(.el-collapse-item__wrap),
.source-collapse :deep(.el-collapse-item__header) { background: transparent; }
.source-collapse-title { font-size: 13px; color: #606266; }
.source-list { margin: 0; padding: 0; list-style: none; }
.source-item { display: flex; align-items: center; gap: 8px; padding: 5px 0; font-size: 13px; }
.source-index { flex: 0 0 18px; height: 18px; line-height: 18px; text-align: center; border-radius: 4px; background: #e1f3d8; color: #529b2e; font-size: 11px; }
.source-title { flex: 1; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-score { flex: 0 0 44px; text-align: right; color: #909399; font-variant-numeric: tabular-nums; }
.source-hint { margin-top: 6px; font-size: 12px; color: #909399; line-height: 1.6; }
.source-empty { margin-top: 12px; font-size: 12px; color: #909399; }
</style>
