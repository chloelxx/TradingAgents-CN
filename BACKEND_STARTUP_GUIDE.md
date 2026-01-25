# TradingAgents-CN 后端启动完整指南

## 📋 快速启动（3步）

### 1️⃣ 准备环境

**第一次启动时，需要进行以下准备：**

#### A. 创建虚拟环境（如果还没有）

```bash
# 在项目根目录运行
python -m venv .venv

# 激活虚拟环境
.venv\Scripts\activate  # Windows PowerShell

# 或在cmd中使用
.venv\Scripts\activate.bat  # Windows CMD
```

#### B. 安装依赖包

```bash
pip install -r requirements.txt
```

#### C. 配置环境变量

```bash
# 复制示例配置文件
copy .env.example .env

# 编辑 .env 文件，填入你的API密钥和数据库信息
# 关键配置项：
# - MONGODB_HOST: MongoDB服务器地址 (默认: localhost)
# - MONGODB_PORT: MongoDB服务器端口 (默认: 27017)
# - REDIS_HOST: Redis服务器地址 (默认: localhost)
# - REDIS_PORT: Redis服务器端口 (默认: 6379)
# - 各种API密钥 (Tushare, AKShare等)
```

### 2️⃣ 启动数据库和缓存服务

**后端依赖MongoDB和Redis，需要先启动：**

#### 启动MongoDB（新终端窗口）

```bash
# 假设MongoDB已安装
mongod

# 如果已配置MongoDB服务，也可以启动服务
# Windows: services.msc 找到MongoDB服务并启动
```

#### 启动Redis（新终端窗口）

```bash
# 假设Redis已安装
redis-server

# 如果已配置Redis服务，也可以启动服务
# Windows: services.msc 找到Redis服务并启动
```

**验证服务是否运行：**

```bash
# 验证MongoDB
mongosh
# 或
mongo

# 验证Redis
redis-cli
# 输入 PING，应返回 PONG
```

### 3️⃣ 启动后端服务

**在项目根目录运行以下命令：**

#### 方式A: 使用启动脚本（推荐）

```bash
# PowerShell中运行
.\start_backend.ps1

# 如果提示执行策略限制，先运行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 方式B: 直接使用uvicorn启动

```bash
# 激活虚拟环境（如果未激活）
.venv\Scripts\activate

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 方式C: 使用Python直接启动

```bash
# 在项目根目录
python -m app.main
```

---

## ✅ 验证后端是否启动成功

### 检查1: 查看启动日志

后端启动成功应该看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 检查2: 访问API文档

打开浏览器，访问：

- **Swagger API文档**: <http://localhost:8000/docs>
- **ReDoc API文档**: <http://localhost:8000/redoc>

如果能看到API文档页面，说明后端启动成功！

### 检查3: 测试API连接

```bash
# 新开一个终端，测试健康检查端点
curl http://localhost:8000/health

# 或在PowerShell中
Invoke-WebRequest -Uri http://localhost:8000/health
```

---

## 🔄 前后端联合启动

### 启动步骤（需要3个终端窗口）

**终端1: 启动MongoDB**

```bash
mongod
```

**终端2: 启动Redis**

```bash
redis-server
```

**终端3: 启动FastAPI后端**

```bash
cd e:\TradingAgents-CN
.venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**终端4: 启动前端（可选，如需测试前后端交互）**

```bash
cd e:\TradingAgents-CN\frontend
npm run dev
```

### 完成后的访问地址

| 服务 | URL | 描述 |
|-----|-----|------|
| 后端API | <http://localhost:8000> | FastAPI服务器 |
| API文档 | <http://localhost:8000/docs> | Swagger文档 |
| 前端应用 | <http://localhost:5173> | Vue3 + Vite应用（如启动了） |

---

## 📋 后端主要API端点

### 核心分析

- `POST /api/analysis/single` - 单股分析
- `POST /api/analysis/batch` - 批量分析
- `GET /api/analysis/history` - 分析历史
- `GET /api/queue/task/{task_id}` - 查询任务状态

### 认证

- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户

### 股票数据

- `GET /api/stocks/list` - 股票列表
- `GET /api/stocks/search` - 股票搜索
- `GET /api/stocks/{symbol}` - 股票详情

### 实时通信

- `WebSocket /ws/notifications` - WebSocket连接（实时进度更新）
- `GET /api/queue/progress/{task_id}` - SSE进度推送

---

## 🐛 常见问题和解决方案

### 问题1: `ModuleNotFoundError: No module named 'app'`

**原因**: Python路径配置不正确

**解决方案**:

```bash
# 确保在项目根目录运行
cd e:\TradingAgents-CN

