#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dcf_screener.py
批量对美股上市公司做 DCF，筛出被低估的股票，输出一个 CSV：
    undervalued_YYYYMMDD.csv
依赖：
    - dcf_builder.py (你的 DCF 核心逻辑)
    - yfinance
    - pandas, numpy, requests

注意事项：
    - SEC 网站有访问频率限制，建议 sleep_sec 不要太小（例如 0.2 秒以上）
    - yfinance 有时会不稳定，获取价格失败时会跳过该股票

	-	DCF 本身并不适用于所有公司
	•	银行、保险、REIT 等 FCF 定义都不一样。
	•	很多亏损成长股会算出乱七八糟的 fair value。
        实际上可能要再加过滤，比如： 
        •	市值 > 某个值
        •	最近几年有稳定正的 FCF / Net Income
	-	阈值怎么选？
	•	undervalue_threshold = 0.0：任何 fair_value > price 都列出来有很多，噪音多。
	•	undervalue_threshold = 0.2：至少低估 20% → 少一点，但更有意义。
        作者: y32lu
        日期: 2024-06
        """


"""
dcf_screener.py

批量调用 dcf_builder.build_dcf，对一批美股做 DCF 估值，
对比当前市场价格，筛出“被低估”的股票，输出一个汇总表。

用法示例：
    /opt/homebrew/bin/python3 dcf_screener.py \
        --tickers-file all_us_tickers_sec.csv \
        --required 0.07 \
        --perp 0.025 \
        --min-discount 0.2 \
        --max-count 200 \ # 先开始用20只股票试试
        --start-from 0 \
        --sleep-sec 0.5 

参数说明：
    --tickers-file   : SEC 导出的所有 ticker 列表 csv（至少要有列 'ticker'）
    --required       : 要求回报率（比如 0.07 = 7%）
    --perp           : 永续增长率（比如 0.025 = 2.5%）
    --avg-years      : 计算平均净利率和 FCF/NI 时用的年数
    --years          : 预测几年现金流（对应 build_dcf 的 projection_years）
    --min-discount   : 最小低估幅度（0.2 = 至少低估 20% 才算）
    --max-count      : 最多处理多少只股票（避免一次性全市场太慢）
    --start-from     : 从第几行开始（用于断点续跑）
    --sleep-sec      : 每只股票之间 sleep 秒数，防止频繁请求 SEC / yfinance
