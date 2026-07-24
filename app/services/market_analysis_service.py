"""
大盘分析服务
使用 AKShare 获取实时指数+市场广度+板块+新闻数据，AI 综合分析，存入数据库
"""

import asyncio
import logging
import datetime
import json
import uuid
import os
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from app.core.database import get_mongo_db
from app.services.memory_state_manager import get_memory_state_manager, TaskStatus

logger = logging.getLogger("market_analysis")

TARGET_INDICES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sz399997": "中证白酒",
    "sh000015": "红利指数",
}

# 用户提供的 AI 分析提示词模板（原文不动）
AI_PROMPT_TEMPLATE = """你是资深A股首席策略分析师，具备宏观、资金面、情绪面、技术面综合研判能力，风格严谨、数据驱动、结论明确、可操作性强。 
 【任务】 
 根据我提供的当日/最新A股大盘数据与市场信息，完成一次完整大盘分析并给出明确可执行的投资策略，输出必须包含以下5个模块，缺一不可： 
 1）大盘核心数据（直接引用我给的数字） 
 上证指数：{点位}点，{涨跌} 
 全市场总成交量：{总成交}亿元；上证成交量：{上证成交}亿元；量能性质（放量/缩量/持平） 
 市场情绪：涨跌家数{涨家数}/{跌家数}、涨停{涨停数}家、连板高度{连板高度}、北向资金{北向}亿 
 2）热门板块与资金流向 
 当日领涨板块（涨幅+核心驱动因素） 
 当日领跌板块（跌幅+核心原因） 
 资金主攻方向（机构/游资/北向分别偏好） 
 板块持续性判断（强/中/弱，理由一句话） 
 3）关键利空与利好消息（只列当日/近期最影响大盘的3–5条） 
 利好：每条一句话，标注影响级别（强/中/弱） 
 利空：每条一句话，标注影响级别（强/中/弱） 
 消息面综合结论：偏多/偏空/中性 
 4）上证指数点位研判（必须量化） 
 当前点位：{点位}
 短期强支撑、弱支撑；强阻力、弱阻力（具体点位） 
 量价匹配：价量齐升/价涨量缩/价跌量增/价跌量缩，结论 
 5）投资策略（必须三选一：买入 / 卖出 / 波段；并给出仓位与操作细节） 
 总体策略：（买入/卖出/波段） 
 仓位建议：（空仓/1–3成/4–6成/7–8成/满仓） 
 若为【买入】：明确入场区间、分批买点、止损位、优先板块/标的类型 
 若为【卖出】：明确减仓区间、止盈位、止损位、优先减仓方向 
 若为【波段】：必须写清楚： 
 ① 高抛区间（具体点位） 
 ② 低吸区间（具体点位） 
 ③ 每次高抛/低吸的仓位比例 
 ④ 止损/止盈条件 
 ⑤ 适合的板块与标的特征 
 【输出要求】 
 语言专业但通俗，结论前置、逻辑清晰、不模棱两可 
 所有策略必须与"当前点位+成交量+消息面"强相关，不能脱离数据 
 不写空话，所有建议必须可直接执行 
 最后加一行：一句话大盘结论（≤20字） 
 下面是本次数据： 
 上证指数：{点位}，涨跌{涨跌} 
 全市场成交量：{总成交}亿，上证成交：{上证成交}亿 
 涨跌家数：{涨家数}/{跌家数}，涨停{涨停数} 
 北向资金：{北向}亿 
 热门板块：{热门板块} 
 利好消息：{利好} 
 利空消息：{利空}"""


