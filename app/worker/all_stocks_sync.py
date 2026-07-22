"""
全量A股股票信息同步 Worker
提供定时任务入口函数，供调度器调用
"""

import logging
from datetime import datetime

logger = logging.getLogger("worker.all_stocks_sync")


async def run_all_stocks_info_sync():
    """
    定时任务：同步全量A股股票信息到 MongoDB

    此函数由 APScheduler 定时调用（默认每天一次），
    获取所有A股股票的详细信息（代码、名称、行业、市值、PE等），
    存入 all_stocks_info 集合。
    """
    logger.info("=" * 60)
    logger.info("📊 [定时任务] 全量A股股票信息同步 - 开始")
    logger.info("=" * 60)

    start_time = datetime.now()

    try:
        # 在线程池中执行同步操作（避免阻塞事件循环）
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _sync_impl)

        elapsed = (datetime.now() - start_time).total_seconds()

        if result.get("success"):
            logger.info("=" * 60)
            logger.info(f"✅ [定时任务] 全量同步完成: {result['count']} 只股票, 耗时 {elapsed:.2f}秒")
            logger.info("=" * 60)
        else:
            logger.error(f"❌ [定时任务] 全量同步失败: {result.get('error')}, 耗时 {elapsed:.2f}秒")

        return result

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ [定时任务] 全量同步异常: {e}, 耗时 {elapsed:.2f}秒", exc_info=True)
        return {"success": False, "error": str(e), "elapsed_seconds": elapsed}


def _sync_impl():
    """同步实现（在线程池中执行）"""
    from app.services.all_stocks_info_service import get_all_stocks_service
    service = get_all_stocks_service()
    return service.sync_all_stocks()