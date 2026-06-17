# AI 股票筛选 API - 行业板块筛选指南

## 🎯 功能概述

改进后的 `/api/search/all` 接口现在支持：

1. **按行业板块筛选** - 支持 AI、机器人、芯片半导体、存储、陶瓷材料等特定板块
2. **批量新闻获取** - 自动为筛选的股票获取市场新闻
3. **智能股票筛选** - 使用 LLM 驱动的深度筛选算法
4. **流式报告输出** - 实时显示筛选进度和结果
5. **结果限制** - 自动限制最终结果为指定数量（默认30只最佳股票）

## 📊 支持的板块

| 板块代码 | 板块名称 | 示例公司 |
|---------|---------|--------|
| AI | 人工智能 | 科大讯飞、汇纳科技、云从科技 |
| 机器人 | 机器人和自动化 | 埃斯顿、新松机器人、发那科 |
| 芯片半导体 | 芯片设计/制造/封测 | 中芯国际、北京君正、卓胜微 |
| 存储 | 存储芯片和器件 | 长江存储、紫光国芯、兆易创新 |
| 陶瓷材料 | 陶瓷材料和精细陶瓷 | 三环集团、瑞泰科技、国瓷材料 |

## 🚀 API 使用指南

### 基础请求格式

```json
POST /api/search/all
Content-Type: application/json

{
  "market": "CN",
  "date": "2026-06-17",
  "max_results": 30,
  "sectors": ["AI", "芯片半导体"],
  "include_news": true
}
```

### 请求参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `market` | string | "CN" | 市场类型：CN(中国)、US(美国)、HK(香港) |
| `date` | string | 当前日期 | 筛选日期，格式 YYYY-MM-DD |
| `max_results` | integer | 30 | 最大返回结果数量 |
| `sectors` | array | null | 板块列表，为空则筛选全部A股 |
| `include_news` | boolean | true | 是否包含股票新闻数据 |

### 使用示例

#### 1. 筛选 AI 和芯片半导体板块的最佳 30 只股票

```bash
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "market": "CN",
    "date": "2026-06-17",
    "max_results": 30,
    "sectors": ["AI", "芯片半导体"],
    "include_news": true
  }'
```

#### 2. 筛选所有支持的板块

```bash
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sectors": ["AI", "机器人", "芯片半导体", "存储", "陶瓷材料"],
    "max_results": 50
  }'
```

#### 3. 筛选全部 A 股（不限板块）

```bash
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sectors": null,
    "max_results": 30
  }'
```

#### 4. 仅获取筛选结果，不需要新闻数据

```bash
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sectors": ["AI"],
    "include_news": false,
    "max_results": 30
  }'
```

## 📡 响应格式（SSE 流式）

### 流式事件类型

接口返回 Server-Sent Events (SSE) 格式的流式数据，包含以下事件类型：

#### 1. start 事件 - 筛选开始

```json
{
  "message": "开始 AI 股票筛选...",
  "timestamp": "2026-06-17T10:30:00.000Z"
}
```

#### 2. status 事件 - 进度更新

```json
{
  "message": "正在获取板块股票列表（板块：AI, 芯片半导体）...",
  "progress": 5
}
```

#### 3. result 事件 - 最终结果

```json
{
  "report": "# 中国A股基本面分析报告...",
  "sender": "ChinaStockScreener",
  "progress": 100
}
```

#### 4. complete 事件 - 筛选完成

```json
{
  "message": "筛选完成",
  "timestamp": "2026-06-17T10:35:00.000Z"
}
```

#### 5. error 事件 - 错误发生

```json
{
  "error": "错误信息描述"
}
```

## 💻 前端集成示例

### Vue.js / TypeScript

```typescript
async function fetchStockScreening(sectors: string[]) {
  const response = await fetch('/api/search/all', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      sectors,
      max_results: 30,
      include_news: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n');

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        const eventType = line.substring(7);
        
        if (eventType === 'status') {
          const dataLine = lines[lines.indexOf(line) + 1];
          const data = JSON.parse(dataLine.substring(6));
          console.log(`进度: ${data.progress}% - ${data.message}`);
        } else if (eventType === 'result') {
          const dataLine = lines[lines.indexOf(line) + 1];
          const data = JSON.parse(dataLine.substring(6));
          console.log('筛选报告:', data.report);
        }
      }
    }
  }
}
```
