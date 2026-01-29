# 🚀 部署与优化指南

**把应用上线和性能优化**

> 学会这些，你就能把项目部署到真实环境，让所有人使用。

---

## 📍 你在这里

```
学习进度：01 → 02 → 03 → 04 → 05 → 06 → 07(你在这)
              开始   架构  后端  前端  Agent 代码   部署
```

---

## 🎯 本文档包含

- ✅ 本地开发环境搭建
- ✅ Docker容器化部署
- ✅ 性能优化技巧
- ✅ 监控和调试
- ✅ 常见问题解决
- ✅ 生产环境最佳实践

---

## 🔧 本地开发环境搭建

### 前置要求

```bash
✅ Python 3.10+
✅ Node.js 18+
✅ MongoDB 5.0+
✅ Redis 6.0+
✅ Git
```

### 第1步：克隆项目

```bash
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN
```

### 第2步：配置后端

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境（Windows）
venv\Scripts\activate

# 激活虚拟环境（Linux/Mac）
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境配置
cp .env.example .env

# 编辑 .env，填入必要的配置
# - MONGODB_URI
# - REDIS_URL
# - API_KEYS (Tushare, AKShare等)
# - LLM配置 (OpenAI, 通义千问等)
```

### 第3步：启动数据库

```bash
# MongoDB (需要单独安装或用Docker)
mongod

# Redis (需要单独安装或用Docker)
redis-server
```

### 第4步：初始化数据库

```bash
# 创建管理员用户
python -c "
from app.services.user_service import user_service
import asyncio
asyncio.run(user_service.create_admin_user())
"

# 创建索引
# MongoDB会自动创建
```

### 第5步：启动后端服务

```bash
# 开发模式（有热重载）
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用提供的启动脚本
./start_backend.ps1  # Windows PowerShell
./start_backend.sh   # Linux/Mac
```

### 第6步：配置前端

```bash
cd frontend

# 安装依赖
npm install
# 或
yarn install

# 启动开发服务器
npm run dev
# 或
yarn dev

# 浏览器访问 http://localhost:5173
```

### 验证安装成功

```bash
# 检查后端API
curl http://localhost:8000/docs

# 检查前端应用
open http://localhost:5173  # Mac
start http://localhost:5173 # Windows
```

---

## 🐳 Docker容器化部署

### 为什么使用Docker？

```
✅ 环境一致性 (开发=测试=生产)
✅ 快速部署 (不需要安装依赖)
✅ 容易扩展 (多个容器)
✅ 方便管理 (docker-compose)
```

### Docker Compose 部署（推荐）

**文件：docker-compose.yml**

```yaml
version: '3.8'

services:
  # MongoDB 数据库
  mongodb:
    image: mongo:6.0
    container_name: tradingagents-mongodb
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: admin123
    volumes:
      - mongodb_data:/data/db
    restart: always

  # Redis 缓存
  redis:
    image: redis:7
    container_name: tradingagents-redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: always

  # 后端 FastAPI 服务
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: tradingagents-backend
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URI=mongodb://admin:admin123@mongodb:27017/TradingAgents
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=info
    depends_on:
      - mongodb
      - redis
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
    restart: always
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  # 前端 Vue 应用
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: tradingagents-frontend
    ports:
      - "80:80"
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
    depends_on:
      - backend
    restart: always

volumes:
  mongodb_data:
  redis_data:

networks:
  default:
    name: tradingagents-network
```

### 启动容器

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 删除所有数据（谨慎！）
docker-compose down -v
```

### 单独部署后端

```bash
# 构建镜像
docker build -f Dockerfile.backend -t tradingagents-backend .

# 运行容器
docker run -d \
  --name tradingagents-backend \
  -p 8000:8000 \
  -e MONGODB_URI=mongodb://... \
  -e REDIS_URL=redis://... \
  tradingagents-backend
```

---

## ⚡ 性能优化

### 1. 后端性能优化

#### 数据库优化

```python
# 添加适当的索引
from pymongo import MongoClient, ASCENDING, DESCENDING

client = MongoClient()
db = client['TradingAgents']

# 用户表索引
db.users.create_index([('username', ASCENDING)], unique=True)
db.users.create_index([('email', ASCENDING)], unique=True)
db.users.create_index([('created_at', DESCENDING)])

# 分析报告表索引
db.analysis_reports.create_index([('user_id', ASCENDING), ('created_at', DESCENDING)])
db.analysis_reports.create_index([('symbol', ASCENDING), ('created_at', DESCENDING)])
db.analysis_reports.create_index([('status', ASCENDING)])

# 分析历史表索引
db.analysis_history.create_index([('user_id', ASCENDING), ('created_at', DESCENDING)])
```

#### 查询优化

```python
# ❌ 不好的做法：N+1查询
users = db.users.find()
for user in users:
    reports = db.analysis_reports.find({'user_id': user['_id']})
    # 查询了很多次数据库！

# ✅ 好的做法：批量查询或聚合
pipeline = [
    {
        '$group': {
            '_id': '$user_id',
            'count': {'$sum': 1},
            'latest': {'$max': '$created_at'}
        }
    }
]
results = list(db.analysis_reports.aggregate(pipeline))
```

