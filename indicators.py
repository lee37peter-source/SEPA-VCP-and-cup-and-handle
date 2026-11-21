"""Trend Template, relative strength, and market condition."""
from __future__ import annotations

import numpy as np
import pandas as pd


def trend_template(df: pd.DataFrame) -> dict[str, bool]:
    c = df["Close"]
    s50, s150, s200 = (c.rolling(n).mean() for n in (50, 150, 200))
    close = c.iloc[-1]
    low52 = df["Low"].iloc[-252:].min()
    high52 = df["High"].iloc[-252:].max()
    return {
        "Price > 150 & 200-day": bool(close > s150.iloc[-1] and close > s200.iloc[-1]),
        "150-day > 200-day": bool(s150.iloc[-1] > s200.iloc[-1]),
        "200-day rising 1 month": bool(s200.iloc[-1] > s200.iloc[-23]),
        "50-day > 150 & 200-day": bool(s50.iloc[-1] > s150.iloc[-1] and s50.iloc[-1] > s200.iloc[-1]),
        "Price > 50-day": bool(close > s50.iloc[-1]),
        "30%+ above 52-wk low": bool(close >= 1.30 * low52),
        "Within 25% of 52-wk high": bool(close >= 0.75 * high52),
    }


def rs_raw(close: pd.Series) -> float:
    """IBD-style: 12-month performance with the latest quarter double-weighted."""
    if len(close) < 253:
        return np.nan
    r = lambda n: close.iloc[-1] / close.iloc[-1 - n] - 1.0
    return 0.4 * r(63) + 0.2 * r(126) + 0.2 * r(189) + 0.2 * r(252)


def rs_ratings(data: dict[str, pd.DataFrame]) -> pd.Series:
    raw = pd.Series({t: rs_raw(df["Close"]) for t, df in data.items()}, dtype=float)
    raw = raw.replace([np.inf, -np.inf], np.nan).dropna()
    return (raw.rank(pct=True) * 98 + 1).round()


def rs_line_new_high(df: pd.DataFrame, bench: pd.DataFrame | None, tol: float = 0.02) -> bool | None:
    if bench is None:
        return None
    ratio = (df["Close"] / bench["Close"].reindex(df.index).ffill()).dropna()
    if len(ratio) < 60:
        return None
    return bool(ratio.iloc[-1] >= (1 - tol) * ratio.iloc[-252:].max())


# --------------------------------------------------------------------------- #
# Market condition
# --------------------------------------------------------------------------- #
def distribution_days(df: pd.DataFrame, window: int = 25) -> list[str]:
    """IBD rule: index down >= 0.2% on higher volume than the prior day, within the last
    25 sessions; a day expires early once the index closes 5% above that day's close."""
    c, v = df["Close"], df["Volume"]
    out = []
    n = len(df)
    for i in range(max(1, n - window), n):
        if v.iloc[i] <= 0 or v.iloc[i - 1] <= 0:
            continue
        if c.iloc[i] / c.iloc[i - 1] - 1 <= -0.002 and v.iloc[i] > v.iloc[i - 1]:
            if c.iloc[i:].max() < c.iloc[i] * 1.05:
                out.append(df.index[i].strftime("%Y-%m-%d"))
    return out


def index_summary(name: str, df: pd.DataFrame) -> dict:
    c = df["Close"]
    ema21 = c.ewm(span=21, adjust=False).mean()
    s50, s200 = c.rolling(50).mean(), c.rolling(200).mean()
    dd = distribution_days(df)
    return {
        "name": name,
        "close": round(float(c.iloc[-1]), 2),
        "chg_pct": round(float(c.iloc[-1] / c.iloc[-2] - 1) * 100, 2),
        "above_21ema": bool(c.iloc[-1] > ema21.iloc[-1]),
        "above_50": bool(c.iloc[-1] > s50.iloc[-1]),
        "above_200": bool(c.iloc[-1] > s200.iloc[-1]),
        "ma50_rising": bool(s50.iloc[-1] > s50.iloc[-6]),
        "dist_days": len(dd),
        "dist_dates": dd,
        "spark": [round(float(x), 2) for x in c.iloc[-60:]],
    }


def breadth(data: dict[str, pd.DataFrame]) -> dict:
    a50 = a200 = hi = lo = tot = 0
    for df in data.values():
        if len(df) < 253:
            continue
        c = df["Close"]
        tot += 1
        a50 += c.iloc[-1] > c.iloc[-50:].mean()
        a200 += c.iloc[-1] > c.iloc[-200:].mean()
        hi += df["High"].iloc[-1] >= df["High"].iloc[-253:-1].max()
        lo += df["Low"].iloc[-1] <= df["Low"].iloc[-253:-1].min()
    if not tot:
        return {}
    return {"stocks": tot, "pct_above_50": round(100 * a50 / tot, 1),
            "pct_above_200": round(100 * a200 / tot, 1), "new_highs": int(hi), "new_lows": int(lo)}


def market_condition(indexes: dict[str, pd.DataFrame], data: dict[str, pd.DataFrame]) -> dict:
    names = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "SPY": "S&P 500 (SPY)", "QQQ": "Nasdaq 100 (QQQ)"}
    idx = []
    for key in ("^GSPC", "^IXIC"):
        if key in indexes:
            idx.append(index_summary(names[key], indexes[key]))
    if not idx:  # fall back to ETFs
        for key in ("SPY", "QQQ"):
            if key in indexes:
                idx.append(index_summary(names[key], indexes[key]))
    b = breadth(data)

    # Simple, transparent regime score (0-5 per index, averaged)
    pts = []
    for s in idx:
        p = s["above_21ema"] + s["above_50"] + s["above_200"] + s["ma50_rising"] + (s["dist_days"] <= 4)
        pts.append(p)
    score = float(np.mean(pts)) if pts else 2.5
    if b:
        score += 0.5 if b["pct_above_50"] >= 55 else (-0.5 if b["pct_above_50"] < 40 else 0)
    if score >= 4:
        regime, color, advice = "Uptrend", "green", "Conditions support new breakout buys at normal size."
    elif score >= 2.5:
        regime, color, advice = "Uptrend under pressure", "amber", \
            "Be selective: best setups only, smaller size, take profits sooner."
    else:
        regime, color, advice = "Correction", "red", \
            "Most breakouts fail in corrections. Mostly cash; build the watchlist."
    return {"regime": regime, "color": color, "advice": advice, "score": round(score, 1),
            "indexes": idx, "breadth": b}
