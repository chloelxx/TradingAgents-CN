"""
板块分析服务
提供A股板块（行业/概念）股票的搜索、排名和多线程并发分析功能

核心流程：
1. 搜索板块股票 → 按市值排名 → 取前N只
2. 多线程并发获取每只股票数据 + LLM评分
3. 汇总评分结果，生成最终板块分析报告
"""

import asyncio
import json
import logging
import os
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger("app.services.sector_analysis")


# ==================== 板块关键词扩展映射 ====================

# 将用户输入的关键词映射到 Tushare industry 字段中的实际行业名 + 公司名关键词
# 因为 Tushare 的 industry 字段是申万行业分类（如"软件服务"），不是"AI"这种概念词
SECTOR_KEYWORD_MAP = {
    "AI": {
        "industries": ["软件服务", "计算机", "互联网", "通信设备", "元器件", "半导体", "电子制造", "IT设备"],
        "name_keywords": ["智能", "AI", "人工智能", "数据", "算力", "软件", "信息", "科技", "网络", "云", "数智", "智慧"],
    },
    "人工智能": {
        "industries": ["软件服务", "计算机", "互联网", "通信设备", "元器件", "半导体"],
        "name_keywords": ["智能", "AI", "人工智能", "数据", "算力", "软件", "信息", "科技", "智慧", "机器"],
    },
    "芯片": {
        "industries": ["半导体", "元器件", "电子制造", "IT设备"],
        "name_keywords": ["芯片", "半导体", "微电子", "集成电路", "晶圆", "存储", "EDA", "IP", "封测", "光刻"],
    },
    "半导体": {
        "industries": ["半导体", "元器件", "电子制造"],
        "name_keywords": ["芯片", "半导体", "微电子", "集成电路", "晶圆", "存储", "硅", "光刻", "EDA"],
    },
    "新能源": {
        "industries": ["电气设备", "电源设备", "新能源", "汽车", "汽车配件"],
        "name_keywords": ["新能源", "光伏", "锂电", "风电", "储能", "电池", "太阳能", "新能", "绿能", "充电"],
    },
    "光伏": {
        "industries": ["电气设备", "电源设备", "新能源"],
        "name_keywords": ["光伏", "太阳能", "硅片", "组件", "逆变器", "电池片", "新能源"],
    },
    "锂电池": {
        "industries": ["电气设备", "电源设备", "汽车", "汽车配件", "化工"],
        "name_keywords": ["锂电", "电池", "锂", "正极", "负极", "电解液", "隔膜", "新能源"],
    },
    "白酒": {
        "industries": ["白酒", "酿酒", "食品饮料"],
        "name_keywords": ["酒", "茅台", "五粮液", "泸州", "汾酒", "洋河", "古井", "舍得"],
    },
    "医药": {
        "industries": ["医药", "生物制药", "化学制药", "中药", "医疗器械", "医药商业"],
        "name_keywords": ["医药", "药", "生物", "医疗", "制药", "健康", "基因", "疫苗"],
    },
    "机器人": {
        "industries": ["机械", "电气设备", "IT设备", "元器件", "软件服务"],
        "name_keywords": ["机器人", "自动化", "智能装备", "机械手", "伺服", "减速器", "机器"],
    },
    "汽车": {
        "industries": ["汽车", "汽车配件", "电气设备", "电源设备"],
        "name_keywords": ["汽车", "新能源", "电动", "智能驾驶", "整车", "零部件"],
    },
    "消费电子": {
        "industries": ["元器件", "电子制造", "IT设备", "通信设备"],
        "name_keywords": ["电子", "智能", "手机", "屏幕", "显示", "声学", "光学", "精密"],
    },
    "军工": {
        "industries": ["航空", "航天", "船舶", "机械"],
        "name_keywords": ["军工", "航空", "航天", "兵器", "船舶", "国防", "军用", "装备"],
    },
    "银行": {
        "industries": ["银行"],
        "name_keywords": ["银行"],
    },
    "证券": {
        "industries": ["证券", "多元金融"],
        "name_keywords": ["证券", "券商", "金融"],
    },
    "房地产": {
        "industries": ["房地产", "物业管理", "园区开发"],
        "name_keywords": ["地产", "房地产", "物业", "置业", "新城"],
    },
}