#### 缓存优化

```python
# 使用Redis缓存热门股票数据
from app.core.redis_client import redis_client

async def get_stock_data(symbol: str):
    # 先查Redis缓存
    cache_key = f"stock:{symbol}"
    cached_data = await redis_client.get(cache_key)
    
    if cached_data:
        return json.loads(cached_data)
    
    # 缓存没有，查数据库
    data = await fetch_from_api(symbol)
    
    # 存入Redis，设置1小时过期
    await redis_client.setex(cache_key, 3600, json.dumps(data))
    
    return data
```

#### 异步优化

```python
# ✅ 正确使用异步，提高并发
import asyncio
from fastapi import FastAPI

app = FastAPI()

# 使用异步任务而不是同步
@app.post("/api/analysis")
async def analyze(symbol: str):
    # 立即返回任务ID
    task_id = generate_task_id()
    
    # 在后台异步处理
    asyncio.create_task(process_analysis(symbol, task_id))
    
    return {"task_id": task_id, "status": "pending"}

# 而不是：
# @app.post("/api/analysis")
# def analyze(symbol: str):
#     # 这样会阻塞，导致响应慢
#     result = process_analysis_sync(symbol)
#     return result
```

### 2. 前端性能优化

#### 代码分割

```typescript
// router/index.ts
// ✅ 动态导入，只在需要时加载
const Dashboard = () => import('@/views/Dashboard/index.vue')
const Analysis = () => import('@/views/Analysis/index.vue')

// ❌ 不要这样做：
// import Dashboard from '@/views/Dashboard/index.vue'  // 全部加载
```

#### 懒加载图片

```vue
<template>
  <!-- ✅ 使用 v-lazy 指令 -->
  <img v-lazy="image.url" :alt="image.name" />
  
  <!-- ❌ 不要这样做 -->
  <img :src="image.url" :alt="image.name" />
</template>
```

#### 虚拟列表

```vue
<template>
  <!-- ✅ 对于大列表，使用虚拟滚动 -->
  <el-virtual-list
    :items="stocks"
    :height="500"
    :item-size="50"
  >
    <template #default="{ item }">
      <div>{{ item.name }}</div>
    </template>
  </el-virtual-list>
  
  <!-- ❌ 不要这样做：一次渲染10000个DOM -->
  <div v-for="stock in stocks" :key="stock.id">
    {{ stock.name }}
  </div>
</template>
```

#### 状态管理优化

```typescript
// ✅ 只订阅需要的状态
const store = useAppStore()
const sidebarWidth = computed(() => store.sidebarWidth)  // 自动更新

// ❌ 不要这样做：
// const appState = reactive(store.$state)  // 订阅整个state
```

### 3. 网络优化

#### API请求优化

```typescript
// ✅ 请求去重（防止重复请求）
const requestCache = new Map()

async function cachedFetch(url: string) {
  if (requestCache.has(url)) {
    return requestCache.get(url)
  }
  
  const promise = fetch(url)
  requestCache.set(url, promise)
  
  try {
    return await promise
  } finally {
    requestCache.delete(url)
  }
}
```

#### 批量API

```python
# ✅ 支持批量操作，减少请求数
@app.post("/api/stocks/batch-info")
async def batch_stock_info(symbols: list[str]):
    """
    一次请求获取多个股票信息
    而不是多个单独请求
    """
    results = {}
    for symbol in symbols:
        results[symbol] = await get_stock_data(symbol)
    return results
```

---

## 📊 监控和调试

### 日志管理

```python
# 配置日志
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

# 文件处理器
file_handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10485760,  # 10MB
    backupCount=10
)

# 格式化
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 使用日志
logger.info("应用启动")
logger.error("发生错误", exc_info=True)
```

### 性能监控

```python
# 使用APScheduler监控系统性能
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.redis_client import redis_client

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=5)
async def monitor_performance():
    """每5分钟检查一次系统性能"""
    
    # 检查MongoDB连接
    try:
        await db.command('ping')
        status = 'healthy'
    except:
        status = 'unhealthy'
    
    # 检查Redis连接
    redis_status = 'healthy' if await redis_client.ping() else 'unhealthy'
    
    # 记录到Redis
    await redis_client.hset('system:health', mapping={
        'mongodb': status,
        'redis': redis_status,
        'timestamp': datetime.now().isoformat()
    })
```

### 调试工具

```python
# 1. FastAPI 自带Swagger UI
# 访问：http://localhost:8000/docs

# 2. 使用 pdb 调试
import pdb

@app.post("/api/debug")
async def debug_endpoint():
    pdb.set_trace()  # 程序会暂停在这里
    return {"status": "ok"}

# 3. 使用 print 和日志
print("调试信息")
logger.debug("调试信息")
```

---

## 🔒 安全最佳实践

### 1. 环境变量管理

