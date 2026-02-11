#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# supply_demand_chart.py
# 铜和石油过去20年 + 未来5年预测的供需线图
#
# Data sources:
#   Oil: IEA, EIA, OPEC (mb/d)
#   Copper: ICSG, USGS, Wood Mackenzie (million metric tons refined)

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# =============================================
#  Data: Oil Supply & Demand (million b/d)
# =============================================
# Sources: IEA World Energy Outlook, EIA STEO, OPEC MOMR, Energy Institute

oil_years = list(range(2005, 2031))

# Global oil supply (production) — mb/d
oil_supply = [
    84.6,  # 2005
    85.4,  # 2006
    85.5,  # 2007
    86.3,  # 2008
    84.9,  # 2009 (GFC)
    87.4,  # 2010
    88.8,  # 2011
    91.0,  # 2012
    91.4,  # 2013
    93.8,  # 2014
    96.7,  # 2015 (US shale boom)
    97.2,  # 2016
    97.5,  # 2017
    100.6, # 2018
    100.5, # 2019
    91.0,  # 2020 (COVID)
    95.6,  # 2021
    99.5,  # 2022
    101.8, # 2023
    103.4, # 2024
    104.5, # 2025 (est)
    # Forecasts (IEA Oil 2025 Medium-Term Report)
    106.0, # 2026
    107.5, # 2027
    109.0, # 2028
    111.0, # 2029
    114.0, # 2030 (IEA supply capacity)
]

# Global oil demand (consumption) — mb/d
oil_demand = [
    84.0,  # 2005
    85.0,  # 2006
    86.1,  # 2007
    85.8,  # 2008
    84.6,  # 2009 (GFC)
    88.0,  # 2010
    89.1,  # 2011
    90.5,  # 2012
    91.8,  # 2013
    93.0,  # 2014
    95.0,  # 2015
    96.2,  # 2016
    98.0,  # 2017
    99.8,  # 2018
    100.3, # 2019
    88.7,  # 2020 (COVID crash)
    96.5,  # 2021
    99.2,  # 2022
    102.2, # 2023
    103.0, # 2024
    104.0, # 2025 (est)
    # Forecasts (IEA — demand plateau scenario)
    104.8, # 2026
    105.2, # 2027
    105.5, # 2028
    105.7, # 2029
    105.6, # 2030 (IEA: demand plateau + EV displacement)
]

# =============================================
#  Data: Copper Supply & Demand (million metric tons, refined)
# =============================================
# Sources: ICSG, USGS Mineral Commodity Summaries, Wood Mackenzie

copper_years = list(range(2005, 2031))

# Global copper refined production — million metric tons
copper_supply = [
    16.6,  # 2005
    17.3,  # 2006
    18.0,  # 2007
    18.2,  # 2008
    18.3,  # 2009
    19.1,  # 2010
    19.7,  # 2011
    20.1,  # 2012
    20.9,  # 2013
    21.7,  # 2014
    22.8,  # 2015
    23.3,  # 2016
    23.5,  # 2017
    24.0,  # 2018
    24.4,  # 2019
    24.5,  # 2020
    25.3,  # 2021
    25.6,  # 2022
    26.5,  # 2023
    27.5,  # 2024
    28.3,  # 2025 (ICSG est, +3.4%)
    # Forecasts (ICSG, Wood Mackenzie, CRU)
    28.6,  # 2026 (+0.9% growth slowing)
    29.0,  # 2027
    29.5,  # 2028
    30.0,  # 2029
    30.5,  # 2030 (supply constrained — few new mines)
]

# Global copper refined consumption — million metric tons
copper_demand = [
    16.7,  # 2005
    17.1,  # 2006
    17.9,  # 2007
    18.0,  # 2008
    17.8,  # 2009 (GFC)
    19.2,  # 2010
    19.8,  # 2011
    20.4,  # 2012
    21.2,  # 2013
    22.0,  # 2014
    22.9,  # 2015
    23.4,  # 2016
    23.7,  # 2017
    24.2,  # 2018
    24.5,  # 2019
    24.3,  # 2020
    25.4,  # 2021
    25.5,  # 2022
    26.4,  # 2023
    27.2,  # 2024
    28.0,  # 2025 (ICSG est)
    # Forecasts (Wood Mackenzie, Fastmarkets — energy transition driven)
    28.7,  # 2026 (deficit emerging)
    29.5,  # 2027
    30.5,  # 2028
    31.5,  # 2029
    33.0,  # 2030 (EV + grid + renewables acceleration)
]


# =============================================
#  Plotting
# =============================================

