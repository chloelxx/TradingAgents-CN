# API 调用链完整分析 - `/api/analysis/single` 后端执行流程

## 🎯 快速导航

**你要研究这个功能，应该按这个顺序看入口：**

1. **前端入口** → `frontend/src/views/Analysis/SingleAnalysis.vue` (3402行)
2. **前端API调用** → `frontend/src/api/analysis.ts` (483行)
3. **后端路由入口** → `app/routers/analysis.py` (1259行，第42-90行)
4. **核心服务** → `app/services/simple_analysis_service.py` (2909行)
5. **多智能体框架** → `tradingagents/graph/trading_graph.py`

---

## 📊 完整调用链流程图

```
用户操作 (前端)
    ↓
SingleAnalysis.vue (填写表单，选择参数)
    ↓
点击"开始分析"按钮
    ↓
analysisApi.startSingleAnalysis() 调用 POST /api/analysis/single
    ├─ 前端发送的请求体 (SingleAnalysisRequest)
    └─ {
        "symbol": "000001",              // 股票代码
        "parameters": {
          "market_type": "A股",          // 市场类型
          "analysis_date": "2025-01-23",  // 分析日期
          "research_depth": "3",          // 分析深度 (1-5)
          "selected_analysts": [...],     // 分析师列表
          "quick_analysis_model": "qwen-turbo",   // 快速分析模型
          "deep_analysis_model": "qwen-plus"      // 深度分析模型
        }
      }
    ↓
=================== 后端处理 ===================
    ↓
@router.post("/single") 路由处理器触发
    ├─ 文件: app/routers/analysis.py
    ├─ 函数: submit_single_analysis()
    └─ 位置: 第42-90行
    ↓
1️⃣ 认证检查
    └─ user: dict = Depends(get_current_user)
       验证用户是否已登录
    ↓
2️⃣ 创建临时任务记录
    └─ analysis_service = get_simple_analysis_service()
       result = await analysis_service.create_analysis_task(user_id, request)
       ├─ 生成 task_id (UUID)
       ├─ 立即返回给前端 {"task_id": "xxx", ...}
       └─ 任务存储在内存和MongoDB中
    ↓
3️⃣ 立即返回给前端（异步执行）
    └─ return {
        "success": True,
        "data": {"task_id": "xxx", ...},
        "message": "分析任务已在后台启动"
      }
    ↓
4️⃣ 在后台异步执行分析
    └─ background_tasks.add_task(run_analysis_task)
       ├─ 不阻塞HTTP响应
       └─ 在 BackgroundTasks 中运行
    ↓
5️⃣ 后台分析执行入口
    └─ async def run_analysis_task():
       └─ service.execute_analysis_background(task_id, user_id, request)
    ↓
=================== 核心分析服务 ===================
    ↓
SimpleAnalysisService.execute_analysis_background()
    ├─ 文件: app/services/simple_analysis_service.py
    ├─ 方法行数: 大约1000+行
    └─ 核心步骤:
    
    Step 1️⃣: 参数解析和验证
        ├─ 股票代码: request.get_symbol()
        ├─ 市场类型: request.parameters.market_type
        ├─ 分析深度: request.parameters.research_depth (1-5或"快速"/"深度"等)
        ├─ 分析师列表: request.parameters.selected_analysts
        ├─ 快速/深度模型: quick_analysis_model, deep_analysis_model
        └─ logger.info() 记录所有参数
    
    Step 2️⃣: 创建分析配置
        └─ config = create_analysis_config(
            research_depth=深度级别,
            selected_analysts=分析师,
            quick_model=快速模型,
            deep_model=深度模型,
            llm_provider=供应商 (dashscope/openai等)
          )
        ├─ 根据深度级别(1-5)调整:
        │  ├─ max_debate_rounds (辩论轮数)
        │  ├─ max_risk_discuss_rounds (风险讨论轮数)
        │  ├─ memory_enabled (是否启用记忆)
        │  └─ online_tools (是否使用在线工具)
        └─ 获取LLM配置:
           ├─ backend_url (API服务器地址)
           ├─ api_key (API密钥)
           └─ 优先级: 模型配置 > 厂家配置 > 环境变量 > 硬编码默认值
    
    Step 3️⃣: 获取历史股票数据
        ├─ financial_data_service.get_historical_data(stock_code, date)
        ├─ 获取K线数据、技术指标、成交量等
        └─ 为LLM分析提供基础数据
    
    Step 4️⃣: 创建多智能体分析框架实例
        └─ trading_graph = self._get_trading_graph(config)
        ├─ TradingAgentsGraph(
             selected_analysts=["市场分析师", "基本面分析师"],
             config=config
           )
        ├─ 每次创建新实例（避免并发冲突）
        └─ 包含多个专业分析师角色
    
    Step 5️⃣: 并发执行多个分析任务
        └─ loop.run_in_executor(executor, trading_graph.run, stock_code)
        ├─ 使用线程池执行同步的TradingAgents
        ├─ 避免阻塞异步事件循环
        └─ 最多同时执行3个分析任务
    
    Step 6️⃣: 多智能体分析执行
        └─ TradingAgentsGraph.run(stock_code)
        ├─ 市场分析师: 技术面分析
        │  └─ 价格趋势、支撑位、阻力位、K线形态等
        ├─ 基本面分析师: 财务数据分析
        │  └─ PE、PB、ROE、净利润增长等
        ├─ 情感分析师: 新闻与市场情绪
        │  └─ 新闻情感、社交媒体热度等
        ├─ 风险分析师: 风险评估
        │  └─ 黑天鹅事件、波动率等
        └─ 多轮辩论:
           └─ 多个智能体之间循环辩论
              ├─ 快速模型(qwen-turbo): 快速响应
              └─ 深度模型(qwen-plus): 深度分析
    
    Step 7️⃣: 生成分析报告
        ├─ 技术分析总结
        ├─ 基本面评分 (1-10分)
        ├─ 情感分析评分
        ├─ 综合评分
        ├─ 投资建议 (买入/持有/卖出)
        ├─ 风险评估
        └─ token使用统计 (用于成本计算)
    
    Step 8️⃣: 保存结果到数据库
        ├─ MongoDB: analysis_results 集合
        ├─ 记录完整的分析报告
        └─ 包含所有详细数据和评分
    
    Step 9️⃣: 发送进度更新通知
        ├─ WebSocket: 实时推送进度到前端
        ├─ Server-Sent Events (SSE): 渐进式推送
        └─ 前端收到 "分析完成" 事件后刷新结果
    
    ✅ 分析完成
        └─ task_status = "completed"
           前端可以调用 analysisApi.getResult(task_id) 获取完整结果
```

