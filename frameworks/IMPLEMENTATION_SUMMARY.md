# 实现总结：AI 股票筛选 API 板块筛选功能

## 📋 项目需求

用户要求增强 `/api/search/all` 接口，实现以下功能：

1. ✅ 获取A股市场上所有股票接口数据和市场新闻
2. ✅ 重点关注 AI、机器人、芯片半导体、存储、陶瓷材料等板块
3. ✅ 调用 `create_china_stock_screener` 函数进行深度筛选
4. ✅ 筛选出最好的 30 只股票的研究报告
5. ✅ 最大程度复用现有功能，新增需要的功能

## 🛠️ 实现方案

### 1. 修改的文件

#### `e:\TradingAgents-CN\app\routers\search.py`

**主要改动：**

| 改动 | 说明 |
|------|------|
| **导入优化** | 添加了 tushare 和 akshare 的可选导入 |
| **StockSearchRequest 模型扩展** | 新增 `sectors` 和 `include_news` 参数 |
| **新增辅助函数** | 5个新函数用于获取板块和新闻数据 |
| **流生成函数重写** | 集成完整的数据获取和筛选流程 |
| **测试接口更新** | 支持板块筛选的非流式测试 |

### 2. 核心新增函数

#### `get_sector_mapping()` 
**功能**: 返回板块与关键词的映射表
```python
{
    "AI": ["科大讯飞", "汇纳科技", ...],
    "机器人": ["埃斯顿", "新松机器人", ...],
    "芯片半导体": ["中芯国际", "北京君正", ...],
    "存储": ["长江存储", "紫光国芯", ...],
    "陶瓷材料": ["三环集团", "瑞泰科技", ...]
}
```

#### `get_sector_stocks_from_tushare()`
**功能**: 从 Tushare 获取特定板块的股票列表
**特点**:
- 支持多个板块关键词搜索
- 自动去重
- 限制返回数量

#### `get_sector_stocks_from_akshare()`
**功能**: 从 AKShare 获取特定板块的股票列表
**特点**:
- 作为 Tushare 的备选方案
- 使用免费数据源
- 支持降级处理

#### `fetch_sector_stocks()`
**功能**: 统一的板块股票获取接口
**特点**:
- 多数据源自动降级
- 支持默认所有板块
- 返回去重后的股票列表

#### `get_news_for_stocks()`
**功能**: 批量获取股票新闻
**特点**:
- 并行处理多只股票
- 支持时间范围筛选
- 自动错误恢复

### 3. 改动后的流程

```
POST /api/search/all
  ↓
[验证请求参数]
  ↓
[获取板块股票列表]
  Tushare → AKShare → 本地映射
  ↓
[获取股票新闻] (可选)
  ↓
[初始化 LLM 和工具包]
  ↓
[运行 create_china_stock_screener 筛选]
  传入: sector_stocks, stock_news, max_results=30
  ↓
[生成研究报告]
  ↓
[限制结果为 30 只股票]
  ↓
[返回流式报告]
```

## 📊 功能对比

### 改动前

| 功能 | 支持 |
|------|------|
| 全市场筛选 | ✅ |
| 板块筛选 | ❌ |
| 新闻获取 | ❌ |
| 流式输出 | ✅ |
| 指定结果数 | ❌ |

### 改动后

| 功能 | 支持 |
|------|------|
| 全市场筛选 | ✅ |
| 板块筛选 | ✅ **NEW** |
| 新闻获取 | ✅ **NEW** |
| 流式输出 | ✅ |
| 指定结果数 | ✅ **NEW** |
| 多数据源支持 | ✅ **NEW** |
| 错误自动恢复 | ✅ **NEW** |

## 🔄 复用的现有功能

