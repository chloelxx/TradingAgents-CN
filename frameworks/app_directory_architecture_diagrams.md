# TradingAgents-CN `/app` 目录 - 代码架构与交互图

## 🏗️ 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         前端应用 (Vue3 + Vite)                      │
└────────────────┬────────────────────────────────────────────────────┘
                 │ REST API + WebSocket
                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI 应用 (main.py)                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 中间件层 (middleware/)                                        │  │
│  │  - 操作日志记录                                               │  │
│  │  - 请求/响应拦截                                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 路由层 (routers/) - 38个API端点文件                           │  │
│  │  ├─ 分析: analysis.py (1259行)                               │  │
│  │  ├─ 认证: auth_db.py                                         │  │
│  │  ├─ 股票: stocks.py, stock_data.py, stock_sync.py            │  │
│  │  ├─ 筛选: screening.py                                       │  │
│  │  ├─ 队列: queue.py                                           │  │
│  │  ├─ 实时: sse.py, websocket_notifications.py                │  │
│  │  ├─ 同步: tushare_init.py, akshare_init.py, ...             │  │
│  │  ├─ 配置: config.py (2100行)                                 │  │
│  │  └─ 系统: health.py, logs.py, database.py, ...              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 服务层 (services/) - 40+个业务逻辑文件                         │  │
│  │  ├─ 分析: analysis_service.py (955行)                        │  │
│  │  ├─ 队列: queue_service.py (364行)                           │  │
│  │  ├─ 实时: websocket_manager.py, sse_manager.py              │  │
│  │  ├─ 同步: multi_source_basics_sync_service.py                │  │
│  │  │         data_sources/tushare_sync_service.py              │  │
│  │  │         data_sources/akshare_sync_service.py              │  │
│  │  │         data_sources/baostock_sync_service.py             │  │
│  │  ├─ 数据: stock_data_service.py, quotes_service.py           │  │
│  │  ├─ 认证: auth_service.py, authentication_service.py         │  │
│  │  ├─ 配置: config_service.py, config_provider.py              │  │
│  │  ├─ 进度: redis_progress_tracker.py                          │  │
│  │  └─ 其他: screening_service.py, notifications_service.py     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 模型层 (models/) - 数据定义                                   │  │
│  │  ├─ analysis.py (237行) - 分析任务/结果                      │  │
│  │  ├─ stock_models.py (246行) - 股票信息                       │  │
│  │  ├─ user.py - 用户信息                                       │  │
│  │  ├─ config.py - 配置模型                                     │  │
│  │  └─ ...                                                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 核心基础设施层 (core/)                                        │  │
│  │  ├─ config.py (301行) - Pydantic Settings                    │  │
│  │  ├─ database.py - MongoDB连接                                │  │
│  │  ├─ redis_client.py - Redis连接                              │  │
│  │  └─ logging_config.py - 日志配置                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────────┘
                 │
        ┌────────┼────────┬────────┐
        ↓        ↓        ↓        ↓
    MongoDB   Redis  TradingAgents  外部API
      数据库   队列    分析框架    (Tushare/AKShare/BaoStock)
