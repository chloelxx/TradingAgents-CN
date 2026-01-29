# 🏗️ TradingAgents-CN 系统架构概览

**简明扼要的整体设计说明**

> 这份文档帮你快速理解"整个系统怎么工作"。45分钟读完，你就能看懂整个项目。

---

## 📍 你在这里

```
学习进度：01 → 02(你在这) → 03 → 04 → 05 → 06 → 07
              快速入门     架构    后端   前端  Agent  代码   部署
```

---

## 🎯 核心问题：这个系统做什么？

### 一句话
**用多个AI Agents分析股票，给出投资建议。**

### 具体流程
```
用户 (前端界面)
  ↓
"请分析股票600000"
  ↓
后端接收请求
  ↓
启动多个AI Agents
  ├─ Agent 1: 基本面分析师 (看财务)
  ├─ Agent 2: 技术分析师 (看K线)
  ├─ Agent 3: 新闻分析师 (看事件)
  └─ Agent 4: 情绪分析师 (看舆论)
  ↓
Agents 互相讨论、辩论
  ↓
综合给出结论
  ↓
前端显示结果
  ↓
用户看到分析报告
```

---

## 🏢 整体系统架构

### 三层架构

```
┌─────────────────────────────────────────────────────────┐
│                    🖥️ 前端层 (Frontend)                 │
│                                                         │
│  Vue 3 + Element Plus                                  │
│  ├─ 仪表板         (Dashboard)                          │
│  ├─ 股票分析       (Analysis)                           │
│  ├─ 股票筛选       (Screening)                          │
│  ├─ 任务中心       (TaskCenter)                         │
│  ├─ 学习中心       (Learning)                           │
│  └─ 设置           (Settings)                           │
│                                                         │
│  浏览器           http://localhost:5173               │
└─────────────────────────────────────────────────────────┘
                           ↑
                           ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────┐
│              🔧 API层 / 中间件 (Backend)                │
│                                                         │
│  FastAPI + Uvicorn                                     │
│  ├─ 认证路由         (Auth API)                        │
│  ├─ 分析路由         (Analysis API)                    │
│  ├─ 任务路由         (Task API)                        │
│  ├─ 股票路由         (Stock API)                       │
│  ├─ 队列路由         (Queue API)                       │
│  └─ WebSocket        (实时通知)                        │
│                                                         │
│  服务器             http://localhost:8000              │
└─────────────────────────────────────────────────────────┘
                           ↑
                           ↓ 同步/异步调用
┌─────────────────────────────────────────────────────────┐
│           🧠 业务逻辑层 (Business Logic)               │
│                                                         │
│  ├─ 用户服务        (User Service)                     │
│  ├─ 分析服务        (Analysis Service)                 │
│  ├─ 任务队列        (Task Queue - APScheduler)         │
│  ├─ AI Agent系统    (LangGraph + LangChain)            │
│  └─ 数据处理        (Data Processing)                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
                           ↑
                           ↓ 读写
┌─────────────────────────────────────────────────────────┐
│             💾 数据存储层 (Data Layer)                  │
│                                                         │
│  ├─ MongoDB        (持久数据: 用户, 报告, 历史)         │
│  ├─ Redis          (缓存 + 任务队列)                    │
│  └─ 外部API        (股票数据: Tushare, AKShare等)      │
│                                                         │
│  数据库             localhost:27017 (MongoDB)          │
│  缓存               localhost:6379 (Redis)             │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 数据流向图

### 用户分析一只股票的完整流程

```
1️⃣ 用户操作 (前端)
   │
   ├─ 打开"股票分析"页面
   ├─ 输入股票代码 "600000"
   └─ 点击"开始分析"按钮
   
2️⃣ 发送请求 (HTTP/API)
   │
   ├─ 前端向后端发送 POST /api/analysis/single
   │  请求体: {symbol: "600000", depth: 3, ...}
   └─ WebSocket 建立实时连接

3️⃣ 后端处理 (FastAPI)
   │
   ├─ 认证用户（JWT Token验证）
   ├─ 验证请求参数
   ├─ 检查用户配额
   └─ 创建分析任务

4️⃣ 任务入队 (Redis Queue)
   │
   ├─ 任务序列化
   ├─ 推送到 Redis 队列
   └─ 返回 task_id 给前端

5️⃣ 实时进度更新 (WebSocket)
   │
   ├─ 任务状态变化 → "preparing"
   ├─ 后端推送进度更新到前端
   └─ 前端显示"正在准备数据..."

