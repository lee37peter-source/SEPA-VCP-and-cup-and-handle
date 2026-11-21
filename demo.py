"""Synthetic market for testing and for previewing the site without downloading data.

Builds ~150 random stocks plus planted examples of each pattern (setups, breakouts, a past
breakout that worked and one that failed), and index series."""
from __future__ import annotations

import numpy as np
import pandas as pd

N_DAYS = 520


def _dates(end=None):
    end = pd.Timestamp(end or pd.Timestamp.today().normalize()) - pd.offsets.BDay(1)
    return pd.bdate_range(end=end, periods=N_DAYS)


def make_series(dates, segments, start, seed=0, noise=0.004, rangek=0.014, base_vol=2e6):
    """segments: list of (days, target_close, volume_multiplier). Path is padded at the front."""
    r = np.random.default_rng(seed)
    path, vmult = [], []
    cur = start
    for days, target, vm in segments:
        path.extend(np.linspace(cur, target, days + 1)[1:])
        vmult.extend([vm] * days)
        cur = target
    n = len(dates)
    path, vmult = np.array(path, float), np.array(vmult, float)
    if len(path) < n:
        pad = n - len(path)
        path = np.concatenate([np.full(pad, start) * np.exp(r.normal(0, 0.01, pad)), path])
        vmult = np.concatenate([np.ones(pad), vmult])
    path, vmult = path[-n:], vmult[-n:]
    close = path * (1 + r.normal(0, noise, n))
    lr = np.abs(np.diff(np.log(path), prepend=np.log(path[0])))
    loc = pd.Series(lr).rolling(10, min_periods=1).mean().to_numpy()
    rk = np.clip(rangek * (0.4 + loc / (loc.mean() + 1e-9)), 0.004, 0.06)
    high = close * (1 + np.abs(r.normal(0, 1, n)) * rk / 2 + 0.002)
    low = close * (1 - np.abs(r.normal(0, 1, n)) * rk / 2 - 0.002)
    opn = np.clip(close * (1 + r.normal(0, noise, n)), low, high)
    vol = base_vol * vmult * np.exp(r.normal(0, 0.22, n))
    return pd.DataFrame({"Open": opn, "High": high, "Low": low, "Close": close,
                         "Volume": vol.astype(np.int64)}, index=dates)


def _surge(df, close, high=None, vol=6e6, low=None, opn=None):
    """Overwrite the last bar with a breakout-style bar."""
    df = df.copy()
    i = df.index[-1]
    df.loc[i, "Close"] = close
    df.loc[i, "High"] = high or close * 1.004
    df.loc[i, "Low"] = low or close * 0.975
    df.loc[i, "Open"] = opn or close * 0.98
    df.loc[i, "Volume"] = int(vol)
    return df


def _strong_bar(df, pos):
    """Make bar `pos` a clean breakout bar: opens low, closes near its high."""
    df = df.copy()
    i = df.index[pos]
    c = df.loc[i, "Close"]
    df.loc[i, ["Open", "High", "Low"]] = [c * 0.975, c * 1.003, c * 0.97]
    return df


UP = [(260, 100, 1.0)]                       # 40 -> 100 advance
VCP = UP + [(14, 73, 1.4), (20, 97, 1.0), (10, 85.5, 0.9), (12, 96, 0.8), (7, 90.3, 0.6),
            (9, 95.5, 0.55), (4, 93.2, 0.4), (4, 95, 0.4)]
CUP = UP + [(8, 92, 1.3), (8, 82, 1.2), (10, 76, 1.0), (14, 74, 0.8), (12, 77, 0.8), (10, 86, 1.0),
            (14, 97.5, 1.1), (4, 93.5, 0.7), (4, 91.5, 0.6), (3, 92.5, 0.5), (4, 94.5, 0.5)]
DBL = UP + [(18, 76, 1.3), (14, 91, 1.0), (14, 74, 1.1), (10, 82, 0.7), (6, 86.5, 0.9)]
FLAT = UP + [(5, 93, 1.0), (6, 99, 0.9), (6, 92.5, 0.8), (6, 98.5, 0.8), (6, 93.5, 0.7), (6, 97.5, 0.6),
             (4, 96, 0.5), (3, 98, 0.5)]
HTF = [(150, 20, 1.0), (40, 21, 0.8), (35, 45, 2.0), (6, 39, 1.0), (5, 42, 0.7), (5, 40, 0.6), (4, 43, 0.6)]


