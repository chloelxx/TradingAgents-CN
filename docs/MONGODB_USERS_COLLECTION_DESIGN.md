# MongoDB Users Collection 设计文档

## 📋 集合概述

**集合名称**: `users`  
**用途**: 存储系统用户账号、认证信息和用户偏好设置  
**数据库**: TradingAgents-CN 项目MongoDB数据库  

---

## 🗂️ 集合结构详设

### 文档结构（Document Schema）

```javascript
{
  _id: ObjectId,                    // MongoDB自动生成的唯一标识符
  
  // ========== 基础身份信息 ==========
  username: String,                 // 用户名（唯一，必填）
  email: String,                    // 邮箱地址（唯一，必填）
  hashed_password: String,          // 密码哈希值（SHA-256）
  
  // ========== 账户状态 ==========
  is_active: Boolean,               // 是否激活 (default: true)
  is_verified: Boolean,             // 是否验证邮箱 (default: false)
  is_admin: Boolean,                // 是否管理员 (default: false)
  
  // ========== 时间戳 ==========
  created_at: ISODate,              // 账户创建时间（UTC）
  updated_at: ISODate,              // 上次更新时间（UTC）
  last_login: ISODate|null,         // 上次登录时间（初始为null）
  
  // ========== 用户偏好设置 ==========
  preferences: {
    // 分析相关
    default_market: String,         // 默认市场 (e.g., "A股")
    default_depth: String,          // 默认分析深度 (1-5级，3级为标准)
    default_analysts: [String],     // 默认分析师列表
    auto_refresh: Boolean,          // 是否自动刷新
    refresh_interval: Number,       // 刷新间隔（秒）
    
    // UI界面
    ui_theme: String,               // UI主题 ("light" | "dark")
    sidebar_width: Number,          // 侧边栏宽度（像素）
    
    // 语言与地区
    language: String,               // 语言代码 (e.g., "zh-CN")
    
    // 通知设置
    notifications_enabled: Boolean, // 是否启用通知
    email_notifications: Boolean,   // 是否启用邮件通知
    desktop_notifications: Boolean, // 是否启用桌面通知
    analysis_complete_notification: Boolean,  // 分析完成提醒
    system_maintenance_notification: Boolean  // 系统维护提醒
  },
  
  // ========== 配额和限制 ==========
  daily_quota: Number,              // 日分析配额（次数）
  concurrent_limit: Number,         // 并发分析限制（个数）
  
  // ========== 使用统计 ==========
  total_analyses: Number,           // 总分析次数
  successful_analyses: Number,      // 成功分析次数
  failed_analyses: Number,          // 失败分析次数
  
  // ========== 用户内容 ==========
  favorite_stocks: [String]         // 收藏股票列表（股票代码）
}
```

---

## 📊 字段详细说明

### 1. 身份认证字段

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `_id` | ObjectId | 主键 | MongoDB自动生成的唯一ID |
| `username` | String | 唯一索引，必填 | 用户名，用于登录 |
| `email` | String | 唯一索引，必填 | 邮箱地址，用于找回密码 |
| `hashed_password` | String | 必填 | SHA-256哈希密码，不存储明文 |

### 2. 账户状态字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `is_active` | Boolean | true | 账户是否激活（可被管理员禁用） |
| `is_verified` | Boolean | false | 邮箱是否验证（初始未验证） |
| `is_admin` | Boolean | false | 是否为管理员账户（权限控制） |

### 3. 时间戳字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `created_at` | ISODate | 账户创建时间，用于统计用户增长 |
| `updated_at` | ISODate | 最后修改时间，用于追踪变更 |
| `last_login` | ISODate\|null | 最后登录时间，用于活跃度统计 |

### 4. 用户偏好设置（嵌套对象）

