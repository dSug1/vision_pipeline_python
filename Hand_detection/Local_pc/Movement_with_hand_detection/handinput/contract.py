"""`HandState` v2 -- the serialisable, language-neutral state contract.

⭐ THE CONTRACT IS NOT NEW AND IS NOT MINE. It is `PERCEPTION_LAYER_SPEC.md` §2,
written 2026-08-02 and frozen as *"the integration point"*, in JS-object notation
because it was always meant to cross languages ("Keep it serialisable and free of
engine types -- a future web/mobile rebuild reimplements against this"). This
module implements the SUBSET this pipeline actually produces, under the spec's own
field names, and says out loud which fields are absent and why.

⛔⛔ NOTHING IS FABRICATED TO FILL THE SCHEMA. A field that has no producer is
ABSENT, never estimated into existence -- a plausible number in a contract slot is
indistinguishable from a measured one to every consumer downstream, and this
project has paid for that class of error more than once. The table below is the
whole story; `analysis/verify_handinput.py` §1 asserts it stays true.

| spec field                     | here                        | why |
|--------------------------------|-----------------------------|-----|
| `schema`                       | ✅ 2                        | |
| `tCapture`                     | ✅ `tCapture`               | the frame's own clock, never sampled here |
| `present`                      | ✅                          | |
| `handedness`                   | ✅ (the SLOT name)          | ⚠ see the note below -- this is a slot, not a truth |
| `trackId`                      | ✅                          | DR-1's stable identity, on the wire since 4.1 |
| `palm.orientation`             | ✅ quaternion, camera frame | Horn's fit (§16.15) |
| `palm.position` (metric)       | ⛔ ABSENT                   | the pipeline works in PIXELS + a separate metric depth; a metric palm position would be a new estimator, not a rename |
| `palm.positionPx`              | ✅ EXTENSION                | what actually drives the game today |
| `palm.linearVelocity` / `angularVelocity` / `covTrace` / `orientationSigma` | ⛔ ABSENT | no producer. 2.3's five null attempts are why there is no covariance here |
| `joints` / `synergyCoeffs` / `landmarksCanonical` | ⛔ ABSENT | Phase B / M3, parked |
| `landmarksScreen`              | ✅ optional (`include_landmarks`) | debug overlay only, per the spec's own note; OFF by default because it is 90% of the bytes |
| `aperture` / `apertureRate`    | ⛔ ABSENT                   | pinch is archived (2026-08-01) |
| `palmFacing` (-1..1 signed cos)| ⛔ ABSENT                   | ⚠⚠ we produce a BOOL (`thumbOutward`), not a signed cosine. Emitting the bool under this name would silently redefine a field of the contract |
| `thumbOutward`                 | ✅ EXTENSION                | the palm/back cue rule 3 actually reads |
| `edgeOnMeasure`                | ✅                          | M5a, `palm_geometry.edge_on_measure` |
| `depth` / `depthRate`          | ✅ `depth` / ⛔ no rate     | 4.2's `HandDepthTracker` |
| `quality.orientationValid`     | ✅                          | DR-2's freeze |
| `quality.depthValid`           | ✅                          | 4.2; `False` means HELD, not measured |
| `quality.trackingState`        | ✅                          | D1 |
| `quality.framesSinceMeasurement`| ✅                         | D1's miss counter |
| `quality.chiralityConfirmed`   | ✅ EXTENSION                | U8, added 2026-08-22 -- AFTER the contract was frozen. Recorded here as an extension rather than quietly slipped into `quality` as though it had always been there |
| `quality.overall` / `occlusionLevel` / `motionBlur` | ⛔ ABSENT | no producer (M4 unbuilt) |
| `latencyBudgetMs` / `tPredicted` | ⛔ ABSENT                 | M7; the project measures latency, it does not publish a budget |

⚠⚠ `handedness` IS A SLOT NAME, NOT A CLAIM ABOUT WHICH HAND THIS IS. MediaPipe's
label is measured **wrong 10.8% of the time at 0.94 confidence**
(`HANDEDNESS_LABEL_DEFECT.md`), and nothing chirality-sensitive in this pipeline
reads it any more -- U7 replaced that with geometry. It is published because
ownership and every per-hand dict are still keyed on it, and a consumer needs the
key. ⛔ **A consumer must not treat it as chirality.** `thumbOutward` is the
palm/back cue; `trackId` is identity.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

SCHEMA = 2

# The three tracking states, re-exported so a consumer of this package never has
# to import the estimator module to compare against them. ⚠ IMPORTED, NOT COPIED
# (N6): `hand_state` owns these strings.
try:                                         # in-repo layout
    from Resources import hand_state as _HS
except ImportError:                          # standalone export, or Resources on sys.path
    import hand_state as _HS

TRACKING = _HS.TRACKING
BRIDGING = _HS.BRIDGING
SUSTAINED_LOST = _HS.SUSTAINED_LOST


@dataclass
class HandObservation:
    """One hand, one frame: everything the input layer is told about it.

    ⭐ THIS IS THE ADAPTER SEAM. A host fills it from whatever it has -- this
    project's two tools fill it from their per-hand pass (so the input system
    reports what RAN); a host with only landmarks would fill it by calling the
    estimator modules. Either way everything above this struct is identical,
    which is what makes the actions portable.

    ⚠ Every optional field defaults to "absent" rather than to a neutral value.
    `depth_m=None` means *no depth was supplied*; `depth_valid=False` means *a
    depth exists but is being HELD rather than measured*. Collapsing those two
    into one would erase 4.2's DECISION 1 (no snapping while depth is frozen).
    """

    slot: str                                   # "Left" | "Right" -- a KEY, not chirality
    present: bool = False                       # landmarks arrived this frame
    tracking_state: str = SUSTAINED_LOST        # D1: TRACKING | BRIDGING | SUSTAINED_LOST
    track_id: int = -1                          # DR-1 identity; -1 = none this frame
    frames_since_measurement: int = 0
    reacquired_after_ms: float = 0.0

    position_px: Optional[Tuple[float, float]] = None      # palm centre, mirrored frame px
    depth_m: Optional[float] = None
    depth_valid: bool = False
    orientation: Optional[Tuple[float, float, float, float]] = None   # (w,x,y,z), camera frame

    thumb_outward: bool = False
    chirality_confirmed: bool = False
    orientation_valid: bool = False
    edge_on: Optional[float] = None
    snap_allowed: bool = False                  # rule 3's ARMED exception (see actions.grab_ready)

    landmarks_px: Optional[Sequence[Sequence[float]]] = None
    world_landmarks: Optional[Sequence[Sequence[float]]] = None

    @property
    def holds_track(self) -> bool:
        """⭐ The same test the game releases an object on (`hand_state`'s own
        property): TRACKING or BRIDGING. A consumer that wants "is this hand
        still there" wants THIS, not `present` -- `present` is False during D2's
        150 ms coast, when the hand is deliberately still considered held."""
        return self.tracking_state != SUSTAINED_LOST


@dataclass
class HandFrame:
    """One pumped frame: when, what resolution, and the hands in it.

    ⚠ `time_ms` is the CAPTURE clock supplied by the host, never sampled here --
    N7's rule, and the reason every harness can replay a recording faster than
    real time and still get identical output.
    """

    time_ms: float
    hands: List[HandObservation] = field(default_factory=list)
    frame_size: Optional[Tuple[int, int]] = None

    def hand(self, slot: str) -> Optional[HandObservation]:
        for h in self.hands:
            if h.slot == slot:
                return h
        return None


def hand_state(obs: HandObservation, time_ms: float,
               include_landmarks: bool = False) -> Dict:
    """`HandState` v2 for one hand, as plain JSON-serialisable data.

    ⭐ Plain dicts and lists on purpose: this crosses a socket, a file and a
    language boundary. No engine types, no tuples-that-mean-something, no
    classes a port has to mirror.
    """
    st = {
        "schema": SCHEMA,
        "tCapture": time_ms,
        "present": bool(obs.present),
        "handedness": obs.slot,
        "trackId": int(obs.track_id),
        "palm": {
            "positionPx": list(obs.position_px) if obs.position_px is not None else None,
            "orientation": list(obs.orientation) if obs.orientation is not None else None,
        },
        "thumbOutward": bool(obs.thumb_outward),
        "edgeOnMeasure": obs.edge_on,
        "depth": obs.depth_m,
        "quality": {
            "orientationValid": bool(obs.orientation_valid),
            "depthValid": bool(obs.depth_valid),
            "trackingState": obs.tracking_state,
            "framesSinceMeasurement": int(obs.frames_since_measurement),
            "chiralityConfirmed": bool(obs.chirality_confirmed),
        },
    }
    if include_landmarks and obs.landmarks_px is not None:
        st["landmarksScreen"] = [list(p) for p in obs.landmarks_px]
    return st