---

## 📁 关键文件详解

### 1️⃣ 前端视图文件

**文件**: `frontend/src/views/Analysis/SingleAnalysis.vue` (3402行)

**核心功能**:
- 📝 表单：用户输入股票代码、选择分析参数
- 🔤 股票代码输入框：支持 A股/美股/港股
- 📅 分析日期选择：选择基准分析日期
- 🎚️ 分析深度滑块：1-5级（快速→全面）
- 🤖 模型选择：快速模型、深度模型
- 📊 实时进度条：显示分析进度百分比
- 📈 结果展示：完整的分析报告

**关键事件**:
```typescript
// 用户点击 "开始分析" 按钮
handleAnalysis() {
  // 1. 验证输入
  // 2. 调用API
  analysisApi.startSingleAnalysis(request)
  // 3. 获取 task_id
  // 4. 轮询进度
}
```

### 2️⃣ 前端API调用文件

**文件**: `frontend/src/api/analysis.ts` (483行)

**关键方法**:
```typescript
// 方法1: 开始分析（发送请求）
analysisApi.startSingleAnalysis(request: SingleAnalysisRequest)
  → POST /api/analysis/single
  → 返回: { task_id, message }

// 方法2: 获取进度
analysisApi.getProgress(analysisId)
  → GET /api/analysis/{analysisId}/progress
  → 返回: { progress %, current_step, steps[] }

// 方法3: 获取结果
analysisApi.getResult(analysisId)
  → GET /api/analysis/{analysisId}/result
  → 返回: { 完整分析报告 }

// 方法4: 任务状态
analysisApi.getTaskStatus(taskId)
  → GET /api/analysis/tasks/{taskId}/status
  → 返回: { status, progress, current_step }
```

**请求体格式** (SingleAnalysisRequest):
```typescript
{
  symbol: "000001",              // 股票代码（必填）
  parameters: {
    market_type: "A股",          // 市场类型
    analysis_date: "2025-01-23",  // 分析日期
    research_depth: "3",          // 分析深度 (1-5或中文)
    selected_analysts: ["市场分析师", "基本面分析师"],  // 分析师
    custom_prompt?: "额外的分析提示",
    include_sentiment: true,      // 包含情感分析
    include_risk: true,           // 包含风险评估
    quick_analysis_model: "qwen-turbo",   // 快速模型
    deep_analysis_model: "qwen-plus"      // 深度模型
  }
}
```

