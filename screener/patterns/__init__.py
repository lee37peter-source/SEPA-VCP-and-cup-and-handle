"""Pattern registry: detector, config section, and prerequisites for each pattern."""
from . import cup_handle, double_bottom, flat_base, htf, vcp

# prereq(stock, cfg): stock is a dict with tt_pass, rs, above_200
PATTERNS = {
    "vcp": {"name": "VCP", "detect": vcp.detect, "cfg": "vcp",
            "prereq": lambda s, cfg: s["tt_pass"] and s["rs"] >= cfg.min_rs},
    "cup": {"name": "Cup with Handle", "detect": cup_handle.detect, "cfg": "cup",
            "prereq": lambda s, cfg: s["above_200"] and s["rs"] >= cfg.min_rs_deep_base},
    "htf": {"name": "High Tight Flag", "detect": htf.detect, "cfg": "htf",
            "prereq": lambda s, cfg: True},
    "dbl": {"name": "Double Bottom", "detect": double_bottom.detect, "cfg": "dbl",
            "prereq": lambda s, cfg: s["above_200"] and s["rs"] >= cfg.min_rs_deep_base},
    "flat": {"name": "Flat Base", "detect": flat_base.detect, "cfg": "flat",
             "prereq": lambda s, cfg: s["tt_pass"] and s["rs"] >= cfg.min_rs},
}
