"""Helpers shared by all pattern detectors, and the setup/breakout status logic."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Ctx:
    weak_market: bool = False


def arrays(df: pd.DataFrame):
    return (df["High"].to_numpy(float), df["Low"].to_numpy(float),
            df["Close"].to_numpy(float), df["Volume"].to_numpy(float))


def swing_flags(h: np.ndarray, l: np.ndarray, k: int):
    win = 2 * k + 1
    hmax = pd.Series(h).rolling(win, center=True).max().to_numpy()
    lmin = pd.Series(l).rolling(win, center=True).min().to_numpy()
    return h == hmax, l == lmin


def clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def fail(*reasons) -> dict:
    return {"reasons": list(reasons)}


def pct(x: float, nd: int = 1) -> str:
    return f"{x * 100:.{nd}f}%"


def evaluate(df: pd.DataFrame, detect, pcfg, scfg, ctx: Ctx) -> dict:
    """Run a detector on today's bars and on yesterday's bars and classify:
       BREAKOUT  - yesterday was a valid setup, today closed above the pivot on volume
       EXTENDED  - same, but already more than max_chase past the pivot
       SETUP     - today's bars form a valid base and price is near the pivot
    Returns {"status": None, "reasons": [...]} when nothing qualifies."""
    today = detect(df, pcfg, ctx)
    prev = detect(df.iloc[:-1], pcfg, ctx)
    c = df["Close"].to_numpy(float)
    v = df["Volume"].to_numpy(float)
    last = df.iloc[-1]
    rng = last["High"] - last["Low"]
    upper_half = rng <= 0 or (last["Close"] - last["Low"]) / rng >= 0.5

    if not prev["reasons"]:
        piv = prev["pivot"]
        vol50 = v[-51:-1].mean()
        prev_ok = (1 - pcfg.max_below_pivot) * piv <= c[-2] <= (1 + scfg.max_above_pivot) * piv
        if prev_ok and c[-1] > piv and vol50 > 0 and v[-1] >= scfg.breakout_vol * vol50 and upper_half:
            status = "EXTENDED" if c[-1] / piv - 1 > scfg.max_chase else "BREAKOUT"
            return _finish(prev, status, df, pcfg, scfg)

    if today["reasons"]:
        return {"status": None, "reasons": today["reasons"]}
    dist = c[-1] / today["pivot"] - 1
    if dist < -pcfg.max_below_pivot:
        return {"status": None, "reasons": [f"{-dist:.1%} below pivot"]}
    if dist > scfg.max_above_pivot:
        return {"status": None, "reasons": [f"{dist:.1%} above pivot (already broke out)"]}
    return _finish(today, "SETUP", df, pcfg, scfg)


def _finish(res: dict, status: str, df: pd.DataFrame, pcfg, scfg) -> dict:
    c = float(df["Close"].iloc[-1])
    v = df["Volume"].to_numpy(float)
    vol50 = v[-51:-1].mean()
    pivot = float(res["pivot"])
    entry = pivot * 1.001 + 0.01
    stop = max(float(res["stop"]), entry * (1 - scfg.max_stop_pct))
    dist = c / pivot - 1
    prox = 10 * clip01(1 - abs(min(dist, 0)) / pcfg.max_below_pivot)
    out = dict(res)
    out.update(status=status, pivot=round(pivot, 2), entry=round(entry, 2), stop=round(stop, 2),
               risk_pct=round((1 - stop / entry) * 100, 1), vs_pivot_pct=round(dist * 100, 1),
               vol_x=round(float(v[-1] / vol50), 2) if vol50 > 0 else None,
               score=float(res["score"]) + prox)
    return out
