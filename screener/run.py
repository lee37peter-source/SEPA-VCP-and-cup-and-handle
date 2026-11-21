"""Daily run: download -> screen five patterns -> market condition -> history -> site -> email.

    python -m screener.run --universe us --out build --history state/history.json --email
    python -m screener.run --demo --out build --backfill 40        # preview with synthetic data
    python -m screener.run --tickers NVDA ANET CRWD --out build --debug
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import time

import numpy as np
import pandas as pd

from . import alerts, history, site_builder
from .common import Ctx, evaluate
from .config import Config
from .data import INDEXES, fetch, load_universe
from .indicators import market_condition, rs_line_new_high, rs_ratings, trend_template
from .patterns import PATTERNS

HKT = dt.timezone(dt.timedelta(hours=8))


def log(*a):
    print(*a, flush=True)


def liquid(df: pd.DataFrame, cfg: Config) -> bool:
    u = cfg.universe
    if len(df) < u.min_bars:
        return False
    close = df["Close"].iloc[-1]
    return close >= u.min_price and (df["Close"] * df["Volume"]).iloc[-50:].mean() >= u.min_dollar_vol


def scan(data, indexes, names, cfg: Config, debug=False):
    """Screen every stock in `data` (bars up to the scan date). Returns candidates, hits, market, stats."""
    t0 = time.time()
    rs = rs_ratings(data)
    liq = {t: df for t, df in data.items() if liquid(df, cfg)}
    market = market_condition(indexes, liq)
    ctx = Ctx(weak_market=market["color"] != "green")
    bench = indexes.get("SPY") if "SPY" in indexes else indexes.get("^GSPC")

    cands, hits, n_tt = [], {}, 0
    for t, df in liq.items():
        tt = trend_template(df)
        s = {"tt_pass": all(tt.values()), "rs": float(rs.get(t, 0) or 0),
             "above_200": bool(df["Close"].iloc[-1] > df["Close"].iloc[-200:].mean())}
        n_tt += s["tt_pass"]
        close = float(df["Close"].iloc[-1])
        for key, P in PATTERNS.items():
            if not P["prereq"](s, cfg):
                continue
            try:
                res = evaluate(df, P["detect"], getattr(cfg, P["cfg"]), cfg.status, ctx)
            except Exception as e:  # one bad series must not kill the run
                if debug:
                    log(f"  {t} {key}: ERROR {e}")
                continue
            if not res["status"]:
                if debug:
                    log(f"  {t:6} {P['name']:16} - {'; '.join(res['reasons'])}")
                continue
            rs_pts = float(np.clip((s["rs"] - 70) / 29, 0, 1)) * 15
            row = {
                "ticker": t, "name": names.get(t, ""), "pattern": key, "pattern_name": P["name"],
                "status": res["status"], "score": round(res["score"] + rs_pts, 1),
                "rs": int(s["rs"]), "rs_line_high": rs_line_new_high(df, bench),
                "tt_pass": s["tt_pass"], "tt": tt,
                "close": round(close, 2), "chg_pct": round((close / df["Close"].iloc[-2] - 1) * 100, 2),
                "pivot": res["pivot"], "entry": res["entry"], "stop": res["stop"],
                "risk_pct": res["risk_pct"], "vs_pivot_pct": res["vs_pivot_pct"], "vol_x": res["vol_x"],
                "base_days": int(res["base_days"]), "details": res["details"], "metrics": res.get("metrics", {}),
            }
            cands.append(row)
            hits.setdefault(t, []).append({**row, "base_start": res["base_start"],
                                           "overlays": res.get("overlays", {})})
    order = {"BREAKOUT": 0, "SETUP": 1, "EXTENDED": 2}
    cands.sort(key=lambda r: (order[r["status"]], -r["score"]))
    stats = {"loaded": len(data), "liquid": len(liq), "trend_template": n_tt,
             "candidates": len(cands), "seconds": round(time.time() - t0, 1)}
    return cands, hits, market, stats


def truncate(d: dict[str, pd.DataFrame], day: pd.Timestamp) -> dict[str, pd.DataFrame]:
    out = {}
    for t, df in d.items():
        x = df[df.index <= day]
        if len(x) and x.index[-1] == day:
            out[t] = x
    return out


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--universe", choices=["us", "sp500"])
    src.add_argument("--tickers", nargs="+")
    src.add_argument("--demo", action="store_true", help="synthetic data, no download")
    ap.add_argument("--out", default="build")
    ap.add_argument("--history", default="state/history.json")
    ap.add_argument("--backfill", type=int, default=0,
                    help="also scan the previous N sessions to seed the signal history")
    ap.add_argument("--email", action="store_true", help="email new breakouts (needs SMTP_* env vars)")
    ap.add_argument("--site-url", default=os.environ.get("SITE_URL", ""))
    ap.add_argument("--limit", type=int, default=0, help="debug: only the first N tickers")
    ap.add_argument("--debug", action="store_true", help="print why each stock/pattern was rejected")
    a = ap.parse_args()
    cfg = Config()
    started = dt.datetime.now(HKT)

    if a.demo:
        from .demo import make_demo
        names, data = make_demo()
    else:
        if a.universe:
            log(f"Loading {a.universe} universe ...")
            names = load_universe(a.universe)
        else:
            names = {t.upper(): "" for t in a.tickers}
        tickers = sorted(names)
        if a.limit:
            tickers = tickers[:a.limit]
        log(f"Downloading {len(tickers)} stocks + indexes ...")
        data = fetch(tickers + INDEXES, period="2y", log=log)

    indexes = {k: data.pop(k) for k in INDEXES if k in data}
    if not data:
        raise SystemExit("No price data loaded.")
    # scan date = the most common last bar date; drop stale (delisted / halted) series
    last_dates = pd.Series({t: df.index[-1] for t, df in data.items()})
    day = last_dates.mode().iloc[0]
    data = {t: df[df.index <= day] for t, df in data.items() if df.index[-1] >= day - pd.Timedelta(days=7)}
    indexes = {k: df[df.index <= day] for k, df in indexes.items()}
    log(f"Scanning {len(data)} stocks as of {day:%Y-%m-%d}")

    hist = history.load(a.history)
    if a.backfill:
        sessions = sorted({d for df in indexes.values() for d in df.index} or set(last_dates.unique()))
        past = [d for d in sessions if d < day][-a.backfill:]
        for d in past:
            sub = truncate(data, d)
            c, _, _, st = scan(sub, truncate(indexes, d), names, cfg)
            new = history.add_signals(hist, c, d.strftime("%Y-%m-%d"))
            log(f"  backfill {d:%Y-%m-%d}: {st['liquid']} liquid, {len(new)} new breakouts ({st['seconds']}s)")

    cands, hits, market, stats = scan(data, indexes, names, cfg, debug=a.debug)
    date_s = day.strftime("%Y-%m-%d")
    new_signals = history.add_signals(hist, cands, date_s)
    history.update(hist, data)
    if not a.demo or a.history != "state/history.json":
        history.save(a.history, hist)

    charts = {t: site_builder.chart_payload(t, names.get(t, ""), data[t], hs) for t, hs in hits.items()}
    site_url = a.site_url
    latest = {
        "data_date": date_s,
        "generated_hkt": dt.datetime.now(HKT).strftime("%Y-%m-%d %H:%M"),
        "run_minutes": round((dt.datetime.now(HKT) - started).total_seconds() / 60, 1),
        "demo": bool(a.demo),
        "stats": stats,
        "market": market,
        "patterns": {k: v["name"] for k, v in PATTERNS.items()},
        "candidates": cands,
        "new_breakouts": [s["id"] for s in new_signals],
        "site_url": site_url,
    }
    site_builder.build(a.out, latest, charts, hist)
    by = pd.Series([c["status"] for c in cands]).value_counts().to_dict() if cands else {}
    log(f"Done: {stats['liquid']} liquid, {stats['trend_template']} pass Trend Template, "
        f"{len(cands)} candidates {by}. Market: {market['regime']}. Site -> {a.out}")
    for c in cands:
        log(f"  {c['status']:9} {c['ticker']:6} {c['pattern_name']:16} score {c['score']:5.1f}  "
            f"close {c['close']:8.2f}  pivot {c['pivot']:8.2f}  {c['details']}")
    if a.email:
        today_bo = [c for c in cands if c["status"] in ("BREAKOUT", "EXTENDED")
                    and f"{date_s}-{c['ticker']}-{c['pattern']}" in latest["new_breakouts"]]
        alerts.send(today_bo, market, site_url, date_s, log=log)


if __name__ == "__main__":
    main()
