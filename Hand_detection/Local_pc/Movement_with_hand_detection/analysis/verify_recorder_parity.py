"""The two recorders must agree on WHAT they write and WHEN they sample it.

⚠⚠ WHY THIS EXISTS. Production and the debug tool each have their own recorder,
and until 2026-08-23 they disagreed on frame semantics: the debug tool snapshotted
`cubes` AFTER each frame's logic, production BEFORE. Nothing announced that. A
harness pairing `hands[i]` with `cubes[i]` therefore read production one frame
skewed, and reported **11 phantom "cube held beyond the margin" violations** that
vanished the moment the rows were realigned.

⭐ That is the same failure shape as the rest of this session: an instrument that
silently disagrees with the thing it measures. The recorders are the instruments
everything else is built on, so they get their own guard.

This checks by SOURCE (no camera, no recording needed):
  1. both recorders write the same per-cube fields;
  2. both stamp `recorder_schema`, so an old take can be told apart;
  3. production's cube snapshot happens in `_record_flush` -- i.e. AFTER the
     frame's logic -- not in `_record_frame`.

Run:  .venv/Scripts/python.exe analysis/verify_recorder_parity.py
"""

import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROD = os.path.join(ROOT, "Resources", "HandsTriggeredActions.py")
DEBUG = os.path.join(ROOT, "LiveSnapDebug.py")

FAILS = []


def check(name, got, want):
    ok = (got == want)
    if not ok:
        FAILS.append("%s: got %r, want %r" % (name, got, want))
    print("  [%s] %-62s %r" % ("PASS" if ok else "FAIL", name, got))


SCHEMA = 3          # ⭐ 3 = 4.2's depth fields. 2 = position+size, 1/absent = old.

# ⚠ Add a field here the moment either recorder gains one. The list is the
# CONTRACT, not a snapshot: a field written by one recorder and not the other is
# precisely the divergence class this file exists to catch, and 4.2 added four.
CUBE_FIELDS = ["depth_m", "orientation", "owner", "position", "projected_size", "size"]
HAND_FIELDS = ["depth_valid", "hand_depth_m"]


def cube_fields(src, marker):
    """The per-cube dict keys written by a recorder, found from its source."""
    i = src.index(marker)
    chunk = src[i:i + 3000]   # wide enough to clear the comment blocks
    return sorted(set(re.findall(
        r'"(owner|position|size|depth_m|projected_size|orientation)":', chunk)))


def hand_fields(src):
    """The 4.2 per-hand depth keys a recorder writes, anywhere in its source."""
    # ⚠ Both spellings: production assigns onto an existing row
    # (`h["hand_depth_m"] = ...`), the debug tool builds a dict literal
    # (`"hand_depth_m": ...`). Matching only one form would report a field
    # missing that is written on every frame -- an instrument saying CLEAN about
    # the wrong thing, which is the failure this whole file guards against.
    return sorted(set(re.findall(r'"(hand_depth_m|depth_valid)"\s*[:\]]', src)))


def main():
    prod = open(PROD, encoding="utf-8").read()
    debug = open(DEBUG, encoding="utf-8").read()

    print("1. both recorders write the same per-cube fields")
    pf = cube_fields(prod, 'row["cubes"] = {"production"')
    df = cube_fields(debug, '"cubes": {')
    check("production fields", pf, CUBE_FIELDS)
    check("debug fields", df, CUBE_FIELDS)
    check("they match", pf == df, True)

    print()
    print("1b. and the same per-hand DEPTH fields (4.2)")
    # ⚠ `depth_ratio` is deliberately in NEITHER: the object's own `depth_m` is
    # the recorded outcome, and the debug tool's ratio tracker is per ARM so it
    # could not write a per-hand value that meant the same thing.
    ph, dh = hand_fields(prod), hand_fields(debug)
    check("production fields", ph, HAND_FIELDS)
    check("debug fields", dh, HAND_FIELDS)
    check("they match", ph == dh, True)
    check("neither writes a per-hand depth_ratio",
          '"depth_ratio"' in prod or '"depth_ratio"' in debug, False)

    print()
    print("2. both stamp recorder_schema, so an old take is distinguishable")
    check("production stamps it", '"recorder_schema": %d' % SCHEMA in prod, True)
    check("debug stamps it", '"recorder_schema": %d' % SCHEMA in debug, True)

    print()
    print("3. production samples cubes AFTER the frame's logic")
    # The snapshot must live in `_record_flush` (called at the end of the frame),
    # never in `_record_frame` (called at the top). This is the alignment bug.
    tree = ast.parse(prod)
    where = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("_record_frame",
                                                               "_record_flush"):
            seg = ast.get_source_segment(prod, node) or ""
            where[node.name] = ('"cubes"' in seg)
    check("_record_flush takes the cubes snapshot", where.get("_record_flush"), True)
    check("_record_frame does NOT (that was the one-frame skew)",
          where.get("_record_frame"), False)

    print()
    if FAILS:
        print("=" * 72)
        print("FAILED (%d):" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        print("=" * 72)
        return 1
    print("=" * 72)
    print("RECORDERS AGREE -- same fields, same frame semantics, both stamped.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
