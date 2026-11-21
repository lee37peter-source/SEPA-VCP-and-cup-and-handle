"""Flat base (O'Neil).

At least 5 weeks moving sideways in a range no more than 15% deep, after a 20%+ advance.
The base high is set early (left side), so a slow drift up is not mistaken for a base.
Pivot = base high."""
from __future__ import annotations

import numpy as np

from ..common import arrays, clip01, fail


def detect(df, p, ctx):
    h, l, c, v = arrays(df)
    n = len(h)
    if n < p.min_len + p.prior_lookback + 5:
        return fail("not enough data")
    N = 0
    for m in range(p.min_len, min(p.max_len, n - p.prior_lookback - 1) + 1):
        hi, lo = h[n - m:].max(), l[n - m:].min()
        if (hi - lo) / hi > p.max_depth:
            break
        N = m
    if N == 0:
        lo5 = l[n - p.min_len:].min(); hi5 = h[n - p.min_len:].max()
        return fail(f"last 5 weeks range {(hi5 - lo5) / hi5:.0%} (max {p.max_depth:.0%})")
    s = n - N
    hi = h[s:].max()
    # the base starts at its left-side high: the first bar that reaches (near) the range top
    s = s + int(np.argmax(h[s:] >= hi * (1 - p.left_high_tol)))
    N = n - s
    if N < p.min_len:
        return fail(f"range top set only {N} days ago (highs still rising)")
    hi = h[s:].max()
    lo_i = s + int(np.argmin(l[s:]))
    depth = (hi - l[lo_i]) / hi
    left = h[s:s + max(3, int(N * p.left_high_share))].max()
    if left < hi * (1 - p.left_high_tol):
        return fail("highs rising through the range (not a flat base)")
    prior = hi / l[s - p.prior_lookback:s].min() - 1
    if prior < p.prior_advance:
        return fail(f"prior advance only {prior:.0%}")
    vol50 = v[-50:].mean()
    dry = v[-10:].mean() / vol50 if vol50 > 0 else 1.0
    tight = (h[-10:].max() - l[-10:].min()) / h[-10:].max()
    score = (clip01(1 - (depth - 0.08) / 0.07) * 20
             + clip01((N - p.min_len) / 25) * 15
             + clip01((1 - dry) / 0.5) * 20
             + clip01(1 - (tight - 0.03) / 0.07) * 20)
    hi_i = s + int(np.argmax(h[s:]))
    return {
        "reasons": [],
        "pivot": hi,
        "stop": l[lo_i],
        "score": score,
        "base_start": s,
        "base_days": N,
        "details": f"{N // 5} wks, {depth * 100:.1f}% deep after a +{prior * 100:.0f}% advance · "
                   f"last 2 wks range {tight * 100:.1f}% · volume {dry:.2f}x avg",
        "metrics": {"depth": round(depth * 100, 1), "weeks": N // 5},
        "overlays": {
            "paths": [[[s, hi], [n - 1, hi]], [[s, l[lo_i]], [n - 1, l[lo_i]]]],
            "labels": [[hi_i, hi, "Base high (pivot)", "above"], [lo_i, l[lo_i], f"-{depth * 100:.1f}%", "below"]],
        },
    }
