# 🔍 `/api/screening/run` 接口完整调用链路分析

---

## 📋 接口概览

| 属性 | 值 |
|------|-----|
| **路径** | `/api/screening/run` |
| **方法** | POST |
| **认证** | 需要登录 (`get_current_user`) |
| **响应模型** | `ScreeningResponse` |
| **功能** | 股票筛选（传统格式，向后兼容） |

---

## 🔄 完整调用链路

```
用户请求
    ↓
[1] app/routers/screening.py:156 - run_screening()
    ↓
[2] _convert_legacy_conditions_to_new_format() - 条件格式转换
    ↓
[3] enhanced_svc.screen_stocks() - 增强筛选服务
    ↓
[4] _analyze_conditions() - 条件分析
    ↓
[5] 决策点：数据库优化 vs 传统方法
    ├─→ [6A] 数据库优化路径
    │   ↓
    │   db_service.screen_stocks()
    │   ↓
    │   _build_query() - 构建MongoDB查询
    │   ↓
    │   collection.find() - 执行查询
    │   ↓
    │   _enrich_with_financial_data() - 财务数据富集
    │   ↓
    │   _format_result() - 格式化结果
    │
    └─→ [6B] 传统方法路径
        ↓
        traditional_service.run()
        ↓
        _get_universe() - 获取股票池
        ↓
        get_data_source_manager() - 获取数据源
        ↓
        get_stock_dataframe() - 获取K线数据
        ↓
        compute_many() - 计算技术指标
        ↓
        _evaluate_conditions() - 条件评估
        ↓
        排序和分页
    ↓
[7] _enrich_results_with_realtime_metrics() - PE/PB富集
    ↓
[8] 返回 ScreeningResponse
```

---

## 📝 详细链路说明

### [1] 路由层：`run_screening()`

**文件**: `app/routers/screening.py:156`

**功能**:
- 接收 `ScreeningRequest` 请求
- 验证用户身份 (`get_current_user`)
- 记录请求日志
- 转换条件格式
- 调用增强筛选服务
- 返回 `ScreeningResponse`

**关键代码**:
```python
@router.post("/run", response_model=ScreeningResponse)
async def run_screening(req: ScreeningRequest, user: dict = Depends(get_current_user)):
    # 记录日志
    logger.info(f"[screening] 请求条件: {req.conditions}")

    # 转换条件格式
    conditions = _convert_legacy_conditions_to_new_format(req.conditions)

    # 调用增强筛选服务
    result = await enhanced_svc.screen_stocks(
        conditions=conditions,
        market=req.market,
        date=req.date,
        adj=req.adj,
        limit=req.limit,
        offset=req.offset,
        order_by=order_by,
        use_database_optimization=True
    )

    # 返回结果
    return ScreeningResponse(total=result["total"], items=result["items"])
```

---

### [2] 条件格式转换：`_convert_legacy_conditions_to_new_format()`

**文件**: `app/routers/screening.py:80-145`

**功能**:
- 将前端传来的传统格式条件转换为新的 `ScreeningCondition` 格式
- 字段名映射（如 `market_cap` → `total_mv`）
- 操作符映射（如 `gt` → `>`）
- 市值单位转换（万元 → 亿元）

**关键转换**:
```python
# 字段映射
field_mapping = {
    "market_cap": "total_mv",      # 市值
    "pe_ratio": "pe",              # 市盈率
    "pb_ratio": "pb",              # 市净率
    "turnover": "turnover_rate",   # 换手率
    "change_percent": "pct_chg",   # 涨跌幅
    "price": "close",              # 价格
}

# 操作符映射
operator_mapping = {
    "between": "between",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
    "eq": "==",
    "ne": "!=",
}
```

---

### [3] 增强筛选服务：`enhanced_svc.screen_stocks()`

**文件**: `app/services/enhanced_screening_service.py:39-98`

**功能**:
- 智能选择筛选策略（数据库优化 vs 传统方法）
- 执行筛选
- 数据富集（实时行情、PE/PB）
- 性能统计

