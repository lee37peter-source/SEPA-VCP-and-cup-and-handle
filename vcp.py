"""Volatility Contraction Pattern (Minervini).

Walk the swing highs/lows from the base high, merge them so the structure is lower-ish highs
and strictly higher lows, then require 2-6 contractions that tighten (e.g. 25% > 12% > 6%),
a tight final contraction, and volume drying up. Pivot = high of the final contraction."""
from __future__ import annotations

import numpy as np

from ..common import arrays, clip01, fail, swing_flags


def _normalize(cons, p):
    changed = True
    while changed:
        changed = False
        for j in range(1, len(cons)):
            (hp, lp), (hj, lj) = cons[j - 1], cons[j]
            if lj is not None and lp is not None and lj[1] <= lp[1]:
                cons[j - 1] = [hp if hp[1] >= hj[1] else hj, lj]
                del cons[j]
                changed = True
                break
            if j - 1 >= 1 and hj[1] > hp[1] * (1 + p.high_tolerance):
                del cons[j - 1]
                changed = True
                break
        if not changed:
            last_complete = max((i for i, c in enumerate(cons) if c[1] is not None), default=-1)
            for j in range(1, last_complete):
                hv, lv = cons[j][0][1], cons[j][1][1]
                if (hv - lv) / hv < p.noise_depth:
                    del cons[j]
                    changed = True
                    break
    return cons


def _analyze(h, l, c, v, h0, p, is_h, is_l):
    n = len(c)
    k = p.swing_window
    seq = [["H", h0, h[h0]]]

    def push(t, i, val):
        last = seq[-1]
        if last[0] == t:
            if (t == "H" and val > last[2]) or (t == "L" and val < last[2]):
                seq[-1] = [t, i, val]
        else:
            seq.append([t, i, val])

    for i in range(h0 + 1, n - k):
        if is_h[i] and is_l[i]:
            if seq[-1][0] == "H":
                push("L", i, l[i]); push("H", i, h[i])
            else:
                push("H", i, h[i]); push("L", i, l[i])
        elif is_h[i]:
            push("H", i, h[i])
        elif is_l[i]:
            push("L", i, l[i])

    s = seq[-1][1] + 1                     # unconfirmed tail
    if s < n:
        if seq[-1][0] == "H":
            j = s + int(np.argmin(l[s:])); push("L", j, l[j])
            if j + 1 < n:
                m = j + 1 + int(np.argmax(h[j + 1:])); push("H", m, h[m])
                if m + 1 < n:
                    q = m + 1 + int(np.argmin(l[m + 1:])); push("L", q, l[q])
        else:
            j = s + int(np.argmax(h[s:])); push("H", j, h[j])
            if j + 1 < n:
                q = j + 1 + int(np.argmin(l[j + 1:])); push("L", q, l[q])

    cons, i = [], 0
    while i < len(seq):
        if seq[i][0] == "H":
            lo = (seq[i + 1][1], seq[i + 1][2]) if i + 1 < len(seq) else None
            cons.append([(seq[i][1], seq[i][2]), lo])
            i += 2
        else:
            i += 1
    cons = _normalize(cons, p)
    complete = [cc for cc in cons if cc[1] is not None]
    depths = [(H[1] - L[1]) / H[1] for H, L in complete]
    R = []
    base_days = n - 1 - h0
    if base_days < p.min_base_days:
        R.append(f"base only {base_days}d")
    if not complete:
        return {"reasons": R + ["no contraction"]}
    nC = len(complete)
    if nC < p.min_contractions:
        R.append(f"{nC} contraction")
    if nC > p.max_contractions:
        R.append(f"{nC} contractions (too many)")
    if depths[0] > p.max_first_depth:
        R.append(f"first pullback {depths[0]:.0%} too deep")
    if depths[-1] > p.max_last_depth:
        R.append(f"final contraction {depths[-1]:.1%} not tight")
    if nC >= 2 and depths[-1] > depths[0] * p.max_tighten_ratio:
        R.append("not tightening")
    viol = sum(depths[i] > depths[i - 1] * (1 + p.depth_tolerance) for i in range(1, nC))
    if viol > p.max_violations:
        R.append(f"{viol} expanding contractions")
    if p.min_step_ratio > 0 and any(depths[i] < depths[i - 1] * p.min_step_ratio for i in range(1, nC)):
        R.append("V-shaped (contraction shrinks too abruptly)")
    vol50 = v[-50:].mean()
    dry = v[-10:].mean() / vol50 if vol50 > 0 else np.nan
    if not dry <= p.dryup_max:
        R.append(f"no volume dry-up (10d/50d {dry:.2f})")
    if R:
        return {"reasons": R}

    score = (min(nC, 4) / 4 * 15
             + clip01(1 - depths[-1] / p.max_last_depth) * 20
             + (clip01(1 - (depths[-1] / depths[0]) / p.max_tighten_ratio) * 20 if nC >= 2 else 0)
             + clip01((1 - dry) / 0.5) * 20)
    labels = [[L[0], L[1], f"-{d * 100:.1f}%", "below"] for (H, L), d in zip(complete, depths)]
    labels.append([complete[-1][0][0], complete[-1][0][1], "Pivot", "above"])
    return {
        "reasons": [],
        "pivot": complete[-1][0][1],
        "stop": complete[-1][1][1],
        "score": score,
        "base_start": h0,
        "base_days": base_days,
        "details": f"{nC} contractions: " + " > ".join(f"{d * 100:.1f}%" for d in depths)
                   + f" · {base_days // 5} wks · volume {dry:.2f}x avg",
        "metrics": {"contractions": [round(d * 100, 1) for d in depths], "dryup": round(float(dry), 2)},
        "overlays": {"paths": [[[H[0], H[1]], [L[0], L[1]]] for H, L in complete], "labels": labels},
    }


def detect(df, p, ctx):
    h, l, c, v = arrays(df)
    n = len(h)
    if n < 60:
        return fail("not enough data")
    is_h, is_l = swing_flags(h, l, p.swing_window)
    starts = {n - lb + int(np.argmax(h[n - lb:]))
              for lb in (min(x, p.max_lookback, n) for x in (40, 65, 100, 130, 190, 250))}
    results = [_analyze(h, l, c, v, s, p, is_h, is_l) for s in sorted(starts)]
    valid = [r for r in results if not r["reasons"]]
    if valid:
        return max(valid, key=lambda r: r["score"])
    return min(results, key=lambda r: len(r["reasons"]))
