"""Universe lists and price downloads (Yahoo Finance via yfinance)."""
from __future__ import annotations

import sys
import time

import pandas as pd

OHLCV = ["Open", "High", "Low", "Close", "Volume"]
INDEXES = ["^GSPC", "^IXIC", "SPY", "QQQ"]

_BAD_NAME_WORDS = ("Warrant", "Unit", "Right", "Preferred", "Notes due", "Debenture",
                   "Depositary Share representing", "% ", "Acquisition Corp")


def load_universe(name: str) -> dict[str, str]:
    """Return {ticker: company name}."""
    if name == "us":
        a = b = None
        for base in ("https://www.nasdaqtrader.com/dynamic/SymDir/",
                     "ftp://ftp.nasdaqtrader.com/SymbolDirectory/"):
            try:
                a = pd.read_csv(base + "nasdaqlisted.txt", sep="|")
                b = pd.read_csv(base + "otherlisted.txt", sep="|")
                break
            except Exception as e:
                print(f"Symbol list from {base} failed: {e}")
        if a is None or b is None:
            print("Falling back to the S&P 500 list")
            return load_universe("sp500")
        a = a[(a["Test Issue"] == "N") & (a["ETF"] == "N")][["Symbol", "Security Name"]]
        b = b[(b["Test Issue"] == "N") & (b["ETF"] == "N")][["ACT Symbol", "Security Name"]]
        df = pd.concat([a, b.rename(columns={"ACT Symbol": "Symbol"})]).dropna()
        df = df[~df["Symbol"].astype(str).str.startswith("File Creation")]
        ok = df["Security Name"].apply(lambda s: not any(w in s for w in _BAD_NAME_WORDS))
        df = df[ok & ~df["Symbol"].astype(str).str.contains(r"[\$\^]", regex=True)]
        pairs = zip(df["Symbol"].astype(str), df["Security Name"].astype(str))
    elif name == "sp500":
        url = ("https://raw.githubusercontent.com/datasets/"
               "s-and-p-500-companies/main/data/constituents.csv")
        df = pd.read_csv(url)
        pairs = zip(df["Symbol"].astype(str), df["Security"].astype(str))
    else:
        raise ValueError(name)
    out = {}
    for sym, nm in pairs:
        sym = sym.strip().replace(".", "-")
        if sym:
            out[sym] = _short_name(nm)
    return out


def _short_name(n: str) -> str:
    for cut in (" - ", " Common Stock", " Class A", " Ordinary Shares", " American Depositary"):
        i = n.find(cut)
        if i > 0:
            n = n[:i]
    return n.strip()[:48]


def clean(df: pd.DataFrame | None, min_bars: int = 60) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    df = df.rename(columns={c: str(c).title() for c in df.columns})
    if not set(OHLCV).issubset(df.columns):
        return None
    df = df[OHLCV].dropna(subset=["Close", "High", "Low"])
    df["Volume"] = df["Volume"].fillna(0)
    df["Open"] = df["Open"].fillna(df["Close"])
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df if len(df) >= min_bars else None


def _download(batch, period):
    import yfinance as yf
    return yf.download(batch, period=period, interval="1d", auto_adjust=True,
                       group_by="ticker", threads=True, progress=False)


def _split(raw, batch) -> dict[str, pd.DataFrame]:
    out = {}
    if raw is None or raw.empty:
        return out
    if isinstance(raw.columns, pd.MultiIndex):
        lv0 = set(raw.columns.get_level_values(0))
        lv1 = set(raw.columns.get_level_values(1))
        for t in batch:
            if t in lv0:
                df = raw[t]
            elif t in lv1:
                df = raw.xs(t, axis=1, level=1)
            else:
                continue
            df = clean(df.copy())
            if df is not None:
                out[t] = df
    elif len(batch) == 1:
        df = clean(raw.copy())
        if df is not None:
            out[batch[0]] = df
    return out


def fetch(tickers: list[str], period: str = "2y", chunk: int = 150, pause: float = 2.0,
          log=print) -> dict[str, pd.DataFrame]:
    try:
        import yfinance  # noqa: F401
    except ImportError:
        sys.exit("yfinance missing: pip install -r requirements.txt")
    out: dict[str, pd.DataFrame] = {}
    todo = list(tickers)
    for attempt, (size, wait) in enumerate([(chunk, pause), (50, 5.0), (20, 10.0)]):
        if not todo:
            break
        if attempt:
            log(f"Retrying {len(todo)} missing tickers (pass {attempt + 1}) ...")
            time.sleep(wait * 3)
        for i in range(0, len(todo), size):
            batch = todo[i:i + size]
            try:
                out.update(_split(_download(batch, period), batch))
            except Exception as e:  # rate limits / network blips
                log(f"  batch {i // size + 1} failed: {e}")
                time.sleep(wait * 3)
            if attempt == 0 and (i // size) % 10 == 0:
                log(f"  {min(i + size, len(todo))}/{len(todo)} requested, {len(out)} loaded")
            time.sleep(wait)
        todo = [t for t in todo if t not in out]
    log(f"Loaded {len(out)} of {len(tickers)} tickers")
    return out
