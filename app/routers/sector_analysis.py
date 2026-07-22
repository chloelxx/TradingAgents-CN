"""
板块分析 API 路由
提供 A股板块（行业/概念）股票的搜索、排名和多线程并发分析接口

核心接口：POST /api/sector/analyze (SSE 流式)
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.services.sector_analysis_service import (
    get_sector_analysis_service,
    rating_label,
)

router = APIRouter()
logger = logging.getLogger("webapi.sector_analysis")


# ==================== 请求/响应模型 ====================

class SectorAnalysisRequest(BaseModel):
    """板块分析请求"""
    sector: str = Field(
        default="AI",
        description="板块/行业名称关键词，如 'AI'、'芯片'、'新能源'、'白酒'、'医药' 等"
    )
    max_stocks: int = Field(
        default=20,
        ge=5,
        le=50,
        description="分析的最大股票数量（默认20，范围5-50）"
    )
    analysis_date: Optional[str] = Field(
        default=None,
        description="分析日期，格式 YYYY-MM-DD，默认当天"
    )
    model_name: Optional[str] = Field(
        default=None,
        description="LLM 模型名称，默认使用环境变量配置"
    )


class SectorSearchRequest(BaseModel):
    """板块搜索请求（仅搜索+排名，不分析）"""
    sector: str = Field(default="AI", description="板块/行业名称关键词")
    max_results: int = Field(default=50, ge=10, le=200, description="最大返回结果数量")


class SectorAnalysisResponse(BaseModel):
    """板块分析响应"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


# ==================== SSE 流式生成器 ====================