6️⃣ 数据获取 (外部API)
   │
   ├─ 从 Tushare/AKShare 获取股票数据
   ├─ 获取财务数据 (基本面)
   ├─ 获取K线数据 (技术面)
   ├─ 获取新闻 (新闻面)
   └─ 缓存到 Redis

7️⃣ AI分析 (Multi-Agent)
   │
   ├─ 基本面分析师 Agent 执行
   │  └─ LLM调用: 分析财务指标
   │
   ├─ 技术分析师 Agent 执行
   │  └─ LLM调用: 分析K线形态
   │
   ├─ 新闻分析师 Agent 执行
   │  └─ LLM调用: 分析事件影响
   │
   └─ 情绪分析师 Agent 执行
      └─ LLM调用: 分析舆论倾向

8️⃣ Agent协作 (讨论/辩论)
   │
   ├─ 看涨研究员汇总看涨观点
   ├─ 看跌研究员汇总看跌观点
   ├─ 两者进行结构化辩论
   └─ 管理员综合给出结论

9️⃣ 结果返回
   │
   ├─ 生成分析报告 (JSON)
   ├─ 保存到 MongoDB
   ├─ 推送到 Redis 缓存
   └─ 通过 WebSocket 发给前端

🔟 前端展示
   │
   ├─ 显示完整的分析报告
   ├─ 显示各Agents的观点
   ├─ 显示最终推荐
   └─ 允许用户保存/分享
```

---

## 🔧 技术栈详解

### 前端 (浏览器端)

```
用户看到 ↓

Vue 3 (框架)
  ├─ 组件化开发 (Components)
  └─ 组件树管理

状态管理 ↓

Pinia (全局状态)
  ├─ authStore (用户认证状态)
  └─ appStore (应用全局状态)

路由管理 ↓

Vue Router (页面路由)
  ├─ /dashboard (仪表板)
  ├─ /analysis (分析)
  ├─ /screening (筛选)
  └─ /settings (设置)

UI组件库 ↓

Element Plus
  ├─ Button, Input, Form
  ├─ Table, Dialog, Menu
  └─ Message, Notification

请求库 ↓

Axios + 拦截器
  ├─ 自动添加 JWT Token
  ├─ 自动处理错误
  └─ 自动刷新 Token

实时通信 ↓

WebSocket
  ├─ 实时接收分析进度
  ├─ 实时接收推送通知
  └─ 实时数据更新

打包工具 ↓

Vite (快速打包)
  └─ 开发: npm run dev
  └─ 生产: npm run build
```

### 后端 (服务器端)

```
用户请求 ↓

FastAPI (Web框架)
  ├─ 快速、高性能
  ├─ 自动API文档 (/docs)
  └─ 异步支持

路由系统 ↓

app/routers/
  ├─ auth.py (认证)
  ├─ analysis.py (分析)
  ├─ stocks.py (股票数据)
  ├─ queue.py (任务队列)
  └─ websocket.py (实时通信)

业务逻辑 ↓

app/services/
  ├─ user_service.py (用户管理)
  ├─ analysis_service.py (分析引擎)
  ├─ stock_service.py (数据获取)
  └─ agent_service.py (Agent编排)

数据模型 ↓

app/models/
  ├─ user.py (用户模型)
  ├─ analysis.py (分析模型)
  └─ stock.py (股票模型)

中间件 ↓

app/middleware/
  ├─ CORS (跨域处理)
  ├─ 错误处理
  └─ 日志记录

配置管理 ↓

app/core/config.py
  ├─ 数据库连接
  ├─ API密钥
  └─ 环境变量

启动文件 ↓

app/main.py
  └─ Uvicorn 运行入口
```

### AI系统 (LLM编排)

```
多Agent框架 ↓

LangGraph (Agent编排)
  ├─ 定义Agent节点
  ├─ 定义转移条件
  └─ 执行工作流

LLM集成 ↓

LangChain
  ├─ OpenAI / Claude
  ├─ 通义千问
  ├─ DeepSeek
  └─ 本地模型

Agent设计 ↓

tradingagents/
  ├─ 基本面分析师
  ├─ 技术分析师
  ├─ 新闻分析师
  ├─ 情绪分析师
  ├─ 看涨研究员
  ├─ 看跌研究员
  └─ 研究管理员

数据源 ↓