def make_chart():
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), dpi=150)
    fig.suptitle("Global Supply & Demand: Oil and Copper (2005–2030)",
                 fontsize=16, fontweight="bold", y=0.98)

    forecast_start = 2026  # vertical line here

    # --- Oil chart ---
    ax1 = axes[0]
    ax1.set_title("Crude Oil — Supply vs Demand", fontsize=13, pad=10)

    # Historical
    hist_mask = [y < forecast_start for y in oil_years]
    fcst_mask = [y >= forecast_start for y in oil_years]
    hist_years = [y for y, m in zip(oil_years, hist_mask) if m]
    fcst_years = [y for y, m in zip(oil_years, fcst_mask) if m]

    # Connect historical and forecast with overlap at boundary
    boundary_idx = oil_years.index(forecast_start)

    ax1.plot(hist_years, oil_supply[:boundary_idx], "o-", color="#2196F3",
             linewidth=2, markersize=4, label="Supply (production)")
    ax1.plot(hist_years, oil_demand[:boundary_idx], "s-", color="#F44336",
             linewidth=2, markersize=4, label="Demand (consumption)")

    # Forecast (dashed, including boundary point for continuity)
    ax1.plot([oil_years[boundary_idx - 1]] + fcst_years,
             [oil_supply[boundary_idx - 1]] + oil_supply[boundary_idx:],
             "o--", color="#2196F3", linewidth=2, markersize=4, alpha=0.7)
    ax1.plot([oil_years[boundary_idx - 1]] + fcst_years,
             [oil_demand[boundary_idx - 1]] + oil_demand[boundary_idx:],
             "s--", color="#F44336", linewidth=2, markersize=4, alpha=0.7)

    # Surplus / deficit shading
    supply_arr = np.array(oil_supply)
    demand_arr = np.array(oil_demand)
    ax1.fill_between(oil_years, oil_supply, oil_demand,
                     where=supply_arr >= demand_arr,
                     alpha=0.15, color="#2196F3", label="Surplus")
    ax1.fill_between(oil_years, oil_supply, oil_demand,
                     where=supply_arr < demand_arr,
                     alpha=0.15, color="#F44336", label="Deficit")

    # Forecast divider
    ax1.axvline(x=forecast_start - 0.5, color="gray", linestyle=":",
                linewidth=1, alpha=0.7)
    ax1.text(forecast_start + 1.5, 87, "Forecast →",
             fontsize=9, color="gray", ha="center")

    # Annotations
    ax1.annotate("COVID-19\ncrash", xy=(2020, 88.7), xytext=(2017.5, 86),
                 fontsize=8, color="#F44336",
                 arrowprops=dict(arrowstyle="->", color="#F44336", lw=1.2))
    ax1.annotate("IEA: growing\nsurplus by 2030", xy=(2029, 111), xytext=(2027, 114),
                 fontsize=8, color="#2196F3",
                 arrowprops=dict(arrowstyle="->", color="#2196F3", lw=1.2))

    ax1.set_ylabel("Million barrels / day", fontsize=11)
    ax1.set_xlim(2004.5, 2030.5)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    # --- Copper chart ---
    ax2 = axes[1]
    ax2.set_title("Refined Copper — Supply vs Demand", fontsize=13, pad=10)

    boundary_idx_cu = copper_years.index(forecast_start)
    hist_years_cu = copper_years[:boundary_idx_cu]
    fcst_years_cu = copper_years[boundary_idx_cu:]

    ax2.plot(hist_years_cu, copper_supply[:boundary_idx_cu], "o-", color="#4CAF50",
             linewidth=2, markersize=4, label="Supply (refined production)")
    ax2.plot(hist_years_cu, copper_demand[:boundary_idx_cu], "s-", color="#FF9800",
             linewidth=2, markersize=4, label="Demand (consumption)")

    ax2.plot([copper_years[boundary_idx_cu - 1]] + fcst_years_cu,
             [copper_supply[boundary_idx_cu - 1]] + copper_supply[boundary_idx_cu:],
             "o--", color="#4CAF50", linewidth=2, markersize=4, alpha=0.7)
    ax2.plot([copper_years[boundary_idx_cu - 1]] + fcst_years_cu,
             [copper_demand[boundary_idx_cu - 1]] + copper_demand[boundary_idx_cu:],
             "s--", color="#FF9800", linewidth=2, markersize=4, alpha=0.7)

    # Surplus / deficit shading
    cu_supply_arr = np.array(copper_supply)
    cu_demand_arr = np.array(copper_demand)
    ax2.fill_between(copper_years, copper_supply, copper_demand,
                     where=cu_supply_arr >= cu_demand_arr,
                     alpha=0.15, color="#4CAF50", label="Surplus")
    ax2.fill_between(copper_years, copper_supply, copper_demand,
                     where=cu_supply_arr < cu_demand_arr,
                     alpha=0.15, color="#FF9800", label="Deficit")

    ax2.axvline(x=forecast_start - 0.5, color="gray", linestyle=":",
                linewidth=1, alpha=0.7)
    ax2.text(forecast_start + 1.5, 17, "Forecast →",
             fontsize=9, color="gray", ha="center")

    ax2.annotate("Energy transition\ndrives demand gap",
                 xy=(2029, 31.5), xytext=(2026.5, 33),
                 fontsize=8, color="#FF9800",
                 arrowprops=dict(arrowstyle="->", color="#FF9800", lw=1.2))
    ax2.annotate("Supply growth\nslowing (few new mines)",
                 xy=(2028, 29.5), xytext=(2025, 27),
                 fontsize=8, color="#4CAF50",
                 arrowprops=dict(arrowstyle="->", color="#4CAF50", lw=1.2))

    ax2.set_ylabel("Million metric tons", fontsize=11)
    ax2.set_xlabel("Year", fontsize=11)
    ax2.set_xlim(2004.5, 2030.5)
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(True, alpha=0.3)

    # Source footnote
    fig.text(0.5, 0.01,
             "Sources: IEA, EIA, OPEC, ICSG, USGS, Wood Mackenzie, Fastmarkets  |  "
             "2026–2030 = forecasts (dashed lines)",
             ha="center", fontsize=8, color="gray")

    plt.subplots_adjust(left=0.08, right=0.95, top=0.93, bottom=0.08, hspace=0.3)

    out_path = "output/energy_cycle/oil_copper_supply_demand.png"
    plt.savefig(out_path)
    print(f"[Saved] {out_path}")
    plt.close()


if __name__ == "__main__":
    make_chart()
