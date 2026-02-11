"""Construction & remodeling cost trend analysis."""
from __future__ import annotations
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import requests
from io import StringIO

OUTPUT_DIR = "output/Seattle_RE"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
START = "2015-01-01"

def fetch_fred(sid):
    url = f"{FRED_CSV}?id={sid}&cosd={START}"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        print(f"  [WARN] {sid}: {r.status_code}")
        return None
    df = pd.read_csv(StringIO(r.text))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna()

print("Fetching data...")
ppi_construction = fetch_fred("WPUSI012011")   # PPI Construction Materials
ppi_residential = fetch_fred("WPUIP2311001")   # PPI Residential Construction Inputs
lumber = fetch_fred("WPU0811")                  # PPI Lumber
ppi_final = fetch_fred("PPIDCS")               # PPI Final Demand Construction

print("Generating chart...")
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle("Construction & Remodeling Cost Trends (10-Year)", fontsize=16)

# 1. PPI Construction Materials
ax = axes[0, 0]
if ppi_construction is not None:
    ax.plot(ppi_construction["date"], ppi_construction["value"],
            color="#D32F2F", linewidth=2)
    latest = ppi_construction.iloc[-1]
    rows2019 = ppi_construction[ppi_construction["date"].dt.year == 2019]
    if not rows2019.empty:
        v2019 = rows2019.iloc[0]["value"]
        chg = (latest["value"] / v2019 - 1) * 100
        ax.annotate(f'{latest["value"]:.0f} (+{chg:.0f}% vs 2019)',
                    xy=(latest["date"], latest["value"]),
                    fontsize=9, fontweight="bold", color="#D32F2F",
                    xytext=(-140, 15), textcoords="offset points")
ax.set_title("PPI: Construction Materials")
ax.set_ylabel("Index (1982=100)")
ax.grid(alpha=0.3)

# 2. PPI Residential Construction Inputs
ax = axes[0, 1]
if ppi_residential is not None:
    ax.plot(ppi_residential["date"], ppi_residential["value"],
            color="#1976D2", linewidth=2)
    latest = ppi_residential.iloc[-1]
    rows2019 = ppi_residential[ppi_residential["date"].dt.year == 2019]
    if not rows2019.empty:
        v2019 = rows2019.iloc[0]["value"]
        chg = (latest["value"] / v2019 - 1) * 100
        ax.annotate(f'{latest["value"]:.0f} (+{chg:.0f}% vs 2019)',
                    xy=(latest["date"], latest["value"]),
                    fontsize=9, fontweight="bold", color="#1976D2",
                    xytext=(-140, 15), textcoords="offset points")
ax.set_title("PPI: Residential Construction Inputs")
ax.set_ylabel("Index")
ax.grid(alpha=0.3)

# 3. Lumber
ax = axes[1, 0]
if lumber is not None:
    ax.plot(lumber["date"], lumber["value"], color="#4CAF50", linewidth=2)
    latest = lumber.iloc[-1]
    ax.annotate(f'{latest["value"]:.0f}',
                xy=(latest["date"], latest["value"]),
                fontsize=9, fontweight="bold", color="#4CAF50",
                xytext=(10, 10), textcoords="offset points")
ax.set_title("PPI: Lumber & Wood Products")
ax.set_ylabel("Index (1982=100)")
ax.grid(alpha=0.3)

# 4. PPI Final Demand Construction
ax = axes[1, 1]
if ppi_final is not None:
    ax.plot(ppi_final["date"], ppi_final["value"], color="#FF9800", linewidth=2)
    latest = ppi_final.iloc[-1]
    rows2019 = ppi_final[ppi_final["date"].dt.year == 2019]
    if not rows2019.empty:
        v2019 = rows2019.iloc[0]["value"]
        chg = (latest["value"] / v2019 - 1) * 100
        ax.annotate(f'{latest["value"]:.0f} (+{chg:.0f}% vs 2019)',
                    xy=(latest["date"], latest["value"]),
                    fontsize=9, fontweight="bold", color="#FF9800",
                    xytext=(-140, 15), textcoords="offset points")
ax.set_title("PPI: Final Demand Construction (incl. labor)")
ax.set_ylabel("Index (2009=100)")
ax.grid(alpha=0.3)

for a in axes.flat:
    a.axvspan(pd.Timestamp("2020-02-01"), pd.Timestamp("2020-06-01"),
              color="grey", alpha=0.1)

fig.tight_layout()
path = os.path.join(OUTPUT_DIR, "09_construction_costs.png")
fig.savefig(path, dpi=150, bbox_inches="tight")
plt.close()
print(f"Saved {path}")

# Key metrics
print("\n=== KEY COST METRICS ===")
for name, df in [("Construction Materials PPI", ppi_construction),
                  ("Residential Inputs PPI", ppi_residential),
                  ("Final Demand Construction", ppi_final)]:
    if df is None:
        continue
    rows2019 = df[df["date"].dt.year == 2019]
    if rows2019.empty:
        continue
    v2019 = rows2019.iloc[0]["value"]
    peak = df["value"].max()
    peak_date = df.loc[df["value"].idxmax(), "date"]
    latest = df.iloc[-1]["value"]
    print(f"\n{name}:")
    print(f"  2019 baseline: {v2019:.0f}")
    print(f"  Peak: {peak:.0f} ({peak_date.strftime('%Y-%m')}), +{(peak/v2019-1)*100:.0f}% vs 2019")
    print(f"  Current: {latest:.0f}, +{(latest/v2019-1)*100:.0f}% vs 2019")
    print(f"  Off peak: {(latest/peak-1)*100:.1f}%")
