"""Action-layer configuration -- data, not code (`Specification.md` §7.4).

⭐ §7.4 asked for an "engine-agnostic `gesture_config.json`" so tuned values do
not have to be maintained in two languages at once. `default_config.json` is that
file for the input layer, and `merged_config()` is the one place it is read.

⛔⛔ WHAT MUST NEVER GO IN HERE, AND IT IS THE ONLY RULE THAT MATTERS.
**No tuning constant that already lives in an estimator module.** `CHIRALITY_
CONFIRM_MS`, `BRIDGE_WINDOW_MS`, `GRAB_Z_TOLERANCE_M`, `EDGE_ON_THRESHOLD`,
`ROTATION_SLERP_TAU_MS` -- every one of those is derived from measurement, is
documented where it lives, and is imported by both tools. Copying any of them
into a config file creates a SECOND value that can be edited without the
derivation, which is how the two tools drift and how a constant loses its
question (4.2 paid 0.10 m for that lesson). This file holds only policy that
belongs to the ACTION layer itself.

⭐ THE ONE POLICY THAT LOOKS LIKE AN EXCEPTION AND IS NOT.
`grab_ready.require_valid_depth` defaults to `null` in the JSON, which means
*"inherit `palm_depth.SNAP_REQUIRES_VALID_DEPTH`"* -- the constant is READ, never
duplicated. A host may override it to `true`/`false` for its own game feel
(rule 7 records it as a tunable), and then the override is visibly a host
decision rather than a second source of truth.
"""
import copy
import json
import os

try:                                         # in-repo layout
    from Resources import palm_depth as _PD
except ImportError:                          # standalone export, or Resources on sys.path
    import palm_depth as _PD

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PATH = os.path.join(_HERE, "default_config.json")


def load_file(path=_DEFAULT_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


DEFAULT_CONFIG = load_file()


def _resolve_inherited(cfg):
    """Turn every `null`-means-inherit into the value its owning module holds."""
    if cfg["grab_ready"].get("require_valid_depth") is None:
        cfg["grab_ready"]["require_valid_depth"] = bool(_PD.SNAP_REQUIRES_VALID_DEPTH)
    return cfg


def merged_config(overrides=None):
    """Defaults, then a shallow-per-section merge of the host's overrides.

    ⚠ Per-section rather than deep: a host overriding one key of `grab_ready`
    must not silently drop the others, and a full deep merge would make it
    impossible to tell which values a host actually set.
    """
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return _resolve_inherited(cfg)
