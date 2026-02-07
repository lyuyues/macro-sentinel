#!/usr/bin/env python3
# get_all_ticker.py
# Get all US tickers from SEC
# Save to CSV file named all_us_tickers_sec.csv

import requests
import pandas as pd
import datetime

SEC_HEADERS = {"User-Agent": "tickers-fetcher (email@example.com)"}

def get_all_us_tickers_from_sec() -> pd.DataFrame:
    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, headers=SEC_HEADERS, timeout=30)
    r.raise_for_status()

    data = r.json()  # 这是一个 dict: {"0": {...}, "1": {...}, ...}

    rows = []
    for _, v in data.items():
        rows.append({
            "cik": str(v["cik_str"]).zfill(10),
            "ticker": v["ticker"].upper(),
            "title": v["title"],
        })

    df = pd.DataFrame(rows)
    print(f"[INFO] Loaded {len(df)} tickers from SEC master list.")
    return df[["ticker", "title", "cik"]]

if __name__ == "__main__":
    df = get_all_us_tickers_from_sec()
    # write output file with a date-stamped filename (UTC date YYYYMMDD)
    date_str = datetime.datetime.utcnow().strftime("%Y%m%d")
    out_file = f"data/all_us_tickers_sec_{date_str}.csv"
    df.to_csv(out_file, index=False)
    print(f"[OK] Saved to {out_file}")