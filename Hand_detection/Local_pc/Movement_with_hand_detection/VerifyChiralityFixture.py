"""M5d `K` fixture test -- merged queue item 1.1. THE permanent guard against the
chirality sign convention silently inverting.

WHY THIS EXISTS
---------------
On 2026-08-01 the thumb-outward rule shipped INVERTED IN PRODUCTION ONLY, and the
bug survived a "confirmed working end-to-end" claim. Root cause
(GESTURE_PIPELINE_SPEC.md §13.6.1): `VisionPipeline.py` runs MediaPipe on the RAW,
un-mirrored frame; the landmark COORDINATES were mirrored afterwards but the
handedness LABEL was not. MediaPipe assumes an already-mirrored ("selfie") input
for its Left/Right classification, so on an unmirrored frame it reports the true
anatomical hand -- inverting `_is_thumb_outward`'s handedness-dependent chirality
correction, the one place in the pipeline that is not handedness-symmetric.

The spec (M5d) warns the convention depends on THREE independent flips:
image-y direction, preview mirroring, and MediaPipe's selfie handedness
convention. Get an even number wrong and it still "works"; get an odd number wrong
and it inverts.

THE ONE RULE THIS FILE OBEYS
----------------------------
**It imports and exercises PRODUCTION's real `_is_thumb_outward`.** It does NOT
reimplement the sign convention. A test carrying its own copy of the formula would
have passed happily on 2026-08-01 while the game was broken -- it would guard
nothing. Importing production means pulling in `HandsTriggeredActions`, which
instantiates `CubeWindow()` at module level and therefore opens a real pygame
window (spec §7.3 flags this as a boundary leak). We work around it here with
SDL's dummy video driver rather than refactoring production untested at night;
when the L7 cleanup lands and that side effect goes away, the two env-var lines
below can simply be deleted.

GROUND TRUTH
------------
Comes from the RECORDING PROTOCOL, not from the pipeline: the operator is told
which hand and which facing to present, and the clip is named for it. Existing
recordings cannot serve -- they hold only the COMPUTED thumb-outward value, which
is the very thing under test.

Record the four clips with (each is 8 s, held steady):

    record_perception_sequence.bat known_right_palm
    record_perception_sequence.bat known_right_back
    record_perception_sequence.bat known_left_palm
    record_perception_sequence.bat known_left_back

then run:  python VerifyChiralityFixture.py

CONVENTION OF THE RECORDED DATA
-------------------------------
`RecordPerceptionSequence.py` flips the frame BEFORE detection (cv2.flip then
detect), exactly like `LiveSnapDebug.py`. So recorded landmarks and labels are in
the MIRRORED / "selfie" convention -- what the operator sees of themselves. That
is also what production's `_is_thumb_outward` receives, after `VisionPipeline.py`
mirrors coordinates and `hands_visualizer._mirror_handedness()` mirrors the label.
The two paths converge, which is what §13.6.1's fix established.

Exit code 0 = all checks passed. 1 = a real failure. 2 = clips missing.
"""

import ast
import glob
import json
import os
import sys

# MUST be set before pygame is imported anywhere down the chain. See the module
# docstring: production opens a real window at import time.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from Resources.HandsTriggeredActions import _is_thumb_outward  # noqa: E402

CAPTURE_ROOTS = [
    r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions",
    os.path.join(_HERE, "perception_recordings", "sessions"),
]

# sequence -> (PHYSICAL hand the operator presented, back-of-hand-to-camera?)
# thumb-outward is defined as "back of hand facing the camera" (§13.6), so
# expected_thumb_outward == back_to_camera.
GROUND_TRUTH = {
    "known_right_palm": ("Right", False),
    "known_right_back": ("Right", True),
    "known_left_palm": ("Left", False),
    "known_left_back": ("Left", True),
}

