"""Raw-capture recorder for the perception layer (merged queue items 0.1 / 0.2b).

Records the scripted test sequences defined in PERCEPTION_LAYER_SPEC.md §7.2 to
the session layout defined in M0, so every perception module can be A/B tested
offline on identical input.

DELIBERATELY PURE L0/L1 CAPTURE. Unlike `RecordTranslationPivotDebug.py` -- which
imports `LiveSnapDebug.py` on purpose, so that recorded cube state is real ground
truth for the translation work -- this recorder imports NO gesture logic at all.
It writes only what MediaPipe produced, plus timing. Everything derived
(edge-on measure, palm normal, bone lengths, sign) is recomputed at analysis
time, so a config change never requires re-recording. That is the spec's
boundary discipline (L0-L6 must not depend on gesture logic) applied to the
tooling itself.

Two consequences worth knowing:
  * `tCapture` is a real monotonic timestamp taken at frame read, NOT the
    synthesised 33 ms cadence the older recorders assume.
  * There is no cube, no snap, no window overlay -- only the camera preview and
    the sequence prompt. Nothing to grab.

OPTIONAL FRAME CAPTURE (`--save-frames`, queue item 0.1 deliverable; required by
item 0.5, the offline HaMeR/WiLoR oracle). Off by default, so existing behaviour
is byte-for-byte unchanged unless asked for.

  * The 24 sessions recorded before 2026-08-03 contain NO image data at all, so
    the oracle cannot be run over them retroactively -- any take intended to feed
    0.5 must be re-recorded with this flag.
  * What is saved is the MIRRORED, PRE-OVERLAY frame -- byte-identical to the
    array handed to MediaPipe. This matters: detection runs on the flipped image
    (`detection_on_mirrored_frame`), so an oracle fed the unflipped frame would
    produce mirrored poses and inverted chirality, and the comparison against the
    recorded landmarks would be silently meaningless. The `REC ...` / prompt
    overlays are drawn only AFTER the frame is buffered.
  * Frames are buffered in RAM and encoded AFTER the take, never inside the
    capture loop. Encoding per frame costs milliseconds against a ~41 ms budget,
    and a take that drops below MIN_EXPECTED_FPS is not comparable to the rest of
    the corpus (N10) -- i.e. paying encode cost during capture could corrupt the
    exact property that makes the recording usable.

Usage:  record_perception_sequence.bat <sequence> [duration_s] [camera_index]
        python RecordPerceptionSequence.py --sequence static_hold
        python RecordPerceptionSequence.py --sequence depth_sweep --save-frames
"""

import argparse
import hashlib
import json
import os

# ⚠ MOVED 2026-08-25 out of the app root. This file's own directory is no
# longer the app root, so every path that used to resolve from `__file__`
# now goes one level up. Behaviour is unchanged; only the anchor moved.
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import time
from datetime import datetime

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer"
# Fallback when the external drive is unavailable (it dropped out repeatedly on
# 2026-08-02: reads and writes both failing intermittently between operations,
# WinError 21). Sessions are self-contained folders of plain JSONL + meta.json,
# so a local capture can simply be moved to CAPTURE_ROOT later -- nothing in the
# analysis path depends on which root a session came from.
LOCAL_CAPTURE_ROOT = os.path.join(_APP_ROOT, "perception_recordings")
HAND_LANDMARKER_MODEL_PATH = os.path.join(
    _APP_ROOT,
    "..", "Python_Server_MediaPipe_vision_pipeline", "Resources", "hand_landmarker.task",
)

COUNTDOWN_S = 3.0

# ⭐ Seconds between the operator pressing SPACE and the step actually recording.
# ⛔ Sized for "put the pressing hand back in frame and settle", not for comfort:
# the frames it protects are the ones where only ONE hand is visible, which is the
# single worst kind of frame for a test that compares the two hands to each other.
PACED_GRACE_S = 2.0        # owner, 2026-08-29: two seconds

# Prescribed number of FULL cycles (palm -> back -> palm) per sequence. One cycle
# is TWO sign changes, so the analyser's per-frame sign-inversion count must be
# compared against 2x this. Overridable with --cycles when the operator does a
# different number; whatever is used is written into meta.json.
DEFAULT_CYCLES = {
    "palm_back_s1_very_slow": 10,
    "palm_back_s2_slow": 15,
    "palm_back_s3_medium": 20,
    "palm_back_s4_fast": 30,
}

YAW_AXIS_NOTE = (
    "YAW axis: rotate about the VERTICAL axis so the palm turns EDGE-ON to the "
    "camera and back, like turning a PAGE. Keep the fingers pointing STRAIGHT UP "
    "throughout -- the wrist stays put and only the palm swings. Do NOT tip the "
    "fingers toward/away (that is PITCH), do NOT tilt the hand sideways in the "
    "image plane (that is ROLL), and do NOT move closer/further. "
    "NOTE: the 2026-08-04 yaw take was measured AXIS-CONTAMINATED (spec 14.3.3): "
    "both palm spans collapsed, meaning pitch was mixed in. Its prompt said "
    "'doorknob', which is ROLL about the depth axis, not yaw -- that wording is "
    "removed. A clean single-axis yaw take is what spec 14.3.4 needs."
)

PITCH_AXIS_NOTE = (
    "PITCH axis: tip the fingers TOWARD then AWAY from the camera, as if nodding "
    "the hand -- the axis runs left-right across the knuckles. Do NOT rotate about "
    "the vertical axis (yaw, like turning a PAGE). Pitch is what the open "
    "pitch-plane-crossing TODO is about and what pitch_sweep_slow/fast used, so a "
    "yaw take would not be comparable; yaw has its own separate open item."
)

# Frame rate below which a take is flagged as suspect at save time.
#
# Learned 2026-08-02 (spec §0.7 / queue N10): two takes recorded at 22:18 measured
# 15.1 and 15.77 fps, against 24.09-24.14 fps for seven takes made 19:13-20:51 on
# the SAME camera and machine. Leading hypothesis is webcam auto-exposure
# lengthening frame duration in dim light. Both low-fps takes were discarded --
# owner: "I don't want the lack of light to pollute our analysis." A quiet
# 15-fps take is worse than a failed one, because it looks valid in analysis
# while being non-comparable to the rest of the corpus, so warn LOUDLY here.
MIN_EXPECTED_FPS = 20.0

# --- optional frame capture (--save-frames), queue item 0.1 / needed by 0.5 ---
#
# Frames are held in RAM for the duration of the take and encoded afterwards (see
# the module docstring for why encoding must stay out of the capture loop). That
# trades the fps risk for a memory ceiling, so the ceiling is preflighted rather
# than discovered by an OOM half way through an operator's take -- the same
# "fail before the operator's effort, never after it" rule the capture-root
# preflight already follows.
#
# 4 GiB on a 15.4 GB machine leaves ample headroom for MediaPipe and the OS. At
# 640x480x3 = 921 KB/frame that is ~4600 frames ~= 190 s at 24 fps, so every
# sequence in SEQUENCES fits at stride 1 -- including the 120 s free_manipulation
# take (2880 frames, ~2.6 GiB).
MAX_FRAME_BUFFER_BYTES = 4 * 1024 ** 3
# JPEG at quality 95 lands around 50 KB/frame at 640x480. Lossy, but PNG costs
# roughly 10x the disk and far more encode time; use --frame-format png when a
# take is specifically meant to rule out compression artifacts as a confound for
# the oracle.
DEFAULT_JPEG_QUALITY = 95

