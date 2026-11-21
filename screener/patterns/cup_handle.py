"""Cup with handle (O'Neil).

Handle: the right-side high R sits 1-4 weeks back with no higher high since; the pullback
from R (the handle) is <= 12% deep, in the upper half of the cup, on lighter volume.
Cup: a left-side high L 6+ weeks before R, preceded by a 30%+ advance; cup 12-35% deep
(50% in a weak market); nothing inside the cup pokes above the rims; rounded, not a V.
Pivot = handle high (R)."""
from __future__ import annotations

import numpy as np

from ..common import arrays, clip01, fail, swing_flags


def detect(df, p, ctx):
    h, l, c, v = arrays(df)
    n = len(h)
    if n < p.cup_min + p.handle_max + 40:
        return fail("not enough data")
    lo_i, hi_i = n - 1 - p.handle_max, n - p.handle_min      # candidate R range
    R = lo_i + int(np.argmax(h[lo_i:hi_i]))
    hR = h[R]
    if h[R + 1:].max() > hR:
        return fail("no handle (price at new highs)")
    handle_len = n - 1 - R
    hl_i = R + 1 + int(np.argmin(l[R + 1:]))
    hlow = l[hl_i]
    hdepth = (hR - hlow) / hR
    if hdepth > p.handle_max_depth:
        return fail(f"handle {hdepth:.0%} too deep")
    vol50 = v[-50:].mean()
    hvol = v[R + 1:].mean() / vol50 if vol50 > 0 else np.nan
    if not hvol <= p.handle_vol_max:
        return fail(f"handle volume {hvol:.2f}x avg (not drying up)")

    max_depth = p.max_depth_weak_market if ctx.weak_market else p.max_depth
    is_h, _ = swing_flags(h, l, 5)
    best, why = None, "no cup found"
    for L in range(max(p.prior_lookback, R - p.base_max), R - p.cup_min + 1):
        if not is_h[L]:
            continue
        hL = h[L]
        if not (p.right_rim_min * hL <= hR <= p.right_rim_max * hL):
            continue
        rim = min(hL, hR)
        if h[L + 1:R].max() > rim * (1 + p.interior_tolerance):
            why = "price above the rim inside the cup"
            continue
        B = L + 1 + int(np.argmin(l[L + 1:R]))
        depth = (hL - l[B]) / hL
        if not (p.min_depth <= depth <= max_depth):
            why = f"cup {depth:.0%} deep"
            continue
        if B - L < p.side_min or R - B < p.side_min:
            why = "cup sides too short"
            continue
        if hlow < l[B] + 0.5 * (rim - l[B]):
            why = "handle in lower half of cup"
            continue
        prior = hL / l[L - p.prior_lookback:L].min() - 1
        if prior < p.prior_uptrend:
            why = f"prior uptrend only {prior:.0%}"
            continue
        band = l[B] + 0.25 * (hL - l[B])
        roundness = float(np.mean(l[L:R + 1] <= band))
        if roundness < p.min_roundness:
            why = "V-shaped cup"
            continue
        ideal = 1.0 if 0.15 <= depth <= 0.33 else 0.5
        score = (ideal * 15
                 + clip01((roundness - 0.25) / 0.25) * 15
                 + clip01(1 - hdepth / p.handle_max_depth) * 15
                 + clip01((1 - hvol) / 0.5) * 15
                 + clip01(1 - abs(hR / hL - 1) / 0.10) * 15)
        if best is None or score > best[0]:
            best = (score, L, B, depth, roundness)
    if best is None:
        return fail(why)
    score, L, B, depth, roundness = best
    base_days = n - 1 - L
    return {
        "reasons": [],
        "pivot": hR,
        "stop": hlow,
        "score": score,
        "base_start": L,
        "base_days": base_days,
        "details": f"Cup {depth * 100:.0f}% deep, {(R - L) // 5} wks · handle {hdepth * 100:.1f}% over "
                   f"{handle_len} days on {hvol:.2f}x volume",
        "metrics": {"cup_depth": round(depth * 100, 1), "handle_depth": round(hdepth * 100, 1),
                    "roundness": round(roundness, 2)},
        "overlays": {
            "paths": [[[L, h[L]], [B, l[B]], [R, hR], [hl_i, hlow]]],
            "labels": [[L, h[L], "Left high", "above"], [B, l[B], f"Cup -{depth * 100:.0f}%", "below"],
                       [R, hR, "Pivot", "above"], [hl_i, hlow, f"Handle -{hdepth * 100:.1f}%", "below"]],
        },
    }
