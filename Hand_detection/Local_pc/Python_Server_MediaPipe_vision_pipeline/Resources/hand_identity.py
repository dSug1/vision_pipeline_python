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

# Constants are expressed in milliseconds and converted using the MEASURED frame
# rate (~24 fps, not the 30 fps the older recorders assumed -- spec §0.3 finding
# N1), so they mean what they say in wall-clock terms.
# TODO (queue item N7): drive this from measured frame timing instead of a
# constant -- every dwell below scales with it, so a different camera silently
# changes every threshold.
ASSUMED_FPS = 24.0

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

TRACK_END_FRAMES = max(2, round(_TRACK_END_MS * ASSUMED_FPS / 1000.0))
LOCK_VOTE_FRAMES = max(2, round(_LOCK_VOTE_MS * ASSUMED_FPS / 1000.0))
POSITION_WINDOW = max(2, round(_POSITION_WINDOW_MS * ASSUMED_FPS / 1000.0))
SWITCH_FRAMES = max(3, round(_SWITCH_MS * ASSUMED_FPS / 1000.0))

# Only confident disagreements count toward a switch. Measured: correct holds
# (transient glitches the lock SHOULD reject) occurred at score 0.52; genuine
# association swaps disagreed at 0.97-0.98. 0.90 sits between them.
SWITCH_MIN_SCORE = 0.90

# Maximum plausible single-frame movement, in palm widths, for a detection to
# still be considered the same hand. Measured frame-to-frame anchor motion in
# normal use peaked at ~58 px against palm widths of ~40-100 px (0.6-1.4 palm
# widths); the recorded Object Jump excursion was 513 px.
MAX_ASSOC_PALM_RATIO = 3.0


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

    def __init__(self, centroid, raw_label, score, pw, log=print):
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

    @property
    def avg(self):
        n = len(self.history)
        return (sum(p[0] for p in self.history) / n,
                sum(p[1] for p in self.history) / n)

    def observe(self, centroid, raw_label, score, pw):
        self.history.append(centroid)
        if len(self.history) > POSITION_WINDOW:
            self.history.pop(0)
        if pw:
            self.palm_width = pw
        self.missing = 0

        if not self.locked:
            self.votes[raw_label] = self.votes.get(raw_label, 0.0) + score
            self.vote_frames += 1
            self.label = max(self.votes, key=self.votes.get)
            if self.vote_frames >= LOCK_VOTE_FRAMES:
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
        return self.mismatch_run >= SWITCH_FRAMES and self.pending_label


class HandIdentityTracker:
    """Assigns stable identities across frames by position, not by label."""

    def __init__(self, log=print):
        self.tracks = []
        self._log = log

    def _free_label(self):
        used = {t.label for t in self.tracks}
        for lab in ("Left", "Right"):
            if lab not in used:
                return lab
        return None

    def update(self, observations):
        """observations: list of (centroid, raw_label, score, palm_width).
        Returns a parallel list of assigned labels."""
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
            tr = HandTrack(cen, start_label, sc, pw, log=self._log)
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
                          f"{SWITCH_FRAMES} confident frames -- exchanged the "
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

        # --- age out tracks that were not seen this frame ---
        for ti, tr in enumerate(self.tracks):
            if ti not in used_tracks:
                tr.missing += 1
        before = len(self.tracks)
        self.tracks = [t for t in self.tracks if t.missing < TRACK_END_FRAMES]
        if len(self.tracks) < before:
            self._log(f"[hands] track ended (absent > {TRACK_END_FRAMES} frames "
                      f"~{_TRACK_END_MS:.0f} ms) -- identity may be re-decided")

        return assigned