def _expand_sector_keywords(sector: str) -> Dict[str, List[str]]:
    """扩展板块关键词：用户输入 → 实际搜索词"""
    # 精确匹配
    if sector in SECTOR_KEYWORD_MAP:
        return SECTOR_KEYWORD_MAP[sector]

    # 模糊匹配：检查 sector 是否包含在映射键中
    for key, value in SECTOR_KEYWORD_MAP.items():
        if key in sector or sector in key:
            return value

    # 默认：直接用 sector 作为关键词搜索 name 和 industry
    return {
        "industries": [sector],
        "name_keywords": [sector],
    }


# ==================== 单股评分常量 ====================

# 评分维度权重
SCORE_WEIGHTS = {
    "market_performance": 0.25,   # 市场表现
    "fundamentals": 0.30,         # 基本面
    "industry_position": 0.20,    # 行业地位
    "news_sentiment": 0.15,       # 新闻舆情
    "valuation": 0.10,            # 估值性价比
}


def rating_from_score(score: float) -> str:
    if score >= 85:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 55:
        return "C"
    else:
        return "D"


def rating_label(rating: str) -> str:
    return {"A": "强烈推荐", "B": "推荐关注", "C": "谨慎观望", "D": "暂时回避"}.get(rating, "未知")


def build_stock_score_prompt(
    stock_code: str,
    stock_name: str,
    market_data: str,
    fundamentals_data: str,
    news_data: str,
    industry: str,
    total_mv,
    pe_ttm,
) -> str:
    """构建单股评分提示词"""
    mv_str = f"{total_mv:.2f}亿" if total_mv else "未知"
    pe_str = f"{pe_ttm:.2f}" if pe_ttm else "未知"

    # 截断数据
    market_snippet = str(market_data)[:1200] if market_data else "无数据"
    fundamentals_snippet = str(fundamentals_data)[:1200] if fundamentals_data else "无数据"
    news_snippet = str(news_data)[:600] if news_data else "无新闻"

    return f"""你是一位专业的A股分析师，请对以下股票进行评分。

## 股票信息
- 代码: {stock_code}
- 名称: {stock_name}
- 行业: {industry}
- 市值: {mv_str}
- PE(TTM): {pe_str}

## 市场数据
{market_snippet}

## 基本面数据
{fundamentals_snippet}

## 新闻舆情
{news_snippet}

## 评分要求

请从以下5个维度评分（每项0-100分），然后按权重计算综合得分：

1. **市场表现** (权重25%): 趋势、量价关系、技术形态
2. **基本面** (权重30%): 盈利能力、成长性、财务健康度
3. **行业地位** (权重20%): 市值排名、护城河、竞争优势
4. **新闻舆情** (权重15%): 利好/利空信号、市场情绪
5. **估值性价比** (权重10%): PE/PB分位、PEG合理性

## 输出格式（严格JSON，不要其他内容）

```json
{{
    "market_performance": 75,
    "fundamentals": 80,
    "industry_position": 85,
    "news_sentiment": 70,
    "valuation": 65,
    "summary": "一句话总结（30字以内）",
    "strengths": ["优势1", "优势2"],
    "risks": ["风险1", "风险2"],
    "reasoning": "评分理由（100字以内）"
}}
```
"""


# ==================== 服务类 ====================