```javascript
preferences: {
  // 分析相关偏好
  default_market: "A股",                          // 用户默认关注的市场
  default_depth: "3",                             // 分析深度（推荐3级）
  default_analysts: ["市场分析师", "基本面分析师"], // 常用分析师
  auto_refresh: true,                             // 自动刷新分析结果
  refresh_interval: 30,                           // 刷新间隔（秒）
  
  // UI界面设置
  ui_theme: "light",                              // 亮色/深色主题
  sidebar_width: 240,                             // 侧边栏宽度
  
  // 语言设置
  language: "zh-CN",                              // 中文（简体）
  
  // 通知偏好
  notifications_enabled: true,                    // 全局通知开关
  email_notifications: false,                     // 邮件通知（默认关闭）
  desktop_notifications: true,                    // 桌面通知（默认开启）
  analysis_complete_notification: true,           // 分析完成提醒
  system_maintenance_notification: true           // 系统维护通知
}
```

### 5. 配额和限制字段

| 字段 | 类型 | 普通用户 | 管理员 | 说明 |
|------|------|---------|--------|------|
| `daily_quota` | Number | 1000 | 10000 | 每日最多分析次数 |
| `concurrent_limit` | Number | 3 | 10 | 同时进行的分析数量 |

### 6. 使用统计字段

| 字段 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `total_analyses` | Number | 0 | 用户进行过的总分析次数 |
| `successful_analyses` | Number | 0 | 成功的分析次数 |
| `failed_analyses` | Number | 0 | 失败的分析次数 |

### 7. 用户内容字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `favorite_stocks` | [String] | 收藏的股票代码数组（如：["600000", "000001"]） |

---

## 🔐 索引设计

### 必需索引

```javascript
// 1. 用户名唯一索引（登录查询）
db.users.createIndex({ username: 1 }, { unique: true })

// 2. 邮箱唯一索引（找回密码、注册验证）
db.users.createIndex({ email: 1 }, { unique: true })

// 3. 创建时间索引（用户统计、分页）
db.users.createIndex({ created_at: -1 })

// 4. 最后登录时间索引（活跃用户统计）
db.users.createIndex({ last_login: -1 })

// 5. 账户状态索引（查询活跃用户）
db.users.createIndex({ is_active: 1 })

// 6. 复合索引（登录查询+状态检查）
db.users.createIndex({ username: 1, is_active: 1 })
```

### 索引创建命令（Python）

```python
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client['TradingAgents']
users = db['users']

# 创建所有索引
users.create_index([('username', 1)], unique=True)
users.create_index([('email', 1)], unique=True)
users.create_index([('created_at', -1)])
users.create_index([('last_login', -1)])
users.create_index([('is_active', 1)])
users.create_index([('username', 1), ('is_active', 1)])

print("✅ 所有索引创建成功")
```

---

## 📝 数据示例

### 示例1：普通用户

```json
{
  "_id": ObjectId("65a7f8c9d1e2f3g4h5i6j7k8"),
  "username": "trader_user",
  "email": "trader@example.com",
  "hashed_password": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
  "is_active": true,
  "is_verified": true,
  "is_admin": false,
  "created_at": ISODate("2025-01-15T10:30:00Z"),
  "updated_at": ISODate("2025-01-23T14:20:00Z"),
  "last_login": ISODate("2025-01-23T08:45:00Z"),
  "preferences": {
    "default_market": "A股",
    "default_depth": "3",
    "default_analysts": ["市场分析师", "基本面分析师"],
    "auto_refresh": true,
    "refresh_interval": 30,
    "ui_theme": "light",
    "sidebar_width": 240,
    "language": "zh-CN",
    "notifications_enabled": true,
    "email_notifications": false,
    "desktop_notifications": true,
    "analysis_complete_notification": true,
    "system_maintenance_notification": true
  },
  "daily_quota": 1000,
  "concurrent_limit": 3,
  "total_analyses": 156,
  "successful_analyses": 152,
  "failed_analyses": 4,
  "favorite_stocks": ["600000", "000001", "000858"]
}
```

### 示例2：管理员用户

