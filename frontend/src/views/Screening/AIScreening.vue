<template>
  <div class="ai-screening-container">
    <!-- 头部 -->
    <div class="header">
      <h1>AI 板块分析</h1>
      <p class="subtitle">输入板块关键词，AI 自动搜索 → 排名 → 多线程评分 → 汇总报告</p>
    </div>

    <!-- 筛选参数 -->
    <div class="filter-section">
      <div class="filter-row">
        <div class="filter-item">
          <label>板块关键词</label>
          <el-input v-model="params.sector" placeholder="如：AI、芯片、新能源、白酒" size="large" />
        </div>
        <div class="filter-item">
          <label>分析数量</label>
          <el-input-number v-model="params.max_stocks" :min="5" :max="50" :step="5" size="large" />
        </div>
        <div class="filter-item">
          <label>分析日期</label>
          <el-date-picker
            v-model="params.analysis_date"
            type="date"
            placeholder="默认今天"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            size="large"
          />
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="action-section">
      <el-button type="primary" size="large" :loading="isRunning" :disabled="isRunning" @click="startAnalysis">
        <el-icon v-if="!isRunning"><Search /></el-icon>
        <span>{{ isRunning ? '分析中...' : '开始分析' }}</span>
      </el-button>
      <el-button v-if="isRunning" type="danger" size="large" @click="stopAnalysis">
        <el-icon><Close /></el-icon>
        停止
      </el-button>
      <el-button v-if="report" type="success" size="large" @click="exportResult">
        <el-icon><Download /></el-icon>
        导出报告
      </el-button>
    </div>

    <!-- 进度显示 -->
    <div v-if="isRunning || progress > 0" class="progress-section">
      <el-progress :percentage="progress" :status="progressStatus" :stroke-width="20" />
      <div class="progress-message">
        <span class="phase-tag" v-if="currentPhase">{{ phaseLabel }}</span>
        {{ progressMessage }}
      </div>
    </div>

    <!-- 排名列表 -->
    <div v-if="rankedStocks.length > 0" class="ranked-section">
      <h3>市值排名 (前 {{ rankedStocks.length }} 只)</h3>
      <el-table :data="rankedStocks" stripe size="small" max-height="300">
        <el-table-column prop="rank" label="排名" width="60" />
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="market_cap" label="市值" width="100" />
        <el-table-column prop="pe_ttm" label="PE(TTM)" width="90" />
        <el-table-column prop="industry" label="行业" />
      </el-table>
    </div>

    <!-- 评分结果（实时追加） -->
    <div v-if="scoredStocks.length > 0" class="scored-section">
      <h3>
        AI 评分结果
        <el-tag type="info" size="small">{{ scoredStocks.length }} / {{ rankedStocks.length }}</el-tag>
      </h3>
      <el-table :data="scoredStocks" stripe size="small" max-height="400">
        <el-table-column prop="rank" label="排名" width="60" />
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="market_cap" label="市值" width="100" />
        <el-table-column label="评分" width="80">
          <template #default="{ row }">
            <span :style="{ color: scoreColor(row.score), fontWeight: 'bold' }">{{ row.score }}</span>
          </template>
        </el-table-column>
        <el-table-column label="评级" width="100">
          <template #default="{ row }">
            <el-tag :type="ratingTagType(row.rating)" size="small">{{ row.rating_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column label="优势/风险" width="120">
          <template #default="{ row }">
            <div class="strength-risk-cell">
              <span v-if="row.strengths?.length" class="strength">+{{ row.strengths.length }}</span>
              <span v-if="row.risks?.length" class="risk">-{{ row.risks.length }}</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 最终报告 -->
    <div v-if="report" class="result-section">
      <div class="result-header">
        <h2>分析报告</h2>
        <div class="result-meta">
          <span class="timestamp">完成时间: {{ finishTime }}</span>
        </div>
      </div>
      <div class="result-content">
        <div class="markdown-content" v-html="renderMarkdown(report)"></div>
      </div>
    </div>

    <!-- 错误信息 -->
    <div v-if="error" class="error-section">
      <el-alert :title="error" type="error" :closable="false" show-icon />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Close, Download } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 参数
const params = reactive({
  sector: '',
  max_stocks: 20,
  analysis_date: '',
})

// 状态
const isRunning = ref(false)
const progress = ref(0)
const progressStatus = ref<'success' | 'exception' | 'warning' | ''>('')
const progressMessage = ref('')
const currentPhase = ref('')
const rankedStocks = ref<any[]>([])
const scoredStocks = ref<any[]>([])
const report = ref('')
const error = ref('')
const finishTime = ref('')
let abortController: AbortController | null = null

// 阶段中文名
const phaseLabel = computed(() => {
  const map: Record<string, string> = {
    searching: '搜索中',
    ranking: '排名中',
    analyzing: '分析中',
    reporting: '生成报告',
    complete: '完成',
  }
  return map[currentPhase.value] || currentPhase.value
})

// 评分颜色
function scoreColor(score: number) {
  if (score >= 85) return '#67c23a'
  if (score >= 70) return '#409eff'
  if (score >= 55) return '#e6a23c'
  return '#f56c6c'
}

// 评级标签类型
function ratingTagType(rating: string) {
  return { A: 'success', B: 'primary', C: 'warning', D: 'danger' }[rating] || 'info'
}

// 开始分析
const startAnalysis = async () => {
  if (!params.sector.trim()) {
    ElMessage.warning('请输入板块关键词')
    return
  }

  // 重置状态
  isRunning.value = true
  progress.value = 0
  progressStatus.value = ''
  progressMessage.value = ''
  currentPhase.value = ''
  rankedStocks.value = []
  scoredStocks.value = []
  report.value = ''
  error.value = ''
  finishTime.value = ''

  const token = authStore.token || localStorage.getItem('auth-token')
  if (!token) {
    error.value = '未登录，请先登录'
    isRunning.value = false
    ElMessage.error('未登录，请先登录')
    return
  }

  abortController = new AbortController()

  try {
    const response = await fetch('/api/sector/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        sector: params.sector,
        max_stocks: params.max_stocks,
        analysis_date: params.analysis_date || null,
      }),
      signal: abortController.signal,
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法获取响应流')

    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''  // 保留不完整的最后一行

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.substring(6).trim()
          continue
        }
        if (line.startsWith('data:')) {
          const dataStr = line.substring(5).trim()
          try {
            const data = JSON.parse(dataStr)
            handleEvent(currentEvent, data)
          } catch (e) {
            console.error('解析SSE数据失败:', e)
          }
        }
      }
    }
  } catch (err: any) {
    if (err.name === 'AbortError') {
      progressMessage.value = '已停止'
    } else {
      error.value = err.message || '分析失败'
      progressStatus.value = 'exception'
    }
    isRunning.value = false
  }
}

