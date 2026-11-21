"""Write the static site: web assets + data/latest.json + data/charts/<T>.json + data/history.json."""
from __future__ import annotations

import json
import math
import os
import shutil

import numpy as np
import pandas as pd

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def _r(x, nd=2):
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else round(x, nd)


def chart_payload(ticker: str, name: str, df: pd.DataFrame, hits: list[dict]) -> dict:
    n = len(df)
    first_base = min((h["base_start"] for h in hits), default=n - 1)
    start = max(0, min(n - 260, first_base - 40))
    d = df.iloc[start:]
    c = df["Close"]
    dates = [ts.strftime("%Y-%m-%d") for ts in d.index]
    nd = 4 if float(c.iloc[-1]) < 5 else 2

    def ser(s):
        return [_r(x, nd) for x in s.iloc[start:]]

    def date_of(i):
        return dates[max(0, min(len(dates) - 1, int(i) - start))]

    pats = []
    for hit in hits:
        ov = hit.get("overlays", {})
        pats.append({
            "pattern": hit["pattern"], "pattern_name": hit["pattern_name"], "status": hit["status"],
            "pivot": hit["pivot"], "stop": hit["stop"], "entry": hit["entry"],
            "paths": [[[date_of(i), _r(p, nd)] for i, p in path] for path in ov.get("paths", [])],
            "labels": [[date_of(i), _r(p, nd), txt, pos] for i, p, txt, pos in ov.get("labels", [])],
        })
    return {
        "ticker": ticker, "name": name, "t": dates,
        "o": [_r(x, nd) for x in d["Open"]], "h": [_r(x, nd) for x in d["High"]],
        "l": [_r(x, nd) for x in d["Low"]], "c": [_r(x, nd) for x in d["Close"]],
        "v": [int(x) for x in d["Volume"].fillna(0)],
        "sma50": ser(c.rolling(50).mean()), "sma150": ser(c.rolling(150).mean()),
        "sma200": ser(c.rolling(200).mean()),
        "patterns": pats,
    }


class _Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        return super().default(o)


def _dump(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, cls=_Enc, separators=(",", ":"))


def build(out_dir: str, latest: dict, charts: dict[str, dict], history: list[dict]):
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(WEB_DIR, out_dir)
    os.makedirs(os.path.join(out_dir, "data", "charts"), exist_ok=True)
    _dump(latest, os.path.join(out_dir, "data", "latest.json"))
    _dump(history, os.path.join(out_dir, "data", "history.json"))
    for t, payload in charts.items():
        _dump(payload, os.path.join(out_dir, "data", "charts", f"{t}.json"))
    open(os.path.join(out_dir, ".nojekyll"), "w").close()