├─ Tushare (A股)
├─ AKShare (多市场)
├─ BaoStock (A股)
├─ Finnhub (美股)
└─ Yahoo Finance (全球)
```

### 数据存储 (持久化)

```
数据库 MongoDB ↓
  collections:
  ├─ users (用户账号)
  ├─ analysis_reports (分析报告)
  ├─ analysis_history (分析历史)
  ├─ stocks (股票基本信息)
  └─ configurations (系统配置)

缓存 Redis ↓
  ├─ 股票数据缓存
  ├─ 用户会话 (Session)
  ├─ 任务队列 (Task Queue)
  ├─ 实时进度 (Progress)
  └─ 频率限制计数

外部数据源 ↓
  ├─ Tushare API
  ├─ AKShare API
  ├─ BaoStock API
  ├─ Finnhub API
  └─ Yahoo Finance API
```

---

## 🔄 核心业务流程

### 流程1：用户认证

```
用户在前端输入用户名密码
         ↓
发送 POST /api/auth/login
         ↓
后端验证用户信息
         ↓
MongoDB查询用户表
         ↓
密码验证成功
         ↓
生成JWT Token
         ↓
返回给前端
         ↓
前端保存Token到localStorage
         ↓
后续请求自动附带Token
         ↓
登录成功
```

### 流程2：分析股票

```
用户提交分析请求
         ↓
后端创建分析任务
         ↓
任务推送到Redis队列
         ↓
返回task_id给前端（立即返回）
         ↓
后端异步处理任务
   ├─ 获取股票数据
   ├─ 启动多个Agent
   ├─ 执行分析
   └─ 生成报告
         ↓
实时推送进度到前端 (WebSocket)
         ↓
分析完成
         ↓
保存报告到MongoDB
         ↓
推送完成通知
         ↓
用户查看报告
```

### 流程3：定时任务

```
系统启动
    ↓
APScheduler 初始化
    ↓
根据配置启动多个定时任务
├─ 每天刷新股票清单 (凌晨2点)
├─ 每小时更新股票缓存 (热门股票)
├─ 每周生成周报 (周五晚)
└─ 每月清理过期数据 (月初)
    ↓
根据时间触发任务
    ↓
执行对应的处理逻辑
    ↓
结果保存到数据库
```

---

## 📁 项目目录结构

### 简化版

```
TradingAgents-CN/
│
├─ frontend/              (前端项目)
│  ├─ src/
│  │  ├─ components/      (页面组件)
│  │  ├─ views/           (页面)
│  │  ├─ api/             (API调用)
│  │  ├─ stores/          (Pinia状态)
│  │  ├─ router/          (路由)
│  │  └─ main.ts          (入口)
│  └─ package.json
│
├─ app/                   (后端项目)
│  ├─ main.py             (启动入口)
│  ├─ routers/            (路由)
│  ├─ services/           (业务逻辑)
│  ├─ models/             (数据模型)
│  ├─ schemas/            (Pydantic schema)
│  ├─ core/               (核心配置)
│  ├─ middleware/         (中间件)
│  └─ utils/              (工具函数)
│
├─ tradingagents/         (AI Agent系统)
│  ├─ agents/             (Agent定义)
│  ├─ workflows/          (工作流)
│  ├─ tools/              (工具)
│  └─ utils/              (工具函数)
│
├─ docker/                (Docker配置)
├─ config/                (配置文件)
├─ docs/                  (文档)
├─ requirements.txt       (Python依赖)
└─ README.md

```

---

## 💾 核心数据模型

### 用户 (User)

```
{
  _id: ObjectId,
  username: string,
  email: string,
  hashed_password: string,
  is_active: boolean,
  is_admin: boolean,
  created_at: datetime,
  last_login: datetime,
  preferences: {
    default_market: string,
    ui_theme: string,
    ...
  },
  daily_quota: number,
  total_analyses: number
}
```

### 分析报告 (AnalysisReport)

```
{
  _id: ObjectId,
  task_id: string,
  user_id: ObjectId,
  symbol: string,
  status: string,  // "pending", "running", "completed", "failed"
  created_at: datetime,
  completed_at: datetime,
  
  analysis_result: {
    fundamental_score: float,      // 基本面评分
    technical_score: float,        // 技术面评分
    news_score: float,             // 新闻面评分
    sentiment_score: float,        // 情绪面评分
    overall_recommendation: string,// "STRONG_BUY", "BUY", "NEUTRAL", "SELL"
    confidence: float,             // 信心度
    
    detailed_reports: [
      { agent_name, analysis, score },
      ...
    ],
    
    discussion: string,            // Agents讨论过程
  },
  
  tokens_used: number,           // 消耗的token数
  cost: float                    // 成本
}
```

### 任务 (Task)

```
{
  _id: ObjectId,
  task_id: string,
  user_id: ObjectId,
  task_type: string,     // "analysis", "screening", etc
  status: string,        // "pending", "running", "completed", "failed"
  progress: float,       // 0-100%
  created_at: datetime,
  started_at: datetime,
  completed_at: datetime,
  
  parameters: {...},     // 任务参数
  result: {...},         // 任务结果
  error: string          // 错误信息（如有）
}
```

---

## 🔐 认证与授权

### JWT Token 流程

```
登录请求
    ↓