### 3️⃣ 后端路由入口文件

**文件**: `app/routers/analysis.py` (1259行)

**路由定义**:
```python
@router.post("/single", response_model=Dict[str, Any])
async def submit_single_analysis(
    request: SingleAnalysisRequest,      # 请求体
    background_tasks: BackgroundTasks,   # FastAPI后台任务
    user: dict = Depends(get_current_user)  # 认证用户
):
    """
    🎯 入口点: POST /api/analysis/single
    
    执行流程:
    1. 验证用户认证
    2. 立即创建任务记录 (task_id)
    3. 立即返回给前端 (非阻塞)
    4. 在后台异步执行分析 (BackgroundTasks)
    """
```

**核心逻辑** (42-90行):
```python
# 第1步: 获取服务实例
analysis_service = get_simple_analysis_service()

# 第2步: 创建任务记录（立即返回）
result = await analysis_service.create_analysis_task(user["id"], request)
# 返回: { "task_id": "xxx", "created_at": "...", ... }

# 第3步: 在后台启动分析
background_tasks.add_task(run_analysis_task)
# 不等待分析完成，立即返回HTTP响应

# 第4步: 异步执行函数定义
async def run_analysis_task():
    # 重新获取服务实例（避免上下文问题）
    service = get_simple_analysis_service()
    # 执行实际的分析逻辑
    await service.execute_analysis_background(task_id, user_id, request)
```

**返回值** (立即返回):
```python
{
    "success": True,
    "data": {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "pending",
        "created_at": "2025-01-23T10:30:00Z",
        "message": "分析任务已在后台启动"
    },
    "message": "分析任务已在后台启动"
}
```

### 4️⃣ 核心服务文件

**文件**: `app/services/simple_analysis_service.py` (2909行)

#### A. 类初始化 (591-620行)

```python
class SimpleAnalysisService:
    def __init__(self):
        self._trading_graph_cache = {}      # TradingAgents缓存
        self.memory_manager = get_memory_state_manager()  # 内存状态管理
        self._progress_trackers = {}        # 进度跟踪器
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)  # 线程池
        self._stock_name_cache = {}         # 股票名称缓存
```

**关键点**:
- 🧵 线程池最多3个并发任务
- 💾 内存管理器：跟踪任务状态
- 📊 进度跟踪器：Redis存储进度信息
- 🗄️ 缓存机制：避免重复查询

#### B. 创建任务 (create_analysis_task)

```python
async def create_analysis_task(user_id: str, request: SingleAnalysisRequest):
    """
    创建任务记录（立即返回，不执行分析）
    
    执行步骤:
    1. 生成任务ID (UUID)
    2. 提取股票代码 (symbol)
    3. 在内存中创建任务状态
    4. 保存到MongoDB
    5. 返回任务信息给前端
    """
    
    task_id = str(uuid.uuid4())
    stock_code = request.get_symbol()  # 获取股票代码
    
    # 在内存中创建任务
    task_state = await self.memory_manager.create_task(
        task_id=task_id,
        user_id=user_id,
        stock_code=stock_code,
        parameters=request.parameters.model_dump(),
        stock_name=self._resolve_stock_name(stock_code)
    )
    
    # 保存到MongoDB
    await db.analysis_tasks.update_one(
        {"task_id": task_id},
        {"$setOnInsert": {...}},
        upsert=True
    )
    
    return {"task_id": task_id, ...}
```

#### C. 执行分析 (execute_analysis_background)

这是最核心的方法，大约1000+行代码。

**执行阶段**:

