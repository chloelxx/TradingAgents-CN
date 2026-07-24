import akshare as ak
import pandas as pd
from datetime import datetime

# 获取所有指数的实时行情数据（新浪数据源）
index_spot = ak.stock_zh_index_spot_sina()
print(f"获取到 {len(index_spot)} 个指数数据")

# 目标指数：精确匹配代码
target_codes = [
    "sh000001",  # 上证指数
    "sz399001",  # 深证成指
    "sz399006",  # 创业板指
    "sh000688",  # 科创50
    "sz399997",  # 中证白酒
    "sh000932",  # 中证消费
    "sh000015",  # 红利指数
]

result = index_spot[index_spot["代码"].isin(target_codes)].copy()

print(f"筛选后共 {len(result)} 个指数:")
for _, row in result.iterrows():
    print(f"  {row['代码']}  {row['名称']}  最新价:{row['最新价']}  涨跌幅:{row['涨跌幅']}%")

# 保存到 Excel
output_file = f"selected_indices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    result.to_excel(writer, sheet_name='精选指数行情', index=False)

print(f"\n✅ 数据已保存到: {output_file}")
