"""M2 -- body schema: per-user bone-length calibration (queue item 1.4).

Pure stdlib, no numpy: the perception layer is reimplemented against the HandState
contract for the web/mobile port, so this transliterates directly.

--------------------------------------------------------------------------------
WHY
--------------------------------------------------------------------------------
MediaPipe emits 21 FREE points -- 63 DOF. A real hand has ~26 DOF with ~20 FIXED
bone lengths. Those constants are the strongest prior available, they are free to
obtain, and they unlock metric depth (M9), foreshortening-based pose, and a
per-frame quality signal.

--------------------------------------------------------------------------------
TWO PROJECT-SPECIFIC AMENDMENTS -- both from measurement, both binding
--------------------------------------------------------------------------------
1. **Gate collection on LOW MOTION** (spec §0.3). Held still this pipeline measures
   bone CV 0.89-1.14%, comfortably inside the <3% target; the 10% figure in the
   original baseline was MOTION-induced, not a sensor floor. So clean samples are
   abundant -- just refuse to collect while the hand is moving. This makes
   calibration easy, and is why `MAX_MOTION_MM` exists.

2. **The raw residual is NOT a per-landmark quality signal** (queue item N2). It
   tracks "the hand is rotating", not "landmark 8 is bad". Fed to M4 unnormalised it
   would down-weight every landmark whenever the hand moves -- useless and actively
   harmful during fast gestures. `pose_normalised_residual()` below exists for that
   reason; **M4 must consume THAT, never `raw_residual()`.**

--------------------------------------------------------------------------------
WHAT IS AND IS NOT CALIBRATED (spec 2f)
--------------------------------------------------------------------------------
Bone *proportions* are observable monocularly and are what this learns. Absolute
hand *size* is NOT recoverable without a known focal length and a reference object,
so `worldLandmarks` units are treated as self-consistent-but-unscaled. Anything
needing true metric scale (M9) must supply its own reference; do not read absolute
millimetres out of this class.
"""

import json
import math
import os

# MediaPipe hand topology. 21 edges (the spec says "20 bones"; the standard
# connection set includes both 0->5 and 0->17 palm edges, and both are rigid and
# useful, so all 21 are kept -- noted so the count difference is not read as a bug).
BONES = (
    (0, 1), (1, 2), (2, 3), (3, 4),            # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),            # index
    (5, 9), (9, 10), (10, 11), (11, 12),       # middle (+ palm 5-9)
    (9, 13), (13, 14), (14, 15), (15, 16),     # ring   (+ palm 9-13)
    (13, 17), (17, 18), (18, 19), (19, 20),    # pinky  (+ palm 13-17)
    (0, 17),                                   # palm outer edge
)

# Bones whose length is dominated by the rigid palm. These are the ones §0.2 found
# already trustworthy (palm rigid to 2.76 mm, inside target) -- used as the
# pose-normalisation reference in `pose_normalised_residual`.
PALM_BONES = ((0, 5), (5, 9), (9, 13), (13, 17), (0, 17))

CALIB_WINDOW = 300          # samples per bone before convergence is even considered
FREEZE_IQR_FRAC = 0.02      # spec: converge when each bone's IQR < 2% of its median
MIN_SAMPLES = 60            # never freeze on fewer than this
# Amendment 1: only collect while the hand is near-still.
#
# ⚠ EXPRESSED AS A FRACTION OF HAND SIZE, DELIBERATELY. The first version used an
# absolute "2.0 mm" -- but MediaPipe's worldLandmarks are in METRES, so the gate
# never fired and every frame (including fast rotation) was accepted for
# calibration. A unit-free threshold cannot fail that way, and ports to the web
# target without carrying a unit assumption.
MAX_MOTION_FRAC = 0.03      # max per-landmark motion, as a fraction of palm width
_REF_BONE = (0, 5)          # wrist -> index MCP: rigid, always visible, good scale ref
DRIFT_ALPHA = 0.001         # spec: slow adaptation, gated on high quality


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    m = n // 2
    return s[m] if n % 2 else 0.5 * (s[m - 1] + s[m])