# 检查当前目录
pwd  # 应该显示 e:\TradingAgents-CN

# 重新启动
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 问题2: `Connection refused` MongoDB错误

**原因**: MongoDB服务未启动

**解决方案**:

```bash
# 启动MongoDB
mongod

# 或检查MongoDB状态
mongosh admin --eval "db.adminCommand('ping')"

# 如果未安装MongoDB，访问官网下载：https://www.mongodb.com/try/download/community
```

### 问题3: `Connection refused` Redis错误

**原因**: Redis服务未启动

**解决方案**:

```bash
# 启动Redis
redis-server

# 或检查Redis状态
redis-cli ping

# 如果未安装Redis，访问官网下载：https://redis.io/download
```

### 问题4: 端口8000已被占用

**原因**: 端口被其他程序占用

**解决方案**:

```bash
# 方案A: 使用其他端口
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# 方案B: 查找占用端口的进程并关闭
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### 问题5: 前端无法连接后端

**检查步骤**:

1. 后端是否启动: 访问 <http://localhost:8000/docs>
2. 防火墙是否阻止: 关闭防火墙或添加端口例外
3. 检查CORS配置: 查看 `app/main.py` 中的CORS设置
4. 检查前端配置: 前端API请求的URL是否正确

---

## 🔧 高级配置

### 修改监听地址和端口

```bash
# 监听所有网卡，端口8001
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# 仅本地监听
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 监听指定IP
python -m uvicorn app.main:app --host 192.168.1.100 --port 8000
```

### 生产环境启动（使用Gunicorn + Uvicorn）

```bash
# 安装gunicorn
pip install gunicorn

# 启动多worker（生产推荐）
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

### 启用日志记录

```bash
# 不同日志级别
python -m uvicorn app.main:app --log-level debug   # 调试信息
python -m uvicorn app.main:app --log-level info    # 信息（默认）
python -m uvicorn app.main:app --log-level warning # 警告
```

### 禁用自动重加载（生产环境）

```bash
# 不使用 --reload 参数即可
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 📊 系统要求

| 组件 | 最低版本 | 推荐版本 |
|-----|---------|---------|
| Python | 3.10 | 3.11+ |
| MongoDB | 5.0 | 6.0+ |
| Redis | 6.0 | 7.0+ |
| pip | - | 23.0+ |

---

## 🚀 快速故障排除

```bash
# 1. 检查Python版本
python --version  # 应该 >= 3.10

# 2. 检查依赖
pip list | findstr fastapi
pip list | findstr uvicorn
pip list | findstr motor

# 3. 检查MongoDB连接
python -c "import motor.motor_asyncio; print('MongoDB驱动OK')"

# 4. 检查Redis连接
python -c "import redis; r=redis.Redis(); r.ping(); print('Redis连接OK')"

# 5. 验证app包可导入
python -c "from app.main import app; print('app包导入OK')"

# 6. 完整启动测试
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📚 相关文档

- [后端API完整文档](http://localhost:8000/docs) - 启动后端后访问
- [.env配置详解](../docs/configuration_guide.md)
- [系统架构概览](../frameworks/system_architecture_overview.md)
- [APP目录深度分析](../frameworks/app_directory_detailed_analysis.md)

---

## 💡 提示

✅ 对于本地开发，可以同时启动多个终端窗口  
✅ 使用 `--reload` 参数时，代码变更会自动重新加载  
✅ API文档 (`/docs`) 可以直接测试所有接口  
✅ 生产环境需要关闭 `--reload` 并配置日志  
✅ 前后端都需要启动才能完整测试应用  

祝你启动顺利！🎉
