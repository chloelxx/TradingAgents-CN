import akshare as ak
import pandas as pd
from datetime import datetime

# ============ 配置 ============
START_DATE = "20260101"
END_DATE = "20260724"

INDICES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sh000688": "科创50",
}

# ============ 获取历史数据 ============
all_data = {}

for code, name in INDICES.items():
    try:
        df = ak.stock_zh_index_daily(symbol=code)
        # 过滤日期范围
        df["date"] = pd.to_datetime(df["date"])
        df = df[(df["date"] >= START_DATE) & (df["date"] <= END_DATE)]
        df = df.sort_values("date")
        all_data[code] = df
        print(f"✅ {name}({code}): {len(df)} 条记录")
    except Exception as e:
        print(f"❌ {name}({code}): 获取失败 - {e}")

print("\n" + "=" * 80)

# ============ 成交量分析 ============
for code, name in INDICES.items():
    if code not in all_data:
        continue

    df = all_data[code]
    vol = df["volume"].astype(float)

    avg_vol = vol.mean()
    max_vol = vol.max()
    min_vol = vol.min()
    max_vol_date = df.loc[vol.idxmax(), "date"].strftime("%Y-%m-%d")
    min_vol_date = df.loc[vol.idxmin(), "date"].strftime("%Y-%m-%d")

    # 最近5日成交量
    recent_vol = vol.tail(5)
    recent_avg = recent_vol.mean()

    # 量能趋势：最近5日均量 vs 全周期均量
    if recent_avg > avg_vol * 1.2:
        vol_trend = "放量↑"
    elif recent_avg < avg_vol * 0.8:
        vol_trend = "缩量↓"
    else:
        vol_trend = "持平→"

    # 最近一日数据
    last = df.iloc[-1]
    last_date = last["date"].strftime("%Y-%m-%d")
    last_close = last["close"]
    last_vol_val = last["volume"]

    # 涨跌幅
    if len(df) >= 2:
        prev_close = df.iloc[-2]["close"]
        pct_chg = (last_close - prev_close) / prev_close * 100
    else:
        pct_chg = 0

    print(f"\n📊 {name}（{code}）")
    print(f"   区间: {START_DATE} ~ {END_DATE}  |  共 {len(df)} 个交易日")
    print(f"   最新: {last_date}  收盘 {last_close:.2f}  涨跌 {pct_chg:+.2f}%")
    print(f"   成交量: 当日 {last_vol_val:.0f}手  |  区间均值 {avg_vol:.0f}手  |  最高 {max_vol:.0f}手({max_vol_date})  |  最低 {min_vol:.0f}手({min_vol_date})")
    print(f"   量能趋势: {vol_trend}（近5日均量 {recent_avg:.0f} vs 全周期均量 {avg_vol:.0f}）")

# ============ 汇总对比表 ============
print("\n" + "=" * 80)
print("\n📋 三大指数成交量对比")
print("-" * 60)

summary_rows = []
for code, name in INDICES.items():
    if code not in all_data:
        continue
    df = all_data[code]
    last = df.iloc[-1]
    vol = df["volume"].astype(float)
    avg = vol.mean()
    recent_avg = vol.tail(5).mean()
    pct = (last["close"] - df.iloc[-2]["close"]) / df.iloc[-2]["close"] * 100 if len(df) >= 2 else 0
    summary_rows.append({
        "name": name,
        "date": last["date"].strftime("%Y-%m-%d"),
        "close": last["close"],
        "pct_chg": pct,
        "volume": last["volume"],
        "avg_vol": avg,
        "vol_ratio": last["volume"] / avg,
    })

summary_df = pd.DataFrame(summary_rows)
print(summary_df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))