**核心逻辑**:
```python
async def screen_stocks(self, conditions, market, date, adj, limit, offset, order_by, use_database_optimization):
    # 分析筛选条件
    analysis = self._analyze_conditions(conditions)

    # 决策：使用哪种筛选方式
    if (use_database_optimization and
        analysis["can_use_database"] and
        not analysis["needs_technical_indicators"]):

        # 使用数据库优化筛选
        result = await self._screen_with_database(conditions, limit, offset, order_by)
        optimization_used = "database"
        source = "mongodb"

    else:
        # 使用传统筛选方法
        result = await self._screen_with_traditional_method(conditions, market, date, adj, limit, offset, order_by)
        optimization_used = "traditional"
        source = "api"

    # 数据富集
    items = await self._enrich_results_with_realtime_metrics(items)

    return {
        "total": total,
        "items": items,
        "took_ms": took_ms,
        "optimization_used": optimization_used,
        "source": source
    }
```

---

### [4] 条件分析：`_analyze_conditions()`

**文件**: `app/services/enhanced_screening/utils.py`

**功能**:
- 分析筛选条件涉及的字段
- 判断是否可以使用数据库优化
- 判断是否需要技术指标

**返回结果**:
```python
{
    "can_use_database": True,           # 是否可以使用数据库优化
    "needs_technical_indicators": False, # 是否需要技术指标
    "fields": ["total_mv", "pe", "pb"],  # 涉及的字段
    "basic_fields": ["total_mv", "pe"],  # 基础字段
    "technical_fields": []               # 技术指标字段
}
```

---

### [5] 决策点：选择筛选策略

**决策逻辑**:

| 条件 | 结果 |
|------|------|
| `use_database_optimization=True` AND `can_use_database=True` AND `needs_technical_indicators=False` | 使用数据库优化路径 |
| 其他情况 | 使用传统方法路径 |

**为什么这样设计**:
- 数据库优化：速度快，但只支持基础字段（市值、PE、PB等）
- 传统方法：支持技术指标（MA、RSI、KDJ等），但需要计算，速度较慢

---

### [6A] 数据库优化路径：`db_service.screen_stocks()`

**文件**: `app/services/database_screening_service.py:68-145`

**功能**:
- 直接从 MongoDB 查询数据
- 支持基础字段筛选
- 支持排序和分页
- 批量查询财务数据

**关键步骤**:

1. **获取数据源优先级配置**
   ```python
   config = UnifiedConfigManager()
   data_source_configs = await config.get_data_source_configs_async()
   source = enabled_sources[0]  # 优先级最高的数据源
   ```

2. **构建MongoDB查询条件**
   ```python
   query = {
       "total_mv": {"$gte": 50, "$lte": 1000},
       "pe": {"$lte": 30},
       "source": "tushare"  # 指定数据源
   }
   ```

3. **执行查询**
   ```python
   cursor = collection.find(query).sort(sort_conditions).skip(offset).limit(limit)
   ```

4. **批量查询财务数据**
   ```python
   pipeline = [
       {"$match": {"code": {"$in": codes}}},
       {"$sort": {"report_period": -1}},
       {"$group": {"_id": "$code", "roe": {"$first": "$roe"}}}
   ]
   ```

5. **格式化结果**
   ```python
   result = {
       "code": doc.get("code"),
       "name": doc.get("name"),
       "total_mv": doc.get("total_mv"),
       "pe": doc.get("pe"),
       # ...
   }
   ```

**性能优势**:
- 直接从数据库查询，无需外部API调用
- 支持复杂的MongoDB查询条件
- 批量查询财务数据，减少数据库往返

---

### [6B] 传统方法路径：`traditional_service.run()`

**文件**: `app/services/screening_service.py:56-165`

**功能**:
- 获取股票池
- 逐个股票获取K线数据
- 计算技术指标
- 评估筛选条件
- 排序和分页

