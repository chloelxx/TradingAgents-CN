from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def _get_company_name_for_china_market(ticker: str, market_info: dict) -> str:
    """
    为中国市场分析师获取公司名称

    Args:
        ticker: 股票代码
        market_info: 市场信息字典

    Returns:
        str: 公司名称
    """
    try:
        if market_info['is_china']:
            # 中国A股：使用统一接口获取股票信息
            from tradingagents.dataflows.interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(ticker)

            logger.debug(f"📊 [中国市场分析师] 获取股票信息返回: {stock_info[:200] if stock_info else 'None'}...")

            # 解析股票名称
            if stock_info and "股票名称:" in stock_info:
                company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                logger.info(f"✅ [中国市场分析师] 成功获取中国股票名称: {ticker} -> {company_name}")
                return company_name
            else:
                # 降级方案：尝试直接从数据源管理器获取
                logger.warning(f"⚠️ [中国市场分析师] 无法从统一接口解析股票名称: {ticker}，尝试降级方案")
                try:
                    from tradingagents.dataflows.data_source_manager import get_china_stock_info_unified as get_info_dict
                    info_dict = get_info_dict(ticker)
                    if info_dict and info_dict.get('name'):
                        company_name = info_dict['name']
                        logger.info(f"✅ [中国市场分析师] 降级方案成功获取股票名称: {ticker} -> {company_name}")
                        return company_name
                except Exception as e:
                    logger.error(f"❌ [中国市场分析师] 降级方案也失败: {e}")

                logger.error(f"❌ [中国市场分析师] 所有方案都无法获取股票名称: {ticker}")
                return f"股票代码{ticker}"

        elif market_info['is_hk']:
            # 港股：使用改进的港股工具
            try:
                from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                company_name = get_hk_company_name_improved(ticker)
                logger.debug(f"📊 [中国市场分析师] 使用改进港股工具获取名称: {ticker} -> {company_name}")
                return company_name
            except Exception as e:
                logger.debug(f"📊 [中国市场分析师] 改进港股工具获取名称失败: {e}")
                # 降级方案：生成友好的默认名称
                clean_ticker = ticker.replace('.HK', '').replace('.hk', '')
                return f"港股{clean_ticker}"

        elif market_info['is_us']:
            # 美股：使用简单映射或返回代码
            us_stock_names = {
                'AAPL': '苹果公司',
                'TSLA': '特斯拉',
                'NVDA': '英伟达',
                'MSFT': '微软',
                'GOOGL': '谷歌',
                'AMZN': '亚马逊',
                'META': 'Meta',
                'NFLX': '奈飞'
            }

            company_name = us_stock_names.get(ticker.upper(), f"美股{ticker}")
            logger.debug(f"📊 [中国市场分析师] 美股名称映射: {ticker} -> {company_name}")
            return company_name

        else:
            return f"股票{ticker}"

    except Exception as e:
        logger.error(f"❌ [中国市场分析师] 获取公司名称失败: {e}")
        return f"股票{ticker}"