async def sector_analysis_stream_generator(
    request: SectorAnalysisRequest,
    user_id: str
):
    """
    板块分析 SSE 流式响应生成器

    事件类型：
    - start          → 开始分析
    - status         → 阶段进度更新 {phase, message, progress}
    - stocks_ranked  → 排名完成 {stocks: [{rank, code, name, market_cap, pe_ttm}]}
    - stock_scored   → 单股评分完成 {code, name, score, rating, summary, strengths, risks}
    - report         → 最终汇总报告 {report: "markdown..."}
    - complete       → 全部完成
    - error          → 错误
    """
    try:
        service = get_sector_analysis_service()

        # ===== 开始 =====
        yield f"event: start\ndata: {json.dumps({'message': f'开始分析板块「{request.sector}」', 'sector': request.sector, 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

        # ===== 阶段1: 搜索板块股票 =====
        yield f"event: status\ndata: {json.dumps({'phase': 'searching', 'message': f'正在搜索板块「{request.sector}」的股票...', 'progress': 5}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)

        all_stocks = service.get_sector_stocks(request.sector)
        if not all_stocks:
            yield f"event: error\ndata: {json.dumps({'error': f'未找到板块「{request.sector}」的相关股票，请检查板块名称是否正确'}, ensure_ascii=False)}\n\n"
            return

        yield f"event: status\ndata: {json.dumps({'phase': 'searching', 'message': f'找到 {len(all_stocks)} 只相关股票', 'progress': 10, 'total_found': len(all_stocks)}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)

        # ===== 阶段2: 按市值排名 =====
        yield f"event: status\ndata: {json.dumps({'phase': 'ranking', 'message': '正在按市值排名...', 'progress': 15}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)

        ranked = service.rank_stocks_by_market_cap(all_stocks, request.max_stocks)
        if not ranked:
            yield f"event: error\ndata: {json.dumps({'error': '股票排名失败'}, ensure_ascii=False)}\n\n"
            return

        # 发送排名结果
        ranked_list = []
        for i, s in enumerate(ranked):
            mv = s.get("total_mv")
            pe = s.get("pe_ttm")
            ranked_list.append({
                "rank": i + 1,
                "code": s.get("code"),
                "name": s.get("name"),
                "market_cap": f"{mv:.2f}亿" if mv else None,
                "pe_ttm": f"{pe:.2f}" if pe else None,
                "industry": s.get("industry", ""),
            })

        yield f"event: stocks_ranked\ndata: {json.dumps({'stocks': ranked_list, 'count': len(ranked_list)}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)

        yield f"event: status\ndata: {json.dumps({'phase': 'analyzing', 'message': f'排名完成，开始并发分析前 {len(ranked)} 只股票（3线程并发）...', 'progress': 20}, ensure_ascii=False)}\n\n"

        # ===== 阶段3: 多线程并发分析（在后台线程中执行） =====
        # 使用队列收集结果，避免阻塞事件循环
        result_queue: asyncio.Queue = asyncio.Queue()

        def on_stock_scored(stock_result):
            """单股评分完成 → 放入异步队列"""
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        result_queue.put(("stock_scored", stock_result)),
                        loop
                    )
            except Exception:
                pass

        def on_stock_start(stock_info):
            """单股开始分析 → 放入异步队列"""
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        result_queue.put(("stock_start", stock_info)),
                        loop
                    )
            except Exception:
                pass

        def on_progress(phase, data=None):
            """进度回调（新签名: fn(phase, data_dict)）"""
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    payload = {"phase": phase}
                    if data:
                        payload.update(data)
                    event_type = "stock_progress" if phase == "stock_progress" else "progress"
                    asyncio.run_coroutine_threadsafe(
                        result_queue.put((event_type, payload)),
                        loop
                    )
            except Exception:
                pass

        # 在线程池中执行分析（不阻塞事件循环）
        def run_analysis():
            return service.analyze_sector(
                sector=request.sector,
                max_stocks=request.max_stocks,
                analysis_date=request.analysis_date,
                model_name=request.model_name,
                progress_callback=on_progress,
                stock_scored_callback=on_stock_scored,
                stock_start_callback=on_stock_start,
            )

        analysis_result = None
        loop = asyncio.get_event_loop()
        analysis_future = loop.run_in_executor(
            None,
            run_analysis
        )

        # 消费队列中的结果，同时等待分析完成
        completed = 0
        total = len(ranked)
        last_progress = 20

        while not analysis_future.done() or not result_queue.empty():
            try:
                event_type, data = await asyncio.wait_for(result_queue.get(), timeout=0.5)
                if event_type == "stock_start":
                    yield f"event: stock_start\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)
                elif event_type == "stock_scored":
                    completed += 1
                    progress = 20 + int((completed / total) * 45)  # 20% → 65%
                    if progress > last_progress:
                        last_progress = progress
                    total_mv = data.get('total_mv')
                    market_cap_str = f"{total_mv:.2f}亿" if total_mv else None
                    stock_data = {
                        'code': data.get('code'),
                        'name': data.get('name'),
                        'score': data.get('score'),
                        'rating': data.get('rating'),
                        'rating_label': rating_label(data.get('rating', 'C')),
                        'summary': data.get('summary', ''),
                        'strengths': data.get('strengths', []),
                        'risks': data.get('risks', []),
                        'market_cap': market_cap_str,
                        'completed': completed,
                        'total': total,
                        'progress': progress,
                    }
                    yield f"event: stock_scored\ndata: {json.dumps(stock_data, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)
                elif event_type == "stock_progress":
                    yield f"event: stock_progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)
                elif event_type == "progress":
                    phase = data.get("phase", "")
                    msg = data.get("message", "")
                    if not msg:
                        msg = {
                            "searching": "正在搜索板块股票...",
                            "ranking": "正在按市值排名...",
                            "reporting": "正在生成汇总报告...",
                        }.get(phase, "处理中...")
                    comp = data.get("completed", 0)
                    if phase == "scoring":
                        progress = 20 + int((comp / total) * 45) if total else 20
                        msg = f"AI评分中 ({comp}/{total})"
                    elif phase == "reporting":
                        progress = 70
                    elif phase == "complete":
                        progress = 100
                    else:
                        progress = last_progress
                    if progress > last_progress:
                        last_progress = progress
                    extra = {}
                    if data.get("code"):
                        extra["code"] = data["code"]
                    yield f"event: status\ndata: {json.dumps({'phase': phase, 'message': msg, 'progress': progress, 'scored': comp, 'total': total, **extra}, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                pass

        # 获取最终结果
        analysis_result = await analysis_future

        if analysis_result.get("error"):
            yield f"event: error\ndata: {json.dumps({'error': analysis_result['error']}, ensure_ascii=False)}\n\n"
            return

        # ===== 阶段4: 最终报告 =====
        yield f"event: status\ndata: {json.dumps({'phase': 'reporting', 'message': 'AI 评分完成，正在生成汇总报告...', 'progress': 70}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)

        if analysis_result.get("report"):
            yield f"event: report\ndata: {json.dumps({'report': analysis_result['report'], 'sector': request.sector, 'stocks_analyzed': analysis_result.get('stocks_analyzed', 0)}, ensure_ascii=False)}\n\n"

        yield f"event: status\ndata: {json.dumps({'phase': 'reporting', 'message': '报告生成完成', 'progress': 95}, ensure_ascii=False)}\n\n"

        # ===== 完成 =====
        yield f"event: complete\ndata: {json.dumps({'message': '板块分析完成', 'sector': request.sector, 'stocks_analyzed': analysis_result.get('stocks_analyzed', 0), 'execution_time': analysis_result.get('execution_time', 0), 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error(f"❌ [板块分析] 流式分析失败: {e}", exc_info=True)
        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


