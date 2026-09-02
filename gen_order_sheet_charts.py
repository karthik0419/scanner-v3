"""
Generate charts for the Monday Order Sheet (2026-07-20).
Overlays the user-specified BUY / SL / T1 / T2 levels on daily + weekly candles.
Unlike gen_charts.py, this does NOT use scanner auto-detected levels —
it uses the exact levels from the order sheet.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import mplfinance as mpf
import pandas as pd
import numpy as np
from data.loader import _fetch_nse, _resample_weekly

# ── Order sheet: symbol -> dict(buy_low, buy_high, sl, t1, t2, qty, note)
# For "cross X" triggers, buy_low == buy_high == X (single trigger price).
ORDER_SHEET = {
    "INDIANB": dict(
        buy_low=820.0, buy_high=832.0, sl=795.30, t1=946.90, t2=None,
        qty="9-10", note="earnings +30.6% YoY (already above trigger)"),
    "MPHASIS": dict(
        buy_low=2479.0, buy_high=2479.0, sl=2357.24, t1=2758.60, t2=None,
        qty="3", note="best risk-math, RR 9.86x (cross w/ volume)"),
    "ZAGGLE": dict(
        buy_low=213.86, buy_high=213.86, sl=203.58, t1=230.55, t2=241.67,
        qty="28", note="Financial Services RISING (cross w/ volume)"),
    "EMKAY": dict(
        buy_low=253.80, buy_high=253.80, sl=236.37, t1=294.48, t2=321.60,
        qty="23", note="Financial Services RISING alt (pick ONE of ZAGGLE/EMKAY)"),
    "TECHM": dict(
        buy_low=1589.0, buy_high=1589.0, sl=1513.54, t1=1746.02, t2=None,
        qty="4", note="IT RISING (cross w/ volume)"),
    "NATCOPHARM": dict(
        buy_low=960.40, buy_high=960.40, sl=918.52, t1=1063.24, t2=1131.80,
        qty="6", note="cross w/ volume"),
    "PIRAMALFIN": dict(
        buy_low=2220.0, buy_high=2220.0, sl=2032.42, t1=2552.94, t2=2774.90,
        qty="3", note="both scanners, likely later in week"),
}

CHARTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "results", "charts", "ordersheet_2026-07-20",
)
os.makedirs(CHARTS_DIR, exist_ok=True)

# ── level config: (key, label, color, linewidth, linestyle)
# BUY shown as a band (low..high); single trigger if low==high.
LEVELS = [
    ("t2",        "T2",   "#00CC44", 1.5, "dashed"),
    ("t1",        "T1",   "#00FF88", 2.0, "dashed"),
    ("buy_high",  "BUY",  "#FFC107", 2.0, "solid"),
    ("sl",        "SL",   "#FF4444", 2.0, "dashed"),
]

STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#26A69A", down="#EF5350",
        edge="inherit", wick="inherit",
        volume={"up": "#26A69A", "down": "#EF5350"},
    ),
    facecolor="#0D1117",
    figcolor="#0D1117",
    gridcolor="#1C2333",
    gridstyle="--",
    gridaxis="both",
    rc={
        "axes.labelcolor": "#AAAAAA",
        "xtick.color":     "#AAAAAA",
        "ytick.color":     "#AAAAAA",
        "axes.edgecolor":  "#2A3A5C",
        "font.size":       10,
    },
)


def _save(df, tf_label, symbol, lvl):
    df = df.copy()
    df.index.name = "Date"
    if len(df) < 10:
        print(f"  {symbol} [{tf_label}]: not enough data")
        return

    # Clip extreme wick outliers so the chart scale stays usable
    for col in ("High", "Low"):
        q1, q3 = df[col].quantile(0.05), df[col].quantile(0.95)
        iqr = q3 - q1
        df[col] = df[col].clip(q1 - 4 * iqr, q3 + 4 * iqr)

    # ── Build hlines (skip None / 0)
    hline_vals, hline_cols, hline_styles, hline_widths = [], [], [], []
    for key, _, col, lw, ls in LEVELS:
        v = lvl.get(key)
        if v is None or v <= 0:
            continue
        hline_vals.append(v)
        hline_cols.append(col)
        hline_styles.append(ls)
        hline_widths.append(lw)

    hlines = dict(
        hlines=hline_vals,
        colors=hline_cols,
        linestyle=hline_styles,
        linewidths=hline_widths,
    )

    # ── Y-axis range: include all levels + price with 8% padding
    all_levels = [v for v in (
        lvl.get("sl"), lvl.get("buy_low"), lvl.get("buy_high"),
        lvl.get("t1"), lvl.get("t2"),
    ) if v]
    price_min = min(df["Low"].min(), min(all_levels))
    price_max = max(df["High"].max(), max(all_levels))
    padding = (price_max - price_min) * 0.08
    ylim = (price_min - padding, price_max + padding)

    mav = (20, 50) if tf_label == "Daily" else (10, 30)
    fig, axes = mpf.plot(
        df.tail(180 if tf_label == "Daily" else 104),
        type="candle", style=STYLE,
        volume=True, mav=mav,
        hlines=hlines,
        figsize=(16, 9),
        ylim=ylim,
        returnfig=True,
        tight_layout=True,
    )
    ax = axes[0]

    # ── BUY band shading if entry is a range (not single trigger)
    bl = lvl.get("buy_low"); bh = lvl.get("buy_high")
    if bl is not None and bh is not None and bh > bl:
        ax.axhspan(bl, bh, color="#FFC107", alpha=0.10, zorder=0)
        ax.text(0.02, (bl + bh) / 2, "  BUY BAND",
                transform=ax.get_yaxis_transform(),
                fontsize=8, color="#FFC107", fontweight="bold",
                va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.2", fc="#0D1117",
                          ec="#FFC107", alpha=0.85))

    # ── Title
    cmp_ = float(df["Close"].iloc[-1])
    bl = lvl.get("buy_low"); bh = lvl.get("buy_high")
    sl = lvl.get("sl"); t1 = lvl.get("t1"); t2 = lvl.get("t2")
    buy_mid = (bl + bh) / 2 if (bl and bh) else 0
    upside = round((t1 - buy_mid) / buy_mid * 100, 1) if buy_mid else 0
    risk = round((buy_mid - sl) / buy_mid * 100, 1) if buy_mid else 0
    rr = round(upside / risk, 2) if risk else 0

    fig.suptitle(
        f"{symbol}  [{tf_label}]   Mon Order Sheet 20-Jul-2026   |   {lvl.get('note','')}",
        fontsize=12, fontweight="bold", color="#E0E0E0", y=0.985, wrap=True,
    )

    # ── Right-side level labels
    for key, lbl, col, _, _ in LEVELS:
        v = lvl.get(key)
        if v is None or v <= 0:
            continue
        ax.annotate(
            f" {lbl}  {v:,.2f}",
            xy=(1.0, v), xycoords=("axes fraction", "data"),
            fontsize=9.5, fontweight="bold", color=col, va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="#0D1117",
                      ec=col, lw=0.8, alpha=0.9),
        )

    # ── Info box bottom-left
    buy_str = f"{bl:,.2f}" if bl == bh else f"{bl:,.2f}-{bh:,.2f}"
    t2_str = f"   T2  {t2:,.2f}" if t2 else ""
    info = (
        f"CMP  {cmp_:,.2f}    BUY  {buy_str}    SL  {sl:,.2f}\n"
        f"T1  {t1:,.2f}  (+{upside}%){t2_str}    RR  {rr}    Qty  {lvl.get('qty','')}"
    )
    ax.text(
        0.01, 0.02, info,
        transform=ax.transAxes,
        fontsize=9, color="#CCCCCC",
        va="bottom", ha="left",
        bbox=dict(boxstyle="round,pad=0.4", fc="#161B27",
                  ec="#2A3A5C", alpha=0.9),
    )

    # ── Legend
    patches = []
    for key, lbl, col, _, _ in LEVELS:
        if lvl.get(key):
            patches.append(mpatches.Patch(color=col, label=lbl))
    if patches:
        ax.legend(handles=patches, loc="upper left", fontsize=8,
                  facecolor="#161B27", edgecolor="#2A3A5C",
                  labelcolor="#CCCCCC")

    out = os.path.join(CHARTS_DIR, f"{symbol}_{tf_label.lower()}.png")
    fig.savefig(out, dpi=110, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  {symbol} [{tf_label}]: saved")


def plot(symbol, lvl):
    df = _fetch_nse(symbol, days=730)
    if df is None or len(df) < 60:
        print(f"  {symbol}: no data")
        return
    dfw = _resample_weekly(df)
    _save(df,  "Daily",  symbol, lvl)
    _save(dfw, "Weekly", symbol, lvl)


if __name__ == "__main__":
    print(f"Saving to {CHARTS_DIR}")
    print(f"Generating charts for {len(ORDER_SHEET)} order-sheet picks...\n")
    for sym, lvl in ORDER_SHEET.items():
        plot(sym, lvl)
    print("\nDone.")