```

---

## 🔄 核心流程 - 时序图

### 流程1: 单股分析请求

```
前端                    routers/analysis.py        services/              Queue              Redis
│                            │                          │                   │                  │
│─── POST /single ────────>  │                          │                   │                  │
│                            │                          │                   │                  │
│                            │──── create_task ────────>│                   │                  │
│                            │                          │                   │                  │
│                            │<──── task_object ────────│                   │                  │
│                            │                          │                   │ save task        │
│                            │                          ├──────────────────>│                  │
│                            │                          │                   │ qa:task:*        │
│                            │                          │                   │────────────────>│
│                            │                          │                   │                  │
│                            │──── add_background_task ─────────────────────┐                 │
│                            │                          │                   │                 │
│  <──── task_id ────────────│                          │                   │                 │
│  (不等待执行完成)           │                          │                   │                 │
│                            │                          │                   │                 │
│  [前端建立WebSocket连接]    │                          │                   │                 │
│                            │                          │                   │                 │
│  WebSocket                 │                          │                   │                 │
│  /ws/notifications         │    [后台执行开始]         │                   │                 │
│  (持续监听)                │                          │                   │                 │
│                            │                          │ update status     │                 │
│                            │                          ├──────────────────>│                 │
│                            │                          │                   │ "processing"    │
│                            │                          │                   │────────────────>│
│                            │                          │                   │                 │
│                            │                          │ TradingGraph      │                 │
│                            │                          │ .run() ─────────────────────────────>│
│                            │                          │ (执行分析)        │                 │
│                            │                          │                   │                 │
│                            │                          │ update progress   │                 │
│                            │                          ├──────────────────>│ update          │
│                            │                          │ (10%)             │ qa:progress:*   │
│                            │                          │                   ├────────────────>│
│                            │                          │                   │                 │
│  <──────── WebSocket ─────────────────────────────────┼───────────────────┤                 │
│  {"progress": 10}          │                          │                   │                 │
│                            │                          │ update progress   │                 │
│                            │                          ├──────────────────>│ update          │
│                            │                          │ (50%)             │ qa:progress:*   │
│                            │                          │                   ├────────────────>│
│                            │                          │                   │                 │
│  <──────── WebSocket ─────────────────────────────────┼───────────────────┤                 │
│  {"progress": 50}          │                          │                   │                 │
│                            │                          │ save result       │                 │
│                            │                          │ to DB ────────────┼──────────────>│
│                            │                          │ (completed)       │  result        │
│                            │                          │                   │                 │
│                            │                          │ update progress   │                 │
│                            │                          ├──────────────────>│ update          │
│                            │                          │ (100%)            │ qa:progress:*   │
│                            │                          │                   ├────────────────>│
│                            │                          │                   │                 │
│  <──────── WebSocket ─────────────────────────────────┼───────────────────┤                 │
│  {"progress": 100,         │                          │                   │                 │
│   "status": "completed",   │                          │                   │                 │
│   "result": {...}}         │                          │                   │                 │
│                            │                          │                   │                 │
```

---

## 📊 数据流向图

### 分析请求数据流

```
前端请求
  {
    "symbol": "000001",
    "parameters": {
      "research_depth": "标准",
      "selected_analysts": ["market", "fundamentals", "news", "social"]
    }
  }
    │
    ↓ (REST POST)
    
routers/analysis.py
  ├─ 验证用户
  ├─ 验证请求参数
  └─ 调用services
    │
    ↓
    
services/simple_analysis_service.py
  ├─ create_analysis_task()
  │   └─ MongoDB.analysis_tasks.insert_one()
  │   └─ Redis.save(task_object)
  │
  ├─ add_background_task()
  │   └─ execute_analysis_background()
  │       │
  │       ├─ create_analysis_config()
  │       │   └─ 获取LLM配置、数据源配置
  │       │
  │       ├─ TradingAgentsGraph(config)
  │       │   └─ 初始化多智能体框架
  │       │
  │       ├─ trading_graph.run(symbol)
  │       │   ├─ MarketAnalystAgent
  │       │   ├─ FundamentalAnalystAgent
  │       │   ├─ NewsAnalystAgent
  │       │   ├─ SocialMediaAnalystAgent
  │       │   └─ ConsumerAgent
  │       │   (并行执行，输入：股票代码 + 历史数据)
  │       │
  │       ├─ 推送进度更新
  │       │   ├─ Redis.update(qa:progress:{task_id})
  │       │   └─ WebSocket.send_progress_update()
  │       │
  │       ├─ 保存结果
  │       │   └─ MongoDB.analysis_tasks.update_one()
  │       │
  │       └─ 更新状态为 COMPLETED
    │
    ↓ (立即返回给前端，不等待执行)
    
前端
  {
    "task_id": "xxx",
    "status": "pending",
    "progress": 0,
    "created_at": "..."
  }
  
  ├─ 建立WebSocket连接
  │   WebSocket /ws/notifications
  │
  └─ 轮询查询任务状态
      GET /api/queue/task/{task_id}
      
WebSocket接收实时进度
  {
    "task_id": "xxx",
    "status": "processing",
    "progress": 25,
    "message": "正在执行市场分析..."
  }
  
  ├─ 更新UI进度条
  └─ (重复直到status=completed)
  
WebSocket接收完成消息
  {
    "task_id": "xxx",
    "status": "completed",
    "progress": 100,
    "result": {
      "summary": "...",
      "recommendation": "...",
      "confidence_score": 0.85,
      "risk_level": "中等",
      "key_points": ["...", "..."],
      "tokens_used": 15000,
      "execution_time": 180.5
    }
  }
  
  └─ 渲染分析结果页面
