"""All tunable thresholds in one place. Defaults follow standard O'Neil / Minervini rules."""
from dataclasses import dataclass, field


@dataclass
class Universe:
    min_price: float = 10.0
    min_dollar_vol: float = 5e6          # 50-day average of close * volume
    min_bars: int = 260                  # ~1 year of history needed


@dataclass
class Status:
    breakout_vol: float = 1.4            # breakout-day volume vs 50-day average
    max_above_pivot: float = 0.02        # a "setup" may be at most 2% over its pivot
    max_chase: float = 0.05              # breakouts closing >5% past pivot are EXTENDED
    max_stop_pct: float = 0.08           # stop never more than 8% under the entry


@dataclass
class VCP:
    max_below_pivot: float = 0.06
    max_lookback: int = 250
    min_base_days: int = 15
    swing_window: int = 3
    high_tolerance: float = 0.02
    noise_depth: float = 0.015
    min_contractions: int = 2
    max_contractions: int = 6
    max_first_depth: float = 0.40
    max_last_depth: float = 0.10
    max_tighten_ratio: float = 0.5
    depth_tolerance: float = 0.15
    max_violations: int = 1
    min_step_ratio: float = 0.2
    dryup_max: float = 0.85


@dataclass
class Cup:
    max_below_pivot: float = 0.08
    handle_min: int = 5                  # 1 week
    handle_max: int = 20                 # 4 weeks
    cup_min: int = 30                    # cup (left high -> right high) at least 6 weeks
    base_max: int = 325                  # whole base at most 65 weeks
    min_depth: float = 0.12
    max_depth: float = 0.35
    max_depth_weak_market: float = 0.50
    handle_max_depth: float = 0.12
    prior_uptrend: float = 0.30
    prior_lookback: int = 130
    right_rim_min: float = 0.90          # right-side high vs left-side high
    right_rim_max: float = 1.05
    interior_tolerance: float = 0.03
    min_roundness: float = 0.25          # share of cup bars in the bottom quarter (a straight V = 0.25)
    side_min: int = 10
    handle_vol_max: float = 1.0          # handle avg volume / 50-day avg


@dataclass
class HTF:
    max_below_pivot: float = 0.10
    pole_max: int = 40                   # 8 weeks
    pole_min_gain: float = 0.90
    flag_min: int = 15                   # 3 weeks
    flag_max: int = 25                   # 5 weeks
    flag_max_depth: float = 0.25


@dataclass
class DoubleBottom:
    max_below_pivot: float = 0.08
    min_len: int = 35                    # 7 weeks
    max_len: int = 325
    min_depth: float = 0.12
    max_depth: float = 0.35
    max_undercut: float = 0.08           # second low may undercut the first by up to 8%
    min_mid_retrace: float = 0.40        # middle peak recovers >= 40% of the first decline
    leg_min: int = 5
    prior_uptrend: float = 0.30
    prior_lookback: int = 130
    swing_window: int = 3


@dataclass
class FlatBase:
    max_below_pivot: float = 0.06
    min_len: int = 25                    # 5 weeks
    max_len: int = 130
    max_depth: float = 0.15
    prior_advance: float = 0.20
    prior_lookback: int = 65
    left_high_share: float = 0.4         # the base high must be reached in the first 40% of the base
    left_high_tol: float = 0.03


@dataclass
class Config:
    universe: Universe = field(default_factory=Universe)
    status: Status = field(default_factory=Status)
    vcp: VCP = field(default_factory=VCP)
    cup: Cup = field(default_factory=Cup)
    htf: HTF = field(default_factory=HTF)
    dbl: DoubleBottom = field(default_factory=DoubleBottom)
    flat: FlatBase = field(default_factory=FlatBase)
    min_rs: float = 70.0                 # VCP, flat base
    min_rs_deep_base: float = 60.0       # cup with handle, double bottom (a 25-35% base drags RS down)