// 处理 SSE 事件
function handleEvent(eventType: string, data: any) {
  switch (eventType) {
    case 'start':
      progressMessage.value = data.message
      progress.value = 2
      break

    case 'status':
      currentPhase.value = data.phase || ''
      progressMessage.value = data.message
      if (data.progress) progress.value = data.progress
      break

    case 'stocks_ranked':
      rankedStocks.value = data.stocks || []
      progress.value = 18
      progressMessage.value = `排名完成，共 ${data.count} 只股票`
      break

    case 'stock_scored':
      // 按排名插入
      scoredStocks.value.push(data)
      scoredStocks.value.sort((a, b) => (a.rank || 99) - (b.rank || 99))
      if (data.progress) progress.value = data.progress
      progressMessage.value = `已完成 ${data.completed}/${data.total} 只股票评分`
      break

    case 'report':
      report.value = data.report || ''
      finishTime.value = new Date().toLocaleString()
      progress.value = 90
      progressMessage.value = '报告生成完成'
      break

    case 'complete':
      progress.value = 100
      progressStatus.value = 'success'
      isRunning.value = false
      progressMessage.value = data.message || '分析完成'
      ElMessage.success(`板块「${data.sector}」分析完成，耗时 ${data.execution_time?.toFixed(1)} 秒`)
      break

    case 'error':
      error.value = data.error
      progressStatus.value = 'exception'
      isRunning.value = false
      ElMessage.error(data.error)
      break
  }
}

// 停止分析
const stopAnalysis = () => {
  abortController?.abort()
  isRunning.value = false
  progressMessage.value = '已停止'
  ElMessage.info('已停止分析')
}

// 导出结果
const exportResult = () => {
  if (!report.value) return
  const blob = new Blob([report.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${params.sector}_板块分析_${new Date().toISOString().slice(0, 10)}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

// 渲染 Markdown
const renderMarkdown = (content: string) => {
  return marked(content)
}
</script>

<style scoped lang="scss">
.ai-screening-container {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  text-align: center;
  margin-bottom: 24px;
  h1 { font-size: 28px; font-weight: 600; color: #303133; margin-bottom: 6px; }
  .subtitle { font-size: 14px; color: #909399; }
}

.filter-section {
  background: #fff;
  padding: 20px 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
  .filter-row { display: flex; gap: 20px; flex-wrap: wrap; }
  .filter-item {
    flex: 1; min-width: 180px;
    label { display: block; font-size: 13px; color: #606266; margin-bottom: 6px; font-weight: 500; }
  }
}

.action-section {
  display: flex; gap: 12px; justify-content: center; margin-bottom: 20px;
}

.progress-section {
  background: #fff; padding: 20px 24px; border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); margin-bottom: 20px;
  .progress-message {
    text-align: center; margin-top: 12px; font-size: 14px; color: #606266;
    .phase-tag {
      display: inline-block; background: #ecf5ff; color: #409eff;
      padding: 2px 8px; border-radius: 4px; margin-right: 8px; font-size: 12px;
    }
  }
}

.ranked-section, .scored-section {
  background: #fff; padding: 20px 24px; border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); margin-bottom: 20px;
  h3 { font-size: 16px; font-weight: 600; color: #303133; margin-bottom: 12px;
    .el-tag { margin-left: 8px; }
  }
}

.strength-risk-cell {
  display: flex; gap: 6px;
  .strength { color: #67c23a; }
  .risk { color: #f56c6c; }
}

.result-section {
  background: #fff; padding: 24px; border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  .result-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #ebeef5;
    h2 { font-size: 20px; font-weight: 600; color: #303133; }
    .timestamp { font-size: 12px; color: #909399; }
  }
  .markdown-content {
    line-height: 1.8; color: #303133;
    :deep(h1), :deep(h2), :deep(h3) { margin-top: 20px; margin-bottom: 12px; font-weight: 600; }
    :deep(h1) { font-size: 22px; } :deep(h2) { font-size: 18px; } :deep(h3) { font-size: 15px; }
    :deep(p) { margin-bottom: 10px; }
    :deep(table) { width: 100%; border-collapse: collapse; margin: 12px 0;
      th, td { border: 1px solid #ebeef5; padding: 10px; text-align: left; }
      th { background: #f5f7fa; font-weight: 600; }
    }
    :deep(code) { background: #f5f7fa; padding: 2px 6px; border-radius: 4px; }
    :deep(pre) { background: #f5f7fa; padding: 16px; border-radius: 4px; overflow-x: auto;
      code { background: none; padding: 0; }
    }
    :deep(ul), :deep(ol) { margin: 12px 0; padding-left: 24px; li { margin-bottom: 6px; } }
  }
}

.error-section { margin-top: 20px; }
</style>