```json
{
  "_id": ObjectId("65a7f8c9d1e2f3g4h5i6j7k9"),
  "username": "admin",
  "email": "admin@tradingagents.cn",
  "hashed_password": "8d969eef6ecad3c29a3a873fba8fc99f24b84c72d874faa93d6e8f7c0f9d6f1f",
  "is_active": true,
  "is_verified": true,
  "is_admin": true,
  "created_at": ISODate("2024-12-01T00:00:00Z"),
  "updated_at": ISODate("2025-01-23T10:00:00Z"),
  "last_login": ISODate("2025-01-23T09:30:00Z"),
  "preferences": {
    "default_market": "A股",
    "default_depth": "深度",
    "ui_theme": "light",
    "language": "zh-CN",
    "notifications_enabled": true,
    "email_notifications": false
  },
  "daily_quota": 10000,
  "concurrent_limit": 10,
  "total_analyses": 5240,
  "successful_analyses": 5100,
  "failed_analyses": 140,
  "favorite_stocks": []
}
```

---

## 🔧 常见操作查询

### 1. 用户登录查询

```python
# 查询用户是否存在
user = db.users.find_one({
    "username": "admin"
})

# 验证密码后返回用户信息
if user and verify_password(input_password, user['hashed_password']):
    # 更新最后登录时间
    db.users.update_one(
        {"_id": user['_id']},
        {"$set": {"last_login": datetime.utcnow()}}
    )
```

### 2. 用户注册

```python
# 创建新用户
new_user = {
    "username": "new_user",
    "email": "newuser@example.com",
    "hashed_password": hash_password("password123"),
    "is_active": True,
    "is_verified": False,
    "is_admin": False,
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
    "last_login": None,
    "preferences": {...},
    "daily_quota": 1000,
    "concurrent_limit": 3,
    "total_analyses": 0,
    "successful_analyses": 0,
    "failed_analyses": 0,
    "favorite_stocks": []
}

result = db.users.insert_one(new_user)
```

### 3. 用户信息更新

```python
# 更新用户邮箱和偏好
db.users.update_one(
    {"username": "admin"},
    {
        "$set": {
            "email": "newemail@example.com",
            "preferences.ui_theme": "dark",
            "updated_at": datetime.utcnow()
        }
    }
)
```

### 4. 修改密码

```python
# 更新密码
db.users.update_one(
    {"username": "admin"},
    {
        "$set": {
            "hashed_password": hash_password("newpassword"),
            "updated_at": datetime.utcnow()
        }
    }
)
```

### 5. 用户活跃度统计

```python
# 查找过去7天登录过的用户
seven_days_ago = datetime.utcnow() - timedelta(days=7)
active_users = db.users.find({
    "last_login": {"$gte": seven_days_ago},
    "is_active": True
})
```

### 6. 查询所有用户列表（分页）

```python
# 获取第2页用户（每页10条）
page = 2
page_size = 10
skip = (page - 1) * page_size

users = db.users.find(
    {"is_active": True}
).sort("created_at", -1).skip(skip).limit(page_size)
```

### 7. 用户禁用/激活

```python
# 禁用用户
db.users.update_one(
    {"username": "trader_user"},
    {
        "$set": {
            "is_active": False,
            "updated_at": datetime.utcnow()
        }
    }
)

# 激活用户
db.users.update_one(
    {"username": "trader_user"},
    {
        "$set": {
            "is_active": True,
            "updated_at": datetime.utcnow()
        }
    }
)
```

### 8. 统计用户分析数据

```python
# 获取用户分析统计
stats = db.users.find_one(
    {"username": "trader_user"},
    {"total_analyses": 1, "successful_analyses": 1, "failed_analyses": 1}
)

# 增加分析计数
db.users.update_one(
    {"username": "trader_user"},
    {
        "$inc": {
            "total_analyses": 1,
            "successful_analyses": 1
        }
    }
)
```

### 9. 管理收藏股票