def create_china_market_analyst(llm, toolkit):
    """创建中国市场分析师（汇总评定模式）
    
    该节点在所有分析完成后执行，收集前序所有分析师的数据，
    结合中国市场特色进行综合汇总评定，生成最终投资建议。
    """
    
    def china_market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        
        # 获取股票市场信息
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        
        # 获取公司名称
        company_name = _get_company_name_for_china_market(ticker, market_info)
        logger.info(f"[中国市场分析师] 公司名称: {company_name}")
        
        # ========== 收集所有前序分析师的数据 ==========
        market_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")
        investment_plan = state.get("investment_plan", "")
        trader_investment_plan = state.get("trader_investment_plan", "")
        final_trade_decision = state.get("final_trade_decision", "")
        
        logger.info(f"📊 [中国市场分析师] 收集前序分析数据:")
        logger.info(f"  - 市场分析报告: {len(market_report)} 字符")
        logger.info(f"  - 情绪分析报告: {len(sentiment_report)} 字符")
        logger.info(f"  - 新闻分析报告: {len(news_report)} 字符")
        logger.info(f"  - 基本面分析报告: {len(fundamentals_report)} 字符")
        logger.info(f"  - 投资方案: {len(investment_plan)} 字符")
        logger.info(f"  - 交易员方案: {len(trader_investment_plan)} 字符")
        logger.info(f"  - 最终决策: {len(final_trade_decision)} 字符")
        
        # 构建前序分析数据汇总
        previous_analysis = f"""
## 一、市场技术分析报告
{market_report if market_report else "（无数据）"}

## 二、社交媒体情绪分析报告
{sentiment_report if sentiment_report else "（无数据）"}

## 三、新闻事件分析报告
{news_report if news_report else "（无数据）"}

## 四、基本面分析报告
{fundamentals_report if fundamentals_report else "（无数据）"}

## 五、投资研究方案
{investment_plan if investment_plan else "（无数据）"}

## 六、交易执行方案
{trader_investment_plan if trader_investment_plan else "（无数据）"}

## 七、风险评估与最终决策
{final_trade_decision if final_trade_decision else "（无数据）"}
"""
        
        system_message = (
            f"""你是一位中国股市顶级投资顾问，每年收益50%，你的任务是基于团队各分析师已完成的研究报告，进行综合汇总评定，并输出最终投资建议。

## 你的核心职责

1. **整合与交叉验证**：仔细阅读下方所有前序分析报告，识别各报告之间的一致性和矛盾点
2. **中国市场特色评估**：基于中国A股市场的特殊性（政策驱动、资金博弈、制度因素），对前序分析进行补充和修正
3. **最终结论输出**：综合所有信息，给出清晰的买入/持有/卖出建议

## 前序分析团队已完成以下报告：

{previous_analysis}

## 你的分析框架

### 第一步：交叉验证（识别矛盾）
- 技术面分析（报告一）的结论与基本面分析（报告四）是否一致？
- 新闻事件（报告三）的风险提示是否已被市场情绪（报告二）消化？
- 投资方案（报告五）的假设是否与风险评估（报告七）的结论冲突？
- 如果有矛盾，明确指出并给出你的判断

### 第二步：中国股市特色修正
- 当前政策环境对该标的的影响（利好/利空/中性）
- 资金面特征（北向资金、机构持仓、游资动向）
- 是否有制度性因素需要考虑（如ST风险、解禁压力、指数调整等）
- 行业政策周期位置

### 第三步：综合评定与最终建议
基于以上分析，给出最终投资建议，必须包含：

**最终Markdown总结表：**
| 维度 | 评级 | 依据 |
|------|------|------|
| 综合评分 | X/100分 | 加权各维度得分 |
| 投资建议 | 买入/持有/观望/卖出 | 明确方向 |
| 目标价格区间 | XX元 - XX元 | 1年期预期 |
| 止损价格 | XX元 | 最大亏损-15% |
| 建议仓位 | X% | 基于凯利公式 |
| 核心风险 | （一句话） | 最大风险点 |
| 核心催化剂 | （一句话） | 最可能触发因素 |

请用中文撰写，确保结论明确、可操作。"""
        )
        
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        
        prompt = prompt.partial(system_message=system_message)
        
        chain = prompt | llm
        result = chain.invoke(state["messages"])
        
        # 直接使用 LLM 回复作为汇总报告
        report = result.content
        logger.info(f"📊 [中国市场分析师] 汇总报告内容: {report[:300]}")
        
        return {
            "messages": [result],
            "china_market_report": report,
            "sender": "ChinaMarketAnalyst",
        }
    
    return china_market_analyst_node


