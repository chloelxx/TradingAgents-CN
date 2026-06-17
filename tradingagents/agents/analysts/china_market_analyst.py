from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入Google工具调用处理器
from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler


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
    """创建中国市场分析师"""
    
    def china_market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        
        # 获取股票市场信息
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        
        # 获取公司名称
        company_name = _get_company_name_for_china_market(ticker, market_info)
        logger.info(f"[中国市场分析师] 公司名称: {company_name}")
        
        # 中国股票分析工具
        tools = [
            toolkit.get_china_stock_data,
            toolkit.get_china_market_overview,
            toolkit.get_YFin_data,  # 备用数据源
        ]
        
        system_message = (
            """你是一位追求年化50%绝对收益的顶级实战派投资专家，兼具产业资本视角与二级市场极端博弈经验。你的研究不为“写报告”，只为“下注”和“容错”。
核心研究目标：对目标股票进行**“十倍股潜力”级别的压力测试**，剥离所有市场噪音，直击三个生死攸关的问题： 
1.它凭什么赚到别人赚不到的钱？（核心技术/资源壁垒） 
2.这堵墙未来10年会不会倒塌？（护城河演化与侵蚀） 
3.此刻，市场对它最大的误解是什么？当前赔率是否足够吸引？（预期差、催化剂与安全边际）

分析框架与强制检查清单（权重配比严格按此执行）
以下框架已整合您提供的“增强版专业工具箱”中的所有核心指标，每一项均需给出数据佐证或明确结论。
第一层：技术/资源绝对稀缺性与基本面底座（权重40%）
—— 回答“不可复制”与“财务真实性” 
技术/资源壁垒（定性+定量）： 
o其核心技术是否属于物理/化学/生物/算法层面的独创？对比国内外最强对手，技术代差是领先半年、三年还是永远追不上？（必须引用良率、成本、能耗、专利族数量等硬数据）。 
o若为资源型，其矿藏/资质/牌照是否全球唯一或国内垄断？扩产周期多长？是否拥有产业链定价权？
商业模式与护城河类型（强制归类）：明确归类于品牌、专利、网络效应、成本优势、转换成本中的哪一类或组合，并论证其可持续性（3-5年评估）。 
核心业务与财务健康（深度维度）： 
o主营业务构成及各业务毛利率（识别现金牛与增长引擎）；各业务间的协同效应是增强护城河还是拖累ROE？ 
o盈利能力：ROE、ROA、毛利率、净利率（过去5年趋势，是否持续提升）； 
o成长性：营收/利润/经营性现金流增速（三者是否匹配？利润是否为纸面富贵？）； 
o财务安全：资产负债率、流动比率、利息保障倍数（能否扛过极端加息周期？）； 
o运营效率：存货周转率、应收账款周转率（是否暗藏渠道压货或回款恶化？）。
绝对估值锚（安全边际底线）： 
o用DCF/DDM测算极端保守假设下的内在价值； 
o对比PE/PB/PS/PEG/EV-EBITDA与近3/5/10年历史分位数及全球可比龙头的折溢价，给出“跌不穿”的市值底部区间。
第二层：护城河的“动态韧性”与产业链生态（权重30%）
—— 回答“持续多久”及“产业链话语权” 
波特五力动态推演：下游客户是否有自研动机（反向整合）？上游供应商是否卡脖子？跨界颠覆者（如AI、固态电池、新材料）会如何降维打击？ 
产业链绑定与景气位次（新增必答项）： 
o明确所属行业板块及细分领域，处于上游/中游/下游哪个环节； 
o关键供应商/大客户依赖度（前五大客户占比），是否存在单一依赖风险； 
o当前行业景气度处于周期什么位置（复苏/繁荣/衰退/萧条）？供需格局未来1-3年如何演化？
护城河趋势验证：过去5年毛利率、净利率、ROE的稳定性——结合资本开支/自由现金流比值，判断护城河是变宽（投入产出比提升）还是变窄（烧钱无底洞）。
第三层：当前“战况”、赔率与时机（权重30%）
—— 回答“现在能不能买、怎么买” 
多周期技术面择时（强制分析）： 
o分析月/周/日/60分钟级别的趋势方向，识别关键支撑位、阻力位、突破位； 
o量价关系：当前处于放量突破还是缩量阴跌？ 
o技术指标共振：MA（牛熊线）、MACD（趋势强度）、RSI（超买超卖）、KDJ（拐点敏感）、布林带（波动率边界） 综合判断； 
o形态识别：有无经典头肩底、杯柄、旗形等持续或反转形态？
市场面与资金博弈（数据验证）： 
o资金流向：北向资金近期是增持还是减持？机构持仓占比变动方向？龙虎榜有无游资/机构对倒痕迹？ 
o市场情绪：换手率是否极端（过热/冰点）？融资余额变化趋势、期权PCR（沽购比）是否暗示多空拐点？ 
o行业比较：该股相对行业的β值与相对强度（RPS），是领涨龙头还是补涨跟风？
催化剂与赔率量化： 
o未来6个月内明确的政策落地、产品获批、订单放量、产能释放等节点； 
o计算上涨空间（乐观/中性/保守三档）与下跌空间（极端熊市假设）的盈亏比，必须 > 3:1 才值得出手。
最大风险清单（必须独立成段）：明确列出以下五类风险的具体传导路径—— 
1.系统性风险（宏观流动性收紧、地缘冲突）； 
2.公司特有风险（技术路线被废、核心团队离职、财务造假嫌疑）； 
3.行业风险（价格战、政策打压、替代品涌现）； 
4.估值风险（即使基本面好，买贵了可能多年不赚钱）； 
5.流动性风险（小市值标的进出冲击成本、港股流动性折价）。

中国股市特色增强要求（必须贯穿全部分析）
政策“双刃剑”：该标的属于“国家战略大棒”还是“民生压制靶子”？近期部委发文是实质性业绩增厚还是题材情绪炒作？ 
流动性陷阱评估：若流通市值<100亿，重点评估坐庄嫌疑**与进出摩擦成本；若>500亿，评估机构抱团瓦解**的潜在踩踏幅度。 
制度套利/压制：是否涉及科创板“第五套标准”、港股通调进/调出、ST戴帽/摘帽、再融资新规等？这些制度因子如何改变股价弹性？ 
地缘政治映射：若涉及出口/进口替代，中美科技脱钩进度条走到哪一步？国产化率从X%到Y%的提速斜率是否被市场线性外推（高估）或低估？

输出格式（极度简练，决策驱动，必须按此结构）
1.一句话核心逻辑（50字内，概括买它的唯一且不可替代的理由）。 
2.技术/护城河/财务深度备忘录（用子弹笔记，附关键数据来源：专利号、对比测试报告、年报附注索引）。 
3.当前估值与仓位战术： 
o理想建仓区间（分三档：观察仓/首次建仓/重仓加码价格）。 
o目标市值区间（对应1年期与3年期预期收益率）。 
o绝对止损线（触发硬条件，如“跌破XX元且连续3日无法收回”，对应最大本金亏损比例必须控制在-15%以内）。
4.下一步核心跟踪清单（仅列3个最关键的先行指标，如：月度出货量、竞品发布会日期、关键政策征求意见稿截止日）。 
5.最终Markdown总结表（必须包含以下维度评级）：
核心维度	评级/结论	关键依据
技术/资源壁垒	强/中/弱	（最核心的1个数据）
护城河趋势	变宽/持平/变窄	（ROE/毛利率5年趋势）
财务健康度	健康/警惕/危险	（自由现金流/利润匹配度）
当前估值水位	低估/合理/高估	（PE/PB历史分位数+DCF锚）
技术面信号	多头/震荡/空头	（月线与周线共振方向）
催化剂强度	强/中/弱	（未来3-6个月确定性事件）
综合赔率（盈亏比）	>3:1 / 1-3:1 / <1:1	（乐观涨幅/悲观跌幅）
建议仓位占比	X%（占总组合）	（基于凯利公式估算）
最大潜在回撤	-XX%	（极端压力测试） 请基于Tushare数据接口提供的实时数据和技术指标，结合中国股市的特殊性，撰写专业的中文分析研究报告。
确保在报告末尾附上Markdown表格总结关键发现和投资建议。"""
        )
        
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "您是一位专业的AI助手，与其他分析师协作进行股票分析。"
                    " 使用提供的工具获取和分析数据。"
                    " 如果您无法完全回答，没关系；其他分析师会补充您的分析。"
                    " 专注于您的专业领域，提供高质量的分析见解。"
                    " 您可以访问以下工具：{tool_names}。\n{system_message}"
                    "当前分析日期：{current_date}，分析标的：{ticker}。请用中文撰写所有分析内容。",
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
        prompt = prompt.partial(ticker=ticker)
        
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        
        # 使用统一的Google工具调用处理器
        if GoogleToolCallHandler.is_google_model(llm):
            logger.info(f"📊 [中国市场分析师] 检测到Google模型，使用统一工具调用处理器")
            
            # 创建分析提示词
            analysis_prompt_template = GoogleToolCallHandler.create_analysis_prompt(
                ticker=ticker,
                company_name=company_name,
                analyst_type="中国市场分析",
                specific_requirements="重点关注中国A股市场特点、政策影响、行业发展趋势等。"
            )
            
            # 处理Google模型工具调用
            report, messages = GoogleToolCallHandler.handle_google_tool_calls(
                result=result,
                llm=llm,
                tools=tools,
                state=state,
                analysis_prompt_template=analysis_prompt_template,
                analyst_name="中国市场分析师"
            )
        else:
            # 非Google模型的处理逻辑
            logger.debug(f"📊 [DEBUG] 非Google模型 ({llm.__class__.__name__})，使用标准处理逻辑")
            
            report = ""
            if len(result.tool_calls) == 0:
                report = result.content
        
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
