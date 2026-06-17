# 🚀 快速开始 - AI 股票筛选 API

## 5分钟快速开始

### 步骤 1: 发起筛选请求

```bash
# 筛选 AI 和芯片半导体板块，返回最好的 30 只股票
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "market": "CN",
    "date": "2026-06-17",
    "max_results": 30,
    "sectors": ["AI", "芯片半导体"],
    "include_news": true
  }' \
  --no-buffer
```

### 步骤 2: 监听流式响应

接口会实时返回筛选进度：

```
event: start
data: {"message":"开始 AI 股票筛选...","timestamp":"2026-06-17T10:30:00Z"}

event: status
data: {"message":"正在获取板块股票列表（板块：AI, 芯片半导体）...","progress":5}

event: status
data: {"message":"成功获取 45 只板块股票","progress":15}

event: status
data: {"message":"正在获取股票市场新闻...","progress":25}

event: status
data: {"message":"成功获取股票新闻","progress":35}

event: status
data: {"message":"正在初始化AI模型...","progress":40}

...

event: result
data: {"report":"# 中国A股基本面分析报告...","progress":100}

event: complete
data: {"message":"筛选完成","timestamp":"2026-06-17T10:35:00Z"}
```

## 📋 常用请求模板

### 模板 1: 仅筛选 AI 板块

```bash
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "sectors": ["AI"],
    "max_results": 20,
    "include_news": true
  }'
```

### 模板 2: 筛选多个板块

```bash
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "sectors": ["AI", "机器人", "芯片半导体", "存储"],
    "max_results": 30,
    "include_news": true
  }'
```

### 模板 3: 全市场筛选

```bash
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "sectors": null,
    "max_results": 50,
    "include_news": false
  }'
```

### 模板 4: 快速筛选（无新闻）

```bash
curl -X POST "http://localhost:8000/api/search/all" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "sectors": ["芯片半导体"],
    "include_news": false
  }'
```

## 🐍 Python 脚本示例

### 完整示例

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
from typing import List, Dict, Any

class StockScreeningClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
    
    def screen_stocks(
        self,
        sectors: List[str] = None,
        max_results: int = 30,
        include_news: bool = True,
        date: str = None
    ) -> Dict[str, Any]:
        """
        筛选股票并获取详细报告
        
        Args:
            sectors: 板块列表，如 ["AI", "芯片半导体"]
            max_results: 最大返回结果数
            include_news: 是否包含新闻
            date: 筛选日期，格式 YYYY-MM-DD
        
        Returns:
            筛选结果字典
        """
        url = f'{self.base_url}/api/search/all'
        
        payload = {
            'market': 'CN',
            'max_results': max_results,
            'include_news': include_news
        }
        
        if sectors:
            payload['sectors'] = sectors
        
        if date:
            payload['date'] = date
        
        print(f"🔍 正在筛选股票: {sectors or '全部A股'}")
        print(f"📊 目标数量: {max_results}")
        print(f"📰 包含新闻: {include_news}")
        print("-" * 50)
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                stream=True
            )
            
            result = {
                'status': response.status_code,
                'events': [],
                'final_report': None
            }
            
            # 处理流式响应
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8') if isinstance(line, bytes) else line
                    
                    # 解析事件类型
                    if line.startswith('event: '):
                        event_type = line[7:].strip()
                        print(f"📡 事件: {event_type}")
                    
                    # 解析事件数据
                    elif line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            result['events'].append({
                                'type': event_type,
                                'data': data
                            })
                            
                            # 打印关键信息
                            if 'progress' in data:
                                progress = data.get('progress', 0)
                                message = data.get('message', '')
                                print(f"  ⏳ [{progress}%] {message}")
                            
                            if 'report' in data:
                                result['final_report'] = data['report']
                                print(f"  ✅ 已生成报告 ({len(data['report'])} 字)")
                            
                            if 'error' in data:
                                print(f"  ❌ 错误: {data['error']}")
                        
                        except json.JSONDecodeError:
                            pass
            
            return result
        
        except Exception as e:
            print(f"❌ 筛选失败: {e}")
            return {'status': 500, 'error': str(e)}


# 使用示例
if __name__ == '__main__':
    # 配置
    BASE_URL = 'http://localhost:8000'
    TOKEN = 'your_token_here'
    
    # 创建客户端
    client = StockScreeningClient(BASE_URL, TOKEN)
    
    # 示例 1: 筛选 AI 和芯片半导体板块
    print("\n" + "="*50)
    print("示例 1: 筛选 AI 和芯片半导体板块")
    print("="*50)
    
    result = client.screen_stocks(
        sectors=['AI', '芯片半导体'],
        max_results=30,
        include_news=True
    )
    
    # 打印最终报告
    if result.get('final_report'):
        print("\n📄 筛选报告:")
        print("-" * 50)
        print(result['final_report'][:500] + "...")
    
    # 示例 2: 快速筛选（无新闻）
    print("\n" + "="*50)
    print("示例 2: 快速筛选（无新闻)")
    print("="*50)
    
    result = client.screen_stocks(
        sectors=['机器人'],
        max_results=20,
        include_news=False
    )
    
    # 示例 3: 全市场筛选
    print("\n" + "="*50)
    print("示例 3: 全市场筛选")
    print("="*50)
    
    result = client.screen_stocks(
        sectors=None,
        max_results=50
    )
```