class SectorAnalysisService:
    """板块分析服务类"""

    def __init__(self):
        self._toolkit = None
        self._llm = None
        self._llm_report = None
        self._stock_name_cache: Dict[str, str] = {}
        # 多线程池：最多3个并发
        self._thread_pool = ThreadPoolExecutor(max_workers=3)

    def _get_toolkit(self):
        """获取或创建 Toolkit 实例（延迟初始化）"""
        if self._toolkit is None:
            from tradingagents.agents.utils.agent_utils import Toolkit
            self._toolkit = Toolkit()
        return self._toolkit

    def shutdown(self):
        """关闭线程池，释放资源"""
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None
        self._toolkit = None
        self._llm = None
        self._llm_report = None

    # ==================== 板块股票获取 ====================

    def get_sector_stocks(
        self,
        sector: str,
        market: str = "A股",
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        获取指定板块的A股股票列表

        策略：
        1. 先通过关键词扩展映射，将用户输入（如"AI"）转换为实际搜索词
           - industry_keywords: 匹配 Tushare 的 industry 字段（申万行业分类）
           - name_keywords: 匹配公司名称
        2. 从 Tushare 获取全量股票 → 按扩展后的关键词多字段筛选
        3. AKShare 补充
        4. MongoDB 兜底
        """
        logger.info(f"📊 [板块分析] 开始获取板块 '{sector}' 的股票列表")

        # 扩展关键词
        kw = _expand_sector_keywords(sector)
        industries = kw.get("industries", [sector])
        name_keywords = kw.get("name_keywords", [sector])
        logger.info(f"🔍 [板块分析] 关键词扩展: industries={industries}, name_keywords={name_keywords}")

        stocks = []
        seen_codes = set()

        # 1. Tushare（按 industry 字段 + name 字段匹配）
        tushare_stocks = self._get_stocks_from_tushare(industries, name_keywords)
        if tushare_stocks:
            for s in tushare_stocks:
                code = s.get("code", "")
                if code and code not in seen_codes:
                    stocks.append(s)
                    seen_codes.add(code)
            logger.info(f"✅ [板块分析] Tushare 获取到 {len(tushare_stocks)} 只股票")

        # 2. AKShare 补充
        if len(stocks) < 10:
            akshare_stocks = self._get_stocks_from_akshare(name_keywords)
            for s in akshare_stocks:
                code = s.get("code", "")
                if code and code not in seen_codes:
                    stocks.append(s)
                    seen_codes.add(code)
            logger.info(f"✅ [板块分析] AKShare 补充获取到 {len(akshare_stocks)} 只股票")

        # 3. MongoDB 兜底
        if len(stocks) < 5:
            mongo_stocks = self._get_stocks_from_mongodb(industries, name_keywords)
            for s in mongo_stocks:
                code = s.get("code", "")
                if code and code not in seen_codes:
                    stocks.append(s)
                    seen_codes.add(code)
            logger.info(f"✅ [板块分析] MongoDB 补充获取到 {len(mongo_stocks)} 只股票")

        logger.info(f"✅ [板块分析] 板块 '{sector}' 共获取到 {len(stocks)} 只股票")
        return stocks[:limit]

    def _get_stocks_from_tushare(
        self,
        industries: List[str],
        name_keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """
        从 Tushare 获取股票列表，按 industry 和 name 多关键词筛选

        匹配逻辑：
        - industry 字段：匹配 industries 列表中的任意一个（模糊匹配）
        - name 字段：匹配 name_keywords 列表中的任意一个（模糊匹配）
        - 满足任一条件即入选
        """
        try:
            from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
            adapter = get_tushare_provider()
            if not adapter or not adapter.is_available():
                logger.warning("⚠️ Tushare 不可用")
                return []

            df = adapter.get_stock_list_sync()
            if df is None or df.empty:
                logger.warning("⚠️ Tushare 返回空数据")
                return []

            # 构建 industry 匹配 mask
            industry_mask = pd.Series(False, index=df.index)
            for ind in industries:
                industry_mask = industry_mask | df['industry'].astype(str).str.contains(ind, na=False)

            # 构建 name 匹配 mask
            name_mask = pd.Series(False, index=df.index)
            for kw in name_keywords:
                name_mask = name_mask | df['name'].astype(str).str.contains(kw, na=False)

            # 合并：industry 或 name 匹配
            filtered = df[industry_mask | name_mask]

            logger.info(f"🔍 [Tushare] industry匹配: {industry_mask.sum()}, name匹配: {name_mask.sum()}, 合并: {len(filtered)}")

            stocks = []
            for _, row in filtered.iterrows():
                code = str(row.get('ts_code', row.get('symbol', '')))
                clean_code = code.replace('.SH', '').replace('.SZ', '').replace('.SS', '')
                stocks.append({
                    "code": clean_code,
                    "ts_code": code,
                    "name": str(row.get('name', '')),
                    "industry": str(row.get('industry', '')),
                    "area": str(row.get('area', '')),
                    "market": str(row.get('market', '')),
                    "list_date": str(row.get('list_date', '')),
                    "source": "tushare"
                })
            return stocks
        except Exception as e:
            logger.warning(f"⚠️ Tushare 获取板块股票失败: {e}")
            return []

    def _get_stocks_from_akshare(self, name_keywords: List[str]) -> List[Dict[str, Any]]:
        """从 AKShare 获取股票列表并按关键词筛选"""
        try:
            from tradingagents.dataflows.providers.china.akshare import AKShareProvider
            provider = AKShareProvider()
            df = provider.get_stock_list_sync()
            if df is None or df.empty:
                return []

            name_col = None
            for col in ['name', '股票名称', '名称']:
                if col in df.columns:
                    name_col = col
                    break
            if name_col is None:
                return []

            # 按多个关键词匹配 name
            name_mask = pd.Series(False, index=df.index)
            for kw in name_keywords:
                name_mask = name_mask | df[name_col].astype(str).str.contains(kw, na=False)
            filtered = df[name_mask]

            stocks = []
            for _, row in filtered.iterrows():
                stocks.append({
                    "code": str(row.get('code', '')),
                    "name": str(row.get(name_col, '')),
                    "industry": "",
                    "source": "akshare"
                })
            return stocks
        except Exception as e:
            logger.warning(f"⚠️ AKShare 获取板块股票失败: {e}")
            return []

    def _get_stocks_from_mongodb(
        self,
        industries: List[str],
        name_keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """从 MongoDB stock_basic_info 缓存中按行业和名称关键词筛选"""
        try:
            from pymongo import MongoClient
            from app.core.config import settings
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            collection = db['stock_basic_info']

            # 构建 $or 查询条件
            or_conditions = []
            for ind in industries:
                or_conditions.append({"industry": re.compile(ind, re.IGNORECASE)})
            for kw in name_keywords:
                or_conditions.append({"name": re.compile(kw, re.IGNORECASE)})

            cursor = collection.find(
                {"$or": or_conditions},
                {"code": 1, "name": 1, "industry": 1, "total_mv": 1, "_id": 0}
            ).limit(200)

            stocks = [{"code": str(d.get("code", "")), "name": str(d.get("name", "")),
                       "industry": str(d.get("industry", "")), "total_mv": d.get("total_mv"),
                       "source": "mongodb"} for d in cursor]
            client.close()
            return stocks
        except Exception as e:
            logger.warning(f"⚠️ MongoDB 获取板块股票失败: {e}")
            return []

    # ==================== 股票排名 ====================

    def rank_stocks_by_market_cap(
        self,
        stocks: List[Dict[str, Any]],
        top_n: int = 20
    ) -> List[Dict[str, Any]]:
        """按市值排名，返回前 N 只"""
        logger.info(f"📊 [板块分析] 开始对 {len(stocks)} 只股票进行排名")

        try:
            from pymongo import MongoClient
            from app.core.config import settings
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            collection = db['stock_basic_info']
            codes = [s.get("code", "") for s in stocks if s.get("code")]
            market_caps = {}
            cursor = collection.find(
                {"code": {"$in": codes}},
                {"code": 1, "name": 1, "total_mv": 1, "pe_ttm": 1, "industry": 1, "_id": 0}
            )
            for doc in cursor:
                market_caps[doc.get("code", "")] = {
                    "total_mv": doc.get("total_mv"),
                    "pe_ttm": doc.get("pe_ttm"),
                    "industry": doc.get("industry", "")
                }
            client.close()
            logger.info(f"✅ [板块分析] 从 MongoDB 获取到 {len(market_caps)} 只股票的市值数据")
        except Exception as e:
            logger.warning(f"⚠️ MongoDB 批量查询市值失败: {e}")
            market_caps = {}

        for stock in stocks:
            code = stock.get("code", "")
            if code in market_caps:
                mc = market_caps[code]
                stock["total_mv"] = mc.get("total_mv")
                stock["pe_ttm"] = mc.get("pe_ttm")
                if mc.get("industry") and not stock.get("industry"):
                    stock["industry"] = mc.get("industry")
            else:
                stock["total_mv"] = None
                stock["pe_ttm"] = None

        def sort_key(s):
            mv = s.get("total_mv")
            try:
                return float(mv) if mv is not None else 0
            except (ValueError, TypeError):
                return 0

        stocks.sort(key=sort_key, reverse=True)
        ranked = stocks[:top_n]
        logger.info(f"✅ [板块分析] 排名完成，取前 {len(ranked)} 只股票")
        return ranked

    # ==================== 单只股票数据获取 ====================

    def fetch_stock_data(
        self,
        stock_code: str,
        analysis_date: str = None
    ) -> Dict[str, Any]:
        """获取单只股票的综合数据"""
        if analysis_date is None:
            analysis_date = datetime.now().strftime("%Y-%m-%d")

        toolkit = self._get_toolkit()
        stock_data = {
            "code": stock_code,
            "market_data": None,
            "fundamentals_data": None,
            "news_data": None,
            "error": None
        }

        # 1. 市场数据
        try:
            market_data = toolkit.get_stock_market_data_unified(stock_code, analysis_date, analysis_date)
            stock_data["market_data"] = market_data if market_data else "无数据"
        except Exception as e:
            stock_data["market_data"] = f"获取失败: {e}"

        # 2. 基本面数据
        try:
            fundamentals = toolkit.get_stock_fundamentals_unified(stock_code, analysis_date, analysis_date, analysis_date)
            stock_data["fundamentals_data"] = fundamentals if fundamentals else "无数据"
        except Exception as e:
            stock_data["fundamentals_data"] = f"获取失败: {e}"

        # 3. 新闻数据
        try:
            news = toolkit.get_stock_news_unified(stock_code, analysis_date)
            stock_data["news_data"] = news if news else "无新闻"
        except Exception as e:
            stock_data["news_data"] = f"获取失败: {e}"

        return stock_data

    # ==================== 单股 LLM 评分 ====================

    def _get_llm(self, model_name: str = None):
        """获取 LLM 实例（缓存）"""
        if self._llm is None:
            from tradingagents.graph.trading_graph import create_llm_by_provider
            provider = os.getenv("DASHSCOPE_PROVIDER", "dashscope")
            model = model_name or os.getenv("DASHSCOPE_MODEL", "qwen-plus")
            api_key = os.getenv("DASHSCOPE_API_KEY")
            backend_url = os.getenv("DASHSCOPE_BASE_URL", "")
            self._llm = create_llm_by_provider(
                provider=provider, model=model, backend_url=backend_url,
                temperature=0.3, max_tokens=2000, timeout=180, api_key=api_key
            )
        return self._llm

    def _get_llm_report(self, model_name: str = None):
        """获取报告 LLM 实例（更大的 max_tokens，缓存）"""
        if self._llm_report is None:
            from tradingagents.graph.trading_graph import create_llm_by_provider
            provider = os.getenv("DASHSCOPE_PROVIDER", "dashscope")
            model = model_name or os.getenv("DASHSCOPE_MODEL", "qwen-plus")
            api_key = os.getenv("DASHSCOPE_API_KEY")
            backend_url = os.getenv("DASHSCOPE_BASE_URL", "")
            self._llm_report = create_llm_by_provider(
                provider=provider, model=model, backend_url=backend_url,
                temperature=0.5, max_tokens=8000, timeout=300, api_key=api_key
            )
        return self._llm_report

    def _parse_score_response(self, text: str) -> Dict[str, Any]:
        """解析 LLM 评分响应，从文本中提取 JSON"""
        try:
            # 1. 尝试提取 ```json ... ``` 代码块中的 JSON
            code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if code_block_match:
                candidate = code_block_match.group(1).strip()
                data = json.loads(candidate)
                return self._compute_final_score(data)

            # 2. 尝试直接解析整个文本
            text_stripped = text.strip()
            if text_stripped.startswith('{'):
                data = json.loads(text_stripped)
                return self._compute_final_score(data)

            # 3. 用正则提取第一个完整 JSON 对象（支持嵌套）
            json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return self._compute_final_score(data)

            # 4. 最后尝试：找到 { 和最后一个 } 之间的内容
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                candidate = text[start:end + 1]
                data = json.loads(candidate)
                return self._compute_final_score(data)

        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON 解析失败: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 解析评分响应失败: {e}")

        return {
            "score": 50,
            "rating": "C",
            "summary": "评分解析失败",
            "strengths": [],
            "risks": [],
            "reasoning": f"原始响应: {text[:200]}"
        }

    def _compute_final_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """根据维度分计算综合得分"""
        score = (
            float(data.get("market_performance", 50)) * SCORE_WEIGHTS["market_performance"]
            + float(data.get("fundamentals", 50)) * SCORE_WEIGHTS["fundamentals"]
            + float(data.get("industry_position", 50)) * SCORE_WEIGHTS["industry_position"]
            + float(data.get("news_sentiment", 50)) * SCORE_WEIGHTS["news_sentiment"]
            + float(data.get("valuation", 50)) * SCORE_WEIGHTS["valuation"]
        )
        data["score"] = round(score, 1)
        data["rating"] = rating_from_score(score)
        return data

    def score_single_stock(
        self,
        stock: Dict[str, Any],
        model_name: str,
        analysis_date: str,
        progress_callback: Callable = None,
        stock_start_callback: Callable = None,
    ) -> Dict[str, Any]:
        """
        对单只股票：获取数据 + LLM评分（在线程中调用）

        Returns:
            Dict: 包含评分结果的完整股票信息
        """
        code = stock.get("code", "")
        name = stock.get("name", "")
        total = stock.get("total", 0)

        logger.info(f"🔍 [评分] 开始分析 {code} {name}")

        if stock_start_callback:
            stock_start_callback({
                "code": code,
                "name": name,
                "rank": stock.get("rank", 0),
                "index": stock.get("rank", 0),
                "total": total,
            })

        # 1. 获取数据
        if progress_callback:
            progress_callback("stock_progress", {
                "code": code, "phase": "fetching_data",
                "message": f"正在获取 {code} {name} 的数据...",
            })
        data = self.fetch_stock_data(code, analysis_date)

        # 2. 构建评分提示词
        prompt = build_stock_score_prompt(
            stock_code=code,
            stock_name=name,
            market_data=data.get("market_data", ""),
            fundamentals_data=data.get("fundamentals_data", ""),
            news_data=data.get("news_data", ""),
            industry=stock.get("industry", ""),
            total_mv=stock.get("total_mv"),
            pe_ttm=stock.get("pe_ttm"),
        )

        if progress_callback:
            progress_callback("stock_progress", {
                "code": code, "phase": "scoring",
                "message": f"AI 正在对 {code} {name} 评分...",
            })

        # 3. 调用 LLM 评分
        from langchain_core.messages import HumanMessage
        llm = self._get_llm(model_name)
        response = llm.invoke([HumanMessage(content=prompt)])
        score_result = self._parse_score_response(response.content)

        logger.info(f"✅ [评分] {code} {name}: {score_result['score']}分 ({score_result['rating']}级)")

        return {
            "code": code,
            "name": name,
            "industry": stock.get("industry", ""),
            "total_mv": stock.get("total_mv"),
            "pe_ttm": stock.get("pe_ttm"),
            "market_data": data.get("market_data", ""),
            "fundamentals_data": data.get("fundamentals_data", ""),
            "news_data": data.get("news_data", ""),
            "score": score_result["score"],
            "rating": score_result["rating"],
            "rating_score": score_result,
            "summary": score_result.get("summary", ""),
            "strengths": score_result.get("strengths", []),
            "risks": score_result.get("risks", []),
            "reasoning": score_result.get("reasoning", ""),
            "rank": stock.get("rank", 0),
        }

    # ==================== 多线程并发分析 ====================

    def analyze_stocks_concurrent(
        self,
        stocks: List[Dict[str, Any]],
        analysis_date: str,
        model_name: str = None,
        progress_callback: Callable = None,
        stock_scored_callback: Callable = None,
        stock_start_callback: Callable = None,
    ) -> List[Dict[str, Any]]:
        """
        多线程并发分析多只股票

        Args:
            stocks: 排名后的股票列表（已含 rank 字段）
            analysis_date: 分析日期
            model_name: LLM 模型名
            progress_callback: 进度回调 fn(phase, data_dict)
            stock_scored_callback: 单股评分完成回调 fn(result)
            stock_start_callback: 单股开始分析回调 fn(stock_info)

        Returns:
            List[Dict]: 按原始排名排序的评分结果
        """
        total = len(stocks)
        logger.info(f"🚀 [多线程] 开始并发分析 {total} 只股票，max_workers=3")

        results_map: Dict[str, Dict] = {}  # code -> result
        future_to_stock: Dict[Future, Dict[str, Any]] = {}

        # 提交所有任务
        for i, stock in enumerate(stocks):
            stock["rank"] = i + 1
            stock["total"] = total
            future = self._thread_pool.submit(
                self.score_single_stock,
                stock,
                model_name,
                analysis_date,
                progress_callback,
                stock_start_callback,
            )
            future_to_stock[future] = stock

        # 收集结果
        completed = 0
        for future in as_completed(future_to_stock):
            stock_info = future_to_stock[future]
            code = stock_info.get("code", "")
            completed += 1
            try:
                result = future.result()
                results_map[code] = result
                logger.info(f"✅ [多线程] ({completed}/{total}) {code} {result.get('name')} 评分完成: {result['score']}分 ({result['rating']}级)")

                if stock_scored_callback:
                    stock_scored_callback(result)

                if progress_callback:
                    progress_callback("scoring", {
                        "completed": completed,
                        "total": total,
                        "code": code,
                    })

            except Exception as e:
                logger.error(f"❌ [多线程] {code} 分析失败: {e}")
                results_map[code] = {
                    "code": code,
                    "name": "",
                    "score": 0,
                    "rating": "D",
                    "summary": f"分析失败: {e}",
                    "strengths": [],
                    "risks": [],
                    "reasoning": str(e),
                    "error": str(e),
                    "rank": stock_info.get("rank", 0),
                }
                if progress_callback:
                    progress_callback("scoring", {
                        "completed": completed,
                        "total": total,
                        "code": code,
                        "error": str(e),
                    })

        # 按原始排名排序
        ordered_results = []
        for stock in stocks:
            code = stock.get("code", "")
            if code in results_map:
                r = results_map[code]
                r["rank"] = stock.get("rank", 0)
                ordered_results.append(r)

        logger.info(f"✅ [多线程] 并发分析完成，共 {len(ordered_results)} 只股票")
        return ordered_results

    # ==================== 汇总报告 ====================

    def build_summary_report_prompt(
        self,
        sector: str,
        scored_stocks: List[Dict[str, Any]],
        analysis_date: str,
    ) -> str:
        """构建汇总报告提示词"""
        # 排名表格
        table_rows = []
        for s in scored_stocks:
            score = s.get("score", 0)
            rating = s.get("rating", "?")
            mv = s.get("total_mv")
            mv_str = f"{mv:.2f}亿" if mv else "?"
            table_rows.append(
                f"| {s.get('rank', '?')} | {s.get('code', '?')} | {s.get('name', '?')} | {mv_str} | {score} | {rating} | {s.get('summary', '')} |"
            )

        table = "\n".join([
            "| 排名 | 代码 | 名称 | 市值 | 评分 | 评级 | 摘要 |",
            "|------|------|------|------|------|------|------|",
        ] + table_rows)

        # 详细分析
        detail_parts = []
        for s in scored_stocks:
            detail = f"""### {s.get('rank', '?')}. {s.get('code', '?')} {s.get('name', '?')}
- **评分**: {s.get('score', 0)}分 ({s.get('rating', '?')}级)
- **行业**: {s.get('industry', '')}
- **优势**: {', '.join(s.get('strengths', [])) if s.get('strengths') else '暂无'}
- **风险**: {', '.join(s.get('risks', [])) if s.get('risks') else '暂无'}
- **分析**: {s.get('reasoning', '')}
"""
            detail_parts.append(detail)

        details = "\n".join(detail_parts)

        return f"""你是一位资深的A股板块分析师，请基于以下评分结果，对"{sector}"板块生成一份专业的投资分析报告。

## 分析日期
{analysis_date}

## 板块评分排名
{table}

## 各股票详细分析
{details}

## 报告要求

请生成一份完整的 Markdown 格式报告，包含：

### 1. 板块综述
- 板块整体特征与估值水平
- 当前市场环境下的板块定位

### 2. 排名解析
- 对排名前5的股票进行重点评述
- 分析高评分和低评分股票的原因

### 3. 投资建议
- 板块配置建议（超配/标配/低配）
- 重点推荐标的（Top 3-5，含理由）
- 需要回避的标的及原因

### 4. 风险提示
- 板块系统性风险
- 个股特有风险

请用中文撰写，数据驱动，客观专业。
"""

    def generate_final_report(
        self,
        prompt: str,
        model_name: str = None,
    ) -> str:
        """调用 LLM 生成最终报告"""
        try:
            from langchain_core.messages import HumanMessage
            llm = self._get_llm_report(model_name)
            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            logger.error(f"❌ 生成最终报告失败: {e}")
            return f"报告生成失败: {e}"

    # ==================== 主入口 ====================

    def analyze_sector(
        self,
        sector: str,
        max_stocks: int = 20,
        analysis_date: str = None,
        model_name: str = None,
        progress_callback: Callable = None,
        stock_scored_callback: Callable = None,
        stock_start_callback: Callable = None,
    ) -> Dict[str, Any]:
        """
        板块分析主入口

        Args:
            sector: 板块名称
            max_stocks: 最大分析股票数
            analysis_date: 分析日期
            model_name: LLM 模型
            progress_callback: fn(phase, data_dict) 进度回调
            stock_scored_callback: fn(stock_result) 单股评分完成回调
            stock_start_callback: fn(stock_info) 单股开始分析回调

        Returns:
            Dict: 完整分析结果
        """
        if analysis_date is None:
            analysis_date = datetime.now().strftime("%Y-%m-%d")

        analysis_id = str(uuid.uuid4())
        start_time = datetime.now()

        logger.info(f"🚀 [板块分析] 开始: sector={sector}, max={max_stocks}")

        # 阶段1: 搜索板块股票
        if progress_callback:
            progress_callback("searching", {"message": f"正在搜索板块「{sector}」的股票...", "total": max_stocks, "completed": 0})
        all_stocks = self.get_sector_stocks(sector)
        if not all_stocks:
            return {"analysis_id": analysis_id, "sector": sector, "error": f"未找到板块 '{sector}' 的相关股票"}

        # 阶段2: 按市值排名
        if progress_callback:
            progress_callback("ranking", {"message": f"正在按市值排名...", "total": max_stocks, "completed": 0})
        ranked = self.rank_stocks_by_market_cap(all_stocks, max_stocks)
        if not ranked:
            return {"analysis_id": analysis_id, "sector": sector, "error": "股票排名失败"}

        # 阶段3: 多线程并发分析
        scored_stocks = self.analyze_stocks_concurrent(
            stocks=ranked,
            analysis_date=analysis_date,
            model_name=model_name,
            progress_callback=progress_callback,
            stock_scored_callback=stock_scored_callback,
            stock_start_callback=stock_start_callback,
        )

        # 阶段4: 汇总报告
        if progress_callback:
            progress_callback("reporting", {"message": "正在生成汇总报告...", "total": 1, "completed": 0})
        summary_prompt = self.build_summary_report_prompt(sector, scored_stocks, analysis_date)
        report = self.generate_final_report(summary_prompt, model_name)

        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ [板块分析] 完成，耗时 {execution_time:.2f}秒")

        if progress_callback:
            progress_callback("complete", {"message": "分析完成", "total": 1, "completed": 1})

        return {
            "analysis_id": analysis_id,
            "sector": sector,
            "analysis_date": analysis_date,
            "max_stocks": max_stocks,
            "total_found": len(all_stocks),
            "stocks_analyzed": len(scored_stocks),
            "ranked_stocks": ranked,
            "scored_stocks": scored_stocks,
            "report": report,
            "execution_time": execution_time,
            "error": None,
        }


# 单例
_sector_analysis_service: Optional[SectorAnalysisService] = None


def get_sector_analysis_service() -> SectorAnalysisService:
    global _sector_analysis_service
    if _sector_analysis_service is None:
        _sector_analysis_service = SectorAnalysisService()
    return _sector_analysis_service