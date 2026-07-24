<template>
  <div class="market-analysis">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">
            <el-icon class="title-icon"><TrendCharts /></el-icon>
            大盘分析
          </h1>
          <p class="page-description">
            AI驱动的大盘走势分析，全面评估市场整体趋势与投资机会
          </p>
        </div>
      </div>
    </div>

    <div class="analysis-container">
      <el-row :gutter="24">
        <el-col :span="24">
          <el-card class="main-form-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>大盘走势分析</h3>
                <el-tag type="info" size="small">实时市场数据</el-tag>
              </div>
            </template>

            <div class="market-info-section">
              <div class="market-overview-grid">
                <div class="market-card" v-for="item in indexData" :key="item.code">
                  <div class="market-card-header">
                    <span class="market-name">{{ item.name }}</span>
                    <span class="market-code">{{ item.code }}</span>
                  </div>
                  <div class="market-card-body">
                    <div class="market-price">{{ item.price }}</div>
                    <div class="market-change" :class="{ up: item.pct_chg >= 0, down: item.pct_chg < 0 }">
                      <span class="change-arrow">{{ item.pct_chg >= 0 ? '▲' : '▼' }}</span>
                      <span class="change-pct">{{ item.pct_chg }}%</span>
                    </div>
                  </div>
                  <div class="market-card-detail">
                    <div class="detail-row">
                      <span class="detail-label">涨跌额</span>
                      <span class="detail-value" :class="{ up: item.change >= 0, down: item.change < 0 }">{{ item.change }}</span>
                    </div>
                    <div class="detail-row">
                      <span class="detail-label">成交量</span>
                      <span class="detail-value">{{ formatVolume(item.volume) }}</span>
                    </div>
                    <div class="detail-row">
                      <span class="detail-label">成交额</span>
                      <span class="detail-value">{{ formatAmount(item.amount) }}</span>
                    </div>
                    <div class="detail-row">
                      <span class="detail-label">今开/最高/最低</span>
                      <span class="detail-value">{{ item.open }} / {{ item.high }} / {{ item.low }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="action-section">
              <div class="action-buttons" style="display: flex; justify-content: center; align-items: center; width: 100%; text-align: center;">
                <el-button
                  v-if="analysisStatus === 'idle'"
                  type="primary"
                  size="large"
                  @click="submitAnalysis"
                  :loading="submitting"
                  class="submit-btn large-analysis-btn"
                  style="width: 280px; height: 56px; font-size: 18px; font-weight: 700; border-radius: 16px;"
                >
                  <el-icon><TrendCharts /></el-icon>
                  开始大盘分析
                </el-button>

                <el-button
                  v-else-if="analysisStatus === 'running'"
                  type="warning"
                  size="large"
                  disabled
                  class="submit-btn large-analysis-btn"
                  style="width: 280px; height: 56px; font-size: 18px; font-weight: 700; border-radius: 16px;"
                >
                  <el-icon><Loading /></el-icon>
                  分析进行中...
                </el-button>

                <div v-else-if="analysisStatus === 'completed'" style="display: flex; gap: 12px;">
                  <el-button
                    type="success"
                    size="large"
                    @click="showResults = !showResults"
                    class="submit-btn"
                    style="width: 180px; height: 56px; font-size: 16px; font-weight: 700; border-radius: 16px;"
                  >
                    <el-icon><Document /></el-icon>
                    {{ showResults ? '隐藏结果' : '查看结果' }}
                  </el-button>

                  <el-button
                    type="primary"
                    size="large"
                    @click="restartAnalysis"
                    class="submit-btn"
                    style="width: 180px; height: 56px; font-size: 16px; font-weight: 700; border-radius: 16px;"
                  >
                    <el-icon><Refresh /></el-icon>
                    重新分析
                  </el-button>
                </div>

                <el-button
                  v-else-if="analysisStatus === 'failed'"
                  type="danger"
                  size="large"
                  @click="restartAnalysis"
                  class="submit-btn large-analysis-btn"
                  style="width: 280px; height: 56px; font-size: 18px; font-weight: 700; border-radius: 16px;"
                >
                  <el-icon><Refresh /></el-icon>
                  重新分析
                </el-button>
              </div>
            </div>

            <div v-if="analysisStatus === 'running'" class="progress-section">
              <el-card class="progress-card" shadow="hover">
                <template #header>
                  <div class="progress-header">
                    <h4>
                      <el-icon class="rotating-icon">
                        <Loading />
                      </el-icon>
                      分析进行中...
                    </h4>
                  </div>
                </template>

                <div class="progress-content">
                  <div class="overall-progress-info">
                    <div class="progress-stats">
                      <div class="stat-item">
                        <div class="stat-label">已用时间</div>
                        <div class="stat-value">{{ formatTime(progressInfo.elapsedTime) }}</div>
                      </div>
                      <div class="stat-item">
                        <div class="stat-label">预计剩余</div>
                        <div class="stat-value">{{ formatTime(progressInfo.remainingTime) }}</div>
                      </div>
                    </div>
                  </div>

                  <div class="progress-bar-section">
                    <el-progress
                      :percentage="Math.round(progressInfo.progress)"
                      :stroke-width="12"
                      :show-text="true"
                      class="main-progress-bar"
                    />
                  </div>

                  <div class="current-task-info">
                    <div class="task-title">
                      <el-icon class="task-icon">
                        <Loading />
                      </el-icon>
                      {{ progressInfo.currentStep || '正在初始化分析引擎...' }}
                    </div>
                    <div class="task-description" style="white-space: pre-wrap; line-height: 1.6;">
                      {{ progressInfo.message || 'AI正在分析市场数据...' }}
                    </div>
                  </div>
                </div>
              </el-card>
            </div>

            <div v-if="analysisStatus === 'completed' && showResults" class="results-section">
              <el-card class="results-card" shadow="hover">
                <template #header>
                  <div class="results-header">
                    <h3>
                      <el-icon><Trophy /></el-icon>
                      分析结果
                    </h3>
                    <div class="results-header-right">
                      <span class="meta-item">分析日期: {{ analysisResult.analysis_date }}</span>
                      <span class="meta-item">耗时: {{ analysisResult.execution_time?.toFixed(1) || 0 }}秒</span>
                      <el-tag type="success" size="small">已完成</el-tag>
                    </div>
                  </div>
                </template>

                <div v-if="analysisResult" class="analysis-results-content">
                  <!-- 市场广度数据 -->
                  <div v-if="analysisResult.market_breadth" class="breadth-section">
                    <h4>📊 市场全景数据</h4>
                    <div class="breadth-grid">
                      <div class="breadth-card">
                        <div class="breadth-value">{{ analysisResult.market_breadth.up_count }}</div>
                        <div class="breadth-label">上涨家数</div>
                      </div>
                      <div class="breadth-card">
                        <div class="breadth-value">{{ analysisResult.market_breadth.down_count }}</div>
                        <div class="breadth-label">下跌家数</div>
                      </div>
                      <div class="breadth-card">
                        <div class="breadth-value">{{ analysisResult.market_breadth.limit_up_count }}</div>
                        <div class="breadth-label">涨停家数</div>
                      </div>
                      <div class="breadth-card">
                        <div class="breadth-value" :class="{ up: analysisResult.market_breadth.north_flow >= 0, down: analysisResult.market_breadth.north_flow < 0 }">
                          {{ analysisResult.market_breadth.north_flow }}亿
                        </div>
                        <div class="breadth-label">北向资金</div>
                      </div>
                    </div>

                    <div v-if="analysisResult.market_breadth.top_sectors?.length" class="sector-row">
                      <span class="sector-label">领涨板块:</span>
                      <el-tag v-for="s in analysisResult.market_breadth.top_sectors" :key="s" type="danger" size="small" class="sector-tag">{{ s }}</el-tag>
                    </div>
                    <div v-if="analysisResult.market_breadth.bottom_sectors?.length" class="sector-row">
                      <span class="sector-label">领跌板块:</span>
                      <el-tag v-for="s in analysisResult.market_breadth.bottom_sectors" :key="s" type="success" size="small" class="sector-tag">{{ s }}</el-tag>
                    </div>
                  </div>

                  <!-- AI 分析报告 -->
                  <div v-if="analysisResult.ai_report" class="ai-report-section">
                    <h4>🤖 AI 策略分析报告</h4>
                    <div class="ai-report-content" v-html="renderMarkdown(analysisResult.ai_report)"></div>
                  </div>
                </div>

                <div v-else class="no-results">
                  <el-empty description="暂无分析结果" />
                </div>
              </el-card>
            </div>

            <div v-if="analysisStatus === 'failed'" class="error-section">
              <el-card class="error-card" shadow="hover">
                <template #header>
                  <div class="error-header">
                    <h3>
                      <el-icon><WarningFilled /></el-icon>
                      分析失败
                    </h3>
                  </div>
                </template>
                <div class="error-content">
                  <el-alert
                    :title="errorMessage || '分析过程中发生错误，请重试'"
                    type="error"
                    :closable="false"
                  />
                </div>
              </el-card>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  Document, TrendCharts, Loading, Refresh,
  Trophy, WarningFilled
} from '@element-plus/icons-vue'
import { ApiClient } from '@/api/request'

