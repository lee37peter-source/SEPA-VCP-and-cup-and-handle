"""Signal history: every breakout is recorded and tracked for 60 sessions.

Assumptions (shown on the site):
- BREAKOUT entries fill at the screener's entry price (a buy-stop just over the pivot).
- EXTENDED entries fill at the breakout-day close, since you would not have caught the pivot.
- A position is stopped out the first day the low touches the stop (filled at the stop, or at
  the open if it gapped below). Otherwise it is marked to the latest close until day 60."""
from __future__ import annotations

import json
import os

import pandas as pd

TRACK_DAYS = 60
MAX_RECORDS = 600


def load(path: str) -> list[dict]:
    if path and os.path.exists(path):
        with open(path) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save(path: str, records: list[dict]):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(records, f, indent=1)


def add_signals(records: list[dict], signals: list[dict], date: str) -> list[dict]:
    """Append today's breakouts (skipping repeats of the same ticker+pattern within 21 days)."""
    d0 = pd.Timestamp(date)
    new = []
    for s in signals:
        if s["status"] not in ("BREAKOUT", "EXTENDED"):
            continue
        rid = f"{date}-{s['ticker']}-{s['pattern']}"
        if any(r["id"] == rid for r in records):
            continue
        if any(r["ticker"] == s["ticker"] and r["pattern"] == s["pattern"]
               and (d0 - pd.Timestamp(r["date"])).days < 21 for r in records):
            continue
        entry = s["entry"] if s["status"] == "BREAKOUT" else s["close"]
        stop = max(s["stop"], round(entry * 0.92, 2))
        rec = {"id": rid, "date": date, "ticker": s["ticker"], "name": s.get("name", ""),
               "pattern": s["pattern"], "pattern_name": s["pattern_name"], "signal": s["status"],
               "entry": round(entry, 2), "stop": round(stop, 2), "pivot": s["pivot"],
               "score": s["score"], "rs": s.get("rs"), "status": "open",
               "last": s["close"], "ret_pct": round((s["close"] / entry - 1) * 100, 2),
               "max_pct": round((s["close"] / entry - 1) * 100, 2), "days": 0, "exit_date": None}
        records.append(rec)
        new.append(rec)
    return new


def update(records: list[dict], data: dict[str, pd.DataFrame]):
    for r in records:
        if r["status"] != "open":
            continue
        df = data.get(r["ticker"])
        if df is None:
            continue
        d0 = pd.Timestamp(r["date"])
        incl = df[df.index >= d0]
        after = df[df.index > d0]
        if incl.empty:
            continue
        entry, stop = r["entry"], r["stop"]
        max_high = float(incl["High"].iloc[0])
        r["days"] = int(len(after))
        exit_px, exit_date = None, None
        for i, (ts, row) in enumerate(after.iterrows()):
            if row["Low"] <= stop:
                exit_px = min(float(row["Open"]), stop)
                exit_date = ts
                r["status"] = "stopped"
                break
            max_high = max(max_high, float(row["High"]))
            if i + 1 >= TRACK_DAYS:
                exit_px, exit_date = float(row["Close"]), ts
                r["status"] = "closed"
                break
        last = exit_px if exit_px is not None else float(incl["Close"].iloc[-1])
        r["last"] = round(last, 2)
        r["ret_pct"] = round((last / entry - 1) * 100, 2)
        r["max_pct"] = round((max_high / entry - 1) * 100, 2)
        r["exit_date"] = exit_date.strftime("%Y-%m-%d") if exit_date is not None else None
    # bound file size: drop the oldest finished records first
    if len(records) > MAX_RECORDS:
        finished = [r for r in records if r["status"] != "open"]
        drop = {id(r) for r in finished[:len(records) - MAX_RECORDS]}
        records[:] = [r for r in records if id(r) not in drop]
