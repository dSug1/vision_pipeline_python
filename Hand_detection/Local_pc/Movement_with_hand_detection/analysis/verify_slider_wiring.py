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


def _raises_keyerror(L):
    try:
        L._set_slider("NO SUCH SLIDER", 1)
    except KeyError:
        return True
    except Exception:                                          # noqa: BLE001
        return False
    return False


def _silent_for_collapsed(L, collapsed):
    """A collapsed name must be a NO-OP -- not an error, and no window call."""
    if not collapsed:
        return True
    try:
        L._set_slider(collapsed[0], 1)
    except Exception:                                          # noqa: BLE001
        return False
    return True


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

        # ⭐⭐ THE TWO MATE RADII (2026-08-28) SCALE THE SHIPPED VALUE, AND MUST NOT
        # COMPOUND. They are a PERCENTAGE of a baseline captured at import; scaling
        # the modules' LIVE values instead would multiply again on every frame and
        # the slider would run away on its own. Reading three times at 100 % must
        # leave both constants exactly where they ship.
        from Resources import object_assembly as _OA
        # ⛔ INDEXED, NOT UNPACKED — and this line WAS a fixed 5-tuple unpack
        # until 2026-08-29, when the `active` field made the rows 6-tuples and
        # this suite died with `too many values to unpack`. **The guard carried
        # the exact fragility it exists to catch**, one file over.
        _pos = {spec[0]: spec[2] for spec in L.SLIDERS}
        cv2.getTrackbarPos = lambda name, win: _pos[name]
        for _ in range(3):
            L._read_sliders()
        ok("⭐ three reads at 100% leave the SHIPPED radii unchanged",
           abs(_OA.MC.MATE_RADIUS_FRACTION - L._SHIPPED_MATE_RADIUS_FRACTION) < 1e-12
           and abs(_OA.PREVIEW_RADIUS_FACTOR - L._SHIPPED_PREVIEW_RADIUS_FACTOR) < 1e-12,
           "snap %.3f, preview %.3f" % (_OA.MC.MATE_RADIUS_FRACTION,
                                        _OA.PREVIEW_RADIUS_FACTOR))
        # ⛔⛔ THE MATE ROWS ARE **COLLAPSED** FOR THE `1.7.41` BUILD, AND THE
        # SCALING THEY DRIVE STILL SHIPS. A collapsed slider feeds `_read_sliders`
        # its DEFAULT, so without forcing them active here this whole section would
        # silently test nothing while still printing PASS -- which is precisely the
        # "passed for the wrong reason" failure three `AS` vectors had.
        # ⭐ Forced for the duration and restored in `finally`, so the check
        # exercises the REAL code path rather than a lookalike.
        _saved_sliders = L.SLIDERS
        L.SLIDERS = tuple(
            (sp[:5] + (True,)) if sp[0].startswith("MATE ") else sp
            for sp in L.SLIDERS)
        _pos["MATE snap r %"], _pos["MATE preview r %"] = 300, 33
        L._read_sliders()
        ok("...and the owner's third-to-triple range reaches both ends",
           abs(_OA.MC.MATE_RADIUS_FRACTION - 3.0 * L._SHIPPED_MATE_RADIUS_FRACTION) < 1e-9
           and abs(_OA.PREVIEW_RADIUS_FACTOR - 0.33 * L._SHIPPED_PREVIEW_RADIUS_FACTOR) < 1e-9,
           "snap %.3f, preview %.3f" % (_OA.MC.MATE_RADIUS_FRACTION,
                                        _OA.PREVIEW_RADIUS_FACTOR))
        # ⭐⭐ THE SNAP SLIDER ALSO DRIVES THE ANGLE TOLERANCE (owner, 2026-08-28):
        # `can_mate` asks how CLOSE and how ALIGNED, and they are one question.
        _pos["MATE snap r %"], _pos["MATE preview r %"] = 100, 100
        L._read_sliders()
        ok("the angle tolerance rides the SNAP slider, at 100% = shipped",
           abs(_OA.MC.MATE_ANGLE_TOL_DEG - L._SHIPPED_MATE_ANGLE_TOL_DEG) < 1e-9,
           "%.1f deg" % _OA.MC.MATE_ANGLE_TOL_DEG)
        _pos["MATE snap r %"] = 50
        L._read_sliders()
        ok("...and it scales down with it",
           abs(_OA.MC.MATE_ANGLE_TOL_DEG - 0.5 * L._SHIPPED_MATE_ANGLE_TOL_DEG) < 1e-9,
           "%.1f deg" % _OA.MC.MATE_ANGLE_TOL_DEG)
        # ⛔⛔ THE HARD GEOMETRIC LIMIT. At 90 deg two outward normals are
        # perpendicular; past it they point the SAME way and "facing each other"
        # stops meaning anything. The slider may reach it, the predicate may not.
        _pos["MATE snap r %"] = 300
        L._read_sliders()
        ok("⛔ the tolerance is CLAMPED below 90 deg however far the slider goes",
           _OA.MC.MATE_ANGLE_TOL_DEG <= L.MATE_ANGLE_HARD_MAX_DEG + 1e-9
           and _OA.MC.MATE_ANGLE_TOL_DEG < 90.0,
           "%.1f deg at 300%%" % _OA.MC.MATE_ANGLE_TOL_DEG)
        ok("⛔ the PREVIEW angle never falls below the mate's — the aid must not "
           "stop guiding at the moment it matters",
           _OA.PREVIEW_ANGLE_DEG >= _OA.MC.MATE_ANGLE_TOL_DEG - 1e-9,
           "preview %.1f vs mate %.1f deg" % (_OA.PREVIEW_ANGLE_DEG,
                                              _OA.MC.MATE_ANGLE_TOL_DEG))
        _pos["MATE snap r %"], _pos["MATE preview r %"] = 100, 100
        L._read_sliders()                                  # restore before leaving
        ok("...and everything returns to the shipped values",
           abs(_OA.MC.MATE_ANGLE_TOL_DEG - L._SHIPPED_MATE_ANGLE_TOL_DEG) < 1e-9
           and abs(_OA.PREVIEW_ANGLE_DEG - L._SHIPPED_PREVIEW_ANGLE_DEG) < 1e-9)
    except Exception as exc:                                   # noqa: BLE001
        ok("`_read_sliders` runs without raising", False,
           "%s: %s" % (type(exc).__name__, exc))
    finally:
        try:
            L.SLIDERS = _saved_sliders        # undo the forced-active MATE rows
        except NameError:
            pass
        cv2.getTrackbarPos = real
        for _n, _v in _saved_cv2.items():
            setattr(cv2, _n, _v)
        for n, v in saved.items():                 # leave no state behind
            if v is not None:
                setattr(L, n, v)

    # -- 5. the panel is tall enough ----------------------------------------
    print("\n5. ⚠ THE PANEL MUST FIT WHAT IT DECLARES")
    rs = re.search(r"resizeWindow\(SLIDER_WIN,\s*\d+,\s*(.+)\)", src)
    # ⚠ `_active_count()` is ALSO table-derived, and since 2026-08-29 it is the
    # CORRECT derivation: a collapsed slider has no trackbar, so sizing from
    # `len(SLIDERS)` would leave exactly the dead space collapsing removes.
    ok("height is derived from the table, not a constant",
       rs is not None and ("len(SLIDERS)" in rs.group(1) + ")"
                           or "_active_count()" in rs.group(1) + ")"),
       rs.group(1).strip() if rs else "not found")
    print("      ⭐ 12 trackbars in a fixed 400 px window pushed the 12th OFF the")
    print("        panel; a newly added slider was invisible. A dead control does")
    print("        not merely take space -- it hides a live one.")

    # -- 6. collapsing (2026-08-29) -----------------------------------------
    print()
    print("6. ⭐⭐ COLLAPSED SLIDERS — present, parked, and never positioned")
    collapsed = [sp[0] for sp in L.SLIDERS if not L._is_active(sp)]
    active = [sp[0] for sp in L.SLIDERS if L._is_active(sp)]
    ok("at least one slider is EXPANDED", bool(active), "%d active" % len(active))
    ok("every collapsed control is STILL IN THE TABLE",
       all(any(sp[0] == n for sp in L.SLIDERS) for n in collapsed),
       "%d collapsed: %s" % (len(collapsed), ", ".join(collapsed)) if collapsed
       else "none collapsed")
    # ⛔ THE FAILURE THIS CATCHES: a collapsed slider has NO trackbar, so a raw
    # `cv2.setTrackbarPos` naming one raises `cv2.error` and kills the tool at
    # startup -- the same shape as the 2026-08-28 `NameError` this file was written
    # for, and equally invisible to every other suite.
    # ⚠ The ONE legitimate call is inside `_set_slider` itself, and it names the
    # bare parameter `name`. Everything else must be a caller, and a caller naming
    # a slider directly is what this check forbids.
    raw = [c for c in re.findall(r"^\s*cv2\.setTrackbarPos\(\s*([^,]+),", src, re.M)
           if c.strip() != "name"]
    ok("⛔ no LIVE raw setTrackbarPos — all go through `_set_slider`",
       not raw, ", ".join(r.strip() for r in raw) if raw else "none")
    ok("`_set_slider` refuses a name that is in NO row", _raises_keyerror(L))
    ok("`_set_slider` is a silent NO-OP for a COLLAPSED row",
       _silent_for_collapsed(L, collapsed),
       collapsed[0] if collapsed else "n/a")

    print()
    print("=" * 78)
    if FAILURES:
        print("FAILED %d check(s):" % len(FAILURES))
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