后端验证用户名密码
    ↓
生成 JWT Token (包含用户ID, 权限等)
    ↓
返回 Token 给前端
    ↓
前端保存 Token (localStorage)
    ↓
后续请求都在 Header 中发送 Token
    Authorization: Bearer <token>
    ↓
后端验证 Token 的有效性
    ↓
验证通过 → 继续处理请求
验证失败 → 返回 401 Unauthorized
    ↓
Token 过期时
    → 调用刷新接口获取新 Token
    → 或返回 401，前端跳转登录页
```

### 权限控制

```
系统有两种用户角色：

普通用户 (User)
├─ 分析自己的股票
├─ 使用有配额限制
└─ 不能管理系统

管理员 (Admin)
├─ 完全访问权限
├─ 无配额限制
├─ 可以管理用户
└─ 可以查看系统统计
```

---

## 📊 性能指标

### 关键指标

| 指标 | 目标 | 当前 |
|------|------|------|
| API响应时间 | < 200ms | ~150ms |
| 分析耗时 | < 60s | ~45s |
| 并发用户数 | 100+ | 可扩展 |
| 数据库查询 | < 50ms | ~30ms |
| WebSocket延迟 | < 100ms | ~50ms |

### 扩展性

```
横向扩展 (增加服务器)
├─ 部署多个 FastAPI 实例
├─ 使用负载均衡
└─ 共享 MongoDB 和 Redis

纵向扩展 (增加单机性能)
├─ 增加服务器内存
├─ 增加CPU核心
└─ 优化数据库索引

任务队列扩展
├─ 启动多个 Worker 处理任务
├─ 自动扩缩容
└─ 任务优先级管理
```

---

## 🚀 快速对比

### 了解核心技术

| 技术 | 用途 | 学习曲线 |
|------|------|---------|
| **Vue 3** | 前端框架 | ⭐⭐ 简单 |
| **FastAPI** | 后端框架 | ⭐⭐ 简单 |
| **MongoDB** | 数据库 | ⭐⭐ 简单 |
| **Redis** | 缓存/队列 | ⭐⭐⭐ 中等 |
| **LangGraph** | Agent编排 | ⭐⭐⭐⭐ 复杂 |
| **异步编程** | 并发处理 | ⭐⭐⭐ 中等 |

---

## 📈 系统容量规划

### 单台服务器可以支持：

```
✅ 100+ 并发用户
✅ 1000+ 每日分析请求
✅ 50,000+ 用户账户
✅ 100GB+ 数据存储
```

### 需要扩展时：

```
添加更多 FastAPI 实例
    ↓ (通过容器编排)
    ↓
添加数据库副本集
    ↓ (MongoDB Replica Set)
    ↓
添加 Redis 集群
    ↓ (Redis Cluster)
    ↓
添加 CDN (加速静态资源)
```

---

## 📚 接下来读什么？

根据你的角色选择：

### 👨‍💻 后端工程师
```
下一步：03_BACKEND_DEVELOPMENT_GUIDE.md
内容：FastAPI, 异步编程, 数据库
时间：90分钟
```

### 👨‍🎨 前端工程师
```
下一步：04_FRONTEND_ARCHITECTURE.md
内容：Vue3, 路由, 状态管理
时间：60分钟
```

### 🧠 AI工程师
```
下一步：05_MULTI_AGENT_FRAMEWORK.md
内容：Agent系统, LLM集成, 工作流
时间：60分钟
```

### 🚀 全栈工程师
```
下一步：03_BACKEND_DEVELOPMENT_GUIDE.md
然后：04_FRONTEND_ARCHITECTURE.md
然后：05_MULTI_AGENT_FRAMEWORK.md
时间：总计 4.5小时
```

---

**现在你已经对整个系统有了清晰认识！选择下一份文档继续深入学习。** 🎯