| 功能 | 来源 | 说明 |
|------|------|------|
| `create_china_stock_screener` | `china_market_analyst.py` | 核心筛选算法 |
| `Toolkit` | `agent_utils.py` | 数据获取工具包 |
| `get_news_data_service` | `news_data_service.py` | 新闻查询服务 |
| `get_default_llm` | `search.py` | LLM 初始化 |
| `create_llm_by_provider` | `trading_graph.py` | LLM 创建 |

## 📈 请求/响应示例

### 请求

```json
{
  "market": "CN",
  "date": "2026-06-17",
  "max_results": 30,
  "sectors": ["AI", "芯片半导体"],
  "include_news": true
}
```

### 响应 (SSE 流式)

```
event: start
data: {"message":"开始 AI 股票筛选...","timestamp":"2026-06-17T10:30:00Z"}

event: status
data: {"message":"正在获取板块股票列表...","progress":5}

event: status
data: {"message":"成功获取 45 只板块股票","progress":15}

event: status
data: {"message":"正在获取股票市场新闻...","progress":25}

... 更多状态更新 ...

event: result
data: {"report":"# 中国A股基本面分析报告\n\n## 📊 筛选摘要\n...","progress":100}

event: complete
data: {"message":"筛选完成","timestamp":"2026-06-17T10:35:00Z"}
```

## 🧪 测试场景

### 场景 1: 单板块筛选 (AI)
```bash
curl -X POST http://localhost:8000/api/search/all \
  -H "Content-Type: application/json" \
  -d '{"sectors": ["AI"], "max_results": 30}'
```
**预期**: 返回 AI 板块最好的 30 只股票

### 场景 2: 多板块筛选
```bash
curl -X POST http://localhost:8000/api/search/all \
  -H "Content-Type: application/json" \
  -d '{"sectors": ["AI", "芯片半导体", "存储"], "max_results": 30}'
```
**预期**: 返回三个板块合并后最好的 30 只股票

### 场景 3: 全市场筛选
```bash
curl -X POST http://localhost:8000/api/search/all \
  -H "Content-Type: application/json" \
  -d '{"sectors": null, "max_results": 50}'
```
**预期**: 返回全市场最好的 50 只股票

### 场景 4: 快速筛选（无新闻）
```bash
curl -X POST http://localhost:8000/api/search/all \
  -H "Content-Type: application/json" \
  -d '{"sectors": ["芯片半导体"], "include_news": false}'
```
**预期**: 无新闻数据，速度更快 (节省 30-40% 时间)

## 📚 生成的文档

1. **API_SECTOR_SCREENING_GUIDE.md** - 完整 API 文档
2. **QUICK_START_SECTOR_SCREENING.md** - 快速开始指南

## 🔧 技术栈

| 组件 | 技术 |
|------|------|
| 股票数据 | Tushare / AKShare |
| 新闻数据 | AKShare (东方财富) |
| LLM | DeepSeek / Claude / Qwen |
| 异步框架 | AsyncIO |
| Web 框架 | FastAPI |
| 数据库 | MongoDB |

## ⚙️ 依赖关系

```
requests
  ↓
Tushare (可选)
  ↓
AKShare (可选)
  ↓
LangChain
  ↓
MongoDB (用于新闻缓存)
```

## 📊 性能优化

### 1. 并行处理
- 使用 `asyncio` 并行获取多只股票的新闻
- 使用 `asyncio.gather()` 同时等待多个任务

### 2. 缓存机制
- 新闻数据缓存到 MongoDB
- 避免重复查询

### 3. 数据源降级
- Tushare → AKShare → 本地映射
- 一个数据源失败自动尝试下一个

### 4. 流式输出
- 实时返回进度，不阻塞客户端
- 使用 SSE 格式

## 🚀 部署建议

### 环境变量配置

```bash
# Tushare 配置（可选）
TUSHARE_TOKEN=your_token

# LLM 配置
DEEPSEEK_API_KEY=your_key
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4000
LLM_TIMEOUT=180
```

### 启动命令

```bash
# 开发环境
uvicorn app.main:app --reload

# 生产环境
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```
