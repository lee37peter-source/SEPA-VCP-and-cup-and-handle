"""Regression test on the synthetic market:  python -m tests.test_patterns"""
from screener import history
from screener.config import Config
from screener.data import INDEXES
from screener.demo import make_demo
from screener.run import scan, truncate


def main():
    names, data = make_demo()
    idx = {k: data.pop(k) for k in INDEXES}
    cands, hits, market, stats = scan(data, idx, names, Config())
    got = {(c["ticker"], c["pattern"], c["status"]) for c in cands}
    expect = {("VCPA", "vcp", "SETUP"), ("VCPB", "vcp", "SETUP"), ("CUPA", "cup", "SETUP"),
              ("HTFX", "htf", "SETUP"), ("DBLB", "dbl", "SETUP"), ("FLAT", "flat", "SETUP"),
              ("BRKV", "vcp", "BREAKOUT"), ("BRKC", "cup", "BREAKOUT")}
    missing = expect - got
    decoys = {c["ticker"] for c in cands} & {"LOOS", "DOWN", "RUNR"}
    assert not missing, f"missed: {missing}"
    assert not decoys, f"false positives: {decoys}"

    # walk forward to check breakout recording + stop tracking
    hist = []
    days = sorted(idx["SPY"].index)[-40:]
    for d in days:
        c, _, _, _ = scan(truncate(data, d), truncate(idx, d), names, Config())
        history.add_signals(hist, c, d.strftime("%Y-%m-%d"))
    history.update(hist, data)
    st = {(r["ticker"], r["pattern"]): r["status"] for r in hist}
    assert st.get(("WINR", "vcp")) == "open", st
    assert st.get(("LOSR", "vcp")) == "stopped", st
    print(f"OK - {len(cands)} candidates, all {len(expect)} planted patterns found, no decoys; "
          f"history tracked {len(hist)} breakouts")


if __name__ == "__main__":
    main()
