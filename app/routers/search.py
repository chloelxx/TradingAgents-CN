"""
AI 股票筛选 API 路由
使用 LLM 驱动的深度筛选，支持流式返回
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import json
import asyncio
import os
from datetime import datetime

from app.routers.auth_db import get_current_user
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import create_llm_by_provider

# 导入获取股票数据的工具
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger("webapi.search")


# ==================== 板块映射与股票获取函数 ====================

def get_sector_mapping() -> Dict[str, List[str]]:
    """
    获取板块与对应的股票代码映射
    这里使用行业关键词映射，实际应该从Tushare等数据源获取
    """
    return {
        "AI": ["科大讯飞", "汇纳科技", "云从科技", "同花顺", "东方财富"],
        "机器人": ["埃斯顿", "发那科", "库卡", "新松机器人", "天机机器人"],
        "芯片半导体": ["中芯国际", "北京君正", "卓胜微", "芯朋微", "斯达半导"],
        "存储": ["长江存储", "紫光国芯", "忆芯科技", "北京君正", "兆易创新"],
        "陶瓷材料": ["三环集团", "瑞泰科技", "宏达新材", "南京高精", "国瓷材料"],
    }


async def get_sector_stocks_from_tushare(sector_keywords: List[str], limit: int = 100) -> List[Dict[str, Any]]:
    """
    从Tushare获取特定板块的股票列表
    """
    if not TUSHARE_AVAILABLE:
        logger.warning("⚠️ Tushare未安装，使用本地映射数据")
        return []
    
    try:
        pro = ts.pro_connect()
        stocks = []
        
        # 使用stock_basic接口获取所有股票
        df = pro.stock_basic(exchange='', list_status='L')
        
        if df is not None and not df.empty:
            # 按行业筛选（需要使用industry字段或name字段中的关键词匹配）
            for keyword in sector_keywords:
                filtered = df[
                    df['name'].str.contains(keyword, case=False, na=False) |
                    df['industry'].str.contains(keyword, case=False, na=False)
                ]
                for _, row in filtered.iterrows():
                    stocks.append({
                        'code': row['ts_code'],
                        'name': row['name'],
                        'industry': row.get('industry', ''),
                        'market': row.get('market', ''),
                        'list_date': row.get('list_date', '')
                    })
        
        return stocks[:limit] if len(stocks) > limit else stocks
        
    except Exception as e:
        logger.error(f"❌ Tushare获取板块股票失败: {e}")
        return []


async def get_sector_stocks_from_akshare(sector_keywords: List[str], limit: int = 100) -> List[Dict[str, Any]]:
    """
    从AKShare获取特定板块的股票列表
    """
    if not AKSHARE_AVAILABLE:
        logger.warning("⚠️ AKShare未安装")
        return []
    
    try:
        # 使用AKShare获取股票列表
        stock_list = ak.stock_basic_info_sina()
        
        stocks = []
        if stock_list is not None and not stock_list.empty:
            for keyword in sector_keywords:
                # 根据名称和行业关键词筛选
                filtered = stock_list[
                    stock_list['股票名称'].str.contains(keyword, case=False, na=False)
                ]
                for _, row in filtered.iterrows():
                    stocks.append({
                        'code': row['股票代码'],
                        'name': row['股票名称'],
                        'industry': row.get('行业', ''),
                        'market': row.get('市场', ''),
                    })
        
        return stocks[:limit] if len(stocks) > limit else stocks
        
    except Exception as e:
        logger.error(f"❌ AKShare获取板块股票失败: {e}")
        return []


async def fetch_sector_stocks(sectors: Optional[List[str]] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    获取指定板块的股票列表，支持多数据源降级
    """
    if not sectors:
        # 使用所有可用板块
        sectors = list(get_sector_mapping().keys())
    
    logger.info(f"📊 [筛选] 开始获取板块股票: {sectors}")
    
    all_stocks = []
    seen_codes = set()
    
    # 优先使用Tushare，失败则使用AKShare
    tushare_stocks = await get_sector_stocks_from_tushare(sectors, limit)
    
    for stock in tushare_stocks:
        code = stock['code']
        if code not in seen_codes:
            all_stocks.append(stock)
            seen_codes.add(code)
    
    # 如果Tushare数据不足，使用AKShare补充
    if len(all_stocks) < limit:
        akshare_stocks = await get_sector_stocks_from_akshare(
            sectors, 
            limit - len(all_stocks)
        )
        
        for stock in akshare_stocks:
            code = stock['code']
            if code not in seen_codes:
                all_stocks.append(stock)
                seen_codes.add(code)
    
    logger.info(f"✅ [筛选] 成功获取 {len(all_stocks)} 只股票")
    return all_stocks[:limit]


