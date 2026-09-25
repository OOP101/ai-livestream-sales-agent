<template>
  <div ref="chartRef" class="stats-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  data: Record<string, number>
  type: 'pie' | 'bar'
  /** 数据类别：intent 意图分布 / sentiment 情感分布，用于选择正确的标签与颜色映射 */
  category?: 'intent' | 'sentiment'
}>()
const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

// 意图类型映射
const intentLabelMap: Record<string, string> = {
  purchase: '购买意向', question: '产品疑问', price: '价格疑虑',
  negative: '负面情绪', interaction: '互动闲聊', other: '其他',
}
const intentColorMap: Record<string, string> = {
  purchase: '#67c23a', question: '#409eff', price: '#e6a23c',
  negative: '#f56c6c', interaction: '#909399', other: '#b37feb',
}

// 情感类型映射
const sentimentLabelMap: Record<string, string> = {
  positive: '积极', neutral: '中性', negative: '消极',
}
const sentimentColorMap: Record<string, string> = {
  positive: '#67c23a', neutral: '#e6a23c', negative: '#f56c6c',
}

function resolveLabel(k: string): string {
  if (props.category === 'sentiment') return sentimentLabelMap[k] || k
  return intentLabelMap[k] || sentimentLabelMap[k] || k
}
function resolveColor(k: string): string {
  if (props.category === 'sentiment') return sentimentColorMap[k] || '#409eff'
  return intentColorMap[k] || sentimentColorMap[k] || '#409eff'
}

function renderChart() {
  if (!chart) return
  const entries = props.data ? Object.entries(props.data) : []
  if (entries.length === 0) {
    // 数据被清空时主动清图，否则会停留在上一次的旧分布上误导人
    chart.clear()
    return
  }
  if (props.type === 'pie') {
    chart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: entries.map(([k, v]) => ({
          name: resolveLabel(k), value: v,
          itemStyle: { color: resolveColor(k) }
        })),
        label: { show: true, formatter: '{b}: {c} ({d}%)' }
      }]
    })
  } else {
    chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: entries.map(([k]) => resolveLabel(k)) },
      yAxis: { type: 'value' },
      series: [{
        type: 'bar', data: entries.map(([k, v]) => ({
          value: v, itemStyle: { color: resolveColor(k) }
        }))
      }]
    })
  }
}

// resize 用具名 handler 注册，否则 onUnmounted 里无法移除，组件反复挂载会累积回调
function handleResize() {
  chart?.resize()
}

onMounted(() => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  renderChart()
  window.addEventListener('resize', handleResize)
})

watch(() => props.data, renderChart, { deep: true })
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.stats-chart { width: 100%; height: 300px; }
</style>