def make_demo(end=None) -> tuple[dict[str, str], dict[str, pd.DataFrame]]:
    dates = _dates(end)
    names, data = {}, {}

    def add(t, name, df):
        names[t], data[t] = name, df

    add("VCPA", "Vector Compute Systems", make_series(dates, VCP, 40, seed=1))
    add("VCPB", "Valence Cloud Platforms", make_series(dates, VCP, 40, seed=2, base_vol=3e6))
    add("CUPA", "Cupertino Analytics", make_series(dates, CUP, 40, seed=3))
    add("DBLB", "Dualbridge Biotech", make_series(dates, DBL, 25, seed=4))
    add("FLAT", "Flatiron Software", make_series(dates, FLAT, 40, seed=5))
    add("HTFX", "Hightide Fusion", make_series(dates, HTF, 20, seed=6, base_vol=4e6, rangek=0.03))
    # breakouts today
    add("BRKV", "Breakwater Semis", _surge(make_series(dates, VCP + [(1, 95, 0.5)], 40, seed=7), 98.3))
    add("BRKC", "Brightcup Retail", _surge(make_series(dates, CUP + [(1, 94.5, 0.5)], 40, seed=8), 99.2))
    # past breakouts for the history tab: one works, one fails
    win = VCP + [(1, 99, 3.0), (6, 104, 1.6), (8, 109, 1.2), (6, 112, 1.0)]
    add("WINR", "Winrock Networks", _strong_bar(make_series(dates, win, 40, seed=9), -21))
    lose = VCP + [(1, 98.5, 3.0), (3, 97, 1.2), (5, 91, 1.6), (6, 88, 1.2)]
    add("LOSR", "Lowstone Materials", _strong_bar(make_series(dates, lose, 40, seed=10), -15))
    # decoys: loose base, downtrend, extended runner
    add("LOOS", "Loosely Coupled Inc", make_series(dates, UP + [(14, 75, 1), (20, 97, 1), (12, 78, 1),
                                                                  (15, 96, 1), (12, 75, 1), (10, 90, 1)], 40, seed=11))
    add("DOWN", "Downhill Holdings", make_series(dates, [(N_DAYS, 30, 1)], 90, seed=12))
    add("RUNR", "Runaway Robotics", make_series(dates, [(N_DAYS, 160, 1)], 40, seed=13, noise=0.006))

    adj = ["Apex", "Blue", "Cedar", "Delta", "Echo", "Falcon", "Granite", "Harbor", "Iron", "Juniper",
           "Keystone", "Lumen", "Maple", "Nova", "Orion", "Pine", "Quartz", "River", "Summit", "Titan"]
    noun = ["Energy", "Foods", "Health", "Logistics", "Media", "Pharma", "Labs", "Industries"]
    rng = np.random.default_rng(42)
    for i in range(150):
        drift = rng.normal(0.0003, 0.0008)
        c = 30 * np.exp(np.cumsum(rng.normal(drift, 0.02, N_DAYS)))
        h = c * (1 + np.abs(rng.normal(0, 0.01, N_DAYS)))
        lo = c * (1 - np.abs(rng.normal(0, 0.01, N_DAYS)))
        o = np.clip(c * (1 + rng.normal(0, 0.005, N_DAYS)), lo, h)
        vol = (2e6 * np.exp(rng.normal(0, 0.3, N_DAYS))).astype(np.int64)
        t = f"R{i:03d}"
        add(t, f"{adj[i % 20]} {noun[i % 8]}", pd.DataFrame(
            {"Open": o, "High": h, "Low": lo, "Close": c, "Volume": vol}, index=dates))

    for t, (start, drift, seed) in {"^GSPC": (4800, 0.0005, 90), "^IXIC": (15000, 0.0007, 91),
                                    "SPY": (480, 0.0005, 90), "QQQ": (400, 0.0007, 91)}.items():
        r = np.random.default_rng(seed)
        c = start * np.exp(np.cumsum(r.normal(drift, 0.009, N_DAYS)))
        h = c * (1 + np.abs(r.normal(0, 0.004, N_DAYS)))
        lo = c * (1 - np.abs(r.normal(0, 0.004, N_DAYS)))
        vol = (4e9 * np.exp(r.normal(0, 0.15, N_DAYS))).astype(np.int64)
        data[t] = pd.DataFrame({"Open": c, "High": h, "Low": lo, "Close": c, "Volume": vol}, index=dates)
    return names, data