async def get_news_for_stocks(stock_codes: List[str], hours_back: int = 24) -> Dict[str, List[Dict[str, Any]]]:
    """
    批量获取股票新闻
    """
    logger.info(f"📰 [新闻] 开始获取 {len(stock_codes)} 只股票的新闻")
    
    news_map = {}
    
    try:
        from app.services.news_data_service import get_news_data_service, NewsQueryParams
        from datetime import timedelta
        
        news_service = await get_news_data_service()
        
        for code in stock_codes:
            try:
                # 标准化股票代码（去除.SH .SZ等后缀）
                clean_code = code.replace('.SH', '').replace('.SZ', '').replace('.SS', '')
                
                # 查询该股票的新闻
                start_time = datetime.utcnow() - timedelta(hours=hours_back)
                params = NewsQueryParams(
                    symbol=clean_code,
                    start_time=start_time,
                    limit=5,
                    sort_by="publish_time",
                    sort_order=-1
                )
                
                news_list = await news_service.query_news(params)
                news_map[code] = news_list if news_list else []
                
            except Exception as e:
                logger.warning(f"⚠️ [新闻] 获取{code}的新闻失败: {e}")
                news_map[code] = []
        
        logger.info(f"✅ [新闻] 成功获取新闻，共 {len([n for nlist in news_map.values() for n in nlist])} 条")
        return news_map
        
    except Exception as e:
        logger.error(f"❌ [新闻] 新闻服务异常: {e}")
        return {code: [] for code in stock_codes}


router = APIRouter()
logger = logging.getLogger("webapi.search")


class StockSearchRequest(BaseModel):
    """股票筛选请求"""
    market: str = Field(default="CN", description="市场：CN-中国，US-美国，HK-香港")
    date: Optional[str] = Field(default=None, description="筛选日期，格式：YYYY-MM-DD，默认为当前日期")
    max_results: int = Field(default=30, description="最大返回结果数量，默认30只")
    include_details: bool = Field(default=True, description="是否包含详细分析")
    sectors: Optional[List[str]] = Field(
        default=None, 
        description="指定板块列表，如：['AI', '机器人', '芯片半导体', '存储', '陶瓷材料']，为空则筛选所有板块"
    )
    include_news: bool = Field(default=True, description="是否包含股票新闻数据")