"""

import argparse
import time
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

# 确保 dcf_builder.py 和本文件在同一目录，或者在 PYTHONPATH 下
from dcf_builder import build_dcf
from dcf_utils import get_latest_price_stooq, map_sic_to_sector,infer_sector_from_facts


def run_screener(
    tickers_file: str,
    required_return: float = 0.07,
    perpetual_growth: float = 0.025,
    avg_years: int = 5,
    projection_years: int = 4,
    min_discount: float = 0.2,
    max_count: int = 200,
    start_from: int = 0,
    sleep_sec: float = 0.5,
):
    # 1. 读取 ticker 列表
    all_df = pd.read_csv(tickers_file)

    if "ticker" not in all_df.columns:
        raise ValueError(f"{tickers_file} 里必须包含列 'ticker'")

    # 可选：如果文件里有 title/cik/exchange，可以一并带上
    # 这里我们只挑一部分做 screening，避免一次性全市场跑太久
    sub_df = all_df.iloc[start_from : start_from + max_count].copy()
    print(f"[INFO] 从 {tickers_file} 读取 {len(all_df)} 条，"
          f"本次处理 {len(sub_df)} 条 (index {start_from} 起)")

    results = []
    errors = []

    for idx, row in sub_df.iterrows():
        ticker = str(row["ticker"]).upper()
        title = row.get("title", "")
        cik = row.get("cik", "")

        print(f"\n[RUN] {ticker} ({title}) - index {idx}")

        try:
            # 2. 调用你的 DCF 主函数（不走 main，只用返回值）
            hist, proj, meta = build_dcf(
                ticker=ticker,
                required_return=required_return,
                perpetual_growth=perpetual_growth,
                avg_years=avg_years,
                projection_years=projection_years,
                save_raw_json=False,
            )

            fair_value = meta.get("Fair Value / Share ")
            if fair_value is None or not np.isfinite(fair_value):
                raise ValueError("Fair Value / Share 无效")

            # 3. 当前市价
            price = get_latest_price_stooq(ticker)

            # 4. 低估幅度： (内在价值 / 现价 - 1)
            discount = fair_value / price - 1.0

            print(
                f"[OK] {ticker}: Fair={fair_value:.2f}, "
                f"Price={price:.2f}, Discount={discount*100:.1f}%"
            )

            results.append(
                {
                    "ticker": ticker,
                    "title": title,
                    "cik": cik,
                    "fair_value": fair_value,
                    "last_price": price,
                    "discount_pct": discount * 100.0,
                    "avg_net_margin_pct 平均净利率": meta.get("Avg Net Profit Margin (%)"),
                    "avg_fcf_to_ni_pct 平均可用现金流": meta.get("Avg FCF/Net Income (%)"),
                    "adopted_growth_pct": meta.get("Adopted Growth Rate (%)"),
                }
            )

        except Exception as e:
            print(f"[ERR] {ticker} 失败: {e}")
            errors.append({"ticker": ticker, "title": title, "cik": cik, "error": str(e)})

        # 控制节奏，避免请求太频繁
        time.sleep(sleep_sec)

    # 5. 汇总结果
    if not results:
        print("[WARN] 没有任何成功的估值结果。")
        return

    res_df = pd.DataFrame(results)

    # 筛出“被低估”的股票
    undervalued_df = res_df[
        (res_df["discount_pct"].astype(float) >= min_discount * 100.0)
        & res_df["fair_value"].notna()
        & res_df["last_price"].notna()
    ].copy()

    # 按低估幅度从高到低排序
    undervalued_df.sort_values("discount_pct", ascending=False, inplace=True)

    # 6. 保存结果文件：带时间戳
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d_%H-%M-%S")
    out_all = f"dcf_screen_all_{ts}.csv"
    out_uv = f"dcf_screen_undervalued_{ts}.csv"

    res_df.to_csv(out_all, index=False)
    undervalued_df.to_csv(out_uv, index=False)

    print(f"\n[SUMMARY] 共成功估值 {len(res_df)} 只股票，"
          f"其中低估幅度 >= {min_discount*100:.0f}% 的有 {len(undervalued_df)} 只。")
    print(f"[OK] 所有结果保存到: {out_all}")
    print(f"[OK] 被低估股票保存到: {out_uv}")

    if errors:
        err_df = pd.DataFrame(errors)
        err_file = f"dcf_screen_errors_{ts}.csv"
        err_df.to_csv(err_file, index=False)
        print(f"[INFO] 失败记录保存到: {err_file}")




# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--tickers-file", required=True, help="包含 ticker 列表的 csv 文件")
#     ap.add_argument("--required", type=float, default=0.07, help="要求回报率 (例如 0.07)")
#     ap.add_argument("--perp", type=float, default=0.025, help="永续增长率 (例如 0.025)")
#     ap.add_argument("--avg-years", type=int, default=5, help="计算平均利润率的年数")
#     ap.add_argument("--years", type=int, default=4, help="预测现金流的年数")
#     ap.add_argument("--min-discount", type=float, default=0.2,
#                     help="最小低估幅度 (0.2 = 20%)")
#     ap.add_argument("--max-count", type=int, default=200,
#                     help="最多处理多少只股票")
#     ap.add_argument("--start-from", type=int, default=0,
#                     help="从 csv 的第几行开始（用于断点续跑）")
#     ap.add_argument("--sleep-sec", type=float, default=0.5,
#                     help="每只股票之间 sleep 秒数，防止频繁请求")

#     args = ap.parse_args()

#     run_screener(
#         tickers_file=args.tickers_file,
#         required_return=args.required,
#         perpetual_growth=args.perp,
#         avg_years=args.avg_years,
#         projection_years=args.years,
#         min_discount=args.min_discount,
#         max_count=args.max_count,
#         start_from=args.start_from,
#         sleep_sec=args.sleep_sec,
#     )

def main(
    tickers_file,
    required_return,
    perpetual_growth,
    avg_years,
    projection_years,
    min_discount,
    max_count,
    start_from,
    sleep_sec
):
    run_screener(
        tickers_file=tickers_file,
        required_return=required_return,
        perpetual_growth=perpetual_growth,
        avg_years=avg_years,
        projection_years=projection_years,
        min_discount=min_discount,
        max_count=max_count,
        start_from=start_from,
        sleep_sec=sleep_sec,
    )


if __name__ == "__main__":
    tickers_file = "/Users/y32lyu/Nextcloud/Project/invest_stock/data/all_us_tickers_sec.csv"

    main(
        tickers_file,
        0.07,
        0.025,
        5,
        4,
        0.2,
        20,   # max_count
        0,    # start_from
        0.5   # sleep_sec
    )