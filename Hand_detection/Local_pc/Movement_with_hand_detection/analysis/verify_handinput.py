"""Golden vectors + boundary guard for the `handinput` package.

    .venv/Scripts/python.exe analysis/verify_handinput.py

⭐ FIVE SECTIONS, AND §1 IS THE ONE THAT KEEPS THE MODULE SHIPPABLE.

  §1 BOUNDARY  -- the package and every module in `handinput/manifest.py` import
                  nothing but the standard library and each other. ⭐⭐ This is what
                  replaces physically moving the estimator files into the package:
                  the property a folder would have given is asserted directly, so
                  a future import of `CubeWindow` (or pygame, or numpy) fails a
                  suite instead of quietly welding the input system to THIS game.
  §2 CONTRACT  -- `HandState` v2 has the fields it claims and, just as important,
                  does NOT have the ones with no producer. A contract that grows a
                  plausible-looking `palmFacing` is worse than one with a hole.
  §3 VECTORS   -- every stored vector still reproduces, to 1e-9.
  §4 TRACE     -- the scripted lifecycle replays event-for-event.
  §5 DELEGATION-- `palm_geometry.palm_center_px` still equals the formula both
                  tools used inline before they delegated to it.

⚠ §3/§4 compare against `handinput/conformance/`, which is DATA a port also runs.
A red result means either a real behaviour change (regenerate deliberately, in a
commit that says what changed) or a real regression. It never means "edit the
expectation".
"""
import ast
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from handinput import manifest, contract, HandInput          # noqa: E402
from handinput.conformance import fixtures as F              # noqa: E402
from handinput.conformance import generate_vectors as GV     # noqa: E402
from handinput.conformance import generate_traces as GT      # noqa: E402
from Resources import palm_geometry as PG                    # noqa: E402

FAILURES = []
CHECKS = [0]


def check(name, ok, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append("%s  %s" % (name, detail))
        print("  FAIL  %s  %s" % (name, detail))
    return ok


def close(a, b, tol=1e-9):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(close(a[k], b[k], tol) for k in a)
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


# ── §1 boundary ─────────────────────────────────────────────────────────────
def _imported_names(path):
    """Every top-level module name imported by a file, via the AST -- not a text
    search. ⚠ A grep for 'pygame' would also match a comment, and this codebase
    is mostly comments; the parser cannot be fooled that way."""
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module.split(".")[0])
                # `from Resources import palm_geometry` -- the INTERESTING name is
                # the one after `import`, so check both halves.
                for a in node.names:
                    names.add(a.name.split(".")[0])
    return names


def section_boundary():
    print("\n§1  BOUNDARY -- the package depends on nothing from the game")
    gone = manifest.missing()
    check("manifest files exist", not gone, "missing: %s" % gone)

    pkg = os.path.join(BASE, "handinput")
    files = []
    for root, dirs, names in os.walk(pkg):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        files += [os.path.join(root, n) for n in names if n.endswith(".py")]
    files += manifest.module_paths()

    forbidden = set(manifest.FORBIDDEN_IMPORTS)
    for path in files:
        if not os.path.isfile(path):
            continue
        bad = sorted(_imported_names(path) & forbidden)
        rel = os.path.relpath(path, BASE)
        check("clean imports: %s" % rel, not bad, "imports %s" % bad)
    print("  %d files scanned, %d forbidden names" % (len(files), len(forbidden)))

    # ⭐ The core must also be numpy-free and stdlib-thin: every non-local import
    # is something a JS/Swift/Kotlin port has to find an equivalent for, so the
    # list is asserted, not merely hoped for.
    local = {n for n, _ in manifest.MODULES}
    for name, path in manifest.MODULES:
        outside = sorted(_imported_names(path) - local - set(manifest.ALLOWED_STDLIB))
        check("core stdlib-only: %s" % name, not outside, "also imports %s" % outside)


# ── §2 contract ─────────────────────────────────────────────────────────────
def section_contract():
    print("\n§2  CONTRACT -- HandState v2 subset, holes included")
    obs = contract.HandObservation(
        slot="Left", present=True, tracking_state=contract.TRACKING, track_id=7,
        position_px=(1.0, 2.0), depth_m=0.5, depth_valid=True,
        orientation=(1.0, 0.0, 0.0, 0.0), thumb_outward=True,
        chirality_confirmed=True, orientation_valid=True, edge_on=0.5,
        landmarks_px=F.pixel_hand())
    st = contract.hand_state(obs, 123.0)

    for key in ("schema", "tCapture", "present", "handedness", "trackId",
                "palm", "thumbOutward", "edgeOnMeasure", "depth", "quality"):
        check("field present: %s" % key, key in st)
    check("schema is 2", st["schema"] == 2, str(st["schema"]))
    for key in ("orientationValid", "depthValid", "trackingState",
                "framesSinceMeasurement", "chiralityConfirmed"):
        check("quality.%s" % key, key in st["quality"])

    # ⛔ The holes are asserted, not just documented. A field with no producer
    # must stay ABSENT: a plausible number in a contract slot is indistinguishable
    # from a measured one to every consumer downstream.
    for absent in ("palmFacing", "aperture", "apertureRate", "joints",
                   "synergyCoeffs", "latencyBudgetMs", "tPredicted", "depthRate"):
        check("absent (no producer): %s" % absent, absent not in st)
    check("palm.position absent (metric)", "position" not in st["palm"])
    check("palm.positionPx present", "positionPx" in st["palm"])
    check("landmarksScreen off by default", "landmarksScreen" not in st)
    check("landmarksScreen opt-in works",
          "landmarksScreen" in contract.hand_state(obs, 1.0, include_landmarks=True))
    check("json-serialisable", json.dumps(st) is not None)

    # `holds_track` must mean TRACKING-or-BRIDGING, because the game releases on it
    for state, expect in ((contract.TRACKING, True), (contract.BRIDGING, True),
                          (contract.SUSTAINED_LOST, False)):
        o = contract.HandObservation(slot="Left", tracking_state=state)
        check("holds_track(%s)" % state, o.holds_track is expect)


