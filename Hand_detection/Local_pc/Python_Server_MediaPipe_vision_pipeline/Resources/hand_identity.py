"""Track-level hand identity (DR-1) -- SHARED by production and the debug tool.

Claude/PERCEPTION_LAYER_SPEC.md M5c / §0.4-§0.5.

Deliberately standalone: pure stdlib, no relative imports, no cv2/mediapipe, no
window side effects. That is what lets BOTH consumers use the same code instead
of duplicating it:

    production : Resources/hands_visualizer.py   (server side, wire protocol)
    debug tool : Movement_with_hand_detection/LiveSnapDebug.py

Extracted 2026-08-02 on the owner's instruction -- "I do not want to have a debug
tool which is not in tune with the production." The alternative (copying ~150
lines into the debug tool) was rejected: perception belongs BELOW the HandState
boundary and should be shared, not duplicated, or the two copies drift exactly
the way the thumb-outward sign convention already did once (§13.6.1).

It works on plain (x, y) tuples rather than any landmark structure, because the
two callers hold landmarks in different shapes (dicts of x_px/y_px server-side,
tuples in the debug tool). Callers convert; this module stays shape-agnostic.

--------------------------------------------------------------------------------
WHY IDENTITY MUST BE A TRACK PROPERTY
--------------------------------------------------------------------------------
MediaPipe decides handedness from APPEARANCE (knuckles, creases, shading), not
landmark geometry, so it degrades exactly when the back of the hand shows or
motion blurs. Measured over 4362 recorded frames (spec §0.4): handedness score
falls from 0.981 held-still to 0.941 under fast rotation, and label flips occur
at ~0.663. One physical hand was labelled `Left` on 448 frames and `Right` on 14,
with continuous position across every flip. Separately, BOTH detections carried
the SAME label on 25 frames.

Downstream, cube ownership is keyed by handedness -- so a flipped or duplicated
label either teleports a cube to the wrong hand or makes a hand read as
not-detected and drops it. That is the recorded "Object Jump Correction" bug
(§14.1.4).

THE RULE:
  * Associate detections to tracks by POSITION, never by MediaPipe's label.
  * A track's label is locked after a short weighted vote, then held.
  * A raw-label mismatch FLAGS the track: brief -> hold (transient glitch);
    long AND confident -> switch (the association swapped through a crossing).
  * Identity is re-decided freely when a track genuinely ends.
  * INVARIANT: never emit two hands with the same label.
"""

import math

MIRRORED_HANDEDNESS = {"Left": "Right", "Right": "Left"}

PALM_LANDMARKS = (0, 5, 9, 13, 17)

# Constants are expressed in milliseconds and converted using the frame rate, so
# they mean what they say in wall-clock terms.
#
# ⭐ QUEUE ITEM N7, RESOLVED 2026-08-04: the frame rate is now MEASURED at
# runtime, not assumed. This value survives only as the fallback used before
# enough timing samples exist, and by callers that pass no timestamp.
#
# Why it was promoted from tidiness to CORRECTNESS: the pipeline's frame rate is
# environment-dependent, not fixed (queue N10) -- 24.09-24.14 fps measured in
# daylight versus 15.1-15.77 fps in dim light on the SAME camera and machine,
# with auto-exposure the leading hypothesis. Every dwell below scales with it, so
# at 15.77 fps `SWITCH_MS` silently became ~761 ms instead of 500 -- a 52%
# overshoot in the one parameter §0.5 flagged as most worth getting right, in the
# lighting people actually play in.
FALLBACK_FPS = 24.0
ASSUMED_FPS = FALLBACK_FPS      # retained for callers/tests that reference it

_TRACK_END_MS = 500.0        # hand absent this long -> track ends, identity re-decidable
_LOCK_VOTE_MS = 330.0        # accumulate label votes this long before locking
_POSITION_WINDOW_MS = 415.0  # rolling average used for association