```bash
# ❌ 不要这样做
DB_PASSWORD = "admin123"  # 暴露在代码中！

# ✅ 这样做
# .env 文件
DB_PASSWORD=admin123
# .gitignore 中添加 .env

# Python代码
from dotenv import load_dotenv
import os

load_dotenv()
DB_PASSWORD = os.getenv('DB_PASSWORD')
```

### 2. API安全

```python
# ✅ 速率限制，防止暴力攻击
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(credentials: LoginForm):
    """每分钟最多5次登录尝试"""
    pass

# ✅ 输入验证
from pydantic import BaseModel, validator

class StockQuery(BaseModel):
    symbol: str
    
    @validator('symbol')
    def validate_symbol(cls, v):
        # 验证股票代码格式
        if not re.match(r'^\d{6}$', v):
            raise ValueError('Invalid stock symbol')
        return v
```

### 3. 数据加密

```python
# ✅ 密码加密
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

---

## 🚨 常见问题排查

### 问题1：连接超时错误

```
错误：mongodb.errors.ServerSelectionTimeoutError

解决：
1. 检查MongoDB是否运行：mongod
2. 检查连接字符串：mongodb://localhost:27017
3. 检查防火墙
```

### 问题2：API响应缓慢

```
问题排查步骤：
1. 检查数据库查询速度
   → 使用 explain() 查看执行计划
   
2. 检查是否有N+1查询
   → 添加日志，统计查询次数
   
3. 检查缓存是否有效
   → 验证Redis连接
   
4. 检查LLM调用速度
   → 查看LLM API延迟
```

### 问题3：内存溢出

```
解决方案：
1. 启用连接池
   from motor.motor_asyncio import AsyncMotorClient
   client = AsyncMotorClient(maxPoolSize=50)

2. 及时关闭连接
   await client.close()

3. 使用流式处理大数据
   async for doc in collection.find():
       process(doc)
```

### 问题4：任务队列堆积

```
症状：任务越来越多，响应变慢

解决方案：
1. 增加Worker数量
2. 优化单个任务处理时间
3. 添加任务优先级
4. 定期清理过期任务
```

---

## 📈 扩展性建议

### 当系统变慢时

```
第1步：定位瓶颈
├─ 监控CPU使用率
├─ 监控内存使用率
├─ 监控数据库慢查询
└─ 监控API响应时间

第2步：优化
├─ 添加数据库索引
├─ 增加Redis缓存
├─ 优化复杂查询
└─ 使用异步处理

第3步：扩展
├─ 增加服务器实例
├─ 使用负载均衡
├─ 配置数据库副本集
└─ 使用CDN加速

第4步：监控
├─ 定期检查性能指标
├─ 设置告警
└─ 记录详细日志
```

### 扩展到多服务器

```
单服务器 → 多服务器
           
原来：
┌──────────────┐
│  FastAPI     │
│  MongoDB     │
│  Redis       │
│  Frontend    │
└──────────────┘

扩展后：
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  FastAPI-1   │       │  FastAPI-2   │       │  FastAPI-3   │
└──────────────┘       └──────────────┘       └──────────────┘
       ↓                       ↓                       ↓
┌──────────────────────────────────────────────────────────┐
│              Nginx (负载均衡)                            │
└──────────────────────────────────────────────────────────┘
       ↓                       ↓
┌──────────────────┐   ┌──────────────────┐
│   MongoDB RS     │   │  Redis Cluster   │
│  (主从+仲裁)     │   │  (分片存储)      │
└──────────────────┘   └──────────────────┘
       ↓
┌──────────────────────────────────────────┐
│      S3 / CDN (静态资源)                  │
└──────────────────────────────────────────┘
```

---

## ✅ 部署清单

### 上线前检查

- [ ] 所有环境变量已配置
- [ ] 数据库备份已设置
- [ ] 日志系统已启用
- [ ] 监控告警已配置
- [ ] SSL/TLS证书已安装
- [ ] 防火墙规则已配置
- [ ] 备份策略已制定
- [ ] 灾难恢复方案已准备
- [ ] 性能测试已完成
- [ ] 安全审计已通过

### 定期维护

```
每日：
- [ ] 检查系统运行状态
- [ ] 检查错误日志
- [ ] 监控资源使用率

每周：
- [ ] 检查数据库大小
- [ ] 审查性能指标
- [ ] 备份数据库

每月：
- [ ] 清理过期数据
- [ ] 更新依赖包
- [ ] 安全补丁更新
- [ ] 容量规划审查

每年：
- [ ] 完整的安全审计
- [ ] 灾难恢复演练
- [ ] 架构优化审查
```

---

## 📚 参考资源

- FastAPI部署: https://fastapi.tiangolo.com/deployment/
- Docker官方文档: https://docs.docker.com/
- MongoDB生产指南: https://docs.mongodb.com/manual/administration/
- Redis最佳实践: https://redis.io/docs/management/
- Vue性能优化: https://vuejs.org/guide/best-practices/performance.html

---

**恭喜！你已经掌握了部署和优化的全部知识。现在可以把应用部署到真实环境了！** 🚀