# ── §3 vectors ──────────────────────────────────────────────────────────────
def section_vectors():
    print("\n§3  VECTORS -- stored expectations still reproduce")
    captured = {}

    def capture(name, payload):
        captured[name] = payload
        return name

    real_w, GV._w = GV._w, capture
    try:
        for gen in (GV.gen_palm_geometry, GV.gen_projection, GV.gen_palm_depth,
                    GV.gen_palm_rotation, GV.gen_hand_state, GV.gen_owner_remap,
                    GV.gen_hand_tracks):
            gen()
    finally:
        GV._w = real_w

    for name, fresh in sorted(captured.items()):
        path = os.path.join(BASE, "handinput", "conformance", "vectors", name + ".json")
        if not check("vector file exists: %s" % name, os.path.isfile(path)):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        tol = stored.get("_tolerance", 1e-9)
        fresh_cases, stored_cases = fresh.get("cases"), stored.get("cases")
        ok = close(fresh_cases, stored_cases, tol)
        check("%s: %d cases" % (name, len(stored_cases or [])), ok,
              "" if ok else _first_diff(fresh_cases, stored_cases, tol))
        for extra in ("ratio_sequence",):
            if extra in stored:
                check("%s.%s" % (name, extra),
                      close(fresh.get(extra), stored[extra], tol))


def _first_diff(a, b, tol, path=""):
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return "%s length %d != %d" % (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            if not close(x, y, tol):
                return _first_diff(x, y, tol, "%s[%d]" % (path, i))
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return "%s.%s only on one side" % (path, k)
            if not close(a[k], b[k], tol):
                return _first_diff(a[k], b[k], tol, "%s.%s" % (path, k))
    return "%s: %r != %r" % (path, a, b)


# ── §4 trace ────────────────────────────────────────────────────────────────
def section_trace():
    print("\n§4  TRACE -- the scripted lifecycle replays event-for-event")
    path = os.path.join(BASE, "handinput", "conformance", "traces",
                        "scripted_lifecycle.json")
    if not check("trace file exists", os.path.isfile(path)):
        return
    with open(path, "r", encoding="utf-8") as fh:
        stored = json.load(fh)
    _, events = GT.build()
    expected = stored["expected_events"]
    if not check("event count %d" % len(expected), len(events) == len(expected),
                 "got %d" % len(events)):
        return
    bad = None
    for i, (got, want) in enumerate(zip(events, expected)):
        if not close(got, want, 1e-9):
            bad = "event %d: got %s/%s want %s/%s" % (
                i, got["action"], got["phase"], want["action"], want["phase"])
            break
    check("all %d events identical" % len(expected), bad is None, bad or "")

    # ⭐ The three behaviours the trace exists to pin, asserted by NAME as well as
    # by comparison -- so a regenerated trace that lost one is still caught.
    def phases(action, hand="Left"):
        return [e["phase"] for e in expected if e["action"] == action and e["hand"] == hand]

    check("a held button does not re-fire",
          phases("grab_ready").count("Performed") == phases("grab_ready").count("Started"))
    check("coast does not cancel `tracked`",
          phases("tracked").count("Canceled") == 1,
          "cancels=%d" % phases("tracked").count("Canceled"))
    check("but it DOES cancel `palm_pose`",
          phases("palm_pose").count("Canceled") >= 1)
    first_rot = next((e for e in expected if e["action"] == "rotation_delta"), None)
    check("rotation starts at IDENTITY (no pop)",
          first_rot is not None and close(first_rot["value"], [1.0, 0.0, 0.0, 0.0], 1e-9),
          str(first_rot and first_rot["value"]))


# ── §5 delegation ───────────────────────────────────────────────────────────
def section_delegation():
    print("\n§5  DELEGATION -- palm_center_px is the tools' own formula")
    WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 0, 5, 9, 13, 17
    for label, kw in F.PIXEL_CASES:
        lm = F.pixel_hand(**kw)
        want_x = sum(lm[i][0] for i in (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)) / 5.0
        want_y = sum(lm[i][1] for i in (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)) / 5.0
        check("palm_center_px %s" % label,
              close(list(PG.palm_center_px(lm)), [want_x, want_y], 1e-12))
    check("HAND_POSITION_LANDMARKS unchanged",
          tuple(PG.HAND_POSITION_LANDMARKS) == (0, 5, 9, 13, 17),
          str(PG.HAND_POSITION_LANDMARKS))


def main():
    print("verify_handinput -- the input-system package")
    print("=" * 62)
    section_boundary()
    section_contract()
    section_vectors()
    section_trace()
    section_delegation()
    print("\n" + "=" * 62)
    if FAILURES:
        print("FAILED: %d of %d checks" % (len(FAILURES), CHECKS[0]))
        for f in FAILURES:
            print("   ", f)
        return 1
    print("ALL %d CHECKS PASS" % CHECKS[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
