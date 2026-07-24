"""
市场数据API路由
提供大盘指数数据获取等功能
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

from app.routers.auth_db import get_current_user
from app.services.market_analysis_service import get_market_analysis_service

router = APIRouter()
logger = logging.getLogger("webapi")


@router.get("/index-data", response_model=Dict[str, Any])
async def get_index_data(
    user: dict = Depends(get_current_user)
):
    """获取主要指数数据（使用AKShare实时数据源）"""
    try:
        logger.info(f"🔍 获取指数数据: {user}")

        market_service = get_market_analysis_service()
        index_data = market_service.fetch_realtime_index_data()

        return {
            "success": True,
            "data": index_data,
            "message": "指数数据获取成功"
        }

    except Exception as e:
        logger.error(f"❌ 获取指数数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))