# ---------------------------------------------------------------------------
# THE LABEL CONVENTION -- ESTABLISHED FROM DATA 2026-08-03, NOT ASSUMED
# ---------------------------------------------------------------------------
# The label carried through this pipeline is the MIRRORED (apparent) hand, i.e.
# the hand as seen in the mirrored preview -- NOT the physical hand. A clip of the
# operator's physical RIGHT hand therefore carries the label "Left".
#
# HOW THIS WAS ESTABLISHED (the first version of this file assumed the opposite
# and failed 0/788, which is what prompted the check): in a mirrored preview the
# operator's physical right hand NECESSARILY appears on the right of the image --
# that is the mirror property, not an interpretation. So across every recorded
# session, for frames holding exactly two distinctly-labelled hands, we asked
# which side the "Right" label fell on. In every take where the hands stay on
# their natural sides -- static_hold (288 frames), non_crossing (723),
# palm_back_s1_very_slow (980) -- the "Right" label was on the image-LEFT hand
# 100% of the time. (The two-hand crossing takes sit near 30% precisely BECAUSE
# the hands deliberately swap sides, which corroborates rather than contradicts.)
#
# BOTH pipeline paths agree on this convention, by different routes:
#   recorder / debug tool : detect on a MIRRORED frame -> MediaPipe returns the
#                           mirrored/apparent hand directly.
#   production            : detect on the UN-mirrored frame -> MediaPipe returns
#                           the true anatomical hand -> _mirror_handedness()
#                           flips it -> mirrored/apparent hand.
# That convergence is exactly what §13.6.1's fix established, and it is why
# `_is_thumb_outward` is correct in both. Do NOT "simplify" either path to make
# the label the physical hand without re-deriving this whole test.
MIRRORED_LABEL = {"Right": "Left", "Left": "Right"}

# Clips are held steady, so agreement should be near-total. Anything below this is
# a real signal, not noise -- do NOT relax it to make a take pass.
MIN_AGREEMENT = 0.90


def _find_sessions(seq):
    out = []
    for root in CAPTURE_ROOTS:
        out.extend(sorted(glob.glob(os.path.join(root, f"*_{seq}"))))
    return out