```python
async def execute_analysis_background(self, task_id: str, user_id: str, request: SingleAnalysisRequest):
    """
    在后台执行分析（非阻塞）
    """
    
    try:
        # ===== 阶段1: 参数解析 =====
        stock_code = request.get_symbol()
        market_type = request.parameters.market_type
        research_depth = request.parameters.research_depth  # 1-5或"快速"等
        selected_analysts = request.parameters.selected_analysts
        quick_model = request.parameters.quick_analysis_model
        deep_model = request.parameters.deep_analysis_model
        
        logger.info(f"📊 开始分析: {stock_code}, 深度: {research_depth}")
        
        # ===== 阶段2: 创建分析配置 =====
        config = create_analysis_config(
            research_depth=research_depth,
            selected_analysts=selected_analysts,
            quick_model=quick_model,
            deep_model=deep_model,
            llm_provider="dashscope",  # 从配置读取
            market_type=market_type
        )
        
        # 配置内容:
        # - max_debate_rounds: 辩论轮数 (1-3)
        # - max_risk_discuss_rounds: 风险讨论轮数
        # - memory_enabled: 是否启用记忆
        # - online_tools: 是否使用在线工具
        # - backend_url: LLM服务器地址
        # - api_key: LLM API密钥
        
        # ===== 阶段3: 获取历史数据 =====
        historical_data = await financial_data_service.get_historical_data(
            stock_code=stock_code,
            analysis_date=request.parameters.analysis_date,
            market_type=market_type
        )
        
        # 返回数据: K线、技术指标、成交量等
        logger.info(f"📈 获取历史数据: {len(historical_data)} 条记录")
        
        # ===== 阶段4: 更新进度（已获取数据） =====
        await self._update_progress(task_id, 20, "已获取股票数据")
        
        # ===== 阶段5: 创建多智能体实例 =====
        trading_graph = self._get_trading_graph(config)
        # 返回: TradingAgentsGraph 实例
        #   ├─ 市场分析师 (MarketAnalyst)
        #   ├─ 基本面分析师 (FundamentalAnalyst)
        #   ├─ 情感分析师 (SentimentAnalyst)
        #   └─ 风险分析师 (RiskAnalyst)
        
        # ===== 阶段6: 执行分析（线程池） =====
        loop = asyncio.get_event_loop()
        analysis_result = await loop.run_in_executor(
            self._thread_pool,
            trading_graph.run,
            stock_code
        )
        
        # TradingAgentsGraph.run() 执行:
        # 1. 多轮辩论 (max_debate_rounds)
        # 2. 风险讨论 (max_risk_discuss_rounds)
        # 3. 综合评分 (1-10分)
        # 4. 生成报告
        
        # ===== 阶段7: 更新进度（分析完成） =====
        await self._update_progress(task_id, 80, "分析完成，生成报告")
        
        # ===== 阶段8: 处理和转换结果 =====
        result_data = {
            "task_id": task_id,
            "stock_code": stock_code,
            "stock_name": self._resolve_stock_name(stock_code),
            "analysis_date": request.parameters.analysis_date,
            "research_depth": research_depth,
            
            # 分析结果
            "summary": analysis_result.get("summary", ""),
            "technical_analysis": analysis_result.get("technical_analysis", ""),
            "fundamental_analysis": analysis_result.get("fundamental_analysis", ""),
            "sentiment_analysis": analysis_result.get("sentiment_analysis", ""),
            "risk_assessment": analysis_result.get("risk_assessment", ""),
            "recommendation": analysis_result.get("recommendation", ""),
            
            # 评分
            "technical_score": analysis_result.get("technical_score", 0),
            "fundamental_score": analysis_result.get("fundamental_score", 0),
            "sentiment_score": analysis_result.get("sentiment_score", 0),
            "overall_score": analysis_result.get("overall_score", 0),
            
            # Token统计
            "token_usage": {
                "prompt_tokens": analysis_result.get("prompt_tokens", 0),
                "completion_tokens": analysis_result.get("completion_tokens", 0),
                "total_tokens": analysis_result.get("total_tokens", 0),
                "cost": analysis_result.get("cost", 0)
            },
            
            "created_at": datetime.utcnow(),
            "analysis_duration": time.time() - start_time
        }
        
        # ===== 阶段9: 保存到MongoDB =====
        db = get_mongo_db()
        await db.analysis_results.insert_one(result_data)
        logger.info(f"💾 结果已保存到MongoDB")
        
        # ===== 阶段10: 更新任务状态 =====
        await db.analysis_tasks.update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "completed",
                "progress": 100,
                "completed_at": datetime.utcnow(),
                "result_id": str(result_data["_id"])
            }}
        )
        
        # ===== 阶段11: 发送完成通知 =====
        await self.memory_manager.update_task_status(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message="分析完成"
        )
        
        # WebSocket推送
        await websocket_manager.send_notification(user_id, {
            "type": "analysis_completed",
            "task_id": task_id,
            "message": f"{stock_code} 分析完成"
        })
        
        logger.info(f"✅ 分析完成: {task_id}")
        
    except Exception as e:
        logger.error(f"❌ 分析失败: {e}")
        # 更新失败状态
        await self.memory_manager.update_task_status(
            task_id=task_id,
            status=TaskStatus.FAILED,
            message=str(e)
        )
```

