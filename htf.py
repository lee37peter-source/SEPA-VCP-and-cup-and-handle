"""High tight flag (O'Neil).

Pole: price up 90%+ in 8 weeks or less. Flag: 3-5 weeks of sideways-to-down action no more
than 25% deep, ideally on lighter volume. Pivot = flag high (top of the pole)."""
from __future__ import annotations

import numpy as np

from ..common import arrays, clip01, fail


def detect(df, p, ctx):
    h, l, c, v = arrays(df)
    n = len(h)
    if n < p.pole_max + p.flag_max + 5:
        return fail("not enough data")
    lo_i, hi_i = n - 1 - p.flag_max, n - p.flag_min
    F = lo_i + int(np.argmax(h[lo_i:hi_i]))
    if h[F + 1:].max() > h[F]:
        return fail("no flag (price at new highs)")
    P = F - p.pole_max + int(np.argmin(l[F - p.pole_max:F + 1]))
    gain = h[F] / l[P] - 1
    if gain < p.pole_min_gain:
        return fail(f"pole only +{gain:.0%}")
    fl_i = F + 1 + int(np.argmin(l[F + 1:]))
    fdepth = (h[F] - l[fl_i]) / h[F]
    if fdepth > p.flag_max_depth:
        return fail(f"flag {fdepth:.0%} too deep")
    pole_vol = v[P:F + 1].mean()
    flag_vol = v[F + 1:].mean()
    vr = flag_vol / pole_vol if pole_vol > 0 else 1.0
    flag_len = n - 1 - F
    score = (clip01((gain - 0.9) / 0.6) * 20
             + clip01(1 - fdepth / p.flag_max_depth) * 20
             + clip01((1 - vr) / 0.6) * 20
             + clip01(1.5 - (F - P) / p.pole_max) * 15)      # faster pole scores higher
    return {
        "reasons": [],
        "pivot": h[F],
        "stop": l[fl_i],
        "score": score,
        "base_start": P,
        "base_days": flag_len,
        "details": f"Pole +{gain * 100:.0f}% in {(F - P) // 5 or 1} wks · flag {fdepth * 100:.1f}% deep over "
                   f"{flag_len} days on {vr:.2f}x pole volume",
        "metrics": {"pole_gain": round(gain * 100, 1), "flag_depth": round(fdepth * 100, 1)},
        "overlays": {
            "paths": [[[P, l[P]], [F, h[F]], [fl_i, l[fl_i]]]],
            "labels": [[P, l[P], "Pole start", "below"], [F, h[F], f"Pivot (+{gain * 100:.0f}%)", "above"],
                       [fl_i, l[fl_i], f"Flag -{fdepth * 100:.0f}%", "below"]],
        },
    }