def create_china_stock_screener(llm, toolkit):
    """创建中国股票筛选器"""
    
    def china_stock_screener_node(state):
        current_date = state["trade_date"]
        
        tools = [
            toolkit.get_china_market_overview,
        ]
        
        system_message = (
            """角色设定
你是一位拥有20年实战经验、历经多轮牛熊转换的中国股票首席投资官。你的风格兼具巴菲特的价值洞察与费雪的成长前瞻，同时对A股特有的政策周期与资金博弈有极深的理解。你极度厌恶永久性资本损失，追求“好行业、好公司、好价格”的三位一体。
核心筛选目标
从A股（含北交所）5300余只股票中，筛选出当前时点（2026年6月）风险收益比最优、具备中长期（1-3年）持有价值的核心标的池。

第一维度：商业本质与护城河（定性之锚）——对应您要求的“护城河、竞争优势、行业地位”
请勿仅用“龙头”二字概括，需进行深度解构：
1.护城河来源：该公司定价权来自哪里？请明确归类为无形资产（品牌溢价/专利壁垒/特许经营权）、转换成本（To B或To G绑定深度）、网络效应（双边平台），还是成本优势（规模效应/独特的资源地理位置）？并量化其近3年毛利率与净利率的稳定性（波动率是否小于行业均值30%以上）。
2.行业地位与卡位：在所属细分产业链中，是链主企业还是关键节点供应商？市占率排名（前3名），且与第2名的差距是否呈现“拉大”趋势而非“缩小”趋势？
3.竞争格局终局：判断该行业处于“百团大战”末期、寡头垄断初期，还是双寡头稳态？行业前5大企业集中度（CR5）是否超过60%？
第二维度：增长逻辑与业务结构（增长引擎与主营业务）
拒绝模糊的“高增长”表述，要求算出“第二曲线”的数学公式：
1.主营业务现金流画像：现有主营业务（第一曲线）是否为“现金牛”（经营现金流净额/净利润 > 80%）？能否为扩张提供充足内源性资金？
2.增长引擎（第二/第三曲线）：未来3年的核心增量逻辑必须明确。是量升（产能投产/出海国际化/渠道下沉）、价涨（产品结构高端化/提价权），还是降本（AI赋能提效/原材料下行周期受益）？
3.成长天花板：当前渗透率处于哪个阶段（渗透率 < 5%为概念期，5%-15%为爆发期，15%-30%为成长期，>30%为成熟期）？只接受处于爆发期或成长期的标的。
第三维度：板块属性与市场生态（所属板块）
不仅看行业分类，更要看“资金偏好属性”：
1.板块风格归因：该股在市场上被定义为核心资产（白马蓝筹）、景气成长（高PE高增长）、困境反转（周期底部），还是微盘主题（题材驱动）？
2.板块联动效应：与所属板块指数的贝塔系数是多少？是板块内的“领涨旗手”还是“补涨跟风”？
3.机构定价权：所属板块是否为公募/北向资金（外资）重仓“赛道”？自由流通市值是否足够承接大资金（通常 > 100亿）？
第四维度：财务质量与估值锚（进阶量化）
在您原有基础上，加入“排雷”与“绝对估值”逻辑：
1.财务排雷（一票否决项）：剔除近3年有审计非标意见、商誉/净资产 > 30%、大股东质押率 > 50%、近1年有监管立案调查的标的。要求应收账款周转天数与应付账款周转天数之差（现金周转周期）持续缩短。
2.估值锚定（PEG与股息率双锚）：
1.成长股：要求PEG（未来1年动态） < 1.2，且G（净利润增速） > 30%。
2.价值股：要求股息率 > 3%（针对A股），且PB处于近5年历史分位点的 < 30%。
3.ROE归因分析：杜邦分析法拆解，明确高ROE是由高利润率（好生意）、高周转（好管理）还是高杠杆（高风险）驱动？优先选择“高利润率+中低杠杆”模式。
第五维度：催化信号与资金共识（择时与动量）
基本面决定方向，资金面决定节奏：
1.机构行为验证：近一季度，北向资金（沪深港通）持仓比例是否逆势提升？公募基金季报是否新进前十大重仓？
2.趋势强度：股价是否处于年线（250日线）之上？且年线方向向上（牛市格局）。
3.事件驱动：未来3个月内是否有明确的股价催化剂（如：重磅新品获批、行业政策出台、纳入重要指数成分股）？

综合评分与输出格式
请以上述五大维度为框架，对筛选出的标的进行加权评分（百分制）：
商业护城河与行业地位：30分（定性决定上限）
增长引擎与景气度：25分（成长性决定弹性）
财务健康度与估值匹配度：25分（安全边际决定下限）
资金共识与筹码结构：20分（市场合力决定效率）
最终输出清单（表格形式）需包含：
1.股票代码与名称
2.所属板块（申万一级+市场风格标签）
3.主营业务（一句话清晰概括）
4.核心护城河/竞争优势（20字内精髓）
5.增长引擎（未来1-3年核心逻辑）
6.当前PEG与估值分位点
7.综合评级（A级：重仓底仓 / B级：战术配置 / C级：观察等待）

当前时间节点特别约束（2026年6月）
请务必结合当下宏观背景：
1.AI+与国产替代：优先关注AI应用端降本增效明确、且芯片/工业软件国产化率加速突破的标的。
2.红利与哑铃策略：在无风险利率下行期，需平衡“高股息红利”与“科技成长”的仓位配比。
3.出海全球化：评估地缘政治风险，规避单一依赖美国市场的出口链，优先关注“一带一路”及东南亚/中东市场拓展有效的企业。
4.供给侧出清：重点关注经历了2-3年行业寒冬、中小产能出清完毕、龙头定价权跃升的周期反转行业（如部分化工、养猪、面板）。
5.只要筛选出符合以上条件的标的，不要筛选出不符合条件的标的，只要筛选前50个就可以。
请开始执行筛选，并在输出每一只标的时，务必先回答：这家公司如果明天退市，它剩下的资产和品牌还值多少钱？（以此倒逼安全边际思维）。"""
        )
        
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system", 
                    "您是一位专业的股票筛选专家。"
                    " 使用提供的工具分析市场概况。"
                    " 您可以访问以下工具：{tool_names}。\n{system_message}"
                    "当前日期：{current_date}。请用中文撰写分析内容。",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        
        prompt = prompt.partial(system_message=system_message)
        # 安全地获取工具名称，处理函数和工具对象
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        
        return {
            "messages": [result],
            "stock_screening_report": result.content,
            "sender": "ChinaStockScreener",
        }
    
    return china_stock_screener_node