class StockSearchResponse(BaseModel):
    """股票筛选响应"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


def get_default_llm():
    """
    获取默认 LLM 实例
    复用项目已有的配置和创建逻辑，自动检测环境变量中的API密钥
    """
    # 自动检测 LLM 提供商（优先顺序：DeepSeek > DashScope > OpenAI）
    # 使用dashscope模型
    provider = "dashscope"
    model = os.getenv("DASHSCOPE_MODEL", "deepseek-v4-pro")
    backend_url = os.getenv("DEEPSEEK_BASE_URL", "")  # DashScope 使用默认 URL
    logger.info(f"🔧 检测到 DashScope API Key，使用阿里百炼 LLM")
    api_key = os.getenv("DEEPSEEK_API_KEY", None)

    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4000"))
    timeout = int(os.getenv("LLM_TIMEOUT", "180"))
    
    return create_llm_by_provider(
        provider=provider,
        model=model,
        backend_url=backend_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        api_key=api_key
    )


async def stock_screening_stream_generator(request: StockSearchRequest, user_id: str):
    """
    生成股票筛选的流式响应
    
    核心流程：
    1. 获取特定板块的A股股票列表
    2. 获取这些股票的市场新闻
    3. 调用 create_china_stock_screener 函数进行筛选
    4. 返回最好的30只股票的研究报告
    """
    try:
        # 发送开始事件
        yield f"event: start\ndata: {json.dumps({'message': '开始 AI 股票筛选...', 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"
        
        # 步骤1: 获取指定板块的股票列表
        yield f"event: status\ndata: {json.dumps({'message': f'正在获取板块股票列表（板块：{", ".join(request.sectors or ["全部"])}）...', 'progress': 5}, ensure_ascii=False)}\n\n"
        
        sector_stocks = await fetch_sector_stocks(
            sectors=request.sectors,
            limit=100  # 先获取较多股票，然后筛选出最好的30只
        )
        
        if not sector_stocks:
            yield f"event: error\ndata: {json.dumps({'error': '无法获取板块股票数据'}, ensure_ascii=False)}\n\n"
            return
        
        stock_codes = [s['code'] for s in sector_stocks]
        logger.info(f"📊 获取到 {len(stock_codes)} 只股票: {stock_codes[:10]}...")
        
        yield f"event: status\ndata: {json.dumps({'message': f'成功获取 {len(stock_codes)} 只板块股票', 'progress': 15}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.3)
        
        # 步骤2: 获取股票新闻（如果启用）
        if request.include_news:
            yield f"event: status\ndata: {json.dumps({'message': '正在获取股票市场新闻...', 'progress': 25}, ensure_ascii=False)}\n\n"
            
            news_map = await get_news_for_stocks(stock_codes, hours_back=48)
            
            yield f"event: status\ndata: {json.dumps({'message': f'成功获取股票新闻', 'progress': 35}, ensure_ascii=False)}\n\n"
        else:
            news_map = {}
        
        await asyncio.sleep(0.3)
        
        # 步骤3: 初始化LLM和工具包
        yield f"event: status\ndata: {json.dumps({'message': '正在初始化AI模型...', 'progress': 40}, ensure_ascii=False)}\n\n"
        
        # 获取LLM实例
        llm = get_default_llm()
        
        # 创建工具包
        from tradingagents.agents.utils.agent_utils import Toolkit
        toolkit = Toolkit()
        
        yield f"event: status\ndata: {json.dumps({'message': 'AI模型初始化完成', 'progress': 50}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.3)
        
        # 步骤4: 创建中国股票筛选器并执行筛选
        yield f"event: status\ndata: {json.dumps({'message': '正在创建股票筛选器...', 'progress': 55}, ensure_ascii=False)}\n\n"
        
        # 调用项目中封装的 create_china_stock_screener 函数
        from tradingagents.agents.analysts.china_market_analyst import create_china_stock_screener
        screener_node = create_china_stock_screener(llm, toolkit)
        
        yield f"event: status\ndata: {json.dumps({'message': f'开始执行A股板块筛选（共 {len(stock_codes)} 只股票）...', 'progress': 60}, ensure_ascii=False)}\n\n"
        
        # 准备状态参数，包含股票和新闻信息
        state = {
            "trade_date": request.date or datetime.now().strftime("%Y-%m-%d"),
            "messages": [],
            "sector_stocks": sector_stocks,
            "stock_news": news_map,
            "max_results": request.max_results,  # 限制结果为30只
        }
        
        # 执行筛选
        result = screener_node(state)
        
        yield f"event: status\ndata: {json.dumps({'message': '筛选分析完成，正在整理报告...', 'progress': 80}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.3)
        
        # 步骤5: 提取并返回筛选结果
        screening_report = result.get("stock_screening_report", "")
        
        if not screening_report:
            screening_report = "未生成筛选报告"
        
        # 限制结果为指定数量（默认30只）
        # 在报告中添加板块和新闻信息摘要
        summary_info = f"""
## 📊 筛选摘要
- **筛选日期**: {state['trade_date']}
- **目标板块**: {", ".join(request.sectors or ["全部A股"])}
- **参与筛选股票数**: {len(stock_codes)}只
- **最大结果数量**: {request.max_results}只
- **包含新闻数据**: {"是" if request.include_news else "否"}