# PERCEPTION_LAYER_SPEC.md §7.2. (default_duration_s, on-screen prompt, what it unblocks)
SEQUENCES = {
    "static_hold": (
        12.0,
        "HOLD BOTH HANDS STILL - one pose, do not move at all",
        "resting jitter, palm-normal jitter, bone CV (3 M0 metrics that CANNOT "
        "come from the existing grab-and-rotate recordings)",
    ),
    "non_crossing": (
        30.0,
        "Move hands freely BUT NEVER turn palm-to-back - palms stay to camera",
        "chirality flip rate: any sign flip here is definitionally spurious, "
        "which is what decides EDGE_ON_THRESHOLD",
    ),
    "pitch_sweep_slow": (
        30.0,
        "SLOW pitch sweep: rotate one hand palm->back->palm, ~3s per sweep",
        "crossing survival, orientation continuity, DR-2 entry/exit behaviour",
    ),
    "pitch_sweep_fast": (
        20.0,
        "FAST pitch sweep: same rotation, ~0.5s per sweep",
        "crossing survival under motion blur; angular-velocity carry-through",
    ),
    # SUPERSEDED 2026-08-02 by the four palm_back_s* takes below. Mixing four
    # speeds into one clip yields a single blended flip count, which cannot
    # answer the question that actually matters -- at WHAT speed does the sign
    # cue start missing crossings. Kept runnable for comparability with any
    # older analysis; prefer the decoupled takes for new work.
    "palm_back": (
        40.0,
        "[SUPERSEDED - prefer palm_back_s1..s4] Rotate palm<->back repeatedly, "
        "at 4 DIFFERENT speeds",
        "chirality flip rate, hysteresis behaviour",
    ),

    # --- Speed-decoupled palm<->back, one speed per take (owner request,
    # 2026-08-02): "it may be worth decoupling and do 4 recordings at different
    # speeds, so we can gauge what is the threshold where we lose detection."
    #
    # Each take prescribes an EXACT cycle count, so ground truth comes from the
    # protocol rather than from the operator remembering a number afterwards.
    # One CYCLE = palm -> back -> palm = TWO sign changes; the recorder writes
    # both figures into meta.json so the two units can never be confused again
    # (that ambiguity caused a wrong reading on 2026-08-02 -- spec §0.7).
    # ROTATION AXIS IS PITCH, NOT YAW (owner instruction, 2026-08-02). This is not
    # incidental: the open pipeline TODO is the PITCH-plane crossing (queue T2 /
    # GESTURE_PIPELINE_SPEC.md §13.7), and the existing pitch_sweep_slow/fast takes
    # these are compared against are pitch too -- a yaw take would not be
    # comparable. Yaw has its own separate open item (the yaw/palm-sinking defect,
    # §14.1.1 / queue T4) and must not be mixed into this measurement.
    "palm_back_s1_very_slow": (
        40.0,
        "VERY SLOW palm<->back, PITCH axis: ~4s per FULL cycle. Do exactly 10 cycles.",
        "detection-threshold sweep: the easy end -- if crossings are missed even "
        "HERE, the problem is not speed",
    ),
    "palm_back_s2_slow": (
        30.0,
        "SLOW palm<->back, PITCH axis: ~2s per FULL cycle. Do exactly 15 cycles.",
        "detection-threshold sweep",
    ),
    "palm_back_s3_medium": (
        20.0,
        "MEDIUM palm<->back, PITCH axis: ~1s per FULL cycle. Do exactly 20 cycles.",
        "detection-threshold sweep",
    ),
    "palm_back_s4_fast": (
        15.0,
        "FAST palm<->back, PITCH axis: ~0.5s per FULL cycle. Do exactly 30 cycles.",
        "detection-threshold sweep: the hard end -- expected to be where the sign "
        "cue and/or MediaPipe detection break down",
    ),
    # SUPERSEDED 2026-08-03: this single prompt bundled three DIFFERENT occlusion
    # mechanisms and did not say how many hands to use -- the operator could not
    # act on it. Split into the three explicit takes below. All are ONE-HANDED on
    # purpose: a second hand injects duplicate-label frames (spec §0.8 finding 4)
    # and would contaminate the reacquisition timing this sequence exists to measure.
    "occlusion": (
        30.0,
        "[SUPERSEDED - use occlusion_exit_reenter / _behind_object / _finger_over_finger] "
        "Occlude: hand behind object, out/in of frame, finger over finger",
        "coast behaviour, reacquisition time, accidental-unsnap safety",
    ),
    "occlusion_exit_reenter": (
        15.0,
        "ONE hand. Move it fully OUT of the camera view, then back IN. Repeat ~4x, "
        "pausing ~1s each time it is back in view.",
        "REACQUISITION TIME (M0): ms from the hand re-entering to a usable pose. "
        "The hand leaves the frame ENTIRELY -- total loss, not partial",
    ),
    "occlusion_behind_object": (
        15.0,
        "ONE hand, stays INSIDE the view the whole time. Pass it BEHIND a "
        "stationary object (mug, book, monitor edge) so it is briefly hidden, then "
        "back out. Repeat ~4x.",
        "COAST behaviour (M4's coast limit): the hand is occluded but never leaves "
        "the frame -- distinct from exit/re-enter, because the estimator should "
        "coast through rather than treat it as a fresh acquisition",
    ),
    "occlusion_finger_over_finger": (
        15.0,
        "ONE hand, fully in view, NO object. Curl and interlace the fingers so they "
        "hide EACH OTHER - make a loose fist, splay, overlap fingers. Wrist stays "
        "steady.",
        "PER-LANDMARK occlusion: the hand is never lost, but individual landmarks "
        "are hidden and hallucinated. This is M4's actual target -- occlusion "
        "detection and per-landmark downweighting",
    ),
    # Two deliberately SEPARATE conditions. The original single "pass hands close
    # together" prompt was ambiguous (2026-08-02, operator feedback: unclear
    # whether the hands should occlude or merely pass near each other) -- and they
    # are different hypotheses, so they must not be mixed in one recording:
    #   overlap  -> one hand visually hides part of the other; MediaPipe loses the
    #               appearance cues (knuckles, creases) that its handedness
    #               classifier depends on. Strongest candidate for the identity
    #               mixup behind Object Jump Correction (§14.1.4): in the recorded
    #               event, one hand was undetected for several frames and then
    #               reappeared exactly where the other had been.
    #   near-miss -> hands come close in the image but never overlap. If the mixup
    #               reproduces here TOO, occlusion is not the mechanism and the
    #               cause is proximity/association alone -- a materially different
    #               fix. This is the control condition.
    "two_hand_overlap": (
        30.0,
        "CROSS hands so they OVERLAP - pass one IN FRONT of the other, briefly "
        "hiding it - then swap sides. Repeat.",
        "Object Jump Correction - the hand-identity-mixup repro condition "
        "(occlusion hypothesis)",
    ),
    "two_hand_near_miss": (
        30.0,
        "Pass hands CLOSE but NEVER touching or overlapping - keep a visible gap "
        "- then swap sides. Repeat.",
        "Object Jump Correction CONTROL: if the mixup happens here too, occlusion "
        "is not the mechanism",
    ),
    # THE ONE ROTATION THE CORPUS HAS NEVER CONTAINED. Every existing rotation
    # take is PITCH by deliberate design (palm_back_*, pitch_sweep_*), because
    # the open crossing TODO is the pitch plane. Yaw was left as a separate item
    # (T4) and never recorded -- which is why GESTURE_PIPELINE 14.3.1 could only
    # INFER, not measure, that palm width collapses under yaw while palm length
    # survives. That inference gates the multi-anchor design for Z-axis
    # translation (4.2), and it also matters to B4's yaw-sink result.
    #
    # CONSTANT DEPTH IS THE WHOLE POINT: the hand must not move toward or away
    # from the camera, so that any change in apparent scale is attributable to
    # rotation alone. A depth change would confound exactly the measurement this
    # take exists to make.
    "yaw_sweep_constant_depth": (
        30.0,
        "ONE hand, fingers pointing STRAIGHT UP, held at a FIXED distance. "
        "Rotate about the VERTICAL axis ONLY -- like turning a PAGE -- so the "
        "palm turns edge-on to the camera and back. ~3s per full sweep. Keep the "
        "fingers vertical the whole time. Do NOT tip the fingers toward/away "
        "(pitch), do NOT tilt the hand sideways in the image (roll), and do NOT "
        "move closer or further away.",
        "the yaw axis, never recorded: palm-width collapse under yaw (14.3.1), "
        "the multi-anchor scale reference for 4.1/4.2, and T4's yaw-sink",
    ),
    "depth_sweep": (
        30.0,
        "Push one hand slowly toward the camera and pull it back, repeatedly",
        "depth monotonicity, foreshortening-correction correctness",
    ),
    # §7.2's regression net. DELIBERATELY UNSCRIPTED -- every other sequence here
    # tests a hypothesis we already hold; this one exists to catch the failure
    # modes nobody thought to script. Precedent: no scripted take would have
    # surfaced Object Jump Correction, because "hands cross while rotating" was
    # not a hypothesis anyone had until the bug forced it.
    #
    # ON SPLITTING (owner question, 2026-08-03): splitting by TIME is free -- there
    # is no continuity requirement, so 3x2min == 1x6min. Splitting by ANNOTATION is
    # NOT: labelling sub-sequences turns this back into a scripted take and
    # destroys the only property that makes it useful. Run several short chunks;
    # do not tell the operator what to do inside them.
    #
    # Length is a statistical argument, not an arbitrary one: rare events need
    # exposure time. Object Jump Correction took FOUR takes to reproduce while
    # being actively hunted.
    "free_manipulation": (
        120.0,
        "UNSCRIPTED: use your hands naturally - both hands, move, rotate, reach, "
        "overlap, leave and re-enter frame. No target behaviour.",
        "regression net: catches what the scripted sequences miss. Run several "
        "chunks rather than one long take",
    ),
    "known_right_palm": (
        8.0,
        "RIGHT hand only, PALM to camera, held steady - ground truth clip",
        "the M5d `K` fixture test (item 1.1) - ground truth is the LABEL itself",
    ),
    "known_right_back": (
        8.0,
        "RIGHT hand only, BACK of hand to camera, held steady - ground truth",
        "the M5d `K` fixture test (item 1.1)",
    ),
    "known_left_palm": (
        8.0,
        "LEFT hand only, PALM to camera, held steady - ground truth clip",
        "the M5d `K` fixture test (item 1.1)",
    ),
    # ⭐⭐ `RB2`'s CLOSERS (2026-08-29). Declared hand AND declared facing AND
    # declared mount, recorded UN-MIRRORED -- the one thing the 415-take corpus
    # cannot provide, and the only thing standing between `hand_frame`'s chirality
    # sign and a measurement.
    "rb2_facing_right_palm": (
        10.0,
        "RIGHT hand, PALM to the camera, held steady - camera FACING you",
        "`RB2`: fixes the palm-determinant sign for UN-MIRRORED capture with the "
        "camera facing the user (`hand_frame.CAPTURE_MIRRORED`)",
    ),
    "rb2_worn_right_back": (
        10.0,
        "RIGHT hand, BACK of hand to the camera, held steady - camera WORN by you",
        "`RB2`: the head-worn half of the same question -- the mount must not change "
        "the chirality, because every mount is a proper rotation",
    ),
    "known_left_back": (
        8.0,
        "LEFT hand only, BACK of hand to camera, held steady - ground truth",
        "the M5d `K` fixture test (item 1.1)",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# ⭐⭐⭐ STEPPED SEQUENCES — the recorder walks the operator through timed steps
# and STAMPS WHICH STEP EACH FRAME BELONGS TO (2026-08-29, for `1.7.41`).
#
# ⛔⛔ WHY THIS EXISTS, AND IT IS NOT CONVENIENCE. `delta_orbit_window.py` has to
# separate frames where the hand was HELD from frames where it was MOVING -- a
# hold's per-frame delta is pure error, and that is the number the whole
# delta-orbit window is drawn around. Today it INFERS the split, by thresholding
# the depth-free truth at 1 deg/frame. That truth is `acos` of a foreshortening
# ratio: ill-conditioned near face-on, and past ~120 deg it leans on the chirality
# bit that is least trustworthy exactly there. **So the hold/move split is inferred
# from the noisiest available signal, at the poses where it is noisiest.**
#
# ⭐ A stepped take DECLARES the split instead. `METHOD`: *record what ran; never
# re-derive it* -- the same rule that made production record its own cue after a
# recomputation reported a session clean on a defect the owner had just watched.
#
# ⭐⭐ AND THE HAND MUST BE GRIPPING. `T6`'s closing rule, which cost that row
# twice: **a corpus whose MOTION does not match the product's cannot validate an
# estimator for the product.** Every take that has misled this project on rotation
# was an OPEN hand; the game GRIPS. Every prompt below says so.
#
# ⚠ The angles are what the operator is ASKED for, not ground truth -- a person
# cannot place their own hand to a degree. They label the SEGMENT; the depth-free
# truth still supplies the measured angle. When the two disagree that is itself a
# finding, which is why both are kept (the pattern `U7`'s declared-ground-truth
# acceptance take established).
#
# ⚠ Hold the DISTANCE roughly constant across the take. `CAVEAT ZERO` (the six
# T6 takes) retracted every depth-derived reading because the hand moved; this
# measurement is angular and survives that, but a distance that drifts changes the
# landmark noise itself and would smear the window.
#
#   name -> [(seconds, step label, on-screen prompt), ...]
STEP_HOLD_S = 3.0          # long enough for a p95 over ~90 frames at 30fps
STEP_MOVE_S = 2.0          # transition; its frames are labelled and EXCLUDED


def _sweep_steps(axis, hint, angles):
    """HOLD / MOVE / HOLD ... across `angles`, every step labelled.

    ⚠ The prompt names the axis AND the motion, because the single most expensive
    recording mistake this project has made was an AXIS-CONTAMINATED take: the
    2026-08-04 yaw take said "doorknob", which is ROLL, and both palm spans
    collapsed -- it measured a mixture and every number from it had to be thrown
    away (`YAW_AXIS_NOTE` above, spec §14.3.3). One axis at a time, named twice."""
    steps = []
    for i, a in enumerate(angles):
        if i:
            steps.append((STEP_MOVE_S, "move_%d" % a,
                          "MOVE to %s %d deg  (%s)  - keep gripping" % (axis, a, hint)))
        steps.append((STEP_HOLD_S, "hold_%d" % a,
                      "HOLD STILL @ %s %d deg  - grip as if holding a small cube"
                      % (axis, a)))
    return steps


# ⚠ 0 deg is PALM SQUARE TO THE CAMERA for yaw and pitch -- the same face-on
# reference `delta_orbit_window.py` measures angles from, so the declared label and
# the measured angle mean the same thing. For roll, 0 is fingers straight up.
WINDOW_ANGLES = (0, 15, 30, 45, 60, 75, 90)

# ⭐⭐⭐ `RB3`'s TAKE: BOTH HANDS, THE SAME MOTION, ONE AXIS AT A TIME.
#
# ⛔ WHY BOTH HANDS TOGETHER AND NOT TWO SINGLE-HAND TAKES. **A rotation is a
# property of the WORLD, not of the hand**: if both hands pitch the same way at the
# same moment, the estimator must report the SAME sign for both. Two separate takes
# cannot test that -- the operator cannot reproduce a motion exactly, so a
# disagreement would be indistinguishable from having moved differently.
# ⚠ EVERY take in this project's rotation work has been single-hand, so this
# invariant has NEVER been tested. It is the one that would have caught a chirality
# leak into orientation, which is the class that gated a whole hand to zero on
# 2026-08-29.
#
# ⛔ ONE AXIS AT A TIME, named twice in the prompt: the 2026-08-04 yaw take was
# measured AXIS-CONTAMINATED and every number from it was thrown away.
# ⭐⭐⭐ THE DECLARED PHYSICAL DIRECTION OF EACH `_pos` STEP, AS DATA.
#
# Owner, 2026-08-29: *"I will pitch towards the camera. note that."* ⭐ So it is
# noted HERE, where the analysis can read it, and not only in a prompt string that
# a human has to remember having read. This is the GROUND TRUTH the `RB3` sign test
# asserts against -- without it the take says only "something moved", and a sign
# test with no declared direction is not a test.
#
# ⚠ SCREEN-RELATIVE, always: "toward you" was ambiguous in the first draft (with
# the camera facing the operator it means AWAY from the camera) and the owner caught
# it. The camera is the one reference both the operator and the analysis share.
RB3_DECLARED = {
    "pitch": "fingertips move TOWARD THE CAMERA",
    "yaw": "both hands turn to the OPERATOR'S LEFT",
    "roll": "both hands rotate CLOCKWISE as seen on screen",
}

RB3_STEPS = []
#
# ⛔⛔ SAME DIRECTION IN THE WORLD, **NEVER** MIRROR-SYMMETRIC (owner asked, and
# the first prompts were ambiguous). The hands naturally want to move as a mirror
# pair -- both rotating OUTWARD -- and that would make the test USELESS: with
# mirrored input the CORRECT answer is opposite signs, so a chirality leak would be
# indistinguishable from a correct result. The prompts below name a screen-relative
# direction, which is unambiguous for both hands.
# ⚠⚠ EVERY PROMPT SAYS **MOVE** OR **HOLD STILL** AS ITS FIRST WORD, and names the
# END POSE rather than an abstraction. The first draft said *"both hands at the
# opposite PITCH"*, and the owner's reply was the only review that matters: *"what
# does it mean?"* — plus *"it is not clear if a take has to be a movement or a
# hold"*. A step whose instruction has to be decoded is a step performed wrong.
_RB3_AXES = (
    ("pitch",
     "MOVE  -  tip BOTH sets of fingertips TOWARD THE CAMERA",
     "HOLD STILL  -  keep fingertips pointing TOWARD THE CAMERA",
     "MOVE  -  tip BOTH sets of fingertips AWAY, back past flat",
     "HOLD STILL  -  keep fingertips pointing AWAY from the camera"),
    ("yaw",
     "MOVE  -  turn BOTH hands to YOUR LEFT (both the same way)",
     "HOLD STILL  -  keep BOTH hands turned to YOUR LEFT",
     "MOVE  -  turn BOTH hands to YOUR RIGHT, past flat",
     "HOLD STILL  -  keep BOTH hands turned to YOUR RIGHT"),
    ("roll",
     "MOVE  -  tilt BOTH hands CLOCKWISE on screen (both the same way)",
     "HOLD STILL  -  keep BOTH hands tilted CLOCKWISE",
     "MOVE  -  tilt BOTH hands ANTICLOCKWISE, past upright",
     "HOLD STILL  -  keep BOTH hands tilted ANTICLOCKWISE"),
)
for _ax, _mp, _hp, _mn, _hn in _RB3_AXES:
    _A = _ax.upper()
    RB3_STEPS.append((3.0, "hold_%s_0" % _ax,
                      "HOLD STILL  -  both hands FLAT, palms to camera, fingers up"))
    RB3_STEPS.append((4.0, "move_%s_pos" % _ax, _mp))
    RB3_STEPS.append((3.0, "hold_%s_pos" % _ax, _hp))
    RB3_STEPS.append((4.0, "move_%s_neg" % _ax, _mn))
    RB3_STEPS.append((3.0, "hold_%s_neg" % _ax, _hn))

# ⚠⚠ YAW ALONE, BECAUSE YAW ALONE WAS INCONCLUSIVE (2026-08-29). On the first
# two-hand take pitch and roll agreed between the hands and yaw did not -- but the
# RIGHT hand's palm swung only **+1.3 deg** on `yaw_neg` against the left's +51.7,
# so that step was simply not performed symmetrically. ⛔ A disagreement produced by
# one hand not moving is not evidence about the pipeline, and re-running the whole
# 15-step script to fix one axis wastes the two axes that were already clean.
#
# ⭐ The prompts here say RETURN ALL THE WAY, which is what actually went wrong:
# the hand stopped short rather than crossing back through flat.
RB3_YAW_STEPS = [
    (3.0, "hold_yaw_0",
     "HOLD STILL  -  both hands FLAT, palms to camera, fingers up"),
    # ⚠ A SMALL TURN, ON PURPOSE (owner, 2026-08-29: *"I will rotate less ... I
    # think we catch the edge on issue"*). A large yaw takes one palm toward
    # edge-on, where the world landmarks collapse and every derived quantity stops
    # meaning anything -- so this take stays in the region where the measurement is
    # trustworthy, and tests the owner's hypothesis by avoiding it rather than
    # arguing about it. ⛔ Keep BOTH hands well inside the frame.
    (4.0, "move_yaw_pos",
     "MOVE  -  turn BOTH hands SLIGHTLY to YOUR LEFT (small, ~30 deg)"),
    (3.0, "hold_yaw_pos",
     "HOLD STILL  -  both hands slightly LEFT, both in frame"),
    (4.0, "move_yaw_neg",
     "MOVE  -  turn BOTH hands SLIGHTLY to YOUR RIGHT (small, past flat)"),
    (3.0, "hold_yaw_neg",
     "HOLD STILL  -  both hands slightly RIGHT, both in frame"),
]

STEPS = {
    # ⭐ `RB3` -- both hands, same motion, one axis at a time. 51 s.
    "rb3_two_hands_axes": RB3_STEPS,
    "rb3_yaw_only": RB3_YAW_STEPS,
    # ⭐ YAW IS THE ONE THAT BLOCKS THE BUILD. `delta_orbit_window.py` cannot place
    # its window from the existing corpus: that take's holds sit at 120-180 deg
    # (n=140) with only 11-12 frames near face-on, where a p95 is barely the max.
    "window_yaw_grip": _sweep_steps("YAW", "turn like a page; fingers stay UP", WINDOW_ANGLES),
    # ⭐ PITCH CONFIRMS a window already measured on two takes (clean 1.1-2.1 deg
    # below 30, degrading past 50, 9.6-13.6 at 60-75). This take is what turns two
    # agreeing accidents into a placed fade.
    "window_pitch_grip": _sweep_steps("PITCH", "tip fingertips toward/away; do NOT twist",
                                      WINDOW_ANGLES),
    # ⚠ ROLL IS THE CONTROL, and it is worth the 35 s precisely because it should
    # come out FLAT (1.33-2.10 deg at every pose on the existing take). A window
    # that appears here would mean the method is manufacturing windows.
    "window_roll_grip": _sweep_steps("ROLL", "spin in the image plane; palm stays facing you",
                                     WINDOW_ANGLES),
}

# ⚠ The declared directions ride into `meta.json` with the take, so a future
# analysis never has to guess what the operator was asked to do.
SEQUENCES["rb3_yaw_only"] = (
    sum(d for d, _l, _p in RB3_YAW_STEPS),
    "YAW only, BOTH hands the SAME way - press SPACE to start each step",
    "`RB3`: the yaw half of the two-hand sign test, which was inconclusive because "
    "one hand did not return through flat",
)

SEQUENCES["rb3_two_hands_axes"] = (
    sum(d for d, _l, _p in RB3_STEPS),
    "BOTH hands, SAME motion (not mirrored) - press SPACE to start each step",
    "`RB3`: a rotation is a property of the WORLD, so both hands must report the "
    "SAME sign for the same motion. Never tested -- every prior take is one hand",
)

for _name, _steps in STEPS.items():
    SEQUENCES[_name] = (
        sum(d for d, _l, _p in _steps),
        "stepped take - follow the on-screen step (grip, do not open the hand)",
        "the delta-orbit rate window (`1.7.41`): the per-pose noise floor a "
        "rate-control build would integrate, on DECLARED holds and a GRIPPING hand",
    )


def _window_open(name):
    return cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) >= 1


def main():
    parser = argparse.ArgumentParser(description="Record a scripted perception-layer test sequence.")
    # ⭐⭐ `1.7.42` DETECTS UN-MIRRORED, so a take meant for it must be recorded
    # that way. ⛔ EVERY ONE OF THE 415 CORPUS TAKES IS MIRRORED, which is why the
    # new frame layer's chirality sign is currently a PREDICTION rather than a
    # measurement -- `hand_frame.CAPTURE_MIRRORED`. This flag is what closes it.
    # ⚠ A mirror is det -1: it INVERTS the palm determinant, so a mirrored and an
    # un-mirrored take of the same hand disagree about which hand it is. They are
    # not interchangeable and `meta.json` records which one this is.
    parser.add_argument("--no-mirror", action="store_true",
                        help="detect and record on the UN-MIRRORED frame (1.7.42)")
    parser.add_argument("--mount", default="", choices=("", "facing_user", "head_worn"),
                        help="declare where the camera is; recorded into meta.json")
    parser.add_argument("--sequence", required=True, choices=sorted(SEQUENCES),
                        help="which §7.2 sequence to record")
    parser.add_argument("--duration", type=float, default=None, help="override the default duration")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--note", type=str, default="", help="free-text note stored in meta.json")
    parser.add_argument("--hand", choices=("left", "right", "both"), default="both",
                        help="which hand(s) the operator used. Recorded in meta.json. "
                             "Use 'left'/'right' for single-hand takes: two-hand takes "
                             "inject duplicate-label frames (spec §0.8 finding 4), which "
                             "contaminate per-hand analysis")
    parser.add_argument("--cycles", type=int, default=None,
                        help="number of FULL palm->back->palm cycles actually performed "
                             "(defaults to the sequence's prescribed count). Stored in "
                             "meta.json along with expected_sign_changes = 2 x cycles")
    parser.add_argument("--local", action="store_true",
                        help="record to the LOCAL capture root instead of the external drive "
                             "(use when E: is unavailable; move the session folder later)")
    parser.add_argument("--capture-root", type=str, default=None,
                        help="explicit capture root, overriding both defaults")
    parser.add_argument("--save-frames", action="store_true",
                        help="also save the raw camera frames alongside the landmarks "
                             "(queue item 0.1; REQUIRED by item 0.5's offline oracle -- "
                             "the pre-2026-08-03 corpus has no images, so an oracle take "
                             "must be re-recorded with this). Saves the MIRRORED, "
                             "pre-overlay frame detection actually ran on")
    parser.add_argument("--frame-format", choices=("jpg", "png"), default="jpg",
                        help="jpg (default, ~50 KB/frame) or png (lossless, ~10x the "
                             "disk; use to rule out compression artifacts as a confound)")
    parser.add_argument("--frame-stride", type=int, default=1,
                        help="save every Nth frame (default 1 = all). The landmark JSONL "
                             "always keeps every frame; this only subsamples the images, "
                             "for when the oracle does not need per-frame density")
    args = parser.parse_args()

    if args.frame_stride < 1:
        raise SystemExit("[perception] --frame-stride must be >= 1.")
    if (args.frame_format != "jpg" or args.frame_stride != 1) and not args.save_frames:
        print("[perception] NOTE: --frame-format/--frame-stride have no effect "
              "without --save-frames.")

    capture_root = args.capture_root or (LOCAL_CAPTURE_ROOT if args.local else CAPTURE_ROOT)

    default_duration, prompt, unblocks = SEQUENCES[args.sequence]
    # ⭐ A stepped sequence carries its own timed script; a classic one does not.
    # ⚠ `steps` stays empty for every pre-2026-08-29 sequence, so their frames
    # carry no `step` key and every existing harness reads them unchanged.
    steps = STEPS.get(args.sequence, ())
    countdown_s = 8.0 if steps else COUNTDOWN_S
    step_left = 0.0
    if steps and args.duration and abs(args.duration - default_duration) > 1e-6:
        # ⛔ A stepped take's length IS its script. Letting `--duration` cut it
        # short would drop the last holds silently -- and the last holds are the
        # large angles, which is the half of the window that is actually in doubt.
        print(f'[perception] ** --duration is ignored for the stepped sequence '
              f'{args.sequence}: its length is its script '
              f'({default_duration:.0f}s).')

    duration = args.duration if args.duration is not None else default_duration

    # PREFLIGHT: create and write-test the session directory BEFORE capturing a
    # single frame. Learned the hard way 2026-08-02 -- the capture root is on an
    # external drive, and when it was unavailable the original ordering failed at
    # SAVE time, discarding a completed 12s take. Fail before the operator's
    # effort, never after it.
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session_dir = os.path.join(capture_root, "sessions", f"{stamp}_{args.sequence}")
    frames_dir = os.path.join(session_dir, "frames")
    try:
        os.makedirs(session_dir, exist_ok=True)
        if args.save_frames:
            os.makedirs(frames_dir, exist_ok=True)
        probe = os.path.join(session_dir, ".writable")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
    except OSError as e:
        raise SystemExit(
            f"[perception] Capture root is not writable, refusing to record.\n"
            f"             path : {session_dir}\n"
            f"             error: {e}\n"
            f"             If this is the external drive, re-run with --local to "
            f"capture locally\n"
            f"             and move the session folder across later."
        )

    base_options = python.BaseOptions(model_asset_path=HAND_LANDMARKER_MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options, num_hands=2, running_mode=vision.RunningMode.VIDEO
    )
    detector = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera_index}). "
                           f"Is another program using the camera?")
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read an initial frame from the webcam.")
    height, width = frame.shape[:2]

    # Frame-buffer preflight, BEFORE the countdown -- same rule as the capture-root
    # probe above: an operator's take must never be lost to a condition that was
    # knowable in advance. Assumes the corpus baseline ~25 fps as the worst case.
    if args.save_frames:
        bytes_per_frame = width * height * 3
        est_frames = int(duration * 25.0 / args.frame_stride) + 1
        est_bytes = est_frames * bytes_per_frame
        if est_bytes > MAX_FRAME_BUFFER_BYTES:
            max_duration = MAX_FRAME_BUFFER_BYTES * args.frame_stride / (bytes_per_frame * 25.0)
            cap.release()
            raise SystemExit(
                f"[perception] --save-frames would buffer ~{est_bytes / 1024 ** 3:.1f} GiB "
                f"({est_frames} frames at {width}x{height}), over the "
                f"{MAX_FRAME_BUFFER_BYTES / 1024 ** 3:.0f} GiB ceiling.\n"
                f"             Refusing before the take rather than failing during it.\n"
                f"             Options: --duration below ~{max_duration:.0f}s, or raise "
                f"--frame-stride (currently {args.frame_stride})."
            )
        print(f"[perception] frames   : saving ~{est_frames} {args.frame_format} images "
              f"(stride {args.frame_stride}), buffering ~{est_bytes / 1024 ** 3:.1f} GiB")

    window_name = f"Perception capture - {args.sequence}"
    records = []
    frame_buffer = []  # (record_index, BGR frame copy) -- encoded after the take
    stop_reason = "unknown"

    print(f"[perception] sequence : {args.sequence}")
    print(f"[perception] duration : {duration:.1f}s (after a {countdown_s:.0f}s countdown)")
    print(f"[perception] DO THIS  : {prompt}")
    if args.sequence.startswith("palm_back") or args.sequence.startswith("pitch_sweep"):
        print(f"[perception] AXIS     : {PITCH_AXIS_NOTE}")
    if args.sequence.startswith("yaw_sweep"):
        print(f"[perception] AXIS     : {YAW_AXIS_NOTE}")
    print(f"[perception] unblocks : {unblocks}")

    t0 = time.perf_counter()
    try:
        # --- countdown ---
        countdown_start = time.perf_counter()
        aborted = False
        while True:
            ret, frame = cap.read()
            if not ret:
                aborted = True
                break
            if not args.no_mirror:
                frame = cv2.flip(frame, 1)  # mirrored preview, matching the debug tools
            # ⭐ A STEPPED take gets a longer runway, and the reason is
            # structural: its FIRST step is `hold_0`, so the operator must
            # already be in position and still when recording starts. A
            # free-motion take can afford to lose its first second; a take
            # whose opening 3 s IS one of the measured holds cannot.
            remaining = countdown_s - (time.perf_counter() - countdown_start)
            if remaining <= 0:
                break
            cv2.putText(frame, f"Get ready... {remaining:.1f}s", (10, 30),
                        cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, prompt, (10, 65),
                        cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow(window_name, frame)
            cv2.waitKey(1)
            if not _window_open(window_name):
                aborted = True
                break

        # --- capture ---
        if not aborted:
            record_start = time.perf_counter()
            # ⭐⭐⭐ OPERATOR-PACED STEPS (owner, 2026-08-29): *"there are a lot of
            # different cases and I don't have time to read the prompts. ask me to
            # press space to start the take each time so I have time to read the
            # prompt."*
            #
            # ⛔ A TIMED SCRIPT ASSUMES THE OPERATOR HAS ALREADY READ IT. The first
            # two-hand attempt produced a hand in only **429 of 1012 frames** -- the
            # operator was still parsing each instruction while its window was
            # already recording. A prompt nobody has time to read is not an
            # instruction, it is a decoration, and the frames it labels are junk.
            #
            # ⭐ So each step now WAITS for SPACE, showing its prompt, and only then
            # records for its own duration. The take's wall-clock becomes the
            # operator's business; the RECORDED span per step is unchanged, which is
            # what the analysis reads.
            # ⚠ `tCapture` still comes from the monotonic clock, so the gaps while
            # waiting are simply absent from the timeline -- steps stay contiguous
            # in the data even though they were not in the room.
            paced = bool(steps)
            grace_until = 0.0
            step_i = 0
            step_t0 = None
            waiting = paced
            while True:
                if paced:
                    if step_i >= len(steps):
                        stop_reason = "all steps done"
                        break
                else:
                    elapsed = time.perf_counter() - record_start
                    if elapsed >= duration:
                        stop_reason = "duration reached"
                        break

                ret, frame = cap.read()
                t_capture_ms = (time.perf_counter() - t0) * 1000.0  # real monotonic clock
                if not ret:
                    # Camera returned no frame. Distinct from a closed window, and
                    # the two were indistinguishable before 2026-08-04, when two
                    # takes in a row stopped early (21.5s and 3.2s of a requested
                    # 30s) with no way to tell which cause it was.
                    stop_reason = "camera read failed (cap.read() returned False)"
                    break
                if not args.no_mirror:
                    frame = cv2.flip(frame, 1)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = detector.detect_for_video(mp_image, int(t_capture_ms))

                hands = []
                for idx in range(len(result.hand_landmarks)):
                    hands.append({
                        "handedness": result.handedness[idx][0].category_name,
                        "score": round(float(result.handedness[idx][0].score), 5),
                        # pixel coords in the MIRRORED preview frame (detection ran on it)
                        "landmarks": [[round(lm.x * width, 2), round(lm.y * height, 2)]
                                      for lm in result.hand_landmarks[idx]],
                        "world_landmarks": [[round(lm.x, 5), round(lm.y, 5), round(lm.z, 5)]
                                            for lm in result.hand_world_landmarks[idx]],
                    })
                record = {"tCapture": round(t_capture_ms, 2), "hands": hands}

                # ⭐⭐ STAMP THE STEP THIS FRAME BELONGS TO. Declared, not inferred:
                # `delta_orbit_window.py` currently guesses hold-vs-move by
                # thresholding a depth-free truth that is ill-conditioned exactly
                # where the answer matters. A labelled frame removes that guess.
                # ⚠ Stamped from `elapsed`, the same monotonic clock the take is
                # cut on -- never from a frame counter, which drifts with fps.
                step_prompt = prompt
                if paced:
                    _d, _label, _p = steps[step_i]
                    step_prompt = _p
                    if waiting:
                        # ⛔ NOT RECORDED. The operator is reading, and whatever the
                        # hands are doing meanwhile is not the step.
                        step_left = 0.0
                        record = None
                    elif step_t0 is None:
                        # ⚠ In the grace window: the prompt is up, the operator is
                        # getting both hands back into frame, and NOTHING is written.
                        step_left = grace_until - time.perf_counter()
                        record = None
                        if step_left <= 0.0:
                            step_t0 = time.perf_counter()
                    else:
                        step_left = _d - (time.perf_counter() - step_t0)
                        record["step"] = _label
                        if step_left <= 0.0:
                            step_i += 1
                            waiting = True
                elif steps:
                    acc = 0.0
                    for _d, _label, _p in steps:
                        acc += _d
                        if elapsed < acc:
                            record["step"] = _label
                            step_prompt = _p
                            step_left = acc - elapsed
                            break
                    else:                      # past the last step: keep the last
                        record["step"] = steps[-1][1]
                        step_prompt = steps[-1][2]
                        step_left = 0.0

                # Buffer the frame BEFORE any overlay is drawn. `frame` is the
                # mirrored array `rgb` (and therefore MediaPipe) was derived from,
                # and cv2.putText mutates it in place a few lines below -- so an
                # oracle fed a later copy would be reading the REC banner and the
                # prompt text baked into the image. .copy() is also required
                # because cap.read() may reuse its buffer.
                if record is not None:
                    if args.save_frames and (len(records) % args.frame_stride == 0):
                        name = f"{len(records):06d}.{args.frame_format}"
                        frame_buffer.append((name, frame.copy()))
                        record["frame"] = f"frames/{name}"
                    records.append(record)

                # minimal overlay: no landmark drawing, to keep this tool free of
                # any dependency on the gesture/visualiser layer
                # ⚠ A PACED take has no meaningful "time left": its length is the
                # operator's. Show the STEP position instead, which is what they
                # actually need. (`elapsed` does not exist on the paced path -- and
                # reading it here is exactly what crashed the first paced run.)
                _hdr = ("STEP %d/%d  frames:%d  hands:%d"
                        % (step_i + 1, len(steps), len(records), len(hands))
                        if paced else
                        "REC %4.1fs  frames:%d  hands:%d"
                        % (duration - elapsed, len(records), len(hands)))
                cv2.putText(frame, _hdr,
                            (10, 30), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, step_prompt, (10, 62),
                            cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
                # ⭐ A stepped take is USELESS if the operator cannot see when the
                # step changes -- the whole point is that the labelled frames really
                # were held. So the step's own countdown is drawn big, and a HOLD is
                # green while a MOVE is amber: the colour is readable out of the
                # corner of an eye while the operator is looking at their hand.
                # ⚠ `record is None` WHILE A PACED STEP IS WAITING — the operator is
                # reading and nothing is being recorded. Two consecutive crashes came
                # from overlay code reading state that only exists while RECORDING
                # (`elapsed`, then `record`), so the label is taken from `steps`
                # directly and the countdown is drawn only when it means something.
                if steps and not (paced and waiting):
                    _lbl = steps[step_i][1] if paced else record.get("step", "")
                    holding = _lbl.startswith("hold")
                    cv2.putText(
                        frame,
                        "%s  %.1fs" % ("HOLD" if holding else "move", step_left),
                        (10, 105), cv2.FONT_HERSHEY_DUPLEX, 1.0,
                        (0, 220, 0) if holding else (0, 190, 255), 2, cv2.LINE_AA)
                if paced and not waiting and step_t0 is None:
                    cv2.putText(frame, "BOTH HANDS UP  %.1fs" % max(0.0, step_left),
                                (10, 140), cv2.FONT_HERSHEY_DUPLEX, 0.9,
                                (0, 200, 255), 2, cv2.LINE_AA)
                if paced and waiting:
                    # ⭐ The whole point: the prompt is on screen and NOTHING is being
                    # recorded until the operator says they have read it.
                    cv2.putText(frame, "step %d/%d  -  press SPACE when ready"
                                % (step_i + 1, len(steps)), (10, 140),
                                cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 220, 255), 2,
                                cv2.LINE_AA)
                cv2.imshow(window_name, frame)
                _k = cv2.waitKey(1) & 0xFF
                if _k == ord("q"):
                    stop_reason = "operator pressed q"
                    break
                if paced and waiting and _k == 32:          # SPACE
                    # ⭐⭐⭐ GRACE BEFORE RECORDING, AND IT IS NOT POLITENESS.
                    # Owner, 2026-08-29: *"I need a hand to press the space bar so
                    # each time, one of the hands appears slightly later on the
                    # recording."*
                    # ⛔⛔ THAT WOULD HAVE CORRUPTED EXACTLY THE MEASUREMENT THIS
                    # TAKE EXISTS FOR. `RB3` compares the TWO HANDS against each
                    # other within a moment; frames where one hand has not returned
                    # are not merely useless, they are the frames most likely to be
                    # mistaken for a real disagreement between the hands.
                    # ⭐ So SPACE starts a short countdown, not the step. The
                    # operator gets both hands back up, and only then does anything
                    # reach the file.
                    waiting = False
                    grace_until = time.perf_counter() + PACED_GRACE_S
                    step_t0 = None
                # ⛔⛔ THE VISIBILITY CHECK IS ADVISORY, NOT FATAL, FOR A **STEPPED**
                # TAKE (2026-08-29). It exists so a closed window ends a take
                # cleanly -- good for a free-motion clip. But a stepped take is a
                # SCRIPT: three consecutive `rb3` recordings died at 12.7 s of 51 s
                # with `preview window reported not visible`, losing two of the
                # three axes each time, because OpenCV reports the window hidden
                # when it is merely not foreground (which it is not, when the tool
                # is launched from a shell that keeps focus).
                # ⚠ A take that ends early is WORSE than one that fails loudly: it
                # looks complete in the folder listing and silently lacks the steps
                # the analysis needs. So a stepped take runs its script out, and the
                # operator ends it with `q` or Ctrl-C.
                if not _window_open(window_name) and not steps:
                    stop_reason = "preview window reported not visible"
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not records:
        print("[perception] No frames captured, nothing saved.")
        try:
            # frames/ is created by the preflight, so it must go first or the
            # session dir is left behind as an empty stub.
            if os.path.isdir(frames_dir):
                os.rmdir(frames_dir)
            os.rmdir(session_dir)  # don't leave an empty session behind
        except OSError:
            pass
        return

    # LANDMARKS FIRST, ALWAYS. The JSONL is the irreplaceable part of a take (a
    # few hundred KB); the frames are bulk that a re-record can regenerate. An
    # earlier version of this wrote frames first, which put an operator's
    # completed take at the mercy of a disk-full or an E: dropout (N4) during a
    # multi-hundred-MB write -- the same "fail before the operator's effort,
    # never after it" rule the capture-root preflight exists to enforce.
    jsonl_path = os.path.join(session_dir, "raw_landmarks.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    # Now the bulk. The camera is released and the operator is done, so nothing
    # here can affect measured_fps. Failures are reported and recorded in
    # meta.json rather than raised: by this point the take is already safe, and
    # killing the process would only lose the metadata too.
    frames_written = 0
    frames_bytes = 0
    frames_error = None
    if frame_buffer:
        encode_params = ([int(cv2.IMWRITE_JPEG_QUALITY), DEFAULT_JPEG_QUALITY]
                         if args.frame_format == "jpg" else [])
        print(f"[perception] landmarks saved; writing {len(frame_buffer)} frames...")
        encode_start = time.perf_counter()
        try:
            for name, img in frame_buffer:
                path = os.path.join(frames_dir, name)
                if not cv2.imwrite(path, img, encode_params):
                    raise OSError(f"cv2.imwrite returned False for {path}")
                frames_written += 1
                frames_bytes += os.path.getsize(path)
        except OSError as e:
            frames_error = str(e)
            print(f"[perception] ** FRAME WRITE FAILED after {frames_written} frames: {e}")
            print(f"[perception] ** The landmark data IS saved -- the take is not lost.")
            print(f"[perception] ** Re-record if the frames are needed.")
        else:
            print(f"[perception] {frames_written} frames written "
                  f"({frames_bytes / 1024 ** 2:.0f} MB) in "
                  f"{time.perf_counter() - encode_start:.1f}s")

    span_s = (records[-1]["tCapture"] - records[0]["tCapture"]) / 1000.0
    meta = {
        "sequence": args.sequence,
        # ⭐ `RB3`: the declared physical direction of each `_pos` step, carried
        # with the take so the sign test has ground truth rather than a memory.
        "declared_directions": (RB3_DECLARED
                                if args.sequence.startswith("rb3_") else None),
        "prompt": prompt,
        "unblocks": unblocks,
        "note": args.note,
        "requested_duration_s": duration,
        "actual_span_s": round(span_s, 3),
        "frames": len(records),
        "measured_fps": round(len(records) / span_s, 2) if span_s > 0 else None,
        "resolution": [width, height],
        "camera_index": args.camera_index,
        "mediapipe_version": getattr(mp, "__version__", "unknown"),
        "model": os.path.basename(HAND_LANDMARKER_MODEL_PATH),
        "mirrored_preview": True,
        # ⛔ THE SINGLE MOST IMPORTANT FIELD FOR A CHIRALITY CONSUMER. A mirror
        # is det -1, so this flag decides which sign of the palm determinant
        # means "right hand". A take without it is ambiguous.
        "detection_on_mirrored_frame": not args.no_mirror,
        "declared_mount": args.mount or None,
        "recorded_at": stamp,
        "stop_reason": stop_reason,
        "completed_full_duration": span_s >= duration - 1.0,
        "config_hash": hashlib.sha256(
            f"{args.sequence}|{width}x{height}|{getattr(mp, '__version__', '?')}".encode()
        ).hexdigest()[:12],
    }
    # Ground truth for the chirality-flip metric, when this sequence has one.
    # BOTH units are stored deliberately: the operator thinks in cycles, the
    # analyser counts sign inversions, and comparing the wrong pair produced a
    # wrong conclusion once (spec §0.7).
    if args.sequence.startswith("palm_back") or args.sequence.startswith("pitch_sweep"):
        meta["rotation_axis"] = "pitch"
        meta["rotation_axis_note"] = PITCH_AXIS_NOTE

    meta["frames_saved"] = frames_written
    if frames_error:
        meta["frames_error"] = frames_error
        meta["frames_incomplete"] = True
    if frames_written:
        meta["frame_format"] = args.frame_format
        meta["frame_stride"] = args.frame_stride
        meta["frame_jpeg_quality"] = DEFAULT_JPEG_QUALITY if args.frame_format == "jpg" else None
        meta["frames_bytes"] = frames_bytes
        meta["frames_note"] = (
            "Saved images are the MIRRORED, PRE-OVERLAY frames MediaPipe itself ran on "
            "(detection_on_mirrored_frame is true). An offline oracle (queue item 0.5, "
            "HaMeR/WiLoR) MUST be fed these as-is: un-flipping them, or using an "
            "un-mirrored capture, inverts chirality and makes any comparison against "
            "the recorded landmarks meaningless. Each JSONL record carries its own "
            "'frame' path; frames are indexed by record position, so a stride > 1 "
            "leaves records without a 'frame' key by design."
        )

    meta["hands_used"] = args.hand
    if args.hand != "both":
        meta["hands_used_note"] = (
            "SINGLE-HAND take. Two-hand takes inject duplicate-label frames that "
            "contaminate per-hand streams (spec §0.8 finding 4); this take avoids that "
            "and also isolates the Left/Right asymmetry logged as queue item N11."
        )

    cycles = args.cycles if args.cycles is not None else DEFAULT_CYCLES.get(args.sequence)
    if cycles is not None:
        meta["counted_crossing_cycles"] = cycles
        meta["expected_sign_changes"] = 2 * cycles
        meta["counted_crossings_definition"] = (
            "One CYCLE = palm -> back -> palm = TWO sign changes. The analyser counts "
            "per-frame sign inversions, so compare its output against "
            "expected_sign_changes, NEVER against counted_crossing_cycles."
        )
        meta["cycles_source"] = ("operator-supplied via --cycles" if args.cycles is not None
                                 else "sequence-prescribed default")

    with open(os.path.join(session_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    detected = sum(1 for r in records if r["hands"])
    print(f"[perception] Saved {len(records)} frames ({meta['measured_fps']} fps measured) to")
    print(f"             {session_dir}")
    print(f"[perception] frames with >=1 hand detected: {detected}/{len(records)}")
    if frames_written:
        print(f"[perception] images saved: {frames_written} ({frames_bytes / 1024 ** 2:.0f} MB) "
              f"-> {frames_dir}")
    if cycles is not None:
        print(f"[perception] ground truth: {cycles} cycles -> {2 * cycles} expected sign changes")

    # A take that ended early looks perfectly valid in analysis -- same fps, same
    # detection rate, just fewer frames -- so say so loudly here rather than
    # leaving it to be noticed by dividing frames by fps afterwards.
    if span_s < duration - 1.0:
        print()
        print(f"[perception] ****************************  WARNING  ****************************")
        print(f"[perception] Take ended EARLY: {span_s:.1f}s of a requested {duration:.1f}s.")
        print(f"[perception] Stop reason: {stop_reason}")
        print(f"[perception] >>> Check whether the target behaviour was completed. <<<")
        print(f"[perception] ********************************************************************")

    fps = meta["measured_fps"]
    if fps is not None and fps < MIN_EXPECTED_FPS:
        print()
        print(f"[perception] ****************************  WARNING  ****************************")
        print(f"[perception] Measured {fps} fps, below the {MIN_EXPECTED_FPS:.0f} fps floor.")
        print(f"[perception] The corpus baseline is ~24 fps; low frame rate is caused by dim")
        print(f"[perception] light (auto-exposure lengthens each frame) and makes this take")
        print(f"[perception] NOT comparable to the rest of the corpus. It also widens the")
        print(f"[perception] per-frame interval, which is a direct confound for crossing and")
        print(f"[perception] motion-blur analysis.")
        print(f"[perception] >>> ADD LIGHT AND RE-RECORD. Consider discarding this take. <<<")
        print(f"[perception] ********************************************************************")


if __name__ == "__main__":
    main()