# ==================== API 接口 ====================

@router.post("/analyze", response_class=StreamingResponse)
async def analyze_sector(
    request: SectorAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """
    板块分析接口 — SSE 流式返回

    分析指定板块的A股股票：搜索 → 排名 → 多线程并发评分 → 汇总报告

    事件类型：
    - start          → 开始分析
    - status         → 阶段进度 {phase, message, progress}
    - stocks_ranked  → 排名完成 {stocks: [...]}
    - stock_scored   → 单股评分 {code, name, score, rating, summary, strengths, risks}
    - report         → 最终报告 {report: "markdown..."}
    - complete       → 完成
    - error          → 错误

    示例：
    POST /api/sector/analyze
    {"sector": "芯片", "max_stocks": 20}
    """
    try:
        logger.info(f"[板块分析] 用户 {user['id']}: sector={request.sector}, max={request.max_stocks}")
        return StreamingResponse(
            sector_analysis_stream_generator(request, user["id"]),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"[板块分析] 接口失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"板块分析失败: {str(e)}")


@router.post("/search", response_model=SectorAnalysisResponse)
async def search_sector_stocks(
    request: SectorSearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    板块股票搜索 — 仅搜索排名，不分析

    POST /api/sector/search
    {"sector": "芯片", "max_results": 30}
    """
    try:
        logger.info(f"[板块搜索] 用户 {user['id']}: sector={request.sector}")
        service = get_sector_analysis_service()
        all_stocks = service.get_sector_stocks(request.sector, limit=200)
        if not all_stocks:
            return SectorAnalysisResponse(success=False, message=f"未找到板块「{request.sector}」的相关股票")

        ranked = service.rank_stocks_by_market_cap(all_stocks, request.max_results)
        result_stocks = []
        for i, s in enumerate(ranked):
            mv = s.get("total_mv")
            pe = s.get("pe_ttm")
            result_stocks.append({
                "rank": i + 1,
                "code": s.get("code"),
                "name": s.get("name"),
                "industry": s.get("industry", ""),
                "market_cap": f"{mv:.2f}亿" if mv else None,
                "pe_ttm": f"{pe:.2f}" if pe else None,
                "source": s.get("source", "")
            })

        return SectorAnalysisResponse(
            success=True,
            data={"sector": request.sector, "total_found": len(all_stocks),
                  "returned": len(result_stocks), "stocks": result_stocks},
            message=f"找到 {len(all_stocks)} 只股票，返回前 {len(result_stocks)} 只"
        )
    except Exception as e:
        logger.error(f"[板块搜索] 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"板块搜索失败: {str(e)}")


@router.post("/analyze-sync", response_model=SectorAnalysisResponse)
async def analyze_sector_sync(
    request: SectorAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """
    板块分析 — 同步返回（非流式）

    POST /api/sector/analyze-sync
    {"sector": "AI", "max_stocks": 20}
    """
    try:
        logger.info(f"[板块分析-同步] 用户 {user['id']}: sector={request.sector}")
        service = get_sector_analysis_service()
        result = service.analyze_sector(
            sector=request.sector,
            max_stocks=request.max_stocks,
            analysis_date=request.analysis_date,
            model_name=request.model_name,
        )

        if result.get("error"):
            return SectorAnalysisResponse(success=False, message=result["error"])

        scored_summary = []
        for s in result.get("scored_stocks", []):
            mv = s.get("total_mv")
            scored_summary.append({
                "rank": s.get("rank"),
                "code": s.get("code"),
                "name": s.get("name"),
                "market_cap": f"{mv:.2f}亿" if mv else None,
                "score": s.get("score"),
                "rating": s.get("rating"),
                "rating_label": rating_label(s.get("rating", "C")),
                "summary": s.get("summary", ""),
                "strengths": s.get("strengths", []),
                "risks": s.get("risks", []),
            })

        return SectorAnalysisResponse(
            success=True,
            data={
                "analysis_id": result["analysis_id"],
                "sector": result["sector"],
                "analysis_date": result["analysis_date"],
                "stocks_analyzed": result["stocks_analyzed"],
                "total_found": result["total_found"],
                "report": result["report"],
                "execution_time": result["execution_time"],
                "scored_stocks": scored_summary,
            },
            message=f"板块「{request.sector}」分析完成，耗时 {result['execution_time']:.2f}秒"
        )
    except Exception as e:
        logger.error(f"[板块分析-同步] 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"板块分析失败: {str(e)}")