# Confident disagreement lasting this long -> the association swapped.
# ** TUNABLE, and the tuning is a real latency-vs-false-glitch trade-off. **
# Measured on the 7 recorded sessions (spec §0.5):
#     longest run correctly HELD (a transient glitch)   :  7 frames (~292 ms)
#     runs that were genuine association swaps          : 62-225 raw frames
#   LOWER  -> faster correction after a real crossing, but the margin above the
#             7-frame glitch shrinks; at 7 or below, an observed glitch would
#             have caused a FALSE switch (a cube visibly jumping to the wrong
#             hand for no reason).
#   HIGHER -> more margin, and real swaps can still never be missed, at the cost
#             of the wrong label persisting longer after a genuine crossing.
# 12 frames (~500 ms) chosen as the balance. Re-derive from fresh recordings if
# the camera, frame rate or lighting change -- the glitch population sets the
# floor and is blur/lighting dependent.
_SWITCH_MS = 500.0

def _round_half_up(x):
    """Round half AWAY FROM ZERO, matching JavaScript's `Math.round`.

    ⚠ PORTABILITY, and this is not pedantry -- it was caught by the golden
    vectors. Python's built-in `round()` uses BANKER'S rounding (half-to-even):
    `round(6.5)` is 6, `round(7.5)` is 8. JavaScript's `Math.round` always
    rounds half up: 6.5 -> 7. The dwells land exactly on .5 at odd frame rates
    (500 ms x 13 fps = 6.5 frames), so a JS port using `Math.round` would
    silently compute a DIFFERENT dwell from Python at 13, 17, 19... fps -- a
    divergence that would never show up in normal testing and would be
    miserable to find later.

    Fixing the convention here, in the shared code, means the port is a
    transcription. Inputs are always positive here, so the simple form is exact.
    """
    return int(x + 0.5)


def frames_for(ms, fps):
    """Convert a wall-clock dwell to a frame count at a given rate.

    The floors (2, 2, 2, 3) are deliberate and are the reason this is a function
    rather than an expression: at a low enough frame rate a dwell could otherwise
    round to 1 frame, and a 1-frame dwell is not a dwell -- it would make the
    glitch-rejection logic fire on single-frame noise, which is the exact failure
    DR-1 exists to prevent.
    """
    return {
        "track_end": max(2, _round_half_up(_TRACK_END_MS * fps / 1000.0)),
        "lock_vote": max(2, _round_half_up(_LOCK_VOTE_MS * fps / 1000.0)),
        "position_window": max(2, _round_half_up(_POSITION_WINDOW_MS * fps / 1000.0)),
        "switch": max(3, _round_half_up(_SWITCH_MS * fps / 1000.0)),
    }[ms]


# Module-level defaults at the fallback rate. Kept because the fixture tests and
# several analysis scripts import them, and because a tracker that has not yet
# seen two timestamps uses exactly these.
TRACK_END_FRAMES = frames_for("track_end", FALLBACK_FPS)
LOCK_VOTE_FRAMES = frames_for("lock_vote", FALLBACK_FPS)
POSITION_WINDOW = frames_for("position_window", FALLBACK_FPS)
SWITCH_FRAMES = frames_for("switch", FALLBACK_FPS)

# --- measured frame-rate estimation (N7) ---
# Median of a short ring buffer, not a mean: a dropped detection produces a
# double-length interval (2.9% of frames under fast motion, §0.3) and a mean
# would let those drag the estimate. A median ignores them outright.
# ~2 s at 24 fps. Deliberately NOT shorter: the condition being corrected is a
# SUSTAINED lighting-driven rate change (N10 -- minutes, not moments), so the
# estimate should follow that and ignore per-second jitter. Measured at a
# 15-frame window, the unscripted `free_manipulation` takes reported 15.7 fps at
# the end of a session averaging 20.7 -- tracking noise, not the rate, and it
# made the derived dwell swing between 8 and 12 frames within one recording.
_FPS_WINDOW = 45
_MIN_FPS_SAMPLES = 5             # below this, trust the fallback instead
_MIN_INTERVAL_MS = 1.0           # guards against duplicate/zero timestamps
_MAX_INTERVAL_MS = 500.0         # a gap longer than this is a stall, not a frame