const analysisStatus = ref<'idle' | 'running' | 'completed' | 'failed'>('idle')
const submitting = ref(false)
const showResults = ref(false)
const currentTaskId = ref('')
const errorMessage = ref('')

const indexData = ref<any[]>([])

const progressInfo = reactive({
  progress: 0,
  currentStep: '',
  currentStepDescription: '',
  message: '',
  elapsedTime: 0,
  remainingTime: 0,
  totalTime: 0
})

const analysisResult = ref<any>(null)

let pollingTimer: number | null = null

const formatVolume = (volume: number) => {
  if (!volume || volume <= 0) return '--'
  if (volume >= 100000000) {
    return (volume / 100000000).toFixed(2) + '亿'
  } else if (volume >= 10000) {
    return (volume / 10000).toFixed(2) + '万'
  }
  return volume.toString()
}

const formatAmount = (amount: number) => {
  if (!amount || amount <= 0) return '--'
  if (amount >= 100000000) {
    return (amount / 100000000).toFixed(2) + '亿'
  } else if (amount >= 10000) {
    return (amount / 10000).toFixed(2) + '万'
  }
  return amount.toString()
}

const formatTime = (seconds: number) => {
  if (!seconds || seconds <= 0) return '--'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}分${secs}秒`
}

const renderMarkdown = (text: string) => {
  if (!text) return ''
  let html = text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>')
    .replace(/<li>/g, '<ul><li>')
    .replace(/<\/li><br>/g, '</li></ul><br>')
    .replace(/<\/li>$/, '</li></ul>')
  return html
}

const fetchIndexData = async () => {
  try {
    const response = await ApiClient.get('/api/market/index-data')
    if (response.success && response.data) {
      indexData.value = response.data
    }
  } catch (error) {
    console.warn('获取指数数据失败:', error)
  }
}

const submitAnalysis = async () => {
  submitting.value = true
  
  try {
    const response = await ApiClient.post('/api/analysis/all')
    
    if (response.success) {
      currentTaskId.value = response.data.task_id
      analysisStatus.value = 'running'
      showResults.value = false
      pollingTimer = window.setInterval(pollTaskStatus, 3000)
      ElMessage.success('大盘分析任务已提交，正在分析中...')
    } else {
      throw new Error(response.message || '提交失败')
    }
  } catch (error: any) {
    analysisStatus.value = 'failed'
    errorMessage.value = error.message || '提交分析任务失败'
    ElMessage.error(errorMessage.value)
  } finally {
    submitting.value = false
  }
}

const pollTaskStatus = async () => {
  if (!currentTaskId.value) return

  try {
    const response = await ApiClient.get(`/api/analysis/tasks/${currentTaskId.value}/status`)
    
    if (response.success && response.data) {
      const status = response.data.status
      progressInfo.progress = response.data.progress || 0
      progressInfo.currentStep = response.data.current_step || ''
      progressInfo.message = response.data.message || ''
      progressInfo.elapsedTime = response.data.elapsed_time || 0
      progressInfo.remainingTime = response.data.remaining_time || 0
      progressInfo.totalTime = response.data.estimated_total_time || 0

      if (status === 'completed') {
        clearInterval(pollingTimer!)
        pollingTimer = null
        analysisStatus.value = 'completed'
        showResults.value = true
        await fetchAnalysisResult()
        ElMessage.success('大盘分析完成！')
      } else if (status === 'failed') {
        clearInterval(pollingTimer!)
        pollingTimer = null
        analysisStatus.value = 'failed'
        errorMessage.value = response.data.error_message || '分析失败'
        ElMessage.error('分析失败，请重试')
      }
    }
  } catch (error) {
    console.error('轮询任务状态失败:', error)
  }
}

const fetchAnalysisResult = async () => {
  if (!currentTaskId.value) return

  try {
    const response = await ApiClient.get(`/api/analysis/tasks/${currentTaskId.value}/result`)
    
    if (response.success && response.data) {
      analysisResult.value = response.data
    }
  } catch (error) {
    console.error('获取分析结果失败:', error)
  }
}

const restartAnalysis = () => {
  analysisStatus.value = 'idle'
  analysisResult.value = null
  currentTaskId.value = ''
  errorMessage.value = ''
  showResults.value = false
  progressInfo.progress = 0
  progressInfo.elapsedTime = 0
  progressInfo.remainingTime = 0
}

onMounted(() => {
  fetchIndexData()
})

onUnmounted(() => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
})
</script>

<style scoped>
.market-analysis {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.header-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 40px;
  color: white;
  box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
}

.title-section {
  text-align: center;
}

.page-title {
  font-size: 36px;
  font-weight: 700;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.title-icon {
  font-size: 40px;
}

.page-description {
  font-size: 16px;
  opacity: 0.9;
  margin: 8px 0 0;
}

.analysis-container {
  max-width: 1200px;
  margin: 0 auto;
}

.main-form-card {
  border-radius: 16px;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.market-info-section {
  margin-bottom: 32px;
}

.market-overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.market-card {
  background: linear-gradient(145deg, #ffffff, #f8f9fa);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  transition: transform 0.3s, box-shadow 0.3s;
  border-left: 4px solid transparent;
}

.market-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.market-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.market-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.market-code {
  font-size: 12px;
  color: #999;
  background: #f0f0f0;
  padding: 2px 8px;
  border-radius: 4px;
}

.market-card-body {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 12px;
}

.market-price {
  font-size: 28px;
  font-weight: 700;
  color: #333;
}

.market-change {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 4px;
}

.market-change.up {
  color: #f56c6c;
}

.market-change.down {
  color: #67c23a;
}

.change-arrow {
  font-size: 14px;
}

.market-card-detail {
  border-top: 1px dashed #e8e8e8;
  padding-top: 12px;
  margin-top: 4px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  font-size: 12px;
}

.detail-row .detail-label {
  color: #999;
}

.detail-row .detail-value {
  color: #555;
  font-weight: 500;
}

.detail-row .detail-value.up {
  color: #f56c6c;
}

.detail-row .detail-value.down {
  color: #67c23a;
}

.market-card-footer {
  font-size: 12px;
  color: #999;
}

.action-section {
  margin-bottom: 24px;
}

.submit-btn {
  transition: all 0.3s;
}

.submit-btn:hover {
  transform: scale(1.05);
}

.progress-section {
  margin-bottom: 24px;
}

.progress-card {
  border-radius: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-header h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.progress-content {
  padding-top: 16px;
}

.overall-progress-info {
  margin-bottom: 16px;
}

.progress-stats {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.progress-bar-section {
  margin-bottom: 16px;
}

.main-progress-bar {
  margin: 0;
}

.current-task-info {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
}

.task-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.task-icon {
  color: #667eea;
}

.task-description {
  font-size: 13px;
  color: #666;
}

.results-section {
  margin-top: 24px;
}

.results-card {
  border-radius: 12px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.results-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.results-header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.results-header-right .meta-item {
  font-size: 13px;
  color: #666;
}

.analysis-results-content {
  padding-top: 16px;
}

/* 市场广度 */
.breadth-section {
  margin-bottom: 24px;
}

.breadth-section h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
}

.breadth-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.breadth-card {
  background: #f8f9fa;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}

.breadth-value {
  font-size: 24px;
  font-weight: 700;
  color: #333;
}

.breadth-value.up {
  color: #f56c6c;
}

.breadth-value.down {
  color: #67c23a;
}

.breadth-label {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.sector-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.sector-label {
  font-size: 13px;
  color: #666;
  font-weight: 500;
  white-space: nowrap;
}

.sector-tag {
  margin: 2px;
}

/* AI 报告 */
.ai-report-section {
  margin-top: 8px;
}

.ai-report-section h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
}

.ai-report-content {
  background: #fafbfc;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 24px;
  line-height: 1.9;
  color: #333;
  font-size: 14px;
  white-space: pre-wrap;
}

.ai-report-content h1 {
  font-size: 20px;
  margin: 20px 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #667eea;
}

.ai-report-content h2 {
  font-size: 17px;
  margin: 16px 0 10px;
  color: #333;
}

.ai-report-content h3 {
  font-size: 15px;
  margin: 12px 0 8px;
  color: #555;
}

.ai-report-content strong {
  color: #667eea;
}

.ai-report-content ul, .ai-report-content ol {
  padding-left: 20px;
  margin: 8px 0;
}

.ai-report-content li {
  margin: 4px 0;
}

.ai-report-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.ai-report-content th, .ai-report-content td {
  border: 1px solid #e4e7ed;
  padding: 8px 12px;
  text-align: left;
  font-size: 13px;
}

.ai-report-content th {
  background: #f0f2f5;
  font-weight: 600;
}

.summary-section {
  margin-bottom: 24px;
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.summary-header h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.summary-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.meta-item {
  font-size: 13px;
  color: #666;
}

.summary-content {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  line-height: 1.8;
  color: #333;
}

.summary-content h2, .summary-content h3 {
  margin-top: 16px;
  margin-bottom: 8px;
  color: #333;
}

.summary-content strong {
  color: #667eea;
}

.recommendation-section {
  margin-bottom: 24px;
}

.recommendation-section h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
}

.recommendation-content {
  background: linear-gradient(145deg, #fff3e0, #fff8e1);
  border-left: 4px solid #ff9800;
  border-radius: 0 8px 8px 0;
  padding: 16px;
  line-height: 1.8;
  color: #5d4037;
}

.decision-card {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 20px;
  margin-top: 16px;
}

.decision-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.decision-label {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.decision-details {
  display: flex;
  gap: 32px;
  margin-bottom: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
}

.detail-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.decision-reasoning {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
}

.decision-reasoning .detail-label {
  margin-bottom: 8px;
}

.decision-reasoning p {
  margin: 0;
  font-size: 14px;
  color: #666;
  line-height: 1.6;
}

.key-points-section {
  margin-bottom: 24px;
}

.key-points-section h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
}

.key-points-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.key-points-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px dashed #e4e7ed;
  font-size: 14px;
  color: #333;
}

.key-points-list li:last-child {
  border-bottom: none;
}

.key-points-list li .el-icon {
  color: #67c23a;
  margin-top: 2px;
}

.reports-section {
  margin-top: 24px;
}

.reports-section h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
}

.reports-tabs {
  min-height: 300px;
}

.report-content {
  padding: 16px;
  line-height: 1.8;
  color: #333;
}

.report-content h2, .report-content h3 {
  margin-top: 16px;
  margin-bottom: 8px;
}

.report-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}

.report-content th, .report-content td {
  border: 1px solid #e4e7ed;
  padding: 8px 12px;
  text-align: left;
  font-size: 14px;
}

.report-content th {
  background: #f8f9fa;
  font-weight: 600;
}

.error-section {
  margin-top: 24px;
}

.error-card {
  border-radius: 12px;
}

.error-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.error-content {
  padding-top: 16px;
}

.no-results {
  padding: 40px;
}

.rotating-icon {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .header-content {
    padding: 24px;
  }
  
  .page-title {
    font-size: 24px;
  }
  
  .market-overview-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .decision-details {
    flex-direction: column;
    gap: 12px;
  }
}
</style>