```python
# 添加收藏股票
db.users.update_one(
    {"username": "trader_user"},
    {"$addToSet": {"favorite_stocks": "600000"}}
)

# 移除收藏股票
db.users.update_one(
    {"username": "trader_user"},
    {"$pull": {"favorite_stocks": "600000"}}
)

# 获取用户收藏
user = db.users.find_one(
    {"username": "trader_user"},
    {"favorite_stocks": 1}
)
```

---

## 📈 性能优化建议

### 1. 批量操作

```python
# 批量插入用户
users_list = [...]
db.users.insert_many(users_list, ordered=False)

# 批量更新用户状态
from pymongo import UpdateOne
operations = [
    UpdateOne({"_id": user_id}, {"$set": {"is_active": False}})
    for user_id in user_ids
]
db.users.bulk_write(operations)
```

### 2. 连接池优化

```python
from pymongo import MongoClient

# 配置连接池
client = MongoClient(
    'mongodb://localhost:27017',
    maxPoolSize=50,
    minPoolSize=10
)
```

### 3. 字段选择（投影）

```python
# 只返回需要的字段，减少网络传输
user = db.users.find_one(
    {"username": "admin"},
    {"username": 1, "email": 1, "is_active": 1, "_id": 0}
)
```

---

## 🔒 安全建议

1. **密码存储**:
   - 使用SHA-256哈希（当前），建议升级到bcrypt
   - 不要存储明文密码

2. **字段权限**:
   - 查询用户时不要返回`hashed_password`
   - 限制管理员字段访问权限

3. **SQL注入防护**:
   - 使用MongoDB ORM/驱动，避免字符串拼接
   - 使用参数化查询

4. **数据加密**:
   - 邮箱等敏感信息考虑加密存储
   - 启用MongoDB传输层加密

5. **日志审计**:
   - 记录所有用户操作日志
   - 监控异常登录行为

---

## 📋 表结构初始化脚本

```javascript
// MongoDB Shell 初始化脚本
use TradingAgents;

// 创建users集合
db.createCollection("users");

// 创建唯一索引
db.users.createIndex({ username: 1 }, { unique: true });
db.users.createIndex({ email: 1 }, { unique: true });

// 创建查询索引
db.users.createIndex({ created_at: -1 });
db.users.createIndex({ last_login: -1 });
db.users.createIndex({ is_active: 1 });

// 创建复合索引
db.users.createIndex({ username: 1, is_active: 1 });

// 创建管理员用户
db.users.insertOne({
  username: "admin",
  email: "admin@tradingagents.cn",
  hashed_password: "8d969eef6ecad3c29a3a873fba8fc99f24b84c72d874faa93d6e8f7c0f9d6f1f",
  is_active: true,
  is_verified: true,
  is_admin: true,
  created_at: new Date(),
  updated_at: new Date(),
  last_login: null,
  preferences: {
    default_market: "A股",
    default_depth: "深度",
    ui_theme: "light",
    language: "zh-CN",
    notifications_enabled: true,
    email_notifications: false
  },
  daily_quota: 10000,
  concurrent_limit: 10,
  total_analyses: 0,
  successful_analyses: 0,
  failed_analyses: 0,
  favorite_stocks: []
});

print("✅ Users集合初始化成功！");
print("✅ 默认管理员账号：admin / admin123");
```

---

## 📌 总结

| 项目 | 描述 |
|------|------|
| **集合名** | `users` |
| **主键** | `_id` (ObjectId) |
| **唯一字段** | `username`, `email` |
| **主要索引** | username, email, created_at, last_login, is_active |
| **典型文档大小** | ~2KB |
| **用途** | 用户账户管理、认证、偏好设置存储 |
| **相关服务** | `app/services/user_service.py` |
| **相关API** | `/api/auth/*` 路由 |

---

## 🚀 快速开始

```bash
# 1. 启动MongoDB
mongod

# 2. 连接MongoDB
mongosh

# 3. 运行初始化脚本
mongo mongodb://localhost:27017/TradingAgents mongodb_init.js

# 4. 验证集合创建成功
db.users.findOne()

# 5. 查看所有索引
db.users.getIndexes()
```

祝你的MongoDB用户表设计顺利！🎉
