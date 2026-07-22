"""
全量A股股票信息同步服务
功能：获取所有A股股票详细信息（代码、名称、行业、市值、PE等），存入 MongoDB all_stocks_info 集合
策略：Tushare → AKShare → BaoStock 多数据源 fallback
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

import pandas as pd

logger = logging.getLogger("app.services.all_stocks_info")


class AllStocksInfoService:
    """全量A股股票信息同步服务"""

    COLLECTION_NAME = "all_stocks_info"

    # ==================== 主入口 ====================

    def sync_all_stocks(self) -> Dict[str, Any]:
        """
        同步全量A股股票信息到 MongoDB

        Returns:
            Dict: 同步结果摘要
        """
        start_time = datetime.now()
        logger.info("🚀 [全量同步] 开始同步全量A股股票信息...")

        # 1. 获取股票列表（含行业信息），多数据源 fallback
        df = self._fetch_stock_list_with_industry()
        if df is None or df.empty:
            return {"success": False, "error": "无法获取股票列表", "count": 0}

        logger.info(f"📊 [全量同步] 获取到 {len(df)} 只股票，开始处理...")

        # 2. 标准化列名
        df = self._normalize_columns(df)

        # 3. 补充市值/PE 数据（从 MongoDB stock_basic_info 缓存读取）
        df = self._enrich_valuation_data(df)

        # 4. 存入 MongoDB all_stocks_info
        stored_count = self._store_to_mongodb(df)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ [全量同步] 完成: {stored_count} 只股票，耗时 {elapsed:.2f}秒")

        return {
            "success": True,
            "count": stored_count,
            "total_fetched": len(df),
            "elapsed_seconds": elapsed,
            "timestamp": start_time.isoformat(),
        }

    # ==================== 数据获取：Tushare → AKShare → BaoStock ====================

    def _fetch_stock_list_with_industry(self) -> Optional[pd.DataFrame]:
        """
        多数据源获取股票列表（含行业信息），优先级：Tushare → AKShare → BaoStock

        每个数据源返回的 DataFrame 都包含 industry 字段。
        Tushare 和 BaoStock 原生支持行业信息，AKShare 不包含行业信息。
        """
        # 1. 尝试 Tushare（含行业信息）
        df = self._fetch_from_tushare()
        if df is not None and not df.empty:
            has_industry = self._count_industry(df)
            logger.info(f"✅ [全量同步] Tushare: {len(df)} 只股票, 行业覆盖 {has_industry}/{len(df)}")
            return df

        # 2. 尝试 AKShare（不含行业信息）
        df = self._fetch_from_akshare()
        if df is not None and not df.empty:
            logger.info(f"✅ [全量同步] AKShare: {len(df)} 只股票（无行业信息）")
            # AKShare 没有行业数据，尝试从 BaoStock 补充
            industry_map = self._fetch_industry_from_baostock()
            if industry_map:
                df['industry'] = df['symbol'].map(industry_map).fillna('')
                has_industry = self._count_industry(df)
                logger.info(f"✅ [全量同步] BaoStock 行业补充: {has_industry}/{len(df)}")
            return df

        # 3. 尝试 BaoStock（含行业信息）
        df = self._fetch_from_baostock()
        if df is not None and not df.empty:
            has_industry = self._count_industry(df)
            logger.info(f"✅ [全量同步] BaoStock: {len(df)} 只股票, 行业覆盖 {has_industry}/{len(df)}")
            return df

        logger.error("❌ [全量同步] 所有数据源均不可用")
        return None

    def _count_industry(self, df: pd.DataFrame) -> int:
        """统计有效行业数据数量"""
        if 'industry' not in df.columns:
            return 0
        col = df['industry']
        return (col.notna() & (col != '') & (col != 'None') & (col != 'nan')).sum()

    # ---------- Tushare ----------

    def _fetch_from_tushare(self) -> Optional[pd.DataFrame]:
        """从 Tushare 获取股票列表（含行业信息）"""
        try:
            from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
            provider = get_tushare_provider()
            if not provider or not provider.is_available():
                logger.warning("⚠️ Tushare 不可用")
                return None

            df = provider.get_stock_list_sync()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"⚠️ Tushare 获取失败: {e}")
        return None

    # ---------- AKShare ----------

    def _fetch_from_akshare(self) -> Optional[pd.DataFrame]:
        """从 AKShare 获取股票列表（不含行业信息）"""
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            if df is None or df.empty:
                return None

            df = df.rename(columns={
                'code': 'symbol', '代码': 'symbol',
                'name': 'name', '名称': 'name'
            })

            if 'symbol' not in df.columns or 'name' not in df.columns:
                return None

            # 生成 ts_code
            def generate_ts_code(code: str) -> str:
                code = str(code).zfill(6)
                if code.startswith(('60', '68', '90')):
                    return f"{code}.SH"
                elif code.startswith(('00', '30', '20')):
                    return f"{code}.SZ"
                elif code.startswith(('8', '4')):
                    return f"{code}.BJ"
                return f"{code}.SZ"

            df['ts_code'] = df['symbol'].apply(generate_ts_code)
            df['area'] = ''
            df['industry'] = ''
            df['market'] = ''
            df['list_date'] = ''

            return df
        except ImportError:
            logger.warning("⚠️ AKShare 未安装")
        except Exception as e:
            logger.warning(f"⚠️ AKShare 获取失败: {e}")
        return None

    # ---------- BaoStock ----------

    def _fetch_from_baostock(self) -> Optional[pd.DataFrame]:
        """
        从 BaoStock 获取股票列表（含行业信息）

        使用 BaoStockAdapter 已有的实现，它已经正确处理了：
        - 登录/登出
        - 行业数据获取（query_stock_industry）
        - 行业名称清洗（去掉 I65/C31 等编码前缀）
        - 编码异常的容错处理
        """
        try:
            from app.services.data_sources.baostock_adapter import BaoStockAdapter
            adapter = BaoStockAdapter()
            if not adapter.is_available():
                logger.warning("⚠️ BaoStock 不可用")
                return None

            df = adapter.get_stock_list()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"⚠️ BaoStock 获取失败: {e}")
        return None

    def _fetch_industry_from_baostock(self) -> Optional[Dict[str, str]]:
        """
        从 BaoStock 获取行业映射表 {code: industry_name}

        复用 BaoStockAdapter.get_stock_list() 的行业获取逻辑，
        该适配器已内置编码异常的容错处理。
        返回 None 表示获取失败（包括编码错误等网络问题）。
        """
        try:
            from app.services.data_sources.baostock_adapter import BaoStockAdapter
            adapter = BaoStockAdapter()
            if not adapter.is_available():
                return None

            df = adapter.get_stock_list()
            if df is None or df.empty:
                return None

            # symbol 是 6 位代码，industry 已清洗
            industry_map = {}
            for _, row in df.iterrows():
                code = str(row.get('symbol', ''))
                industry = str(row.get('industry', ''))
                if code and industry and industry != 'None' and industry != 'nan':
                    industry_map[code] = industry

            logger.info(f"✅ [全量同步] BaoStock 行业映射: {len(industry_map)} 条")
            return industry_map if industry_map else None
        except ImportError:
            logger.warning("⚠️ BaoStock 未安装")
        except Exception as e:
            logger.warning(f"⚠️ BaoStock 行业获取失败（可能是编码或网络问题）: {e}")
        return None

    # ==================== 列标准化 ====================

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名，确保 DataFrame 包含关键字段"""
        # 确保有 code 字段（6位数字代码）
        if 'code' not in df.columns:
            if 'symbol' in df.columns:
                df['code'] = df['symbol'].astype(str).str.replace('.SH', '').str.replace('.SZ', '').str.replace('.SS', '').str.zfill(6)
            elif 'ts_code' in df.columns:
                df['code'] = df['ts_code'].astype(str).str.replace('.SH', '').str.replace('.SZ', '').str.replace('.SS', '').str.zfill(6)

        # 确保有 name 字段
        if 'name' not in df.columns:
            if 'code_name' in df.columns:
                df['name'] = df['code_name']
            else:
                df['name'] = ''

        # 确保各字段存在
        for col, default in [('industry', ''), ('area', ''), ('market', ''), ('list_date', '')]:
            if col not in df.columns:
                df[col] = default

        return df

    # ==================== 估值数据补充 ====================

    def _enrich_valuation_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """从 MongoDB stock_basic_info 补充市值和PE数据"""
        try:
            from pymongo import MongoClient
            from app.core.config import settings

            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            collection = db['stock_basic_info']

            codes = df['code'].dropna().astype(str).tolist()
            if not codes:
                client.close()
                return df

            cursor = collection.find(
                {"code": {"$in": codes}},
                {"code": 1, "total_mv": 1, "pe_ttm": 1, "pb": 1, "_id": 0}
            )

            valuation_map = {}
            for doc in cursor:
                valuation_map[doc.get("code", "")] = {
                    "total_mv": doc.get("total_mv"),
                    "pe_ttm": doc.get("pe_ttm"),
                    "pb": doc.get("pb"),
                }
            client.close()

            df['total_mv'] = df['code'].map(lambda c: valuation_map.get(str(c), {}).get('total_mv'))
            df['pe_ttm'] = df['code'].map(lambda c: valuation_map.get(str(c), {}).get('pe_ttm'))
            df['pb'] = df['code'].map(lambda c: valuation_map.get(str(c), {}).get('pb'))

            has_mv = df['total_mv'].notna().sum()
            logger.info(f"✅ [全量同步] 补充估值数据: {has_mv}/{len(df)} 只")
        except Exception as e:
            logger.warning(f"⚠️ 补充估值数据失败: {e}")
            df['total_mv'] = None
            df['pe_ttm'] = None
            df['pb'] = None

        return df

    # ==================== MongoDB 存储 ====================

    def _store_to_mongodb(self, df: pd.DataFrame) -> int:
        """将股票数据存入 MongoDB all_stocks_info 集合（upsert 模式）"""
        try:
            from pymongo import MongoClient, UpdateOne
            from app.core.config import settings

            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            collection = db[self.COLLECTION_NAME]

            now = datetime.now().isoformat()
            operations = []
            stored_count = 0

            for _, row in df.iterrows():
                code = str(row.get('code', '')).strip()
                if not code:
                    continue

                doc = {
                    "code": code,
                    "ts_code": str(row.get('ts_code', '')),
                    "name": str(row.get('name', '')),
                    "industry": str(row.get('industry', '')),
                    "area": str(row.get('area', '')),
                    "market": str(row.get('market', '')),
                    "list_date": str(row.get('list_date', '')),
                    "total_mv": self._safe_float(row.get('total_mv')),
                    "pe_ttm": self._safe_float(row.get('pe_ttm')),
                    "pb": self._safe_float(row.get('pb')),
                    "is_active": True,
                    "updated_at": now,
                }

                operations.append(
                    UpdateOne({"code": code}, {"$set": doc}, upsert=True)
                )
                stored_count += 1

                if len(operations) >= 500:
                    collection.bulk_write(operations, ordered=False)
                    operations = []

            if operations:
                collection.bulk_write(operations, ordered=False)

            # 标记退市股
            current_codes = df['code'].dropna().astype(str).tolist()
            collection.update_many(
                {"code": {"$nin": current_codes}},
                {"$set": {"is_active": False, "updated_at": now}}
            )

            # 索引
            collection.create_index("code", unique=True)
            collection.create_index("industry")
            collection.create_index("is_active")
            collection.create_index("total_mv")

            client.close()
            logger.info(f"✅ [全量同步] MongoDB 写入 {stored_count} 条记录到 {self.COLLECTION_NAME}")
            return stored_count

        except Exception as e:
            logger.error(f"❌ [全量同步] MongoDB 写入失败: {e}")
            raise

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        try:
            if value is None or value == '' or value == 'None' or (isinstance(value, float) and pd.isna(value)):
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    # ==================== 查询接口 ====================

    def get_stock_info(self, code: str) -> Optional[Dict[str, Any]]:
        """查询单只股票的详细信息"""
        try:
            from pymongo import MongoClient
            from app.core.config import settings
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            result = db[self.COLLECTION_NAME].find_one({"code": str(code).zfill(6)}, {"_id": 0})
            client.close()
            return result
        except Exception as e:
            logger.error(f"查询股票信息失败: {e}")
            return None

    def get_stocks_by_industry(self, industry: str, limit: int = 100) -> List[Dict[str, Any]]:
        """按行业查询股票"""
        try:
            import re
            from pymongo import MongoClient
            from app.core.config import settings
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            cursor = db[self.COLLECTION_NAME].find(
                {"industry": re.compile(industry, re.IGNORECASE), "is_active": True},
                {"_id": 0}
            ).sort("total_mv", -1).limit(limit)
            result = list(cursor)
            client.close()
            return result
        except Exception as e:
            logger.error(f"按行业查询失败: {e}")
            return []

    def get_all_active_stocks(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取所有活跃股票"""
        try:
            from pymongo import MongoClient
            from app.core.config import settings
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            query = db[self.COLLECTION_NAME].find({"is_active": True}, {"_id": 0}).sort("total_mv", -1)
            if limit:
                query = query.limit(limit)
            result = list(query)
            client.close()
            return result
        except Exception as e:
            logger.error(f"查询所有股票失败: {e}")
            return []


# 单例
_all_stocks_service: Optional[AllStocksInfoService] = None


def get_all_stocks_service() -> AllStocksInfoService:
    global _all_stocks_service
    if _all_stocks_service is None:
        _all_stocks_service = AllStocksInfoService()
    return _all_stocks_service