#### D. 创建分析配置 (create_analysis_config)

```python
def create_analysis_config(
    research_depth,          # 1-5 或 "快速"/"标准"等
    selected_analysts,       # ["市场分析师", "基本面分析师"]
    quick_model,            # "qwen-turbo"
    deep_model,             # "qwen-plus"
    llm_provider,           # "dashscope"
    market_type="A股"
) -> dict:
    """
    根据参数创建分析配置
    """
    
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = llm_provider
    config["quick_think_llm"] = quick_model
    config["deep_think_llm"] = deep_model
    config["selected_analysts"] = selected_analysts
    
    # 根据深度级别调整配置
    if research_depth == 1 or research_depth == "快速":
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = False
    
    elif research_depth == 3 or research_depth == "标准":  # 推荐
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
    
    elif research_depth == 5 or research_depth == "全面":
        config["max_debate_rounds"] = 3
        config["max_risk_discuss_rounds"] = 3
        config["memory_enabled"] = True
    
    # 获取LLM配置
    provider_info = get_provider_and_url_by_model_sync(quick_model)
    config["backend_url"] = provider_info["backend_url"]     # API地址
    config["api_key"] = provider_info.get("api_key")         # API密钥
    
    return config
```

### 5️⃣ 多智能体框架

**文件**: `tradingagents/graph/trading_graph.py`

这个文件包含：
- TradingAgentsGraph 类：主要的多智能体编排
- 各个分析师角色的定义
- 辩论逻辑
- 综合评分算法

**执行过程**:
```python
trading_graph = TradingAgentsGraph(
    selected_analysts=["市场分析师", "基本面分析师"],
    config=config
)

result = trading_graph.run(stock_code)
# 返回完整的分析报告
```

---

## 🔄 数据流转图

```
前端输入
├─ 股票代码: "000001"
├─ 市场类型: "A股"
├─ 分析深度: 3 (标准)
├─ 分析师: ["市场分析师", "基本面分析师"]
├─ 快速模型: "qwen-turbo"
└─ 深度模型: "qwen-plus"

        ↓ HTTP POST

后端接收 @ /api/analysis/single
        ↓
        ├─ 创建 task_id
        ├─ 保存到 MongoDB (analysis_tasks)
        └─ 立即返回 {"task_id": "xxx"}

        ↓ 异步执行（不阻塞）

后台分析线程
        ├─ 从金融数据服务获取历史数据
        ├─ 创建分析配置
        ├─ 初始化 TradingAgentsGraph
        ├─ 执行多轮辩论和分析
        ├─ 生成报告和评分
        ├─ 保存结果到 MongoDB (analysis_results)
        └─ 更新任务状态 (completed)

        ↓

前端轮询
├─ GET /api/analysis/tasks/{task_id}/status → 获取进度
├─ 显示进度条 (0% → 100%)
└─ 当状态为 completed 时

        ↓

前端获取结果
└─ GET /api/analysis/{task_id}/result → 获取完整报告
   ├─ 技术分析
   ├─ 基本面分析
   ├─ 情感分析
   ├─ 风险评估
   ├─ 综合评分
   ├─ 投资建议
   └─ Token成本统计

        ↓

前端展示结果
├─ 显示分析报告
├─ 显示评分图表
├─ 显示推荐等级
└─ 显示成本信息
```

---

## 🗄️ 数据库表结构

### analysis_tasks 集合

```json
{
  "_id": ObjectId,
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": ObjectId,
  "stock_code": "000001",
  "stock_symbol": "000001",
  "stock_name": "平安银行",
  "status": "pending/running/completed/failed",
  "progress": 0-100,
  "created_at": ISODate,
  "started_at": ISODate,
  "completed_at": ISODate,
  "current_step": "正在分析技术面",
  "error_message": null,
  "result_id": ObjectId  // 指向 analysis_results 表
}
```

### analysis_results 集合

