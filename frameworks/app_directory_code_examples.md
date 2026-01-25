# TradingAgents-CN `/app` 目录 - 实战代码示例与学习指南

## 📚 学习路线

```
初级 → 中级 → 高级 → 专家级
 ↓      ↓      ↓       ↓
了解   使用   扩展   优化
结构  框架   功能   性能
```

---

## 🎯 Part 1: 初级 - 理解核心结构

### 1.1 API请求流程（最简单）

#### 场景：获取用户的分析历史

**前端代码**（你不需要关心）

```typescript
// frontend/src/api/analysis.ts
async function getAnalysisHistory(userId: string) {
  const response = await fetch('/api/analysis/history', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
  return response.json()
}
```

**后端代码追踪**

1️⃣ **路由层** (`app/routers/analysis.py`)

```python
@router.get("/history")
async def get_analysis_history(
    user: dict = Depends(get_current_user)  # 自动验证用户
):
    """获取分析历史"""
    # 验证自动完成，直接拿到user对象
    user_id = user["id"]  # 从Token中提取
    
    # 调用服务层
    service = get_analysis_service()
    history = await service.get_user_history(user_id)
    
    return history  # 自动转为JSON响应
```

2️⃣ **服务层** (`app/services/analysis_service.py`)

```python
class AnalysisService:
    async def get_user_history(self, user_id: str) -> List[AnalysisTask]:
        """获取用户的分析历史"""
        # 从MongoDB查询
        db = get_mongo_db()
        tasks = await db["analysis_tasks"].find(
            {"user_id": ObjectId(user_id)},
            sort=[("created_at", -1)]  # 降序排列（最新优先）
        ).to_list(length=100)
        
        # 转换为Pydantic模型
        return [AnalysisTask(**task) for task in tasks]
```

3️⃣ **数据模型** (`app/models/analysis.py`)

```python
class AnalysisTask(BaseModel):
    """分析任务模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    task_id: str                        # 唯一任务ID
    user_id: PyObjectId                # 用户ID
    symbol: str                         # 股票代码
    status: AnalysisStatus              # 任务状态
    progress: int = 0                   # 进度 0-100
    result: Optional[AnalysisResult]    # 分析结果
    created_at: datetime                # 创建时间
    completed_at: Optional[datetime]    # 完成时间
```

4️⃣ **数据库** (`MongoDB`)

```json
// collection: analysis_tasks
{
  "_id": ObjectId("..."),
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": ObjectId("507f1f77bcf86cd799439011"),
  "symbol": "000001",
  "status": "completed",
  "progress": 100,
  "result": {
    "summary": "该股票呈上升趋势...",
    "recommendation": "持有",
    "confidence_score": 0.85
  },
  "created_at": ISODate("2024-01-15T10:30:00Z"),
  "completed_at": ISODate("2024-01-15T10:35:00Z")
}
```

**关键概念**

```
用户请求 → Router (入口) → Service (逻辑) → Model (数据结构) → Database (存储)
  ↑                                                                  ↓
  └──────────────────── 返回JSON响应 ──────────────────────────────┘
```

---

### 1.2 依赖注入模式（FastAPI特性）

```python
# 模式：使用 Depends() 进行依赖注入

from fastapi import Depends

# 定义依赖函数
async def get_current_user(token: str = Header(...)) -> dict:
    """从Token中提取用户信息"""
    user = auth_service.validate_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# 在路由中使用
@router.get("/my-data")
async def get_my_data(
    user: dict = Depends(get_current_user)  # ← 自动调用get_current_user()
):
    """获取当前用户的数据"""
    # user 自动包含当前用户信息
    return {"user_id": user["id"], "username": user["username"]}
```

**好处**

- ✅ 代码复用（多个路由可用同一依赖）
- ✅ 测试友好（可以Mock依赖）
- ✅ 自动验证（依赖失败时自动返回401）

---

## 🎯 Part 2: 中级 - 实现新功能

### 2.1 添加新API端点

#### 场景：添加"我的收藏"API

**步骤1：创建数据模型** (`app/models/favorite.py`)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.user import PyObjectId

