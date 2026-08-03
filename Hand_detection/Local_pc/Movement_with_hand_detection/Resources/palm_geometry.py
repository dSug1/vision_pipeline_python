"""Palm chirality geometry -- SHARED by production and the debug tool.

Merged queue item 1.2 (M5a `edgeOnMeasure`). See PERCEPTION_LAYER_SPEC.md §0.9 for
the chirality convention this rests on, and A2 for why only the *magnitude* is new.

--------------------------------------------------------------------------------
WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
Two things, and the second is the reason it is a MODULE rather than a function
added twice:

1. **The magnitude was being thrown away.** `_is_thumb_outward` already computed
   the signed area `s` of (index_MCP - wrist) x (pinky_MCP - wrist) and used only
   `sign(s)`. `|s|`, normalised, is the **edge-on measure**: how close the palm is
   to edge-on, 0 = perfectly edge-on, 1 = square to the camera. It costs one
   division and is the observability signal DR-2 (item 2.2), M4 and M6 need.

2. **The sign convention was duplicated.** `HandsTriggeredActions.py` and
   `LiveSnapDebug.py` each carried their own copy, "kept in sync" by hand. That is
   exactly how the convention drifted into the production-only inversion of
   2026-08-01 (§13.6.1). Duplication was already fixed once this way for the hand
   identity tracker (`hand_identity.py`, queue N6) on the owner's instruction --
   *"I do not want to have a debug tool which is not in tune with the
   production."* Same treatment here.

Deliberately dependency-free (pure stdlib, no numpy/cv2/pygame) so both callers
can import it without side effects -- `HandsTriggeredActions` opens a real pygame
window at import, so anything shared must not live there.

--------------------------------------------------------------------------------
THE NORMALISATION MUST NOT DRIFT FROM THE ANALYSER
--------------------------------------------------------------------------------
`AnalyzePerceptionSequences.edge_on()` computes `|s| / (|v1| * |v2|)`, and every
recorded threshold -- notably `EDGE_ON_THRESHOLD = 0.15`, settled by measurement
in spec §0.3 -- is expressed in THAT scale. Using a different normalisation here
would silently invalidate the threshold. `verify_matches_analyser()` below exists
to keep the two honest; `VerifyChiralityFixture.py` runs it.

Geometrically the quantity is |sin(theta)| between the two palm vectors, so it
falls to zero as the knuckle row turns edge-on to the camera -- which is precisely
the degenerate configuration behind the pitch-plane crossing (T2).
"""

import math

WRIST = 0
INDEX_MCP = 5
PINKY_MCP = 17

# Below this, the palm is close enough to edge-on that the SIGN is untrustworthy.
# Settled by measurement, NOT guessed (spec §0.3): the `non_crossing` sequence gave
# 0 sign flips in 723 frames with edge-on never dropping below 0.353, so 0.15 is
# never reached in normal motion -- but 4.6-8.0% of normal frames fall below 0.60,
# so raising it toward 0.60 would suppress valid gestures for no benefit. Keep 0.15.
EDGE_ON_THRESHOLD = 0.15


def palm_vectors(landmarks):
    """(index_MCP - wrist, pinky_MCP - wrist) in 2D pixel space."""
    wx, wy = landmarks[WRIST][0], landmarks[WRIST][1]
    v1 = (landmarks[INDEX_MCP][0] - wx, landmarks[INDEX_MCP][1] - wy)
    v2 = (landmarks[PINKY_MCP][0] - wx, landmarks[PINKY_MCP][1] - wy)
    return v1, v2


def signed_palm_area(landmarks):
    """2D cross product of the two palm vectors. Its SIGN is the palm/back cue."""
    v1, v2 = palm_vectors(landmarks)
    return v1[0] * v2[1] - v1[1] * v2[0]


def edge_on_measure(landmarks):
    """0..1. How far the palm is from edge-on: 0 = edge-on (sign meaningless),
    1 = knuckle row square to the camera. Equals |sin(theta)| between the palm
    vectors. Same normalisation as AnalyzePerceptionSequences.edge_on()."""
    v1, v2 = palm_vectors(landmarks)
    s = v1[0] * v2[1] - v1[1] * v2[0]
    den = math.hypot(*v1) * math.hypot(*v2)
    return abs(s) / den if den > 1e-9 else 0.0


def is_thumb_outward(landmarks, handedness):
    """True when the hand shows its BACK to the camera (thumb outward) --
    GESTURE_PIPELINE_SPEC.md §13.6, GAME_RULES.md rule 3.

    `handedness` is the MIRRORED/apparent hand, which is what both pipeline paths
    deliver (spec §0.9) -- production via `_mirror_handedness()` after detecting on
    an un-mirrored frame, the debug tool directly from detecting on a mirrored one.
    Passing the raw un-mirrored label here inverts the result: that was the
    production-only bug of 2026-08-01.

    Calibrated live 2026-08-01 and re-verified 2026-08-03 against four
    known-hand/known-facing clips (788/788 frames, spec §0.9).
    """
    cross = signed_palm_area(landmarks)
    if handedness == "Left":
        cross = -cross
    return cross > 0


def is_edge_on(landmarks, threshold=EDGE_ON_THRESHOLD):
    """True when the palm is too close to edge-on for the sign to be trusted.
    DR-2's gate (item 2.2) -- consumers should suppress palm-facing-dependent
    decisions rather than act on a coin-flip sign."""
    return edge_on_measure(landmarks) < threshold


def verify_matches_analyser(landmarks_list, analyser_edge_on, tol=1e-9):
    """Assert this module agrees with AnalyzePerceptionSequences.edge_on().

    Kept here rather than in the test so the invariant sits next to the code it
    constrains. Returns (max_abs_diff, n_compared); raises on disagreement.
    """
    worst = 0.0
    n = 0
    for lm in landmarks_list:
        _s, expected = analyser_edge_on(lm)
        got = edge_on_measure(lm)
        worst = max(worst, abs(got - expected))
        n += 1
    if worst > tol:
        raise AssertionError(
            f"edge_on_measure has DRIFTED from AnalyzePerceptionSequences.edge_on(): "
            f"max abs diff {worst:g} over {n} frames. Every recorded threshold "
            f"(EDGE_ON_THRESHOLD=0.15) is expressed in the analyser's scale, so this "
            f"must stay exact."
        )
    return worst, n