```json
{
  "_id": ObjectId,
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "stock_code": "000001",
  "stock_name": "平安银行",
  "analysis_date": "2025-01-23",
  "summary": "市场看好，基本面稳定...",
  "technical_analysis": "上升趋势明显...",
  "fundamental_analysis": "PE合理，增长稳定...",
  "sentiment_analysis": "市场情绪偏好...",
  "risk_assessment": "系统风险较低...",
  "recommendation": "买入",
  "technical_score": 8,
  "fundamental_score": 7,
  "sentiment_score": 6,
  "overall_score": 7.2,
  "token_usage": {
    "prompt_tokens": 5000,
    "completion_tokens": 2000,
    "total_tokens": 7000,
    "cost": 0.5
  },
  "created_at": ISODate,
  "analysis_duration": 125.5
}
```

---

## 🎓 学习路径

### 第1步：理解前端调用逻辑
**文件**: `frontend/src/views/Analysis/SingleAnalysis.vue`
- 查看表单结构
- 理解参数含义
- 了解如何调用API

### 第2步：理解API格式
**文件**: `frontend/src/api/analysis.ts`
- 研究 SingleAnalysisRequest 数据结构
- 理解各个请求方法
- 学习response处理

### 第3步：理解路由处理
**文件**: `app/routers/analysis.py` (第42-90行)
- 查看 @router.post("/single") 函数
- 理解为什么立即返回（非阻塞）
- 学习 BackgroundTasks 的使用

### 第4步：深入服务实现
**文件**: `app/services/simple_analysis_service.py`
- 研究 create_analysis_task() 方法
- 学习 execute_analysis_background() 的完整流程
- 理解配置创建逻辑

### 第5步：理解多智能体框架
**文件**: `tradingagents/graph/trading_graph.py`
- 学习 TradingAgentsGraph 的架构
- 理解各个分析师角色
- 研究辩论和综合评分算法

### 第6步：调试和测试
**文件**: `tests/test_api_analysis.py` 或 `scripts/debug/quick_test_stock_code.py`
- 运行测试脚本
- 查看日志输出
- 理解整个流程的执行细节

---

## 🐛 关键日志点

当研究代码时，关注这些日志输出：

```
# 路由接收请求
🎯 收到单股分析请求

# 创建任务
📝 创建分析任务

# 后台执行开始
🚀 [BackgroundTask] 开始执行分析任务

# 参数解析
📊 开始分析: 000001, 深度: 3

# 配置创建
📋 ========== 创建分析配置完成 ==========

# 数据获取
📈 获取历史数据

# 分析执行
🔄 执行多智能体分析

# 结果保存
💾 结果已保存到MongoDB

# 完成
✅ 分析完成
```

---

## 📌 常见问题

### Q: 为什么要立即返回 task_id，而不是等待分析完成？

**A**: 为了提供更好的用户体验：
- ✅ 前端立即获得 task_id，显示加载状态
- ✅ HTTP 连接不会超时（分析可能需要几分钟）
- ✅ 用户可以返回列表或做其他事情
- ✅ 前端轮询进度，实时显示分析进度

### Q: 为什么每次都创建新的 TradingAgentsGraph 实例？

**A**: 避免多线程并发冲突：
- TradingAgentsGraph 有可变状态 (self.ticker, self.curr_state等)
- 如果多个线程共享同一个实例，会互相影响
- 虽然初始化有开销，但安全性更重要

### Q: 如何调试分析失败的问题？

**A**: 按这个顺序检查：
1. 检查任务是否创建 (MongoDB: analysis_tasks)
2. 检查后台任务是否启动 (日志: "🚀 [BackgroundTask]")
3. 检查参数是否正确 (日志: "📊 开始分析")
4. 检查LLM配置是否正确 (日志: "✅ 使用数据库配置")
5. 检查数据是否获取 (日志: "📈 获取历史数据")
6. 查看完整错误日志

---

## 🚀 总结

**快速总结整个调用链**:

```
User Input
    ↓
Frontend API Call (POST /api/analysis/single)
    ↓
Backend Route Handler (app/routers/analysis.py)
    ↓
Create Task + Return Immediately (非阻塞)
    ↓
Background Execution (app/services/simple_analysis_service.py)
    ├─ Parse Parameters
    ├─ Create Config
    ├─ Get Historical Data
    ├─ Initialize Multi-Agent Framework
    ├─ Run Analysis (TradingAgentsGraph)
    ├─ Generate Report
    ├─ Save Results (MongoDB)
    ├─ Update Status
    └─ Send Notifications (WebSocket/SSE)
    ↓
Frontend Polling for Results
    ├─ GET /api/analysis/tasks/{task_id}/status (进度)
    └─ GET /api/analysis/{task_id}/result (结果)
    ↓
Display Results on Frontend
```

现在你已经理解了整个后端调用链！🎉