class Favorite(BaseModel):
    """收藏模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId        # 用户ID
    symbol: str                # 股票代码
    stock_name: str            # 股票名称
    created_at: datetime = Field(default_factory=now_tz)
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "symbol": "000001",
                "stock_name": "平安银行"
            }
        }
    )
```

**步骤2：创建服务** (`app/services/favorites_service.py`)

```python
from app.core.database import get_mongo_db
from bson import ObjectId

class FavoritesService:
    """收藏服务"""
    
    async def add_favorite(self, user_id: str, symbol: str, stock_name: str):
        """添加到收藏"""
        db = get_mongo_db()
        
        # 检查是否已收藏
        existing = await db["favorites"].find_one({
            "user_id": ObjectId(user_id),
            "symbol": symbol
        })
        
        if existing:
            raise ValueError(f"股票 {symbol} 已在收藏中")
        
        # 插入新收藏
        result = await db["favorites"].insert_one({
            "user_id": ObjectId(user_id),
            "symbol": symbol,
            "stock_name": stock_name,
            "created_at": datetime.now(timezone.utc)
        })
        
        return str(result.inserted_id)
    
    async def get_my_favorites(self, user_id: str) -> List[Favorite]:
        """获取用户的所有收藏"""
        db = get_mongo_db()
        
        favorites = await db["favorites"].find({
            "user_id": ObjectId(user_id)
        }).to_list(length=None)
        
        return [Favorite(**fav) for fav in favorites]
    
    async def remove_favorite(self, user_id: str, symbol: str) -> bool:
        """删除收藏"""
        db = get_mongo_db()
        
        result = await db["favorites"].delete_one({
            "user_id": ObjectId(user_id),
            "symbol": symbol
        })
        
        return result.deleted_count > 0

# 单例实例
_favorites_service = None

def get_favorites_service() -> FavoritesService:
    """获取服务单例"""
    global _favorites_service
    if _favorites_service is None:
        _favorites_service = FavoritesService()
    return _favorites_service
```

**步骤3：创建路由** (`app/routers/favorites.py`)

```python
from fastapi import APIRouter, Depends, HTTPException
from app.routers.auth_db import get_current_user
from app.services.favorites_service import get_favorites_service
from app.models.favorite import Favorite

router = APIRouter(prefix="/api/favorites", tags=["favorites"])

@router.post("/add")
async def add_favorite(
    symbol: str,
    stock_name: str,
    user: dict = Depends(get_current_user)
):
    """添加收藏"""
    try:
        service = get_favorites_service()
        favorite_id = await service.add_favorite(
            user["id"], symbol, stock_name
        )
        return {"success": True, "favorite_id": favorite_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/list")
async def get_favorites(user: dict = Depends(get_current_user)):
    """获取我的收藏列表"""
    service = get_favorites_service()
    favorites = await service.get_my_favorites(user["id"])
    return favorites

@router.delete("/{symbol}")
async def remove_favorite(
    symbol: str,
    user: dict = Depends(get_current_user)
):
    """删除收藏"""
    service = get_favorites_service()
    success = await service.remove_favorite(user["id"], symbol)
    
    if not success:
        raise HTTPException(status_code=404, detail="收藏不存在")
    
    return {"success": True}
```

**步骤4：在main.py中注册**

```python
# app/main.py
from app.routers import favorites

# 在app创建后添加
app.include_router(favorites.router, tags=["favorites"])
```

**完成！现在你有了以下API端点**

```
POST   /api/favorites/add         # 添加收藏
GET    /api/favorites/list        # 获取收藏列表
DELETE /api/favorites/{symbol}    # 删除收藏
```

---

### 2.2 处理异步操作

#### 场景：后台同步股票数据（耗时操作）

```python
# app/routers/stocks.py
from fastapi import BackgroundTasks

@router.post("/sync-data")
async def sync_stock_data(
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """同步股票数据（后台执行）"""
    
    # 关键：立即返回，不等待执行完成
    background_tasks.add_task(
        run_sync,  # 函数名
        "000001",  # 参数
        "Tushare"  # 参数
    )
    
    return {
        "message": "同步已启动，请稍候...",
        "status": "processing"
    }

async def run_sync(symbol: str, source: str):
    """后台同步函数"""
    try:
        print(f"开始同步 {symbol} 数据 (来源: {source})")
        
        # 耗时的I/O操作
        service = get_stock_data_service()
        data = await service.fetch_from_source(symbol, source)
        
        # 保存到数据库
        db = get_mongo_db()
        await db["stock_data"].insert_one(data)
        
        print(f"同步完成: {symbol}")
    except Exception as e:
        print(f"同步失败: {e}")
        # 可以记录错误到日志或通知用户
```

**关键点**

```
用户请求
  ↓
立即返回响应 (不等待)
  ↓
后台任务开始执行
  ├─ 获取数据 (I/O)
  ├─ 处理数据 (CPU)
  └─ 保存结果 (I/O)
  
用户已收到响应，不需要等待
```

---

### 2.3 处理长时间运行任务 + 实时进度

#### 场景：执行分析任务，实时推送进度

```python
# app/routers/analysis.py
from fastapi import WebSocket

@router.websocket("/ws/analysis/{task_id}")
async def websocket_analysis_progress(
    websocket: WebSocket,
    task_id: str
):
    """WebSocket连接：接收分析进度更新"""
    
    await websocket.accept()
    print(f"Client connected: {task_id}")
    
    try:
        # 定期推送进度
        while True:
            # 从Redis获取最新进度
            progress_data = await redis_client.hgetall(
                f"qa:progress:{task_id}"
            )
            
            # 发送给客户端
            await websocket.send_json({
                "task_id": task_id,
                "progress": int(progress_data.get("progress", 0)),
                "message": progress_data.get("message", ""),
                "status": progress_data.get("status", "processing")
            })
            
            # 每秒检查一次
            await asyncio.sleep(1)
            
            # 如果完成，退出循环
            if progress_data.get("status") in ["completed", "failed"]:
                break
    
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()
        print(f"Client disconnected: {task_id}")


# 后台任务中更新进度
async def run_analysis_task(task_id: str):
    """后台分析任务"""
    
    try:
        # Step 1: 市场分析
        await update_progress(task_id, 20, "正在执行市场分析...")
        market_result = await market_analyst.analyze()
        
        # Step 2: 基本面分析
        await update_progress(task_id, 40, "正在执行基本面分析...")
        fundamental_result = await fundamental_analyst.analyze()
        
        # Step 3: 新闻分析
        await update_progress(task_id, 60, "正在执行新闻分析...")
        news_result = await news_analyst.analyze()
        
        # Step 4: 综合
        await update_progress(task_id, 80, "正在生成综合分析...")
        final_result = await synthesize_results(
            market_result, fundamental_result, news_result
        )
        
        # Step 5: 保存结果
        await update_progress(task_id, 100, "分析完成！", "completed")
        
        db = get_mongo_db()
        await db["analysis_tasks"].update_one(
            {"task_id": task_id},
            {"$set": {"result": final_result, "status": "completed"}}
        )
    
    except Exception as e:
        await update_progress(task_id, 0, str(e), "failed")

async def update_progress(
    task_id: str,
    progress: int,
    message: str,
    status: str = "processing"
):
    """更新进度（写入Redis，WebSocket读取）"""
    
    redis = get_redis_client()
    await redis.hset(f"qa:progress:{task_id}", mapping={
        "progress": progress,
        "message": message,
        "status": status,
        "updated_at": datetime.now().isoformat()
    })
    
    print(f"Task {task_id}: {progress}% - {message}")
```

**前端代码** (Vue3)

```typescript
// frontend/src/components/AnalysisProgress.vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const progress = ref(0)
const message = ref('')
const taskId = ref('550e8400-e29b-41d4-a716-446655440000')

let ws: WebSocket | null = null

onMounted(() => {
  // 连接WebSocket
  ws = new WebSocket(`/api/analysis/ws/analysis/${taskId.value}`)
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    progress.value = data.progress
    message.value = data.message
    
    if (data.status === 'completed') {
      alert('分析完成！')
    }
  }
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
})
</script>

<template>
  <div>
    <p>{{ message }}</p>
    <progress :value="progress" max="100"></progress>
    <span>{{ progress }}%</span>
  </div>
</template>
```

---

## 🎯 Part 3: 高级 - 扩展框架

### 3.1 添加新的数据源

#### 场景：添加东方财富（东财）作为新的股票数据源

**步骤1：创建同步服务** (`app/services/data_sources/eastmoney_sync_service.py`)

```python
import aiohttp
import logging

logger = logging.getLogger(__name__)

class EastmoneySyncService:
    """东财数据源同步服务"""
    
    API_BASE = "https://api.eastmoney.com/qt/v1"
    
    async def fetch_stock_basics(self, limit: int = 5000) -> List[dict]:
        """获取股票列表"""
        
        try:
            async with aiohttp.ClientSession() as session:
                # 构建请求URL
                url = f"{self.API_BASE}/stock/list"
                params = {
                    "limit": limit,
                    "offset": 0,
                    "type": "cn"
                }
                
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"东财API返回错误: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    # 数据转换为统一格式
                    stocks = []
                    for item in data.get("result", []):
                        stocks.append({
                            "symbol": item["code"],      # 6位代码
                            "full_symbol": item["code"] + "." + item["market"],
                            "name": item["name"],
                            "industry": item.get("industryName", ""),
                            "area": item.get("areaName", ""),
                            "list_date": item.get("listDate", ""),
                            "market_value": item.get("marketValue", None),
                            "source": "eastmoney",
                            "updated_at": datetime.now(timezone.utc)
                        })
                    
                    logger.info(f"获取 {len(stocks)} 条东财股票数据")
                    return stocks
        
        except aiohttp.ClientError as e:
            logger.error(f"东财API请求失败: {e}")
            return []
        except Exception as e:
            logger.error(f"东财数据处理失败: {e}")
            return []

# 工厂函数
async def get_eastmoney_stocks() -> List[dict]:
    """获取东财股票数据"""
    service = EastmoneySyncService()
    return await service.fetch_stock_basics()
```

**步骤2：在多源同步中注册** (`app/services/multi_source_basics_sync_service.py`)

```python
from app.services.data_sources.eastmoney_sync_service import get_eastmoney_stocks

class MultiSourceBasicsSyncService:
    """多源数据同步"""
    
    async def sync_all_sources(self):
        """从所有数据源同步"""
        
        results = {}
        
        # 并行执行所有源
        try:
            tushare_result, akshare_result, baostock_result, eastmoney_result = await asyncio.gather(
                get_tushare_stocks(),
                get_akshare_stocks(),
                get_baostock_stocks(),
                get_eastmoney_stocks()  # ← 新增
            )
            
            results["tushare"] = tushare_result or []
            results["akshare"] = akshare_result or []
            results["baostock"] = baostock_result or []
            results["eastmoney"] = eastmoney_result or []  # ← 新增
        
        except Exception as e:
            logger.error(f"并行同步失败: {e}")
        
        # 合并结果
        merged = self._merge_sources(results)
        return merged
```

**步骤3：创建API路由** (`app/routers/eastmoney_init.py`)

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/eastmoney-init", tags=["eastmoney"])

@router.post("/sync_basics")
async def sync_eastmoney_basics(
    user: dict = Depends(get_current_user)
):
    """同步东财股票基础数据"""
    
    try:
        service = EastmoneySyncService()
        stocks = await service.fetch_stock_basics()
        
        # 保存到MongoDB
        db = get_mongo_db()
        if stocks:
            await db["stock_basic_info"].insert_many(stocks)
        
        return {
            "success": True,
            "message": f"同步 {len(stocks)} 条东财数据",
            "count": len(stocks)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**步骤4：在main.py注册**

```python
# app/main.py
from app.routers import eastmoney_init

app.include_router(eastmoney_init.router, tags=["eastmoney"])
```

**完成！现在系统支持4个数据源**

```
数据源优先级：
1. Tushare
2. AKShare
3. BaoStock
4. 东财 (新增)
```

---

### 3.2 添加新的分析Agent

#### 场景：添加"估值分析Agent"

**在 tradingagents 目录中**

```python
# tradingagents/agents/valuation_analyst.py

from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

class ValuationAnalystAgent:
    """估值分析Agent"""
    
    def __init__(self, llm):
        self.llm = llm
        self.prompt = PromptTemplate(
            input_variables=["symbol", "financial_data", "market_data"],
            template="""
            根据以下数据分析股票 {symbol} 的估值：
            
            财务数据：{financial_data}
            市场数据：{market_data}
            
            请分析：
            1. PE估值水平（相对于行业平均）
            2. PB估值水平
            3. 分红收益率
            4. 主要估值指标对比
            
            输出格式：JSON
            """
        )
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    def analyze(self, symbol: str, financial_data: dict, market_data: dict):
        """执行估值分析"""
        return self.chain.invoke({
            "symbol": symbol,
            "financial_data": financial_data,
            "market_data": market_data
        })
```

**在 trading_graph.py 中注册**

```python
# tradingagents/graph/trading_graph.py

from tradingagents.agents.valuation_analyst import ValuationAnalystAgent

class TradingAgentsGraph:
    def __init__(self, ...):
        # ... 其他初始化
        
        # 注册新Agent
        self.graph.add_node(
            "ValuationAnalyst",
            ValuationAnalystAgent(self.llm)
        )
        
        # 添加边（流程）
        self.graph.add_edge("DataFetcher", "ValuationAnalyst")
        self.graph.add_edge("ValuationAnalyst", "ConsumerAgent")
```

**在 app 层使用**（无需修改app代码！）

```python
# app/services/analysis_service.py

# 用户选择了"估值"分析
config = {
    "selected_analysts": [
        "market",
        "fundamentals", 
        "valuation",        # ← 新Agent
        "news"
    ]
}

# TradingAgentsGraph会自动调用新Agent
trading_graph = TradingAgentsGraph(config=config)
result = await trading_graph.run(symbol)  # 自动包含估值分析
```

---

## 🎯 Part 4: 专家级 - 性能优化

### 4.1 使用缓存减少数据库查询

```python
# app/services/stock_data_service.py
from functools import lru_cache
from app.core.redis_client import get_redis_client
import json

class StockDataService:
    """股票数据服务（带缓存）"""
    
    CACHE_TTL = 3600  # 1小时缓存
    
    async def get_stock_info(self, symbol: str) -> dict:
        """获取股票信息（带缓存）"""
        
        redis = get_redis_client()
        cache_key = f"stock:info:{symbol}"
        
        # 1. 尝试从Redis缓存获取
        cached = await redis.get(cache_key)
        if cached:
            logger.info(f"缓存命中: {symbol}")
            return json.loads(cached)
        
        # 2. 从数据库查询
        logger.info(f"缓存未命中，查询数据库: {symbol}")
        db = get_mongo_db()
        stock = await db["stock_basic_info"].find_one({
            "symbol": symbol
        })
        
        if not stock:
            raise ValueError(f"股票 {symbol} 不存在")
        
        # 3. 保存到缓存
        await redis.set(
            cache_key,
            json.dumps(stock, default=str),  # ObjectId转字符串
            ex=self.CACHE_TTL
        )
        
        return stock
    
    async def get_stock_quotes_batch(self, symbols: List[str]) -> dict:
        """批量获取股票行情（并行查询）"""
        
        # 使用 asyncio.gather 并行查询
        tasks = [
            self.get_stock_quotes(symbol)
            for symbol in symbols
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            symbol: result
            for symbol, result in zip(symbols, results)
            if not isinstance(result, Exception)
        }

# 使用
service = StockDataService()
# 单个查询（带缓存）
info = await service.get_stock_info("000001")

# 批量查询（并行）
infos = await service.get_stock_quotes_batch(
    ["000001", "000002", "000003"]
)
```

### 4.2 数据库索引优化

```python
# app/core/database.py
from motor.motor_asyncio import AsyncIOMotorDatabase

async def init_db():
    """初始化数据库索引"""
    
    db = get_mongo_db()
    
    # 分析任务表索引
    await db["analysis_tasks"].create_index([("user_id", 1)])
    await db["analysis_tasks"].create_index([("created_at", -1)])
    await db["analysis_tasks"].create_index([("status", 1)])
    await db["analysis_tasks"].create_index([
        ("user_id", 1),
        ("created_at", -1)
    ])  # 复合索引
    
    # 股票数据表索引
    await db["stock_basic_info"].create_index([("symbol", 1)])
    await db["stock_basic_info"].create_index([("name", 1)])
    await db["stock_basic_info"].create_index([("industry", 1)])
    
    # 行情数据表索引
    await db["quotes"].create_index([("symbol", 1)])
    await db["quotes"].create_index([("timestamp", -1)])
    await db["quotes"].create_index([
        ("symbol", 1),
        ("timestamp", -1)
    ])
    
    logger.info("数据库索引创建完成")
```

### 4.3 并发限制与线程池

```python
# app/services/analysis_service.py
from concurrent.futures import ThreadPoolExecutor
import asyncio

class AnalysisService:
    def __init__(self):
        # CPU密集操作用ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def execute_analysis_with_concurrency_control(
        self,
        task_id: str,
        user_id: str,
        symbol: str
    ):
        """带并发控制的分析执行"""
        
        # 1. 检查并发限制
        queue_service = get_queue_service()
        
        # 用户并发检查
        user_concurrent = await queue_service._check_user_concurrent_limit(user_id)
        if not user_concurrent:
            raise ValueError(f"用户 {user_id} 达到并发限制 (最多5个)")
        
        # 全局并发检查
        global_concurrent = await queue_service._check_global_concurrent_limit()
        if not global_concurrent:
            raise ValueError(f"系统达到全局并发限制 (最多20个)")
        
        # 2. 标记为处理中
        await queue_service._mark_task_processing(
            task_id, user_id, worker_id="worker-1"
        )
        
        try:
            # 3. 执行分析
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._sync_analysis,  # CPU密集操作
                symbol
            )
            
            # 4. 解除并发计数
            await queue_service._unmark_task_processing(user_id)
            
            return result
        
        except Exception as e:
            await queue_service._unmark_task_processing(user_id)
            raise
    
    def _sync_analysis(self, symbol: str) -> dict:
        """同步分析（运行在线程池中）"""
        # CPU密集操作
        trading_graph = self._get_trading_graph({})
        return trading_graph.run(symbol)
```

---

## 📊 性能对比

```
优化前 vs 优化后

查询股票信息：
  ❌ 每次查询都访问数据库
  ✅ 第一次查询数据库，后续使用缓存
  性能提升: 10-100倍 (depending on query frequency)

批量查询：
  ❌ 顺序查询10个股票: T × 10
  ✅ 并行查询10个股票: T × 1
  性能提升: 10倍

并发控制：
  ❌ 无限并发导致系统崩溃
  ✅ 限制用户5个、全局20个任务
  系统稳定性: ⬆️ 显著提升
```

---

## 🔍 调试技巧

### 1. 查看日志

```bash
# 查看fastapi日志
tail -f logs/webapi.log

# 查看worker日志
tail -f logs/worker.log

# 查看错误堆栈
cat logs/webapi.log | grep -A 10 "ERROR"
```

### 2. 使用Swagger调试API

```
访问: http://localhost:8000/docs
- 可视化API浏览器
- 直接测试API
- 查看请求/响应示例
```

### 3. 数据库查询调试

```python
# 在服务中添加日志
logger.info(f"执行查询: user_id={user_id}, symbol={symbol}")
result = await db["analysis_tasks"].find_one(...)
logger.info(f"查询结果: {result}")
```

### 4. Redis调试

```bash
# 连接Redis
redis-cli

# 查看所有键
keys *

# 查看特定键
hgetall qa:task:550e8400-e29b-41d4-a716-446655440000

# 查看过期时间
ttl qa:progress:550e8400-e29b-41d4-a716-446655440000
```

---

## 📝 总结

### 学习路线总结

| 级别 | 重点 | 实践项目 | 时间 |
|-----|------|---------|------|
| 初级 | 理解架构、API调用流程 | 查询分析历史 | 1-2天 |
| 中级 | 实现新功能、异步处理 | 添加收藏功能、实时进度 | 3-5天 |
| 高级 | 扩展框架、添加Agent | 新增数据源、新Agent | 5-7天 |
| 专家 | 性能优化、系统设计 | 缓存、索引、并发控制 | 7-10天 |

### 核心概念梳理

```
Router (入口)
  ↓ (接收请求)
Service (逻辑)
  ↓ (业务处理)
Model (定义)
  ↓ (数据结构)
Database (存储)
  ↓ (持久化)
Response (返回)
```

### 关键技术

- ✅ **FastAPI** - 现代Web框架
- ✅ **MongoDB** - 文档数据库
- ✅ **Redis** - 缓存和队列
- ✅ **AsyncIO** - 异步编程
- ✅ **Pydantic** - 数据验证
- ✅ **LangGraph** - 多智能体框架

---

## 🚀 下一步

1. **本地运行** - 克隆项目，搭建环境
2. **查看示例** - 阅读现有代码（analysis.py, queue_service.py）
3. **实现功能** - 按照步骤添加新功能
4. **部署上线** - Docker容器化部署

祝你成为TradingAgents-CN的贡献者！🎉