class MarketAnalysisService:
    """大盘分析服务"""

    def __init__(self):
        self._thread_pool = ThreadPoolExecutor(max_workers=4)

    # ==================== 公开数据接口 ====================

    def fetch_realtime_index_data(self) -> List[Dict[str, Any]]:
        """获取指数实时数据"""
        try:
            import akshare as ak
            df = ak.stock_zh_index_spot_sina()
            if df is None or df.empty:
                return []

            result = []
            for code, name in TARGET_INDICES.items():
                row = df[df["代码"] == code]
                if row.empty:
                    continue
                r = row.iloc[0]
                result.append({
                    "code": code, "name": name,
                    "price": round(float(r.get("最新价", 0)), 2),
                    "change": round(float(r.get("涨跌额", 0)), 2),
                    "pct_chg": round(float(r.get("涨跌幅", 0)), 2),
                    "open": round(float(r.get("今开", 0)), 2),
                    "high": round(float(r.get("最高", 0)), 2),
                    "low": round(float(r.get("最低", 0)), 2),
                    "pre_close": round(float(r.get("昨收", 0)), 2),
                    "volume": int(r.get("成交量", 0)),
                    "amount": round(float(r.get("成交额", 0)), 2),
                })
            logger.info(f"✅ 指数数据: {len(result)} 个")
            return result
        except Exception as e:
            logger.error(f"❌ 指数数据获取失败: {e}")
            return []

    def fetch_market_breadth(self) -> Dict[str, Any]:
        """获取市场广度数据（涨跌家数、涨停数、北向资金、板块资金流向）"""
        result = {
            "up_count": 0, "down_count": 0, "limit_up_count": 0,
            "north_flow": 0, "top_sectors": [], "bottom_sectors": [],
            "ladder_height": "—",
        }
        try:
            import akshare as ak

            # 1. 涨跌家数 — 从全市场行情计算
            try:
                spot = ak.stock_zh_a_spot_em()
                if spot is not None and not spot.empty:
                    pct = spot["涨跌幅"].astype(float)
                    result["up_count"] = int((pct > 0).sum())
                    result["down_count"] = int((pct < 0).sum())
            except Exception as e:
                logger.warning(f"⚠️ 涨跌家数获取失败: {e}")

            # 2. 涨停板数据
            try:
                zt = ak.stock_zt_pool_em(date=datetime.datetime.now().strftime("%Y%m%d"))
                if zt is not None and not zt.empty:
                    result["limit_up_count"] = len(zt)
            except Exception as e:
                logger.warning(f"⚠️ 涨停板数据获取失败: {e}")

            # 3. 北向资金
            try:
                north = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
                if north is not None and not north.empty:
                    result["north_flow"] = round(float(north.iloc[0].get("value", 0)), 2)
            except Exception as e:
                logger.warning(f"⚠️ 北向资金获取失败: {e}")

            # 4. 行业板块资金流向
            try:
                sector = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流向")
                if sector is not None and not sector.empty:
                    top5 = sector.head(5)
                    bottom5 = sector.tail(5)
                    result["top_sectors"] = [
                        f"{r['名称']}(+{r['涨跌幅']}%)" for _, r in top5.iterrows()
                    ]
                    result["bottom_sectors"] = [
                        f"{r['名称']}({r['涨跌幅']}%)" for _, r in bottom5.iterrows()
                    ]
            except Exception as e:
                logger.warning(f"⚠️ 板块资金流向获取失败: {e}")

            logger.info(f"✅ 市场广度: 涨{result['up_count']}/跌{result['down_count']} "
                        f"涨停{result['limit_up_count']} 北向{result['north_flow']}亿")
        except Exception as e:
            logger.error(f"❌ 市场广度获取失败: {e}")
        return result

    def fetch_market_news(self) -> Dict[str, List[str]]:
        """获取市场新闻（利好/利空分类）"""
        news = {"利好": [], "利空": []}
        try:
            import akshare as ak
            df = ak.news_cctv()
            if df is None or df.empty:
                return news

            good_keywords = ["利好", "增长", "突破", "上升", "回暖", "反弹", "政策支持", "降息", "放水", "流入"]
            bad_keywords = ["利空", "下跌", "风险", "制裁", "加息", "收紧", "流出", "衰退", "危机", "贸易战"]

            for _, row in df.head(20).iterrows():
                title = str(row.get("title", ""))
                content = str(row.get("content", ""))[:80]
                text = title + content
                if any(kw in text for kw in good_keywords):
                    news["利好"].append(title[:80])
                elif any(kw in text for kw in bad_keywords):
                    news["利空"].append(title[:80])

            logger.info(f"✅ 新闻: 利好{len(news['利好'])}条 利空{len(news['利空'])}条")
        except Exception as e:
            logger.warning(f"⚠️ 新闻获取失败: {e}")
        return news

    # ==================== 任务管理 ====================

    async def create_task(self, user_id: str) -> Dict[str, Any]:
        task_id = str(uuid.uuid4())
        logger.info(f"📝 创建大盘分析任务: {task_id}")

        self.memory_manager = get_memory_state_manager()
        await self.memory_manager.create_task(
            task_id=task_id, user_id=user_id,
            stock_code="MARKET", stock_name="大盘分析",
            parameters={"market_type": "A股"}
        )

        db = get_mongo_db()
        await db.analysis_tasks.update_one(
            {"task_id": task_id},
            {"$setOnInsert": {
                "task_id": task_id, "user_id": user_id,
                "stock_code": "MARKET", "stock_name": "大盘分析",
                "status": "pending", "progress": 0,
                "created_at": datetime.datetime.utcnow(),
            }}, upsert=True
        )
        return {"task_id": task_id, "status": "pending", "message": "大盘分析任务已创建"}

    async def execute_background(self, task_id: str, user_id: str):
        try:
            self.memory_manager = get_memory_state_manager()
            logger.info(f"🚀 后台执行: {task_id}")
            await self.memory_manager.update_task_status(
                task_id=task_id, status=TaskStatus.RUNNING,
                progress=10, message="正在获取大盘数据...", current_step="fetching_data"
            )
            result = await self._execute_sync(task_id)
            await self._save_to_db(task_id, result)
            await self.memory_manager.update_task_status(
                task_id=task_id, status=TaskStatus.COMPLETED,
                progress=100, message="分析完成", current_step="completed", result_data=result
            )
            logger.info(f"✅ 大盘分析完成: {task_id}")
        except Exception as e:
            logger.error(f"❌ 大盘分析失败: {task_id} - {e}")
            self.memory_manager = get_memory_state_manager()
            await self.memory_manager.update_task_status(
                task_id=task_id, status=TaskStatus.FAILED,
                progress=0, message="分析失败", current_step="failed", error_message=str(e)
            )

    async def _execute_sync(self, task_id: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self._run_analysis, task_id)

    def _run_analysis(self, task_id: str) -> Dict[str, Any]:
        try:
            from tradingagents.utils.logging_init import init_logging
            init_logging()
        except Exception as e:
            print(f"⚠️ 日志初始化失败（不影响分析）: {e}")

        tlog = logging.getLogger('market_analysis_thread')
        tlog.info(f"🔄 开始分析: {task_id}")
        start = datetime.datetime.now()
        analysis_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # 1. 获取全部数据
        tlog.info("📡 获取实时指数数据...")
        index_list = self.fetch_realtime_index_data()
        tlog.info(f"📡 指数数据: {len(index_list)} 个")

        tlog.info("📡 获取市场广度数据...")
        breadth = self.fetch_market_breadth()
        tlog.info(f"📡 市场广度: 涨{breadth.get('up_count',0)}/跌{breadth.get('down_count',0)}")

        tlog.info("📡 获取市场新闻...")
        news = self.fetch_market_news()
        tlog.info(f"📡 新闻: 利好{len(news.get('利好',[]))}条/利空{len(news.get('利空',[]))}条")

        # 2. 提取上证指数数据
        sh_index = next((i for i in index_list if i["name"] == "上证指数"), None)
        sh_price = sh_index["price"] if sh_index else 0
        sh_change = f"{sh_index['pct_chg']}%" if sh_index else "—"
        sh_vol = sh_index["volume"] if sh_index else 0
        total_vol = sum(i.get("volume", 0) for i in index_list)
        total_amount = sum(i.get("amount", 0) for i in index_list)

        tlog.info(f"✅ 数据全部获取完成")
        tlog.info(f"   上证: {sh_price} ({sh_change})")
        tlog.info(f"   涨跌: {breadth['up_count']}/{breadth['down_count']} 涨停:{breadth['limit_up_count']}")
        tlog.info(f"   北向: {breadth['north_flow']}亿")

        # 3. 构建 AI 提示词
        prompt = AI_PROMPT_TEMPLATE.format(
            点位=sh_price,
            涨跌=sh_change,
            总成交=round(total_amount, 0),
            上证成交=round(sh_vol / 10000, 0) if sh_vol else 0,
            涨家数=breadth["up_count"],
            跌家数=breadth["down_count"],
            涨停数=breadth["limit_up_count"],
            连板高度=breadth["ladder_height"],
            北向=breadth["north_flow"],
            热门板块="、".join(breadth["top_sectors"][:5]) if breadth["top_sectors"] else "暂无",
            利好="；".join(news["利好"][:3]) if news["利好"] else "暂无",
            利空="；".join(news["利空"][:3]) if news["利空"] else "暂无",
        )

        # 4. AI 分析
        ai_report = self._ai_analyze(prompt, tlog)

        elapsed = (datetime.datetime.now() - start).total_seconds()

        return {
            "analysis_id": str(uuid.uuid4()),
            "stock_code": "MARKET",
            "stock_name": "大盘分析",
            "analysis_date": analysis_date,
            "index_data": index_list,
            "market_breadth": breadth,
            "market_news": news,
            "ai_report": ai_report,
            "execution_time": elapsed,
        }

    # ==================== AI 分析 ====================

    def _ai_analyze(self, prompt: str, tlog: logging.Logger) -> str:
        """使用 AI 分析大盘，返回完整报告文本"""
        try:
            api_key = os.getenv('DASHSCOPE_API_KEY')
            if not api_key:
                tlog.warning("⚠️ 未配置 DASHSCOPE_API_KEY")
                return "AI 分析不可用：未配置 API Key"

            from tradingagents.llm_adapters import ChatDashScopeOpenAI
            llm = ChatDashScopeOpenAI(model="qwen-plus", api_key=api_key, temperature=0.3)

            resp = llm.invoke([
                {"role": "system", "content": "你是一位资深A股首席策略分析师。严格按照用户要求的5模块格式输出分析报告，结论明确、可执行。"},
                {"role": "user", "content": prompt}
            ])

            report = resp.content.strip()
            tlog.info(f"✅ AI 分析完成 ({len(report)} 字)")
            return report

        except Exception as e:
            tlog.error(f"❌ AI 分析失败: {e}")
            return f"AI 分析失败: {str(e)}"

    # ==================== 数据持久化 ====================

    async def _save_to_db(self, task_id: str, result: Dict[str, Any]):
        """保存分析结果到 market_analysis 集合，同时同步到 analysis_tasks"""
        try:
            db = get_mongo_db()
            record = {
                "analysis_id": result.get("analysis_id"),
                "task_id": task_id,
                "stock_code": "MARKET",
                "stock_name": "大盘分析",
                "analysis_type": "market",
                "analysis_date": result.get("analysis_date"),
                "index_data": result.get("index_data", []),
                "market_breadth": result.get("market_breadth", {}),
                "market_news": result.get("market_news", {}),
                "ai_report": result.get("ai_report", ""),
                "execution_time": result.get("execution_time", 0),
                "created_at": datetime.datetime.utcnow(),
                "status": "completed",
            }

            # 写入 market_analysis 集合
            insert_result = await db.market_analysis.insert_one(record)
            logger.info(f"✅ 结果已入库 market_analysis: {task_id}, inserted_id={insert_result.inserted_id}")

            # 验证写入
            saved = await db.market_analysis.find_one({"task_id": task_id})
            if saved:
                logger.info(f"✅ 验证成功: market_analysis 中存在 task_id={task_id}")
            else:
                logger.error(f"❌ 验证失败: 写入后未找到 task_id={task_id}")

            # 同步写入 analysis_tasks 集合（前端任务列表读取）
            await db.analysis_tasks.update_one(
                {"task_id": task_id},
                {"$set": {
                    "result": {
                        "analysis_id": result.get("analysis_id"),
                        "analysis_date": result.get("analysis_date"),
                        "ai_report": result.get("ai_report", ""),
                        "index_data": result.get("index_data", []),
                        "market_breadth": result.get("market_breadth", {}),
                    },
                    "status": "completed",
                    "completed_at": datetime.datetime.utcnow(),
                }}
            )
            logger.info(f"✅ 同步到 analysis_tasks: {task_id}")

        except RuntimeError as e:
            logger.error(f"❌ MongoDB 未初始化: {task_id} - {e}")
            raise  # 让上层感知失败
        except Exception as e:
            logger.error(f"❌ 入库失败: {task_id} - {e}", exc_info=True)
            raise  # 让上层感知失败，标记任务为 FAILED

    @staticmethod
    def _fmt_vol(vol: int) -> str:
        if vol >= 100000000:
            return f"{vol / 100000000:.2f}亿"
        elif vol >= 10000:
            return f"{vol / 10000:.2f}万"
        return str(vol)


_market_analysis_service = None


def get_market_analysis_service() -> MarketAnalysisService:
    global _market_analysis_service
    if _market_analysis_service is None:
        _market_analysis_service = MarketAnalysisService()
    return _market_analysis_service