def _iqr(xs):
    s = sorted(xs)
    n = len(s)
    if n < 4:
        return float("inf")
    return s[(3 * n) // 4] - s[n // 4]


def bone_lengths(world_landmarks):
    """Measured length of every bone this frame."""
    out = {}
    for b in BONES:
        p, c = b
        if p < len(world_landmarks) and c < len(world_landmarks):
            out[b] = _dist(world_landmarks[p], world_landmarks[c])
    return out


class HandModel:
    """A frozen per-user skeleton: one length per bone."""

    def __init__(self, lengths=None, frozen=False):
        self.lengths = dict(lengths or {})
        self.frozen = frozen

    # --- the M4 interface ---------------------------------------------------

    def raw_residual(self, world_landmarks):
        """Per-bone fractional deviation from calibration.

        ⚠ NOT a per-landmark quality signal -- see amendment 2 in the module
        docstring. It reports hand ROTATION as much as landmark error. M4 must use
        `pose_normalised_residual` instead. Exposed because foreshortening itself is
        a SIGNAL (a bone at 60% of its calibrated length is tilted ~53° out of the
        image plane), which is what M9 wants.
        """
        out = {}
        meas = bone_lengths(world_landmarks)
        for b, L in self.lengths.items():
            if b in meas and L > 1e-9:
                out[b] = (meas[b] - L) / L
        return out

    def pose_normalised_residual(self, world_landmarks):
        """Residual with the whole-hand pose effect divided out (queue item N2).

        The palm is rigid and already accurate (2.76 mm, §0.2), so whatever
        foreshortening the palm bones show this frame is a POSE effect, not a
        landmark defect. Dividing each bone's residual by the palm's mean scale
        factor removes the common-mode term, leaving what is specific to that bone.

        THIS is what M4 consumes: it answers "is landmark 8 bad right now?", not
        "is the hand rotating?".
        """
        meas = bone_lengths(world_landmarks)
        # common-mode scale from the rigid palm
        ratios = [meas[b] / self.lengths[b]
                  for b in PALM_BONES
                  if b in meas and self.lengths.get(b, 0) > 1e-9]
        scale = _median(ratios) if ratios else 1.0
        if scale < 1e-6:
            scale = 1.0
        out = {}
        for b, L in self.lengths.items():
            if b in meas and L > 1e-9:
                out[b] = (meas[b] - L * scale) / (L * scale)
        return out

    # --- persistence (spec M0 layout: profiles/<id>.json) -------------------

    def to_dict(self):
        return {"frozen": self.frozen,
                "lengths": {f"{p}-{c}": v for (p, c), v in self.lengths.items()}}

    @staticmethod
    def from_dict(d):
        lengths = {}
        for k, v in (d.get("lengths") or {}).items():
            p, c = k.split("-")
            lengths[(int(p), int(c))] = float(v)
        return HandModel(lengths, bool(d.get("frozen")))

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(path):
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return HandModel.from_dict(json.load(f))


class BoneCalibrator:
    """Collects samples and freezes a HandModel once every bone is stable.

    Robust by construction: running MEDIAN, never mean. Occlusion outliers are
    severe AND one-sided (a hidden fingertip is guessed short, rarely long), so a
    mean would be dragged systematically low.
    """

    def __init__(self, window=CALIB_WINDOW, max_motion_frac=MAX_MOTION_FRAC):
        self.samples = {b: [] for b in BONES}
        self.window = window
        self.max_motion_frac = max_motion_frac
        self.model = None
        self._prev = None
        self.rejected_motion = 0
        self.accepted = 0

    def _motion(self, world_landmarks):
        """Largest per-landmark movement since the previous frame, as a FRACTION of
        hand size. Unit-free by construction -- see MAX_MOTION_FRAC."""
        if self._prev is None:
            return None
        p, c = _REF_BONE
        if p >= len(world_landmarks) or c >= len(world_landmarks):
            return None
        ref = _dist(world_landmarks[p], world_landmarks[c])
        if ref < 1e-9:
            return None
        return max(_dist(a, b) for a, b in zip(world_landmarks, self._prev)) / ref

    def observe(self, world_landmarks, quality=1.0):
        """Feed one frame. Returns True if the sample was used."""
        motion = self._motion(world_landmarks)
        self._prev = list(world_landmarks)

        # Amendment 1: only sample while near-still. Held still the sensor is
        # already inside target, so there is no reason to accept noisy frames.
        if motion is None or motion > self.max_motion_frac or quality < 0.5:
            self.rejected_motion += 1
            return False

        for b, L in bone_lengths(world_landmarks).items():
            s = self.samples[b]
            s.append(L)
            if len(s) > self.window:
                s.pop(0)
        self.accepted += 1
        self._try_freeze()
        return True

    def _try_freeze(self):
        if self.model is not None:
            return
        lengths = {}
        for b, s in self.samples.items():
            if len(s) < MIN_SAMPLES:
                return
            med = _median(s)
            if med <= 1e-9 or _iqr(s) > FREEZE_IQR_FRAC * med:
                return
            lengths[b] = med
        self.model = HandModel(lengths, frozen=True)

    def progress(self):
        """(bones_stable, total_bones, min_samples_so_far) -- for reporting."""
        stable = 0
        least = None
        for b, s in self.samples.items():
            least = len(s) if least is None else min(least, len(s))
            if len(s) >= MIN_SAMPLES:
                med = _median(s)
                if med > 1e-9 and _iqr(s) <= FREEZE_IQR_FRAC * med:
                    stable += 1
        return stable, len(self.samples), (least or 0)

    def adapt(self, world_landmarks, quality=1.0):
        """Slow drift adaptation after freezing, gated on high quality (spec)."""
        if self.model is None or quality < 0.85:
            return
        for b, L in bone_lengths(world_landmarks).items():
            if b in self.model.lengths:
                cur = self.model.lengths[b]
                self.model.lengths[b] = cur + DRIFT_ALPHA * (L - cur)