```

---

## 🔗 模块间交互图

### 核心交互关系

```
                    前端应用
                      │
                ┌─────┴─────┐
                ↓           ↓
          WebSocket      REST API
                ↓           ↓
        websocket_     routers/*
        notifications.py
                │           │
                └─────┬─────┘
                      ↓
              services/*
              │   │   │   │   │
        ┌─────┼───┼───┼───┼───┼─────┐
        │     │   │   │   │   │     │
        ↓     ↓   ↓   ↓   ↓   ↓     ↓
      analysis queue websocket auth config
      _service _service _manager _service _service
        │         │        │        │        │
        ├─────────┼────────┼────────┼────────┤
        │         │        │        │        │
        ↓         ↓        ↓        ↓        ↓
      models   Redis   WebSocket  MongoDB  Config
        │       Keys    Broadcast  Collections
        │
        ├──> stock_data_service (股票数据)
        │
        ├──> multi_source_basics_sync_service (多源同步)
        │    ├──> tushare_sync_service
        │    ├──> akshare_sync_service
        │    └──> baostock_sync_service
        │
        └──> TradingAgentsGraph (多智能体分析)
             ├──> MarketAnalystAgent
             ├──> FundamentalAnalystAgent
             ├──> NewsAnalystAgent
             └──> SocialMediaAnalystAgent
```

---

## 🎯 请求处理流程（完整）

```
1. 请求到达
   │
   ├─ URL: POST /api/analysis/single
   ├─ Body: SingleAnalysisRequest
   └─ Headers: Authorization: Bearer <token>

2. 中间件处理
   │
   ├─ operation_log_middleware
   │   └─ 记录请求信息到操作日志
   │
   ├─ CORS处理
   └─ 其他中间件

3. 路由匹配
   │
   └─ routers/analysis.py::submit_single_analysis()

4. 依赖注入解析
   │
   ├─ Depends(get_current_user)
   │   └─ auth_service.validate_token()
   │
   ├─ Depends(BackgroundTasks)
   │   └─ FastAPI后台任务管理器
   │
   └─ 其他依赖

5. 请求验证
   │
   ├─ Pydantic验证SingleAnalysisRequest
   ├─ 验证symbol格式
   ├─ 验证parameters有效性
   └─ 返回400错误（如果验证失败）

6. 业务逻辑处理
   │
   ├─ simple_analysis_service.create_analysis_task()
   │   ├─ 生成task_id (uuid)
   │   ├─ 构建AnalysisTask对象
   │   ├─ 保存到MongoDB
   │   │   └─ collection: analysis_tasks
   │   │
   │   └─ 保存到Redis
   │       ├─ Hash key: qa:task:{task_id}
   │       └─ 内容: task_id, user_id, symbol, status, etc
   │
   ├─ background_tasks.add_task()
   │   └─ 添加run_analysis_task到后台队列
   │       (此时还未执行)
   │
   └─ 返回response (task_id + status)

7. 响应返回
   │
   ├─ HTTP 200
   ├─ Content-Type: application/json
   └─ Body: AnalysisTaskResponse
       {
         "task_id": "550e8400-e29b-41d4-a716-446655440000",
         "status": "pending",
         "progress": 0,
         "created_at": "2024-01-15T10:30:00"
       }

8. 后台任务执行 (FastAPI BackgroundTasks)
   │
   ├─ run_analysis_task(task_id, user_id, request)
   │   │
   │   ├─ 获取服务实例
   │   │   └─ simple_analysis_service = get_simple_analysis_service()
   │   │
   │   ├─ 更新任务状态为PROCESSING
   │   │   └─ MongoDB.update_one()
   │   │   └─ Redis.hset()
   │   │
   │   ├─ execute_analysis_background(task_id, user_id, request)
   │   │   │
   │   │   ├─ 创建分析配置
   │   │   │   └─ create_analysis_config(request.parameters)
   │   │   │
   │   │   ├─ 创建TradingGraph
   │   │   │   └─ TradingAgentsGraph(
   │   │   │         selected_analysts=["market", "fundamentals", ...],
   │   │   │         config={...}
   │   │   │       )
   │   │   │
   │   │   ├─ 执行分析 (关键步骤)
   │   │   │   │
   │   │   │   ├─ trading_graph.run(symbol)
   │   │   │   │   │
   │   │   │   │   ├─ Step 1: 市场分析 (MarketAnalystAgent)
   │   │   │   │   │   ├─ 获取历史K线数据
   │   │   │   │   │   ├─ 计算技术指标
   │   │   │   │   │   └─ LLM分析 (调用LLM)
   │   │   │   │   │
   │   │   │   │   ├─ Step 2: 基本面分析 (FundamentalAnalystAgent)
   │   │   │   │   │   ├─ 获取财务数据
   │   │   │   │   │   ├─ 计算财务指标
   │   │   │   │   │   └─ LLM分析
   │   │   │   │   │
   │   │   │   │   ├─ Step 3: 新闻分析 (NewsAnalystAgent)
   │   │   │   │   │   ├─ 爬取最新新闻
   │   │   │   │   │   ├─ 情感分析
   │   │   │   │   │   └─ LLM分析
   │   │   │   │   │
   │   │   │   │   ├─ Step 4: 社交媒体分析 (SocialMediaAnalystAgent)
   │   │   │   │   │   ├─ 获取社交数据
   │   │   │   │   │   ├─ 舆情分析
   │   │   │   │   │   └─ LLM分析
   │   │   │   │   │
   │   │   │   │   └─ Step 5: 综合分析 (ConsumerAgent)
   │   │   │   │       ├─ 整合各Agent结果
   │   │   │   │       ├─ 生成建议
   │   │   │   │       └─ 输出最终分析
   │   │   │   │
   │   │   │   └─ 推送进度更新 (每个步骤)
   │   │   │       ├─ Redis更新: qa:progress:{task_id}
   │   │   │       │   ├─ step: 1-5
   │   │   │       │   ├─ total: 5
   │   │   │       │   ├─ progress: 20-100
   │   │   │       │   └─ message: "正在执行市场分析..."
   │   │   │       │
   │   │   │       └─ WebSocket推送
   │   │   │           └─ websocket_manager.send_progress_update()
   │   │   │               └─ 发送给所有监听task_id的WebSocket连接
   │   │   │
   │   │   ├─ 保存结果到MongoDB
   │   │   │   └─ analysis_tasks.update_one(
   │   │   │         {"task_id": task_id},
   │   │   │         {
   │   │   │           "status": "completed",
   │   │   │           "result": AnalysisResult,
   │   │   │           "completed_at": now(),
   │   │   │           "progress": 100
   │   │   │         }
   │   │   │       )
   │   │   │
   │   │   ├─ 更新Redis
   │   │   │   └─ Redis.hset(qa:task:{task_id}, mapping={...})
   │   │   │
   │   │   └─ 推送完成通知
   │   │       └─ WebSocket推送
   │   │           {
   │   │             "task_id": "xxx",
   │   │             "status": "completed",
   │   │             "progress": 100,
   │   │             "result": {...}
   │   │           }
   │   │
   │   └─ 异常处理
   │       ├─ catch Exception
   │       ├─ 更新状态为FAILED
   │       ├─ 保存错误信息
   │       ├─ 推送错误通知
   │       └─ 记录异常日志
   │
   └─ 后台任务完成

9. 前端处理
   │
   ├─ WebSocket接收实时更新
   │   └─ 更新UI进度条、日志信息
   │
   └─ 完成消息到达
       ├─ 关闭WebSocket或切换为轮询
       ├─ 显示最终分析结果
       └─ 提示分析完成
```

---

## 📦 数据模型关系图

```
┌─────────────────┐
│     User        │
│─────────────────│
│ id              │
│ username        │
│ email           │
│ password_hash   │
│ created_at      │
└────────┬────────┘
         │
         │ 1:N
         │
         ├──────────────┬──────────────┬──────────────┐
         │              │              │              │
         ↓              ↓              ↓              ↓
    ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────────┐
    │AnalysisTask │ │ Notification │ │ Favorite    │ │OperationLog  │
    │─────────────│ │──────────────│ │─────────────│ │──────────────│
    │ id          │ │ id           │ │ id          │ │ id           │
    │ task_id     │ │ user_id      │ │ user_id     │ │ user_id      │
    │ user_id (FK)│ │ content      │ │ symbol      │ │ action_type  │
    │ symbol      │ │ read         │ │ created_at  │ │ action       │
    │ status      │ │ created_at   │ │ updated_at  │ │ timestamp    │
    │ progress    │ │ updated_at   │ └─────────────┘ │ details      │
    │ result      │ └──────────────┘                 └──────────────┘
    │ created_at  │
    │ completed_at│
    │ parameters  │
    │ retry_count │
    └─────────────┘
         │
         │ references
         ↓
    ┌──────────────────┐
    │ AnalysisBatch    │
    │──────────────────│
    │ id               │
    │ user_id (FK)     │
    │ batch_id         │
    │ task_ids (array) │
    │ status           │
    │ created_at       │
    │ completed_at     │
    └──────────────────┘

┌────────────────────┐
│  StockBasicInfo    │
│────────────────────│
│ id                 │
│ symbol (6位代码)   │
│ full_symbol        │
│ name               │
│ industry           │
│ area               │
│ list_date          │
│ market_value       │
│ updated_at         │
└────────────────────┘
         │
         │ references
         │
         ↓
    ┌────────────────┐
    │   Quotes       │
    │────────────────│
    │ id             │
    │ symbol (FK)    │
    │ price          │
    │ change_pct     │
    │ volume         │
    │ amount         │
    │ timestamp      │
    └────────────────┘
```

---

## 🔌 API端点组织图

```
/api/
├── /auth                          (认证)
│   ├── POST /register
│   ├── POST /login
│   ├── POST /logout
│   └── GET /me
│
├── /analysis                       (分析 - 1259行)
│   ├── POST /single               ← 核心分析端点
│   ├── POST /batch
│   ├── GET /history
│   ├── GET /{task_id}
│   ├── POST /{task_id}/retry
│   └── DELETE /{task_id}
│
├── /queue                          (队列管理)
│   ├── GET /stats
│   ├── GET /task/{task_id}
│   ├── GET /user-tasks
│   └── POST /task/{task_id}/cancel
│
├── /config                         (配置 - 2100行)
│   ├── GET /system
│   ├── POST /llm
│   ├── POST /datasource
│   ├── GET /models
│   ├── GET /model-catalog
│   ├── POST /model-catalog
│   ├── DELETE /model-catalog/{provider}
│   └── POST /test
│
├── /stocks                         (股票数据)
│   ├── GET /list
│   ├── GET /search
│   ├── GET /{symbol}
│   ├── GET /{symbol}/quotes
│   └── GET /{symbol}/financials
│
├── /screening                      (筛选)
│   ├── POST /create
│   ├── GET /list
│   ├── POST /execute
│   └── DELETE /{id}
│
├── /system                         (系统管理)
│   ├── /database
│   │   ├── GET /status
│   │   ├── GET /stats
│   │   ├── POST /backup
│   │   └── POST /restore
│   │
│   ├── /logs
│   │   ├── GET /files
│   │   ├── GET /read
│   │   └── POST /export
│   │
│   └── /cache
│       ├── GET /stats
│       └── DELETE /clear
│
├── /tushare-init                  (Tushare同步)
│   ├── POST /sync_basics
│   └── GET /progress
│
├── /akshare-init                  (AKShare同步)
│   ├── POST /sync_basics
│   └── GET /progress
│
├── /baostock-init                 (BaoStock同步)
│   ├── POST /sync_basics
│   └── GET /progress
│
├── /notifications                 (通知)
│   ├── GET /
│   ├── GET /unread
│   ├── PUT /{id}/read
│   └── DELETE /{id}
│
├── /favorites                     (收藏)
│   ├── GET /
│   ├── POST /
│   ├── DELETE /{symbol}
│   └── GET /{symbol}
│
└── /reports                       (报告)
    ├── GET /
    ├── POST /generate
    ├── GET /{id}
    └── DELETE /{id}

非API端点：
├── /ws/notifications              (WebSocket实时通知)
├── /health                        (健康检查)
└── /docs                          (Swagger文档)
```

---

## 🔄 状态转换图

### 分析任务状态机

```
                   ┌────────────────┐
                   │   PENDING      │
                   │ (队列中等待)    │
                   └────────┬────────┘
                            │
                      dequeue_task()
                            │
                            ↓
                   ┌────────────────┐
                   │  PROCESSING    │
                   │ (执行中)        │
                   └─────┬──────┬───┘
                         │      │
              (完成)      │      │    (失败)
                         │      │
         ┌───────────────┘      └───────────────┐
         │                                      │
         ↓                                      ↓
    ┌─────────────┐                    ┌──────────────┐
    │  COMPLETED  │                    │   FAILED     │
    │ (分析成功)  │                    │ (分析失败)   │
    └─────────────┘                    └──┬───────┬──┘
         │                                │       │
         │                         (重试<3次)     (给up)
         │                                │       │
         │                                └───┬───┘
         │                                    │
         └────────────────┬───────────────────┘
                          │
                    (或手动取消)
                          │
                          ↓
                   ┌────────────────┐
                   │   CANCELLED    │
                   │ (已取消)        │
                   └────────────────┘
```

### 批次任务状态机

```
    ┌───────────────────────────────────┐
    │                                   │
    │ PENDING → PROCESSING → COMPLETED  │
    │                    → FAILED       │
    │                    → PARTIAL_SUCCESS
    │                    → CANCELLED    │
    │                                   │
    └───────────────────────────────────┘
```

---

## 🚀 扩展点设计

### 1. 新增数据源

```
新建文件：
  app/services/data_sources/new_source_sync_service.py
  
class NewSourceSyncService:
    async def sync_basics(self):
        # 从API获取数据
        # 转换为标准格式
        return stocks_data
        
在 multi_source_basics_sync_service.py 中注册：
  from .data_sources.new_source_sync_service import NewSourceSyncService
  
  async def sync_all_sources(self):
      results = await asyncio.gather(
          TushareSync(),
          AKShareSync(),
          BaoStockSync(),
          NewSourceSync()  # ← 新增
      )
```

### 2. 新增分析Agent

```
在 tradingagents/agents/ 中创建新Agent：
  new_agent.py
  
class NewAgent:
    def run(self, input):
        # 分析逻辑
        return result

在 tradingagents/graph/trading_graph.py 中注册：
  self.graph.add_node("NewAgent", NewAgent)
  
在 app/services/analysis_service.py 中使用：
  config["selected_analysts"].append("new_agent")
  # 已自动调用
```

### 3. 新增API端点

```
新建文件：
  app/routers/new_feature.py
  
from fastapi import APIRouter
router = APIRouter(prefix="/api/new_feature", tags=["new_feature"])

@router.get("/")
async def list_items():
    return []

在 app/main.py 中注册：
  from app.routers import new_feature
  app.include_router(
      new_feature.router,
      tags=["new_feature"]
  )
```

### 4. 新增服务

```
新建文件：
  app/services/new_service.py
  
class NewService:
    async def do_something(self):
        pass

在需要的 routers 或 services 中：
  from app.services.new_service import NewService
  service = NewService()
  result = await service.do_something()
```

---

## 💾 关键文件总结

| 文件 | 行数 | 功能 |
|-----|------|------|
| **main.py** | 764 | FastAPI应用初始化、路由注册 |
| **analysis.py (routers)** | 1259 | 分析API端点 |
| **config.py (routers)** | 2100 | 配置管理API |
| **analysis_service.py** | 955 | 分析业务逻辑 |
| **queue_service.py** | 364 | 队列管理和并发控制 |
| **websocket_manager.py** | 100 | WebSocket实时通信 |
| **stock_models.py** | 246 | 股票数据模型 |
| **analysis.py (models)** | 237 | 分析数据模型 |
| **config.py (core)** | 301 | 配置管理 |
| **worker.py** | 240 | 后台任务处理 |

**总计**：约8000+行代码（核心业务逻辑）

---

## 🎯 总结

### 架构特点

✅ **分层设计** - Router → Service → Model → Database  
✅ **异步全覆盖** - AsyncIO + 后台任务  
✅ **实时通信** - WebSocket + SSE + 轮询  
✅ **并发控制** - 分布式限流  
✅ **多源数据** - Fallback机制  
✅ **多智能体** - LangGraph框架  
✅ **模块化扩展** - 易于添加新功能  

### 请求生命周期

```
来自客户端 → 中间件 → 路由匹配 → 依赖注入 → 验证 → 
业务逻辑 → 数据库/缓存 → 响应返回 → 后台任务 → 完成
```

### 数据流向

```
输入 → Router → Service → 分析框架 → 存储 → 推送 → 输出
                    ↓
              Redis缓存和队列
```

这就是 TradingAgents-CN `/app` 目录的完整架构！
