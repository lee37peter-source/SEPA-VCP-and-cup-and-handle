"""Double bottom (O'Neil "W").

Left high L (after a 30%+ advance) -> first low B1 -> middle peak M -> second low B2 that
undercuts B1 slightly -> price recovering toward M. Base 7+ weeks, 12-35% deep.
Pivot = middle peak M."""
from __future__ import annotations

import numpy as np

from ..common import arrays, clip01, fail, swing_flags


def detect(df, p, ctx):
    h, l, c, v = arrays(df)
    n = len(h)
    if n < p.min_len + p.prior_lookback:
        return fail("not enough data")
    is_h, _ = swing_flags(h, l, p.swing_window)
    vol50 = v[-50:].mean()
    best, why = None, "no W found"
    for M in range(n - 1 - p.leg_min - 3, max(p.prior_lookback + 2 * p.leg_min, n - p.max_len), -1):
        if not is_h[M]:
            continue
        hM = h[M]
        if h[M + 1:].max() > hM:
            continue
        B2 = M + 1 + int(np.argmin(l[M + 1:]))
        if B2 - M < p.leg_min or n - 1 - B2 < 3:
            continue
        for lb in (40, 65, 100, 150, 200, 260, 325):
            lo = M - lb
            if lo < p.prior_lookback:
                break
            L = lo + int(np.argmax(h[lo:M - p.leg_min]))
            hL = h[L]
            if hM >= hL or h[L + 1:].max() > hL:
                continue
            B1 = L + 1 + int(np.argmin(l[L + 1:M]))
            if B1 - L < p.leg_min or M - B1 < p.leg_min:
                continue
            if h[B1:B2 + 1].max() > hM:
                continue
            under = 1 - l[B2] / l[B1]
            if not (0 <= under <= p.max_undercut):
                why = "second low does not undercut the first" if under < 0 else "second low undercuts too far"
                continue
            depth = (hL - l[B2]) / hL
            if not (p.min_depth <= depth <= p.max_depth):
                why = f"base {depth:.0%} deep"
                continue
            retr = (hM - l[B1]) / (hL - l[B1])
            if retr < p.min_mid_retrace:
                why = "middle peak too low"
                continue
            if n - 1 - L < p.min_len or n - 1 - L > p.max_len:
                continue
            prior = hL / l[L - p.prior_lookback:L].min() - 1
            if prior < p.prior_uptrend:
                why = f"prior uptrend only {prior:.0%}"
                continue
            dry = v[max(B2 - 2, 0):B2 + 3].mean() / vol50 if vol50 > 0 else 1.0
            score = ((1.0 if 0.18 <= depth <= 0.33 else 0.5) * 15
                     + (1.0 if 0.005 <= under <= 0.05 else 0.4) * 15
                     + clip01((retr - 0.4) / 0.4) * 15
                     + clip01(1 - abs((B1 - L) - (B2 - M)) / max(B1 - L, B2 - M)) * 15
                     + clip01((1.2 - dry) / 0.6) * 15)
            if best is None or score > best[0]:
                best = (score, L, B1, M, B2, depth, under, dry)
    if best is None:
        return fail(why)
    score, L, B1, M, B2, depth, under, dry = best
    return {
        "reasons": [],
        "pivot": h[M],
        "stop": l[B2],
        "score": score,
        "base_start": L,
        "base_days": n - 1 - L,
        "details": f"W {depth * 100:.0f}% deep over {(n - 1 - L) // 5} wks · 2nd low undercuts by "
                   f"{under * 100:.1f}% · volume at low {dry:.2f}x avg",
        "metrics": {"depth": round(depth * 100, 1), "undercut": round(under * 100, 1)},
        "overlays": {
            "paths": [[[L, h[L]], [B1, l[B1]], [M, h[M]], [B2, l[B2]], [n - 1, c[-1]]]],
            "labels": [[L, h[L], "Left high", "above"], [B1, l[B1], "Low 1", "below"],
                       [M, h[M], "Pivot", "above"], [B2, l[B2], f"Low 2 (-{under * 100:.1f}%)", "below"]],
        },
    }
