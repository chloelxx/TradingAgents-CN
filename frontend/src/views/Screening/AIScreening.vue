<template>
  <div class="ai-screening-container">
    <!-- 头部 -->
    <div class="header">
      <h1>AI 智能股票筛选</h1>
      <p class="subtitle">基于 LLM 深度分析，从 5300+ A 股中筛选最优标的</p>
    </div>

    <!-- 筛选参数 -->
    <div class="filter-section">
      <div class="filter-row">
        <div class="filter-item">
          <label>市场</label>
          <el-select v-model="params.market" placeholder="选择市场">
            <el-option label="中国 A 股" value="CN"></el-option>
            <el-option label="美国股市" value="US"></el-option>
            <el-option label="香港股市" value="HK"></el-option>
          </el-select>
        </div>
        <div class="filter-item">
          <label>筛选日期</label>
          <el-date-picker
            v-model="params.date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </div>
        <div class="filter-item">
          <label>最大结果数</label>
          <el-input-number
            v-model="params.max_results"
            :min="1"
            :max="100"
            :step="10"
          />
        </div>
        <div class="filter-item">
          <label>包含详细分析</label>
          <el-switch v-model="params.include_details" />
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="action-section">
      <el-button
        type="primary"
        size="large"
        :loading="isRunning"
        :disabled="isRunning"
        @click="startScreening"
      >
        <el-icon v-if="!isRunning"><Search /></el-icon>
        <span>{{ isRunning ? '筛选中...' : '开始筛选' }}</span>
      </el-button>
      <el-button
        v-if="isRunning"
        type="danger"
        size="large"
        @click="stopScreening"
      >
        <el-icon><Close /></el-icon>
        停止筛选
      </el-button>
      <el-button
        v-if="result"
        type="success"
        size="large"
        @click="exportResult"
      >
        <el-icon><Download /></el-icon>
        导出结果
      </el-button>
    </div>

    <!-- 进度显示 -->
    <div v-if="isRunning || progress > 0" class="progress-section">
      <el-progress
        :percentage="progress"
        :status="progressStatus"
        :stroke-width="20"
      />
      <div class="progress-message">{{ progressMessage }}</div>
    </div>

    <!-- 结果展示 -->
    <div v-if="result" class="result-section">
      <div class="result-header">
        <h2>筛选结果</h2>
        <div class="result-meta">
          <span class="timestamp">完成时间: {{ result.timestamp }}</span>
        </div>
      </div>
      <div class="result-content">
        <div class="markdown-content" v-html="renderMarkdown(result.report)"></div>
      </div>
    </div>

    <!-- 错误信息 -->
    <div v-if="error" class="error-section">
      <el-alert
        :title="error"
        type="error"
        :closable="false"
        show-icon
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Close, Download } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { useAuthStore } from '@/stores/auth'
// 参数
const params = reactive({
  market: 'CN',
  date: '',
  max_results: 50,
  include_details: true
})

// 状态
const isRunning = ref(false)
const progress = ref(0)
const progressStatus = ref<'success' | 'exception' | 'warning' | ''>('')
const progressMessage = ref('')
const result = ref<any>(null)
const error = ref('')

// 获取认证store
const authStore = useAuthStore()

// 开始筛选
const startScreening = async () => {
  // 重置状态
  isRunning.value = true
  progress.value = 0
  progressStatus.value = ''
  progressMessage.value = ''
  result.value = null
  error.value = ''

  try {
    // 获取token（从authStore或localStorage）
    const token = authStore.token || localStorage.getItem('auth-token')
    if (!token) {
      error.value = '未登录，请先登录'
      progressStatus.value = 'exception'
      isRunning.value = false
      ElMessage.error('未登录，请先登录')
      return
    }
    
    // 使用相对路径访问API（通过Vite代理转发到后端）
    const response = await fetch('/api/search/all', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(params)
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法获取响应流')
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (!line.trim()) continue

        if (line.startsWith('event:')) {
          const eventType = line.substring(6).trim()
          continue
        }

        if (line.startsWith('data:')) {
          const dataStr = line.substring(5).trim()
          try {
            const data = JSON.parse(dataStr)

            if (data.message) {
              progressMessage.value = data.message
            }

            if (data.progress !== undefined) {
              progress.value = data.progress
            }

            if (data.report) {
              result.value = {
                report: data.report,
                timestamp: new Date().toLocaleString()
              }
              progressStatus.value = 'success'
              isRunning.value = false
              ElMessage.success('筛选完成')
            }

            if (data.error) {
              error.value = data.error
              progressStatus.value = 'exception'
              isRunning.value = false
              ElMessage.error(data.error)
            }
          } catch (e) {
            console.error('解析数据失败:', e)
          }
        }
      }
    }
  } catch (err: any) {
    error.value = err.message || '筛选失败'
    progressStatus.value = 'exception'
    isRunning.value = false
    ElMessage.error(error.value)
  }
}

// 停止筛选
const stopScreening = () => {
  isRunning.value = false
  progressMessage.value = '已停止筛选'
  ElMessage.info('已停止筛选')
}

// 导出结果
const exportResult = () => {
  if (!result.value) return

  const blob = new Blob([result.value.report], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `AI股票筛选结果_${new Date().getTime()}.md`
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

// 清理
onUnmounted(() => {
  // 清理逻辑（如果需要）
})
</script>

<style scoped lang="scss">
.ai-screening-container {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  text-align: center;
  margin-bottom: 32px;

  h1 {
    font-size: 32px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 8px;
  }

  .subtitle {
    font-size: 14px;
    color: #909399;
  }
}

.filter-section {
  background: #fff;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;

  .filter-row {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }

  .filter-item {
    flex: 1;
    min-width: 200px;

    label {
      display: block;
      font-size: 14px;
      color: #606266;
      margin-bottom: 8px;
      font-weight: 500;
    }
  }
}

.action-section {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 24px;
}

.progress-section {
  background: #fff;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;

  .progress-message {
    text-align: center;
    margin-top: 16px;
    font-size: 14px;
    color: #606266;
  }
}

.result-section {
  background: #fff;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid #ebeef5;

    h2 {
      font-size: 20px;
      font-weight: 600;
      color: #303133;
    }

    .result-meta {
      .timestamp {
        font-size: 12px;
        color: #909399;
      }
    }
  }

  .result-content {
    .markdown-content {
      line-height: 1.8;
      color: #303133;

      :deep(h1),
      :deep(h2),
      :deep(h3) {
        margin-top: 24px;
        margin-bottom: 16px;
        font-weight: 600;
      }

      :deep(h1) {
        font-size: 24px;
      }

      :deep(h2) {
        font-size: 20px;
      }

      :deep(h3) {
        font-size: 16px;
      }

      :deep(p) {
        margin-bottom: 12px;
      }

      :deep(table) {
        width: 100%;
        border-collapse: collapse;
        margin: 16px 0;

        th,
        td {
          border: 1px solid #ebeef5;
          padding: 12px;
          text-align: left;
        }

        th {
          background: #f5f7fa;
          font-weight: 600;
        }
      }

      :deep(code) {
        background: #f5f7fa;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
      }

      :deep(pre) {
        background: #f5f7fa;
        padding: 16px;
        border-radius: 4px;
        overflow-x: auto;

        code {
          background: none;
          padding: 0;
        }
      }

      :deep(ul),
      :deep(ol) {
        margin: 16px 0;
        padding-left: 24px;

        li {
          margin-bottom: 8px;
        }
      }
    }
  }
}

.error-section {
  margin-top: 24px;
}
</style>