class FrameRateEstimator:
    """Running frame-rate estimate from supplied capture timestamps.

    Deliberately driven by CALLER-SUPPLIED timestamps rather than reading the
    clock itself: a replay harness runs far faster than real time, and a tracker
    that sampled wall-clock internally would compute a meaningless rate during
    replay while looking correct in production -- precisely the debug/production
    divergence class this project has been bitten by before.

    ⭐ PORT CONTRACT -- THIS CLASS IS A DESIGNATED WEB/MOBILE PORT UNIT.
    ------------------------------------------------------------------
    The cross-platform target (iOS/Android/Windows, `Specification.md` §12) means
    this logic will be reimplemented, most likely in JavaScript. It is written to
    make that a transcription rather than a redesign, following the precedent of
    `palm_geometry.palm_observability` (numpy-free closed form, verified against
    numpy to 1.6e-11 specifically so the port could be trusted).

    Guarantees this class upholds, and which the port must preserve:

      * **No dependencies at all.** Not numpy, not `math`, not `time` -- only
        list operations, comparison and division. Everything here exists in
        every target language.
      * **No clock access.** The caller supplies the timestamp. In Python that
        is `time.perf_counter() * 1000`; in the browser it is
        `performance.now()`, which is already milliseconds and monotonic. In a
        replay harness it is the recording's own `tCapture`. **The port must not
        substitute `Date.now()`** -- it is wall-clock, not monotonic, and jumps
        on NTP correction.
      * **Milliseconds throughout.** No frame-count arithmetic escapes this
        class; `frames_for()` converts at the boundary.
      * **Deterministic.** The same timestamp sequence yields the same fps and
        the same dwells, with no hidden state, randomness or ordering
        dependence.

    ⚠ **`analysis/verify_frame_rate_estimator.py` holds GOLDEN VECTORS** --
    timestamp sequences with their expected fps and dwell outputs. That file is
    the executable specification for the port: a JavaScript reimplementation is
    correct when it reproduces those numbers, and is not to be trusted until it
    does. Do not change the vectors to match a port; fix the port.

    One translation note: `_intervals.pop(0)` is a list shift. In JS use
    `Array.prototype.shift()`; the window is 45 elements so the O(n) cost is
    irrelevant, and a ring buffer would only obscure the intent.
    """

    def __init__(self, fallback_fps=FALLBACK_FPS):
        self.fallback_fps = fallback_fps
        self._intervals = []
        self._last_ms = None

    def reset(self):
        self._intervals = []
        self._last_ms = None

    def observe(self, now_ms):
        if now_ms is None:
            return
        if self._last_ms is not None:
            dt = now_ms - self._last_ms
            if _MIN_INTERVAL_MS <= dt <= _MAX_INTERVAL_MS:
                self._intervals.append(dt)
                if len(self._intervals) > _FPS_WINDOW:
                    self._intervals.pop(0)
        self._last_ms = now_ms

    @property
    def fps(self):
        if len(self._intervals) < _MIN_FPS_SAMPLES:
            return self.fallback_fps
        s = sorted(self._intervals)
        median = s[len(s) // 2]
        return 1000.0 / median if median > 0 else self.fallback_fps

    @property
    def measured(self):
        """True once the estimate is real rather than the fallback."""
        return len(self._intervals) >= _MIN_FPS_SAMPLES

# Only confident disagreements count toward a switch. Measured: correct holds
# (transient glitches the lock SHOULD reject) occurred at score 0.52; genuine
# association swaps disagreed at 0.97-0.98. 0.90 sits between them.
SWITCH_MIN_SCORE = 0.90

# Maximum plausible single-frame movement, in palm widths, for a detection to
# still be considered the same hand. Measured frame-to-frame anchor motion in
# normal use peaked at ~58 px against palm widths of ~40-100 px (0.6-1.4 palm
# widths); the recorded Object Jump excursion was 513 px.
MAX_ASSOC_PALM_RATIO = 3.0


# ---------------------------------------------------------------------------
# DISPLAY-ONLY anatomical hand name (2026-08-22, owner report)
# ---------------------------------------------------------------------------
# Owner, 2026-08-22, after the 14.3.4.3 mirror fix was confirmed working:
# "on both the sessions, the label 'left' or 'right' hands are inverted".
# Correct, and MEASURED against the ground-truth clips:
#
#     physical RIGHT hand  ->  internal label 'Left'    (751/751 frames)
#     physical LEFT  hand  ->  internal label 'Right'   (200/200 frames)
#
# ⚠ THIS IS PRE-EXISTING, NOT A SIDE EFFECT OF THE MIRROR FIX. Before it,
# detection ran on the raw frame and `_mirror_handedness()` flipped the label;
# after it, detection runs on the mirrored frame and MediaPipe reports the same
# value directly. Both routes display the SAME thing, which is why
# `VerifyChiralityFixture.py` -- whose ground truth literally reads "PHYSICAL
# Right hand -> expected label 'Left' (mirrored convention)" -- passed unchanged
# before AND after.
#
# ⛔⛔ DO NOT "FIX" THIS BY FLIPPING THE INTERNAL LABEL. The internal value is
# load-bearing in four places that are all calibrated to the current convention:
#   1. `palm_geometry.is_thumb_outward()` applies a handedness-dependent
#      chirality correction (`if handedness == "Left": cross = -cross`).
#      Flipping the label inverts that sign -- which IS §13.6.1, the bug that
#      shipped inverted in production and survived an "end-to-end confirmed"
#      claim.
#   2. All 415 recorded sessions store labels in this convention; flipping live
#      would desynchronise every replay harness from the live pipeline.
#   3. `VerifyChiralityFixture.py` encodes it as ground truth.
#   4. Cube ownership and DR-1's track slots key on it (see queue T3).
#
# ⭐ So the label is corrected for DISPLAY ONLY, at the two places a human reads
# it, and the internal convention is left exactly as it is. Defined HERE, in the
# module both the server and `LiveSnapDebug.py` already import, so the two
# cannot drift (rule N6: imported, never copied).
_ANATOMICAL = {"Left": "Right", "Right": "Left"}


def anatomical_name(track_label):
    """The physical hand a track label refers to -- for ON-SCREEN TEXT ONLY.

    `track_label` is the pipeline's internal label ('Left'/'Right'). Returns the
    hand the operator is actually holding up, which is its opposite. ⚠ Never feed
    this back into any rule, filter or ownership key -- see the block above.
    """
    return _ANATOMICAL.get(track_label, track_label)


def palm_centroid(points_xy):
    """Centroid of the rigid palm landmarks. `points_xy` is the full 21-point
    list of (x, y) tuples; returns None if any needed point is missing."""
    pts = []
    for i in PALM_LANDMARKS:
        if i >= len(points_xy):
            return None
        p = points_xy[i]
        if p is None or p[0] is None or p[1] is None:
            return None
        pts.append(p)
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def palm_width(points_xy):
    """Index-MCP to pinky-MCP distance -- the scale reference for association."""
    if len(points_xy) <= 17:
        return None
    a, b = points_xy[5], points_xy[17]
    if a is None or b is None or None in (a[0], a[1], b[0], b[1]):
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


class HandTrack:
    """One persistent hand identity. `label` is provisional until `locked`."""

    def __init__(self, centroid, raw_label, score, pw, log=print, owner=None,
                 track_id=-1):
        # `owner` supplies the CURRENT frame-rate-derived dwells (N7). None means
        # "use the module defaults", which keeps this class usable standalone.
        self.owner = owner
        # ⭐ STABLE IDENTITY (2026-08-22, queue 4.1 / T3). The label is NOT an
        # identity -- it flips, and 113 of 205 spurious cube releases were
        # exactly that flip orphaning a held cube. `track_id` is monotonic per
        # tracker and never reused, so anything keyed on it survives a relabel.
        # ⚠ List POSITION is not an identity either: `self.tracks` is filtered
        # every frame as tracks age out, so indices shift under you.
        self.track_id = track_id
        self.history = [centroid]
        self.votes = {"Left": 0.0, "Right": 0.0}
        self.votes[raw_label] = score
        self.label = raw_label
        self.locked = False
        self.vote_frames = 1
        self.missing = 0
        self.mismatch_run = 0
        self.pending_label = None
        self.palm_width = pw or 60.0
        self._log = log

    def _dwell(self, name, default):
        return getattr(self.owner, name) if self.owner is not None else default

    @property
    def avg(self):
        n = len(self.history)
        return (sum(p[0] for p in self.history) / n,
                sum(p[1] for p in self.history) / n)

    def observe(self, centroid, raw_label, score, pw):
        self.history.append(centroid)
        while len(self.history) > self._dwell("position_window", POSITION_WINDOW):
            self.history.pop(0)
        if pw:
            self.palm_width = pw
        self.missing = 0

        if not self.locked:
            self.votes[raw_label] = self.votes.get(raw_label, 0.0) + score
            self.vote_frames += 1
            self.label = max(self.votes, key=self.votes.get)
            if self.vote_frames >= self._dwell("lock_vote_frames", LOCK_VOTE_FRAMES):
                self.locked = True
                self._log(f"[hands] identity locked: '{self.label}' "
                          f"(votes L={self.votes.get('Left', 0):.1f} "
                          f"R={self.votes.get('Right', 0):.1f})")
            return

        # Locked. Brief disagreement -> hold. Long, CONFIDENT disagreement ->
        # the position association has swapped, so the label must follow.
        if raw_label != self.label:
            if score >= SWITCH_MIN_SCORE:
                self.mismatch_run += 1
            self.pending_label = raw_label
        elif self.mismatch_run:
            self._log(f"[hands] track '{self.label}' agrees again after "
                      f"{self.mismatch_run} confident mismatched frame(s) "
                      f"-- transient glitch rejected, lock held")
            self.mismatch_run = 0
            self.pending_label = None

    @property
    def wants_switch(self):
        return (self.mismatch_run >= self._dwell("switch_frames", SWITCH_FRAMES)
                and self.pending_label)


class HandIdentityTracker:
    """Assigns stable identities across frames by position, not by label."""

    def __init__(self, log=print, fallback_fps=FALLBACK_FPS):
        self.tracks = []
        self._next_track_id = 0
        # Parallel to the `observations` list passed to update(): the stable
        # track id backing each detection, or -1 where none does (a detection
        # that started no track, e.g. the "no free slot" fallback).
        # ⭐ Exposed as an ATTRIBUTE rather than folded into update()'s return so
        # existing callers keep working unchanged -- update() still returns just
        # the labels (analysis harnesses depend on that).
        self.last_track_ids = []
        self._log = log
        self.rate = FrameRateEstimator(fallback_fps)
        self._logged_fps = None

    # --- N7: dwells derived from the MEASURED rate, re-evaluated every frame ---
    @property
    def fps(self):
        return self.rate.fps

    @property
    def track_end_frames(self):
        return frames_for("track_end", self.fps)

    @property
    def lock_vote_frames(self):
        return frames_for("lock_vote", self.fps)

    @property
    def position_window(self):
        return frames_for("position_window", self.fps)

    @property
    def switch_frames(self):
        return frames_for("switch", self.fps)

    def _free_label(self):
        used = {t.label for t in self.tracks}
        for lab in ("Left", "Right"):
            if lab not in used:
                return lab
        return None

    def update(self, observations, now_ms=None):
        """observations: list of (centroid, raw_label, score, palm_width).
        now_ms: capture timestamp in ms. OPTIONAL -- omitting it keeps the
                pre-N7 behaviour exactly (dwells at FALLBACK_FPS), so existing
                callers are unaffected until they choose to pass it.
        Returns a parallel list of assigned labels."""
        self.rate.observe(now_ms)
        if self.rate.measured:
            f = round(self.fps, 1)
            # Log only on a material change, so this never becomes per-frame spam.
            if self._logged_fps is None or abs(f - self._logged_fps) >= 2.0:
                self._logged_fps = f
                self._log(f"[hands] measured {f} fps -> dwells: "
                          f"lock {self.lock_vote_frames}, switch "
                          f"{self.switch_frames}, track-end {self.track_end_frames} "
                          f"frames (N7)")
        assigned = [None] * len(observations)
        used_tracks = set()
        obs_to_track = {}

        # --- associate by position, nearest first, greedily ---
        pairs = []
        for oi, (cen, _lab, _sc, pw) in enumerate(observations):
            for ti, tr in enumerate(self.tracks):
                a = tr.avg
                dist = math.hypot(cen[0] - a[0], cen[1] - a[1])
                limit = max(tr.palm_width, pw or 0, 30.0) * MAX_ASSOC_PALM_RATIO
                if dist <= limit:
                    pairs.append((dist, oi, ti))
        pairs.sort()

        for _dist, oi, ti in pairs:
            if assigned[oi] is not None or ti in used_tracks:
                continue
            cen, lab, sc, pw = observations[oi]
            self.tracks[ti].observe(cen, lab, sc, pw)
            assigned[oi] = self.tracks[ti].label
            used_tracks.add(ti)
            obs_to_track[oi] = ti

        # --- unassociated detections start new tracks ---
        for oi, (cen, lab, sc, pw) in enumerate(observations):
            if assigned[oi] is not None:
                continue
            if len(self.tracks) >= 2:
                # No slot free: emit the raw label; the invariant below repairs
                # any collision this causes.
                assigned[oi] = lab
                continue
            free = self._free_label()
            # With two hands tracked they are almost certainly one of each, so a
            # new track takes the label the existing track is not using.
            start_label = free if (free and self.tracks) else lab
            tr = HandTrack(cen, start_label, sc, pw, log=self._log, owner=self,
                           track_id=self._next_track_id)
            self._next_track_id += 1
            if free and self.tracks:
                tr.locked = True
                self._log(f"[hands] identity locked: '{start_label}' "
                          f"(assigned as the complement of the existing track)")
            self.tracks.append(tr)
            assigned[oi] = tr.label
            used_tracks.add(len(self.tracks) - 1)
            obs_to_track[oi] = len(self.tracks) - 1

        # --- resolve confirmed switches (association swapped through a crossing)
        # Done at tracker level, never per-track, so two tracks can never end up
        # holding the same label mid-swap.
        switching = [t for t in self.tracks if t.wants_switch]
        if switching:
            if len(switching) == 2:
                a, b = switching
                a.label, b.label = b.label, a.label
                self._log(f"[hands] association swap confirmed after "
                          f"{self.switch_frames} confident frames -- exchanged the "
                          f"two track labels ('{b.label}' <-> '{a.label}')")
            else:
                tr = switching[0]
                new = tr.pending_label
                clash = next((t for t in self.tracks
                              if t is not tr and t.label == new), None)
                old = tr.label
                tr.label = new
                if clash:
                    clash.label = old
                    self._log(f"[hands] switch confirmed: '{old}' -> '{new}'; "
                              f"the other track takes '{old}' to avoid a duplicate")
                else:
                    self._log(f"[hands] switch confirmed after {SWITCH_FRAMES} "
                              f"confident frames: '{old}' -> '{new}'")
            for t in switching:
                t.mismatch_run = 0
                t.pending_label = None
            # Re-emit this frame's labels using the corrected assignment, so the
            # switch takes effect immediately rather than one frame late.
            for oi, ti in obs_to_track.items():
                assigned[oi] = self.tracks[ti].label

        # --- INVARIANT: never emit two hands with the same label ---
        # Enforced explicitly rather than left as an emergent property. Found by
        # testing (2026-08-02): the "no free slot" fallback above could emit a
        # raw label that collided with a track-backed one -- reachable when a
        # detection jumps beyond the association limit while both slots are
        # full. A track-backed assignment always wins; the other is flipped.
        if len(assigned) == 2 and assigned[0] == assigned[1]:
            loser = 1 if 0 in obs_to_track else 0
            if loser in obs_to_track and (1 - loser) not in obs_to_track:
                loser = 1 - loser          # keep the track-backed one
            assigned[loser] = MIRRORED_HANDEDNESS.get(assigned[loser],
                                                      assigned[loser])
            self._log(f"[hands] duplicate label would have been emitted; "
                      f"flipped the non-track-backed detection to "
                      f"'{assigned[loser]}'")

        # --- publish the stable id backing each observation (4.1 / T3) ---
        # ⚠ MUST happen BEFORE the age-out below. `obs_to_track` holds INDICES
        # into `self.tracks`, and the age-out rebuilds that list -- every index
        # after a removed track shifts by one, so reading them afterwards
        # silently returns the wrong track's id. (Caught while writing this.)
        self.last_track_ids = [-1] * len(observations)
        for oi, ti in obs_to_track.items():
            if 0 <= ti < len(self.tracks):
                self.last_track_ids[oi] = self.tracks[ti].track_id

        # --- age out tracks that were not seen this frame ---
        for ti, tr in enumerate(self.tracks):
            if ti not in used_tracks:
                tr.missing += 1
        before = len(self.tracks)
        track_end = self.track_end_frames
        self.tracks = [t for t in self.tracks if t.missing < track_end]
        if len(self.tracks) < before:
            self._log(f"[hands] track ended (absent > {track_end} frames "
                      f"~{_TRACK_END_MS:.0f} ms at {self.fps:.1f} fps) "
                      f"-- identity may be re-decided")

        return assigned
