# -*- coding: utf-8 -*-
"""⛔ THE SLIDER PANEL IS CONSISTENT — a guard written the day it broke.

    .venv/Scripts/python.exe analysis/verify_slider_wiring.py

⭐⭐ WHY THIS EXISTS. On 2026-08-28 three retired sliders were removed from
`SLIDERS` and from `_read_sliders`'s unpack. Two of the constants they fed --
`SLANT_AXIS_GAIN` and `POSE_BLEND` -- existed ONLY as unpack targets, so removing
them deleted their sole assignment while `_read_sliders` still pushed them into
the estimator modules. The tool died with `NameError` on the first frame.

⛔⛔ AND ALL 38 SUITES PASSED. Not one of them exercises `_read_sliders`, because
it needs a live OpenCV window -- so the panel's wiring was the one part of the
debug tool no fixture covered. `METHOD.md` names this exactly: **automated green is
necessary, not sufficient; a live look is what closes a change.** The owner found
it by running the tool.

⭐ These checks are STATIC -- they read the source and the module, never open a
window -- so they run in the ordinary suite sweep and would have caught it.

WHAT IS ASSERTED
  1. the panel's arity matches the unpack's arity (the failure mode that silently
     shifts every slider's meaning by one);
  2. every name `_read_sliders` declares `global` is either defined at module level
     or assigned in the function -- no name can be read before it exists;
  3. every retired slider's constant still HAS a value (retiring a control must not
     delete the behaviour it controlled);
  4. no live `setTrackbarPos` names a slider that is no longer in the table;
  5. the panel is tall enough for every trackbar it declares.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

FAILURES = []


def ok(name, cond, detail=""):
    print("  [%s] %-56s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        FAILURES.append(name)


def main():
    print("=" * 78)
    print("SLIDER PANEL WIRING — static, no window opened")
    print("=" * 78)
    import LiveSnapDebug as L                                  # noqa: E402

    src = io.open(os.path.join(BASE, "LiveSnapDebug.py"), encoding="utf-8-sig").read()
    body = re.search(r"def _read_sliders\(\).*?(?=\ndef )", src, re.S)
    ok("`_read_sliders` found in source", body is not None)
    if not body:
        return 1
    body = body.group(0)

    # -- 1. arity ------------------------------------------------------------
    print("\n1. ⛔ PANEL ARITY == UNPACK ARITY")
    m = re.search(r"\(([^)]*?)\) = vals", body, re.S)
    ok("the unpack tuple is found", m is not None)
    if m:
        targets = [t.strip() for t in m.group(1).replace("\n", " ").split(",")
                   if t.strip() and not t.strip().startswith("#")]
        ok("panel %d == unpack %d" % (len(L.SLIDERS), len(targets)),
           len(L.SLIDERS) == len(targets),
           "a mismatch shifts every slider's meaning by one")

    # -- 2. every declared global resolves ----------------------------------
    print("\n2. ⛔ NO GLOBAL IS READ BEFORE IT EXISTS")
    declared = set()
    for g in re.finditer(r"^\s*global (.+)$", body, re.M):
        declared |= {n.strip() for n in g.group(1).split(",")}
    assigned_here = set(re.findall(r"^\s*([A-Z_][A-Z0-9_]*)\s*=", body, re.M))
    if m:
        assigned_here |= set(targets)
    unresolved = sorted(n for n in declared
                        if not hasattr(L, n) and n not in assigned_here)
    ok("all %d declared globals resolve" % len(declared), not unresolved,
       "missing: %s" % (unresolved or "none"))

    # -- 3. retired sliders kept their constants ----------------------------
    print("\n3. ⭐ RETIRING A CONTROL MUST NOT DELETE THE BEHAVIOUR")
    live = {s[0] for s in L.SLIDERS}
    for label, const in (("TRIM gain %", "tip_trim.TRIM_GAIN"),
                         ("SLANT axis %", "SLANT_AXIS_GAIN"),
                         ("POSE blend %", "POSE_BLEND")):
        if label in live:
            continue
        name = const.split(".")[-1]
        holder = L if "." not in const else __import__(
            "Resources." + const.split(".")[0], fromlist=["x"])
        ok("retired %-14s keeps %s" % (label, const), hasattr(holder, name),
           "= %r" % getattr(holder, name, None))

    # -- 4. no orphaned setTrackbarPos --------------------------------------
    print("\n4. ⛔ NO LIVE setTrackbarPos NAMES A RETIRED SLIDER")
    orphans = []
    for line in src.splitlines():
        st = line.strip()
        if st.startswith("#") or "setTrackbarPos(" not in line:
            continue
        q = re.search(r'setTrackbarPos\(\s*"([^"]+)"', line)
        if q and q.group(1) not in live:
            orphans.append(q.group(1))
    ok("no orphaned trackbar writes", not orphans, "orphans: %s" % (orphans or "none"))

    # -- 3b. every slider carries its own description ------------------------
    # ⛔ STANDING RULE, owner 2026-08-28: every slider carries a one-line purpose
    # AS A FIELD OF THE ROW, so a control cannot exist without its explanation and
    # the two cannot drift. The panel renders from the same table.
    print("")
    print("3b. ⛔ EVERY SLIDER CARRIES ITS OWN ONE-LINE PURPOSE")
    for spec in L.SLIDERS:
        has = len(spec) > 4 and isinstance(spec[4], str) and spec[4].strip()
        ok("%-16s has a description" % spec[0], bool(has),
           (spec[4][:44] + "...") if has else "MISSING")
    ok("no description mentions a retired control",
       not any("slant" in (sp[4] if len(sp) > 4 else "").lower()
               or "pose blend" in (sp[4] if len(sp) > 4 else "").lower()
               for sp in L.SLIDERS))

    # -- 4b. ⭐⭐ ACTUALLY RUN IT -------------------------------------------
    # ⛔⛔ THE STATIC CHECKS ABOVE MISSED A SECOND `NameError` THE SAME DAY.
    # `_gain` was a plain local unpack target, not a declared `global`, so check 2
    # could not see it -- and the source-slice regex stopped short of the line that
    # used it. Two static passes, two escapes, two wasted live sessions.
    # ⭐ So the real guard is to EXECUTE the function. `cv2.getTrackbarPos` is
    # stubbed, which needs no window and no camera, and any unresolved name in the
    # WHOLE body raises here instead of on the owner's first frame.
    # ⚠ The lesson generalises: when a thing can simply be RUN, running it beats
    # reasoning about its source. The static checks are kept -- they localise a
    # failure this one only reports -- but this is the one that catches.
    print("")
    print("4b. ⭐⭐ `_read_sliders` EXECUTES (cv2 stubbed, no window)")
    import cv2
    real = cv2.getTrackbarPos
    _saved_cv2 = {n: getattr(cv2, n) for n in
                  ("namedWindow", "resizeWindow", "createTrackbar", "setTrackbarPos")}
    saved = {n: getattr(L, n, None) for n in dir(L) if n.isupper()}
    try:
        # ⛔ `_create_sliders` TOO. It was left out of the first version of this
        # check because it "needs a window" -- and it was the very next thing to
        # break, on a fixed-arity unpack, the moment the row grew a field. Stubbing
        # namedWindow/resizeWindow/createTrackbar costs three lines.
        cv2.namedWindow = lambda *a, **k: None
        cv2.resizeWindow = lambda *a, **k: None
        cv2.createTrackbar = lambda *a, **k: None
        cv2.setTrackbarPos = lambda *a, **k: None
        cv2.getTrackbarPos = lambda name, win: 1
        L._create_sliders()
        ok("`_create_sliders` runs (row arity tolerated)", True)
        L._read_sliders()
        ok("runs with every slider at 1", True)
        cv2.getTrackbarPos = lambda name, win: 0
        L._read_sliders()
        ok("runs with every slider at 0", True)
    except Exception as exc:                                   # noqa: BLE001
        ok("`_read_sliders` runs without raising", False,
           "%s: %s" % (type(exc).__name__, exc))
    finally:
        cv2.getTrackbarPos = real
        for _n, _v in _saved_cv2.items():
            setattr(cv2, _n, _v)
        for n, v in saved.items():                 # leave no state behind
            if v is not None:
                setattr(L, n, v)

    # -- 5. the panel is tall enough ----------------------------------------
    print("\n5. ⚠ THE PANEL MUST FIT WHAT IT DECLARES")
    rs = re.search(r"resizeWindow\(SLIDER_WIN,\s*\d+,\s*(.+)\)", src)
    ok("height is derived from the table, not a constant",
       rs is not None and "len(SLIDERS)" in rs.group(1) + ")",
       rs.group(1).strip() if rs else "not found")
    print("      ⭐ 12 trackbars in a fixed 400 px window pushed the 12th OFF the")
    print("        panel; a newly added slider was invisible. A dead control does")
    print("        not merely take space -- it hides a live one.")

    print("\n" + "=" * 78)
    if FAILURES:
        print("FAILED %d check(s):" % len(FAILURES))
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