**关键步骤**:

1. **获取股票池**
   ```python
   def _get_universe() -> List[str]:
       db = get_mongo_db()
       cursor = collection.find({"market_info.market": "CN"}, {"code": 1})
       return [doc.get("code") for doc in cursor]
   ```

2. **获取K线数据**
   ```python
   manager = get_data_source_manager()
   df = manager.get_stock_dataframe(code, start_s, end_s)
   ```

3. **计算技术指标**
   ```python
   specs = [
       IndicatorSpec("ma", {"n": 20}),
       IndicatorSpec("rsi", {"n": 14}),
       IndicatorSpec("kdj", {"n": 9}),
       # ...
   ]
   dfc = compute_many(df, specs)
   ```

4. **评估条件**
   ```python
   passes = self._evaluate_conditions(dfc, conditions)
   ```

5. **排序和分页**
   ```python
   results.sort(key=lambda x: x.get(field), reverse=(direction == "desc"))
   page_items = results[offset:offset+limit]
   ```

**性能特点**:
- 支持技术指标筛选
- 需要逐个股票获取数据，速度较慢
- 限制样本规模（最多120只股票）

---

### [7] 数据富集：`_enrich_results_with_realtime_metrics()`

**文件**: `app/services/enhanced_screening_service.py:185-210`

**功能**:
- 为筛选结果添加PE/PB指标
- 使用静态数据（避免性能问题）

**实现方式**:
```python
async def _enrich_results_with_realtime_metrics(self, items):
    # 使用 stock_basic_info 中的静态 PE/PB
    # 避免批量计算动态 PE 导致的性能问题
    return items
```

**为什么使用静态数据**:
- 批量计算动态PE需要查询多个集合，性能开销大
- 静态PE基于最近交易日收盘价，对筛选场景已足够准确

---

### [8] 返回响应：`ScreeningResponse`

**文件**: `app/routers/screening.py:34-37`

**响应格式**:
```python
class ScreeningResponse(BaseModel):
    total: int              # 总数量
    items: List[dict]       # 筛选结果列表
```

**示例响应**:
```json
{
  "total": 156,
  "items": [
    {
      "code": "000001",
      "name": "平安银行",
      "total_mv": 2456.78,
      "pe": 5.23,
      "pb": 0.62,
      "close": 12.45,
      "pct_chg": 2.34,
      "amount": 123456.78
    }
  ]
}
```

---

## 🎯 两种筛选路径对比

| 维度 | 数据库优化路径 | 传统方法路径 |
|------|---------------|-------------|
| **速度** | 快（<100ms） | 慢（>1s） |
| **支持字段** | 基础字段（市值、PE、PB等） | 基础字段 + 技术指标 |
| **数据来源** | MongoDB | 外部API（Tushare/AKShare） |
| **样本规模** | 无限制 | 限制120只股票 |
| **适用场景** | 快速筛选、基础指标 | 技术分析、复杂条件 |

---

## 📊 性能优化策略

1. **智能路由**: 根据条件自动选择最优路径
2. **数据库优化**: 使用MongoDB索引和聚合管道
3. **批量查询**: 减少数据库往返次数
4. **缓存策略**: 避免重复计算
5. **样本限制**: 传统方法限制样本规模

---

## 🔧 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `use_database_optimization` | 是否使用数据库优化 | `True` |
| `limit` | 返回数量限制 | `50` |
| `offset` | 偏移量 | `0` |
| `order_by` | 排序条件 | `None` |

---

## 🚨 注意事项

1. **数据源优先级**: 数据库优化路径会使用优先级最高的数据源
2. **市值单位转换**: 前端传入万元，后端自动转换为亿元
3. **技术指标限制**: 传统方法限制样本规模为120只股票
4. **静态PE/PB**: 使用静态数据，非实时计算

---

**文档版本**: v1.0  
**创建日期**: 2026-06-16  
**适用版本**: TradingAgents-CN v1.0.0-preview