def _load(session_dir):
    with open(os.path.join(session_dir, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    frames = []
    with open(os.path.join(session_dir, "raw_landmarks.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return meta, frames


def _check_session(seq, session_dir):
    """Returns (passed, list_of_message_lines)."""
    physical_hand, expected_outward = GROUND_TRUTH[seq]
    expected_hand = MIRRORED_LABEL[physical_hand]   # see MIRRORED_LABEL above
    meta, frames = _load(session_dir)
    width = meta.get("resolution", [640, 480])[0]
    msgs = [f"  session: {os.path.basename(session_dir)}  "
            f"({meta.get('frames')} frames, {meta.get('measured_fps')} fps)"]

    if not meta.get("detection_on_mirrored_frame", False):
        msgs.append("  ** meta says detection was NOT run on a mirrored frame -- "
                    "this file's convention assumptions do not hold. ABORT. **")
        return False, msgs

    n = label_ok = outward_ok = neg_control_inverted = 0

    for rec in frames:
        hands = rec.get("hands") or []
        if len(hands) != 1:
            continue          # ground truth is single-hand by protocol
        h = hands[0]
        lm = [(p[0], p[1]) for p in h["landmarks"]]
        raw_label = h["handedness"]
        n += 1

        # --- check 1: the LABEL convention ---
        if raw_label == expected_hand:
            label_ok += 1

        # --- check 2: production's real sign function, on the real convention ---
        got = _is_thumb_outward(lm, raw_label)
        if got == expected_outward:
            outward_ok += 1

        # --- check 3: NEGATIVE CONTROL -- reintroduce the §13.6.1 bug ---
        # Production mirrors the coordinates but, in the bug, NOT the label. Feed
        # the same landmarks with the label flipped; the answer MUST invert. If it
        # does not, this test has no power to detect the regression it exists for.
        bugged_label = "Left" if raw_label == "Right" else "Right"
        if _is_thumb_outward(lm, bugged_label) != got:
            neg_control_inverted += 1

    if n == 0:
        msgs.append("  ** no single-hand frames found -- unusable clip **")
        return False, msgs

    label_rate = label_ok / n
    outward_rate = outward_ok / n
    neg_rate = neg_control_inverted / n
    passed = (label_rate >= MIN_AGREEMENT
              and outward_rate >= MIN_AGREEMENT
              and neg_rate >= MIN_AGREEMENT)

    msgs.append(f"  presented: PHYSICAL {physical_hand} hand -> expected label "
                f"'{expected_hand}' (mirrored convention)  thumb_outward={expected_outward}")
    msgs.append(f"  [{'PASS' if label_rate   >= MIN_AGREEMENT else 'FAIL'}] label matches ground truth      "
                f"{label_ok}/{n}  ({label_rate:.1%})")
    msgs.append(f"  [{'PASS' if outward_rate >= MIN_AGREEMENT else 'FAIL'}] production sign is correct     "
                f"{outward_ok}/{n}  ({outward_rate:.1%})")
    msgs.append(f"  [{'PASS' if neg_rate     >= MIN_AGREEMENT else 'FAIL'}] negative control inverts       "
                f"{neg_control_inverted}/{n}  ({neg_rate:.1%})")
    if label_rate < MIN_AGREEMENT:
        msgs.append("      -> MediaPipe disagreed with the stated hand. Either the clip was "
                    "recorded with the wrong hand, or the LABEL convention has flipped.")
    if outward_rate < MIN_AGREEMENT and label_rate >= MIN_AGREEMENT:
        msgs.append("      -> THE SIGN CONVENTION IS INVERTED. This is the §13.6.1 class of bug. "
                    "Do not 'fix' it by flipping the expectation in this file.")
    return passed, msgs


def _check_debug_copy_has_not_drifted():
    """`LiveSnapDebug.py` keeps its OWN copy of `_is_thumb_outward` by design (it
    must not import production, which opens a window). Duplication is exactly how
    the sign convention drifted once already, so compare the two ASTs."""
    prod = os.path.join(_HERE, "Resources", "HandsTriggeredActions.py")
    dbg = os.path.join(_HERE, "LiveSnapDebug.py")

    class _Canonicalise(ast.NodeTransformer):
        """Rename the landmarks parameter to a fixed name everywhere it is used.

        Production calls it `landmarks`, the debug copy `pixel_landmarks`. Dumping
        the raw AST includes identifiers, so identical logic compared UNEQUAL --
        a false positive that made this guard useless on its first run. Only the
        parameter is renamed; any real change to the maths still trips the guard.
        """

        def __init__(self, param):
            self.param = param

        def visit_Name(self, node):
            if node.id == self.param:
                node.id = "_LM"
            return node

    def body_of(path):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_is_thumb_outward":
                # strip the docstring: prose differs between the two by design
                body = node.body
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body = body[1:]
                mod = ast.Module(body=body, type_ignores=[])
                mod = _Canonicalise(node.args.args[0].arg).visit(mod)
                return ast.dump(mod)
        return None

    def delegates_to_shared(path):
        """Since item 1.2 both sides DELEGATE to Resources/palm_geometry.py instead
        of carrying the formula. That is now the invariant worth guarding: comparing
        two one-line delegations for equality is nearly vacuous, whereas 'neither
        side has reinlined the maths' is the thing that actually prevents drift."""
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_is_thumb_outward":
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Attribute)
                            and sub.attr == "is_thumb_outward"
                            and isinstance(sub.value, ast.Name)
                            and sub.value.id == "palm_geometry"):
                        return True
        return False

    msgs = []
    ok = True

    p, d = body_of(prod), body_of(dbg)
    if p is None or d is None:
        return False, ["  ** could not locate _is_thumb_outward in both files **"]
    if p != d:
        msgs.append("  [FAIL] production and LiveSnapDebug copies have DRIFTED.")
        msgs.append("      -> They must stay identical, or the debug tool validates a "
                    "different rule than the game plays (§13.6.1 precedent).")
        ok = False
    else:
        msgs.append("  [PASS] production and LiveSnapDebug copies are identical")

    for label, path in (("production", prod), ("LiveSnapDebug", dbg)):
        if delegates_to_shared(path):
            msgs.append(f"  [PASS] {label} delegates to the shared palm_geometry module")
        else:
            msgs.append(f"  [FAIL] {label} does NOT delegate to palm_geometry -- the "
                        f"formula has been reinlined.")
            msgs.append("      -> Duplication is what caused §13.6.1. Restore the "
                        "delegation rather than re-syncing two copies by hand.")
            ok = False

    return ok, msgs


def main():
    print("=" * 78)
    print("M5d `K` chirality fixture test (queue item 1.1)")
    print("Exercising PRODUCTION's own _is_thumb_outward -- not a reimplementation.")
    print("=" * 78)

    all_passed = True
    missing = []

    print("\n--- drift guard: production vs. debug copy ---")
    ok, msgs = _check_debug_copy_has_not_drifted()
    all_passed &= ok
    print("\n".join(msgs))

    for seq in GROUND_TRUTH:
        print(f"\n--- {seq} ---")
        sessions = _find_sessions(seq)
        if not sessions:
            missing.append(seq)
            print("  (no recording found)")
            continue
        for s in sessions:
            ok, msgs = _check_session(seq, s)
            all_passed &= ok
            print("\n".join(msgs))

    print("\n" + "=" * 78)
    if missing:
        print(f"INCOMPLETE -- {len(missing)} of {len(GROUND_TRUTH)} clips not yet recorded:")
        for m in missing:
            print(f"    record_perception_sequence.bat {m}")
        print("The fixture test cannot certify the convention until all four exist.")
        print("=" * 78)
        return 2
    if all_passed:
        print("ALL CHECKS PASSED -- the chirality convention is correct end-to-end.")
        print("=" * 78)
        return 0
    print("FAILURES ABOVE -- the sign convention or the label convention is wrong.")
    print("Fix the pipeline, NOT this file's expectations.")
    print("=" * 78)
    return 1


if __name__ == "__main__":
    sys.exit(main())