"""
        
        final_report = summary_info + screening_report
        
        # 发送结果
        yield f"event: result\ndata: {json.dumps({'report': final_report, 'sender': result.get('sender', 'ChinaStockScreener'), 'progress': 100}, ensure_ascii=False)}\n\n"
        
        # 发送完成事件
        yield f"event: complete\ndata: {json.dumps({'message': '筛选完成', 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        logger.error(f"股票筛选失败: {e}", exc_info=True)
        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


@router.post("/all", response_class=StreamingResponse)
async def search_all_stocks(
    request: StockSearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    AI 股票筛选接口 - 流式返回
    
    核心功能：
    1. 获取A股市场特定板块的所有股票数据
    2. 批量获取这些股票的市场新闻
    3. 调用项目的 create_china_stock_screener 进行深度筛选
    4. 返回最好的30只股票的详细研究报告
    
    支持的板块：
    - AI: 人工智能相关
    - 机器人: 机器人和自动化
    - 芯片半导体: 芯片设计、制造、封测
    - 存储: 存储芯片、存储器件
    - 陶瓷材料: 陶瓷材料和精细陶瓷
    - 不指定: 则筛选全部A股
    
    Args:
        request: 筛选请求参数，包含：
            - market: 市场类型 (默认CN-中国A股)
            - date: 筛选日期 (默认当前日期)
            - max_results: 最大返回结果数 (默认30只)
            - sectors: 指定板块列表 (可选，示例: ["AI", "芯片半导体"])
            - include_news: 是否包含新闻数据 (默认True)
        - user: 当前用户（自动注入）
    
    Returns:
        StreamingResponse: SSE 流式响应
    
    示例请求：
    ```
    POST /api/search/all
    {
        "market": "CN",
        "date": "2026-06-17",
        "max_results": 30,
        "sectors": ["AI", "芯片半导体", "存储"],
        "include_news": true
    }
    ```
    
    流式事件类型：
    - start: 开始筛选
    - status: 进度更新
    - result: 筛选结果（包含报告和元数据）
    - complete: 筛选完成
    - error: 错误发生
    """
    try:
        logger.info(f"[AI筛选] 用户 {user['id']} 发起筛选请求: {request}")
        
        return StreamingResponse(
            stock_screening_stream_generator(request, user["id"]),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        logger.error(f"[AI筛选] 接口调用失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"筛选失败: {str(e)}")


@router.post("/test", response_model=StockSearchResponse)
async def test_search(
    request: StockSearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    测试接口 - 非流式返回，用于调试
    
    Args:
        request: 筛选请求参数（支持板块筛选）
        user: 当前用户（自动注入）
    
    Returns:
        StockSearchResponse: 筛选结果
    """
    try:
        logger.info(f"[AI筛选-测试] 用户 {user['id']} 发起测试请求，板块: {request.sectors}")
        
        # 获取板块股票
        sector_stocks = await fetch_sector_stocks(
            sectors=request.sectors,
            limit=100
        )
        
        if not sector_stocks:
            return StockSearchResponse(
                success=False,
                message="无法获取板块股票数据"
            )
        
        stock_codes = [s['code'] for s in sector_stocks]
        logger.info(f"📊 测试获取到 {len(stock_codes)} 只股票")
        
        # 获取新闻
        news_map = {}
        if request.include_news:
            news_map = await get_news_for_stocks(stock_codes, hours_back=48)
        
        # 获取LLM实例
        llm = get_default_llm()
        
        # 创建工具包
        from tradingagents.agents.utils.agent_utils import Toolkit
        toolkit = Toolkit()
        
        # 创建筛选器
        from tradingagents.agents.analysts.china_market_analyst import create_china_stock_screener
        screener_node = create_china_stock_screener(llm, toolkit)
        
        # 执行筛选
        state = {
            "trade_date": request.date or datetime.now().strftime("%Y-%m-%d"),
            "messages": [],
            "sector_stocks": sector_stocks,
            "stock_news": news_map,
            "max_results": request.max_results,
        }
        
        result = screener_node(state)
        
        # 提取报告
        screening_report = result.get("stock_screening_report", "")
        
        # 添加摘要信息
        summary_info = f"""## 📊 筛选摘要
- **筛选日期**: {state['trade_date']}
- **目标板块**: {", ".join(request.sectors or ["全部A股"])}
- **参与筛选股票数**: {len(stock_codes)}只
- **最大结果数量**: {request.max_results}只

"""
        
        final_report = summary_info + screening_report
        
        return StockSearchResponse(
            success=True,
            data={
                "report": final_report,
                "sender": result.get("sender", "ChinaStockScreener"),
                "timestamp": datetime.now().isoformat(),
                "stocks_analyzed": len(stock_codes),
                "sectors": request.sectors or ["全部A股"]
            },
            message="筛选成功"
        )
        
    except Exception as e:
        logger.error(f"[AI筛选-测试] 测试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"筛选失败: {str(e)}")
