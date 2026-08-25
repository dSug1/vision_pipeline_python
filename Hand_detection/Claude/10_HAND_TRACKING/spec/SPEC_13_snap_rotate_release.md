# SNAP / TRANSLATE / ROTATE / RELEASE — §13

> **live · the current gesture set's design, build record and the mesh-generic renderer**
> **SOURCE** · `GESTURE_PIPELINE_SPEC.md` §13–§13.8 — extracted verbatim, not edited

⭐ The pivot away from pinch, and everything that shipped after it. ⚠ §13.6.1 is
the production-only inversion that passed an "end-to-end confirmed" claim while
shipped inverted — the origin of the *automated green is not sufficient* rule.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/GESTURE_PIPELINE_SPEC.md lines 2675-3463
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 13. Pinch archived (2026-08-01); pivot to snap / open-palm rotate / closed-fist release

> **See `Claude/GAME_RULES.md` for the plain-language rules inventory** —
> this section documents design/rationale/build history; that file lists
> only the confirmed rules themselves, updated every time a new one is
> added. Check both: this section for *why*, `GAME_RULES.md` for *what*.

### 13.1 Stage 4 live-validation result — why pinch is being archived, not just re-tuned again

Live-tested via `debug.bat` against the final pipeline state from §12.6
(200ms window, `mlp/raw_plus_handcrafted_plus_articulation`, re-tuned event
layer, 77.7% avg priority-orientation recall on recorded data). Direct,
observed result:

- **False positives: rare** — consistent with the recorded rotation-FP
  numbers staying low throughout this arc.
- **False negatives (missed pinches/releases): frequent**, and
  **noticeably worse off the `front` orientation** — consistent with the
  recorded numbers (`palmin`=69%, weaker than `front`=86%), but the live
  *feel* of a missed grab/release is a harder failure than the aggregate
  percentage suggests, since a game interaction needs each individual
  attempt to register, not just a good hit-rate averaged over many.
- **A small but perceptible detection lag** between the real gesture and
  the reported event — small in absolute terms, but the kind of latency
  that measurably degrades direct-manipulation UX (well-established in
  HCI latency literature: even sub-100ms delays are detectable and
  degrade a sense of direct control). This is a structural property of
  the current design (the event tracker needs a `window_frames`-sized
  lookback of confidence/ratio history before it can confirm an
  onset/offset — see `Resources/event_layer.py`), not a bug fixable by
  more tuning.

**Decision**: archive the pinch classifier (all code, corpus, and trained
weights kept, not deleted — genuinely reusable if pinch is revisited
later) and pivot to a simpler gesture set that doesn't share pinch's core
difficulty (discriminating a *fine, low-amplitude, easily-occluded*
finger-contact signal from incidental motion). This is consistent with
§12.7's lesson #8: a bar that turns out to be structurally hard to clear
is a legitimate reason to change strategy, not just push harder on the
same one.

### 13.2 State-of-the-art check for the replacement gesture set (2026-08-01)

Per the standing "search literature proactively" discipline
(`feedback_proactive_literature_search` memory), checked three things
before committing to the new design:

**1. MediaPipe already ships pretrained `Open_Palm`/`Closed_Fist`
classifiers.** MediaPipe Tasks' **Gesture Recognizer** (distinct from the
Hand Landmarker this project already uses) outputs one of 7 built-in
gesture labels per detected hand: `Closed_Fist`, `Open_Palm`,
`Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory`, `ILoveYou` (plus
`Unknown`), trained on ~30K real-world images plus rendered synthetic hand
models. **This means open-palm and closed-fist detection may not need
this document's Stage 1-3 custom-training pipeline at all** — a
significant simplification opportunity, and consistent with the intuition
that these are coarse, high-amplitude poses (a fully open hand vs. a
fully closed fist), structurally easier to discriminate than pinch's fine
near-contact measurement. **Still subject to this project's own
hard-won Stage 4 discipline**: try the built-in recognizer, live-verify
it (per §12.7 lesson #6 — don't trust a claim, even Google's own, without
checking it against this project's actual camera/lighting/hand setup),
and only fall back to a custom-trained classifier (reusing
`RecordSession.py`/`train_pinch_classifier.py`'s infrastructure,
generalized past pinch-specific label parsing) if the built-in one proves
insufficient live. [Gesture recognition task guide — MediaPipe / Google AI
Edge](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer).

**2. Proximity-based "snap" grabbing is an established, validated VR/HCI
interaction technique**, not a simplification that sacrifices UX quality.
Literature on hand-tracking object manipulation in VR describes the
"virtual hand technique" with pose-snapping as increasing presence and
usability, and proximity/psychological-closeness cues as reducing
interaction demand versus more indirect techniques (e.g. raycasting) —
directly relevant since this project's UX goal is the same "reach out and
grab" interaction. This validates the "snap when hand position is close
to the object" trigger as a reasonable, literature-backed design, not an
ad-hoc shortcut. [Controller-Free Hand Tracking for Grab-and-Place Tasks
in Immersive Virtual Reality](https://www.researchgate.net/publication/346966176_Controller-Free_Hand_Tracking_for_Grab-and-Place_Tasks_in_Immersive_Virtual_Reality_Design_Elements_and_Their_Empirical_Study),
[Evaluating Hand-tracking Interaction for Performing Motor-tasks in VR
Learning Environments](https://www.researchgate.net/publication/352866232_Evaluating_Hand-tracking_Interaction_for_Performing_Motor-tasks_in_VR_Learning_Environments).

**3. Quaternion-based rotation tracking (already the existing design —
`PART_ONE.md` §2, `Specification.md` §7.5) is confirmed correct and
doesn't need to change.** Orientation-control and robotics/graphics
literature consistently confirms quaternions avoid gimbal lock (a
property of Euler-angle decomposition specifically, not of rotation
itself) and are the standard representation for this exact problem —
nothing found that changes or improves on the orthonormal-frame-from-
landmarks → quaternion → slerp approach already specified. [A quaternionic
approach to teaching 3D rotations and the resolution of gimbal
lock](https://arxiv.org/pdf/2511.04452), [Quaternion Rotation in 3D: A
Solution to Gimbal Lock](https://medium.com/@ratwolf/quaternion-3d-rotation-32a3de61a373).

**4. MediaPipe's monocular depth (`world_landmarks` `z`) is
literature-confirmed unreliable for absolute positioning.** Directly
relevant to "how to measure hand position in the camera-view direction":
validation literature explicitly notes MediaPipe Hands' positional
landmarks are "not suitable for augmented or mixed reality applications"
in terms of depth accuracy for monocular setups — confirming
`PART_ONE.md` §2's existing decision (depth proxy via apparent hand span,
not raw `z`, and no Z-axis translation) was already correct, not a
compromise to revisit. [Hand tracking for clinical applications:
validation of the Google MediaPipe Hand (GMH) and the depth-enhanced
GMH-D frameworks](https://arxiv.org/pdf/2308.01088).

### 13.3 New gesture design: snap / translate / open-palm rotate / closed-fist release

Replaces pinch as the primary manipulation gesture. Reuses
`PART_ONE.md` §2's already-correct architecture decisions (sticky grab,
shared-registry arbitration, image-space translation, depth-proxy-not-
raw-z, quaternion rotation) — only the **trigger conditions** change, not
the underlying object-manipulation architecture.

- **Hand position** (new concept, replaces "pinch midpoint" throughout):
  the palm-center point — centroid of `wrist(0)` + the four non-thumb
  MCP joints (`index_MCP(5)`, `middle_MCP(9)`, `ring_MCP(13)`,
  `pinky_MCP(17)`). A standard palm-center approximation, more stable
  than the wrist alone (which is offset from the palm) or any single MCP
  (asymmetric). Used in **image-space X/Y** for translation, per §13.2
  point 4 above (no Z-axis translation, matching the existing
  depth-proxy-only decision).
- **Snap (acquisition)**: pure proximity trigger — no pose/gesture
  precondition. When a hand's position enters grab-radius of an unowned
  object, snap it (claim in the same shared-registry arbitration scheme
  `PART_ONE.md` §2 already specifies for pinch — reused unchanged, just
  triggered by proximity instead of a pinch rising-edge).
  - Snap should probably be *inert* if that hand is currently
    closed-fist (so nothing weird happens if a hand loitering in a fist
    passes near an object without intending to grab) — worth deciding as
    that step is built, not blocking design now.
- **Translate**: while snapped, object position = mapped(hand position),
  X/Y only — identical mechanism to the old pinch-midpoint version, new
  input signal.
- **Rotate**: while snapped **and** the hand is classified `Open_Palm`,
  track hand orientation via the existing quaternion design (`PART_ONE.md`
  §2/§7.5) and slerp the object's orientation toward it. Gating rotation
  on `Open_Palm` specifically (rather than applying it whenever snapped)
  avoids rotation jitter/noise while the hand is transitioning through
  other shapes (e.g. mid-way into closing a fist) — **this gating choice
  is a design inference, not explicitly stated by direction; confirm or
  adjust once live-tested.**
- **Un-snap (release)**: `Closed_Fist` detected on a hand currently
  holding a snapped object → release: clear ownership, freeze object at
  last position, hand returns to idle. Same freeze-in-place semantics
  `PART_ONE.md` §2 already specifies for pinch release.
- **Both hands can each independently snap/translate/rotate/release their
  own object** — no fixed hand-to-object pairing, same "either hand, any
  unowned object" arbitration already designed for pinch.

### 13.4 Open questions, to resolve empirically once building starts (not blocking design)

- Exact grab-radius value (likely scaled to object size — same open item
  `PART_ONE.md` §5 already flagged for pinch, unresolved, still open).
- ~~Whether `Open_Palm`/`Closed_Fist` from MediaPipe's built-in Gesture
  Recognizer are reliable enough live~~ — **checked and answered, see
  §13.5: no, reverted.**
- ~~Whether snap should be blocked while closed-fist (see §13.3's inert-fist
  note)~~ — **moot (2026-08-01, later conversation): open-palm/closed-fist
  detection (row 2) is now PARKED, not being actively pursued.** The
  mechanism was built and worked once, but was reverted along with the
  Gesture Recognizer integration (§13.5); revisit only if row 2 is
  explicitly un-parked later.
- ~~Whether rotation should be gated on `Open_Palm` specifically~~ —
  **resolved (2026-08-01, later conversation): rotation stays permanently
  ungated**, not just pending a working open-palm signal — row 2 being
  parked makes this the settled answer, not a temporary gap.
- ~~Depth (Z-axis) translation and/or the old depth-proxy scale/color
  effect~~ — **superseded (2026-08-01, later conversation).** Depth-proxy
  scale/color (`PART_ONE.md` §2's last bullet, row 6 of the matrix) stays
  dropped, but Z-axis translation itself is no longer just "not mentioned"
  — it has a confirmed design now, matrix row 9, full detail §14.3.

### 13.5 Build progress (2026-08-01) — proximity snap/translate live-verified; MediaPipe's built-in Closed_Fist reverted

**Phase A (hand position, proximity snap, translation, tracking-loss
release) built and live-verified.** New combined debug tool
`LiveSnapDebug.py`/`debug_snap.bat` (temporary, single-window: video +
hand landmarks + a semi-transparent cube overlay in one OpenCV window,
replacing the old troubleshooting need for the depth-proxy color effect —
directly requested, and confirms translation visually against the real
hand position without needing that old technique). Production code
(`Resources/HandsTriggeredActions.py`, `Resources/CubeWindow.py`) updated
in parallel with matching logic.

**A same-frame ordering bug was found live and fixed**: releasing a cube
(tracking lost) and re-snapping it (the other hand's check) happened in
one combined per-hand pass, so a cube could instantly "jump" to the other
hand the instant one hand disappeared, whenever the other hand was
already within grab radius — the release and the re-snap were two steps
of the same tick with no ordering guarantee against each other. Fixed:
split into two passes (release everyone who needs releasing, across both
hands, *then* snap/translate), and any cube released this frame is
excluded from this frame's snap pass — a cube can only be re-claimed
starting the next frame at the earliest, never the same tick as its
release. Applied identically in both the production module and the debug
tool (kept in sync by hand, documented in both files' docstrings).

**Phase B (`Open_Palm`/`Closed_Fist` via MediaPipe's built-in Gesture
Recognizer) tried, live-tested, and reverted.** Downloaded
`gesture_recognizer.task` (Google's official MediaPipe model repository,
`storage.googleapis.com/mediapipe-models/gesture_recognizer/...`) and
wired it into `LiveSnapDebug.py`, replacing `HandLandmarker` (the
Recognizer conveniently returns gestures + both landmark coordinate types
in one call). Wired `Closed_Fist` to block snap and to trigger release,
per §13.3/§13.4's confirmed design. **Live result: closed-fist detection
was unreliable across different hand positions/orientations — a lot of
missed fist closures.** This is exactly the failure mode §13.2 flagged as
a risk ("still subject to Stage 4 discipline... don't trust a claim
without checking it") — the built-in classifier is evidently tuned to a
narrow set of canonical poses, not usable as-is for this project's
purpose (the hand needs to be trackable as closed-fist across the same
range of positions/orientations pinch needed, not just head-on).
**Decision: revert the Gesture Recognizer integration** (both files back
to `HandLandmarker`, bug fix retained) **but keep `gesture_recognizer.task`
on disk** — its `Thumb_Up` class may be useful for a later, different
game interaction, unrelated to this open-palm/closed-fist need.

**Not yet decided**: the replacement approach for `Open_Palm`/
`Closed_Fist` detection. Candidates, not yet evaluated: (a) a simple
geometric heuristic reusing `features.py`'s existing finger-curl-angle
functions (`curl_worst_deg` etc., already built for pinch/fist
discrimination in the archived corpus) — plausible since fist/open-palm
are coarse, large-amplitude poses that a hand-crafted rule might
discriminate robustly across orientations without needing MediaPipe's
canonical-pose-biased classifier; (b) a custom-trained classifier via
this document's own Stage 1-3 pipeline (proven to work, but the heavier
option, and pinch's own difficulty was in a much finer-grained
measurement than fist/open-palm need). Evaluate (a) first — cheaper to
try, and directly matches this project's literature-grounded intuition
that these are structurally easier poses than pinch, only unreliable in
MediaPipe's *specific* pretrained classifier, not necessarily inherently
hard to detect geometrically.

**PARKED (2026-08-01, later conversation)**: `Open_Palm`/`Closed_Fist`
detection (matrix row 2) is not intended to be pursued for the moment —
neither candidate (a) nor (b) above is being evaluated now. This is a
deprioritization, not a rejection of either candidate's merit; revisit if
explicitly requested again. Its two former dependents have already moved
on without it: rotation (row 7) stays permanently ungated by design;
release (row 4) now relies on the hand-open-quick-release gesture (§14.2)
as its sole deliberate trigger instead of `Closed_Fist`.

### 13.6 Thumb-outward snap restriction (2026-08-01) — new rule, built and live-verified

Direct request, added to the current (Phase A) snap/translate build: a
hand should not be able to snap an object while oriented thumb-outward
(back of hand facing the camera), with a specific exception for
continuity across a release/re-grab in that same orientation. Full rule
text: `Claude/GAME_RULES.md`.

**Detection approach**: a purely 2D geometric signal, no wire-protocol or
model changes needed — the sign of the 2D cross product of
`(index_MCP - wrist) × (pinky_MCP - wrist)` in the already-available
mirrored pixel-space landmarks, mirrored again per handedness for a
consistent sign across both hands (their landmark geometry is chirally
opposite). **Calibrated live before being trusted** (per §13.5's own
lesson, not repeating the Closed_Fist mistake): a calibration-only build
showed the raw sign/a tentative "A"/"B" label on screen, the operator
showed palm then back of hand for both hands, and confirmed the mapping
(positive, mirrored-for-Left = thumb-outward) before the label was wired
into any gating logic.

**State machine**: two bits of per-hand state — `last_known_thumb_outward`
(the most recent orientation reading while the hand WAS detected, persists
through frames where it's lost, so a tracking-loss release still has an
orientation to record) and `thumb_outward_snap_allowed` (the armed/
disarmed exception: armed on release with whatever orientation held at
that moment, disarmed the instant the hand is next seen thumb-inward).
Built and live-verified in both `LiveSnapDebug.py` and
`Resources/HandsTriggeredActions.py` (kept in sync), confirmed working
end-to-end (block-from-neutral, allow-immediately-after-same-orientation-
release, re-block-after-showing-thumb-inward) by the operator, 2026-08-01.

### 13.6.1 Correction (2026-08-01, later conversation): production's thumb-outward was actually INVERTED — root-caused and fixed

**The "confirmed working end-to-end" claim above was wrong for
production specifically**, discovered live: "in the production pipeline,
it seems you inverted the logic for the grab: I can grab only if the
hands are with the thumbs facing outwards: this is the opposite of the
debug pipeline where rightfully the grab was done when the thumbs were
facing inwards." The `_is_thumb_outward` formula itself was byte-for-byte
identical in both files (ruled out first, not assumed) — the actual cause
was upstream, in the wire protocol.

**Root cause, confirmed by reading the code (not guessed)**:
`VisionPipeline.py` runs MediaPipe detection on the RAW, un-mirrored
camera frame (no `cv2.flip` anywhere in that file), then mirrors the
pixel/world landmark COORDINATES afterward for display consistency
(`remap_keypoints`/`remap_world_keypoints`, `invert_x=True`). But
MediaPipe's own Left/Right handedness classification assumes an
already-mirrored ("selfie") input by convention — fed an un-mirrored
frame, it reports the TRUE anatomical hand, the opposite of what the
mirrored display shows. `hands_visualizer.py` took that raw handedness
label with no correction (`"handedness": handedness[0].category_name`).
Every OTHER hand behavior (snap, translate, rotate, release) is
handedness-symmetric and was unaffected — `_is_thumb_outward` is the ONE
place with an explicit `if handedness == "Left": cross = -cross`
chirality correction, so it was the only visible symptom.
`LiveSnapDebug.py` never had this problem because it flips the frame
BEFORE detection, so MediaPipe's handedness comes out already
display-consistent — this is exactly the same class of unverified
mirroring risk `remap_world_keypoints`'s own docstring already flagged
for `world_landmarks` ("has NOT been live-verified yet... confirm the
rotation's sign/axis feel live"), just materializing on the 2D pixel/
handedness side instead, and for a different consumer (thumb-outward, not
rotation).

**Fix**: `hands_visualizer.py` gained `_mirror_handedness()`, applied at
the single source point where handedness first enters the pipeline (both
the on-screen debug label and the `"handedness"` field every downstream
packet — "hands" AND "hands_world" — reads from), rather than patching
`_is_thumb_outward` or any other individual consumer. Verified by reading
the full call chain (`VisionPipeline.py`'s `extract_hand_by_type(...,
"Left")`/`"Right"` lookups → `hands_visualizer.py`'s `all_hands_coords` →
this fix) to confirm this is genuinely the single source, not one of
several. Compiles and the swap function smoke-tested (`Left ↔ Right`).
**Not yet independently live-tested** — recommend the user re-run
`launch.bat` and confirm thumb-inward now (correctly) permits grab in
production, matching the debug tool.

### 13.7 Rotation while snapped (2026-08-01) — built in the debug tool, relative not absolute, two noise filters, one open TODO

**Confirmed direction**: rotation is **UNGATED** (active for any snapped
hand regardless of pose) rather than gated on `Open_Palm` — a pragmatic
choice since `Open_Palm` detection has no working implementation (§13.5);
a gate can be added later. Built entirely in `LiveSnapDebug.py` first
(fast iteration — that tool already runs `HandLandmarker` in-process and
gets `hand_world_landmarks` for free, no wire-protocol change needed to
prototype). **Not yet ported to production** (`HandsTriggeredActions.py`/
`CubeWindow.py`) or the wire protocol (§4's `world_landmarks` gap still
applies there).

**Quaternion math is hand-rolled**, not via scipy: scipy is only an
incidental transitive dependency of mediapipe's `jax` in this project's
venv, not a declared requirement, so not something to build a core
mechanic on. Gram-Schmidt orthonormal frame → quaternion (Shepperd's
method, numerically stable across all rotation angles) → shortest-path
slerp. Offline-sanity-checked (identity round-trip, a known 90° rotation,
slerp endpoints/midpoint) before ever touching the camera.

**Rotation is RELATIVE to the hand's orientation at grab time, not
absolute** — direct request, superseding an initial absolute-follow
attempt that made the cube visibly pop/snap-rotate to match whatever
twist the hand happened to be at the moment of the grab. Fixed via a
grab-time baseline pair stored on the cube (`grab_hand_orientation`,
`grab_cube_orientation`) and applying the hand's world-frame rotation
*delta* since grab on top of the cube's own orientation at grab time. On
the grab frame itself the delta is identity by construction — no pop.

**Two independent noise-filtering mechanisms**, found necessary by live
testing (a naive slerp-only or single-filter approach was insufficient):
1. **Reactive raw-jump filter** (`RAW_ORIENTATION_GLITCH_DEG = 60`):
   compares each frame's raw hand-orientation reading only to the
   IMMEDIATELY PRECEDING raw reading (never a lagged/smoothed value),
   substituting rather than freezing when the jump exceeds a threshold no
   real hand can physically achieve in one ~33ms frame. Went through two
   live-caught bugs before landing here: v1 compared against the cube's
   own (lagging) slerped orientation, which created a self-reinforcing
   trap (one rejection made the cube fall further behind, making the next
   frame's gap look bigger, causing MANY consecutive frames to be
   rejected instead of a brief blip); v2's fix still had the substituted
   reference reassigned to the SUBSTITUTED (i.e., stale) value instead of
   the frame's true raw reading, silently never advancing on a flagged
   frame and reproducing the same stuck-trap one level down — this
   specifically caused PROLONGED (not brief) glitch flags whenever the
   hand settled into a genuinely different but stable pose. Both found via
   live testing, not by inspection, and fixed with offline regression
   tests added for each (including a "transitions to a new stable pose"
   case that the v2 bug's fix specifically had to pass).
2. **Proactive geometric confidence gate** (`GEOMETRIC_DEGENERACY_NORM =
   0.035`), added after root-causing the pitch-vs-yaw asymmetry below —
   checks the actual numerical conditioning of the frame construction
   directly (before any jump ever shows up downstream), substituting when
   the orthogonalized second axis's pre-normalization length falls below a
   data-derived threshold.

**Root-caused the "chaotic" rotation report (2026-08-01) with recorded
data, not guesses** — built a new ad hoc recorder, `RecordRotationDebug.py`
+ `record_rotation_debug.bat` (imports directly from `LiveSnapDebug.py`
rather than duplicating, so it records exactly what that tool computes;
saves locally under `rotation_debug_recordings/`, NOT the external-drive
corpus dir, since this is diagnostic data, not training data):
- User reported rotation was chaotic specifically with the back of the
  hand facing the camera, and separately that a **pitch** crossing (hand
  tipping through edge-on about the screen's horizontal axis) had the
  problem while a **yaw** crossing (about the vertical axis) did not.
- A no-slerp test (slerp temporarily disabled entirely, `cube.orientation
  = target_quat` directly) proved the chaos was a faithful, unmodified
  reflection of the raw signal — not a slerp artifact, not the
  relative-delta math, not the (then-only) raw-jump filter.
- Geometric analysis of the recorded `world_landmarks` pinned the exact
  mechanism: the original frame (`wrist→index_MCP`, `wrist→pinky_MCP`)
  uses two vectors that both point from the wrist toward opposite ends of
  the SAME knuckle row — only moderately non-parallel even at rest. A
  PITCH rotation sweeps exactly that knuckle-row axis edge-on to the
  camera at the crossing, driving the two vectors toward collinearity
  right when the hand is edge-on; normalizing then divides by a near-zero
  orthogonalized component, amplifying ordinary landmark noise into wild
  swings. A YAW rotation instead foreshortens the wrist→fingertip axis,
  which the frame never used at all — explaining the asymmetry exactly.
  Quantified: across a full recording, this conditioning norm correlated
  with the per-frame rotation jump at r=-0.52; the most-degenerate
  quartile of frames averaged a 36.3° jump vs. 2.2° for the
  best-conditioned quartile (16x).
- **Fix**: switched to `index_MCP→pinky_MCP` (width axis, taken directly,
  larger magnitude, one less wrist-noise term) and `wrist→middle_MCP`
  (length axis) — much closer to genuinely orthogonal at rest, giving far
  more margin before collinearity. **Chirality was explicitly verified
  preserved** against real recorded data before shipping (211/211 frames,
  palm-normal dot product with the old construction averaged 0.991 — not
  flipped) specifically so yaw/roll, which the user confirmed were
  already working correctly, would not regress; the vector order
  (`index_MCP→pinky_MCP`, not the reverse) is chosen deliberately for this
  reason and must be re-verified the same way before ever being swapped.
- **Measured improvement**, matched recordings of the same pitch-sweep
  test, back-toward-camera pose only: mean per-frame jump 20.6°→12.1°;
  frames jumping >30° in one frame 14-18%→4% (4-5x fewer); frames jumping
  >60° 6-10%→3% (2-3x fewer). A real, substantial, data-confirmed
  improvement — not a complete elimination.

**Open TODO (2026-08-01, direct request)**: rotation quality is still
reportedly poor specifically with the **back of the hand** facing the
camera — i.e. this is NOT a new/different failure mode, it's the SAME
pitch-crossing pose already diagnosed and fixed above, just not fully
eliminated. Consistent with the data: the fix substantially reduced the
frequency and severity of large per-frame jumps in that pose (see the
"measured improvement" bullet above) but did not bring it to zero — a few
percent of frames still exceed the raw-jump threshold.

**Three alternative geometric constructions tested against already-
recorded data (2026-08-01), all NEGATIVE — this avenue is reasonably
exhausted for now**:
1. Thumb-based fallback vector (`wrist→thumb_CMC`, `wrist→thumb_MCP`,
   `wrist→thumb_TIP` in place of `wrist→middle_MCP`) — literature-motivated
   (the thumb is the one MediaPipe landmark NOT coplanar with the rest of
   the palm; Horn's classic absolute-orientation method documents that
   coplanar point sets are mathematically degenerate for full 3D
   orientation and need an out-of-plane reference). Tested against the
   exact 15 frames the current fix flags as degenerate in a real
   recording: CMC and MCP were degenerate on 15/15 (mean conditioning
   0.023-0.036 vs. the current pair's 0.074 overall — substantially
   WORSE, not better); TIP only resolved 8/15 and was roughly on par
   overall. Root cause: anatomically, the thumb emerges near the wrist on
   the index side, so its direction from the wrist isn't much more
   orthogonal to the knuckle-row width axis than the wrist itself is —
   `wrist→middle_MCP` ("straight up the palm") was already the
   better-conditioned choice, independent of viewing angle. Also
   independently flagged as a reliability risk: a robustness study
   testing MediaPipe Hands specifically found thumb occlusion causes far
   larger accuracy drops than occluding other fingers (~20% recall drop on
   FreiHand, ~40% on Panoptic) — the thumb is a documented weak point in
   this exact model, for reasons unrelated to viewing angle (self-occlusion
   against the palm/other fingers, more kinematic freedom than the other
   MCPs).
2. PCA-fit width axis (best-fit line through all 4 non-thumb MCPs via
   first principal component, instead of the raw `index_MCP→pinky_MCP`
   two-point vector) and/or a centroid-based length axis (`wrist→mean(4
   MCPs)` instead of `wrist→middle_MCP`) — motivated by "average out
   individual-landmark noise using more points." Tested against the same
   recording: conditioning values were statistically indistinguishable
   from the current simple pair (differences of ~0.002-0.005, within
   noise) at every one of the 15 degenerate frames, and nearly identical
   overall (mean 0.073-0.075 across all variants). **This is the more
   informative negative result**: if the residual noise were independent
   per-landmark measurement error, averaging over more points should have
   visibly reduced it — it didn't, at all, and all variants rise and fall
   together in lockstep at the same frames. This means the degradation is
   a SYSTEMATIC, CORRELATED distortion of the whole knuckle-row
   reconstruction at that viewing angle (consistent with genuine reduced
   monocular depth-disambiguation at edge-on views), not independent noise
   on any single landmark — no choice or combination of landmarks *within
   the palm plane* can fix this, since they're all subject to the same
   correlated degradation together.

**Prospective directions for further improvement (2026-08-01, literature
review, NOT YET IMPLEMENTED)** — since all three tested approaches worked
*within a single frame* (picking/combining landmarks), and none helped,
the productive next axis is *across frames* (temporal), which hasn't been
tried yet:

- **Literature context — why a human doesn't perceive this the same way a
  per-frame geometric estimator does**: Ernst & Banks (2002, *Nature*)
  showed human sensory integration is reliability-weighted (Bayesian/MLE)
  — multiple cues are combined in proportion to their inverse variance, so
  a momentarily-degraded cue is automatically down-weighted rather than
  trusted at face value. Wolpert's forward-model work (and Friston's
  predictive-coding/active-inference framework) shows the brain regulates
  perception and action against a *predicted* sensory state (from an
  efference copy of the motor command / a forward model of ongoing
  motion), not raw instantaneous sensory input — this is specifically
  valuable when sensory feedback is noisy, delayed, or has gaps, exactly
  this project's situation at an edge-on crossing. Johansson's biological-
  motion-perception work (point-light displays) shows humans reconstruct
  plausible body structure from extremely sparse/ambiguous visual data by
  applying strong learned priors on which configurations and motions are
  kinematically plausible for a human body — the visual system doesn't
  entertain wildly implausible instantaneous readings the way an
  unconstrained per-frame estimator can. Note one important asymmetry that
  bounds how far this analogy goes: a person moving their OWN hand also
  has proprioception plus an efference copy of the motor command — a
  non-visual channel with no camera-viewing-angle ambiguity at all, which
  this vision-only pipeline has no equivalent of and cannot replicate in
  software; the achievable parallel is specifically the
  temporal-prediction/reliability-weighting mechanism, not full parity
  with biological perception.
  Sources: [Predictions not commands: active inference in the motor
  system](https://link.springer.com/article/10.1007/s00429-012-0475-5);
  [Humans integrate visual and haptic information in a statistically
  optimal
  fashion](https://www.researchgate.net/publication/11550808_Humans_integrate_visual_and_haptic_information_in_a_statistically_optimal_fashion)
  (Ernst & Banks 2002); [Biological motion
  perception](https://en.wikipedia.org/wiki/Biological_motion_perception)
  (Johansson).
- **Directly translatable engineering parallel, and already standard CV
  practice for exactly this problem** (not just a neuroscience analogy):
  Kalman/Extended-Kalman/Unscented-Kalman filtering is the established
  technique for monocular hand-pose tracking specifically under depth
  ambiguity — literature confirms EKF has been used "to estimate the pose
  of the hand... even when using only a monocular camera and without any
  depth information." The concrete, incremental proposal: maintain a
  short-window estimate of the hand's recent angular velocity from the
  last few ACCEPTED good frames; each frame, predict this frame's expected
  orientation by extrapolating that velocity (a constant-angular-velocity
  motion model); then blend the raw geometric reading with that
  prediction, weighted by real-time reliability — using
  `conditioning_norm` (already computed every frame) directly as the
  inverse-variance-style reliability signal, exactly mirroring Ernst &
  Banks' MLE cue-weighting. This upgrades the current binary
  accept/substitute gate into a continuous, principled fusion that can
  distinguish "the raw signal disagrees because of noise" from "the raw
  signal disagrees because the hand genuinely accelerated," which a fixed
  jump threshold cannot. This is a materially different, untried axis (temporal
  integration) from the three geometric (spatial, single-frame) attempts
  above, so there's real reason to expect it could help where those
  plateaued — but per this project's standing discipline, build small and
  verify against recorded data (the existing `rotation_debug_recordings/`
  captures plus fresh ones) before trusting it, the same way every other
  claim in this section was checked rather than assumed. Source:
  [Predictive Tracking in Vision-based Hand Pose Estimation Using
  Unscented Kalman
  Filter](https://www.intechopen.com/books/human-robot-interaction/predictive-tracking-in-vision-based-hand-pose-estimation-using-unscented-kalman-filter-and-multi-vie).
- **Kinematic-plausibility prior** (softer version of the current hard
  `RAW_ORIENTATION_GLITCH_DEG` threshold): Johansson-style body-constraint
  priors suggest replacing the fixed 60°/frame cutoff with a proper
  probabilistic plausibility weight derived from measured human wrist
  angular-velocity statistics, feeding into the same reliability-weighted
  fusion above rather than a hard reject/accept boundary.
- **Out of scope but worth naming**: the fundamental reason binocular
  human vision doesn't hit this exact ambiguity is stereo depth — an
  actual second camera or an IMU on the hand would structurally resolve
  it the way no amount of single-RGB-camera processing can. Not pursued
  here (this project's whole premise is a single webcam), but worth
  remembering as the ceiling on what pure software can achieve.

**Predictive filter IMPLEMENTED and live-tested (2026-08-01)** — the
Kalman-style proposal above was built (`HandOrientationFilter`,
`_predictive_filter_step`, `_reliability_alpha`, replacing BOTH earlier
binary filter mechanisms entirely) and offline-verified against recorded
data before ever touching the live tool (no-pop-at-grab preserved, healthy
rotation stays fully raw-trusted with zero added lag, tracking-loss reset
confirmed clean, an engineered degenerate frame correctly drives
reliability to 0 instead of freezing) — see `LiveSnapDebug.py`'s module
comment above `CONDITIONING_ALPHA_LOW` for the full implementation
account. Same-recording analysis showed it eliminating >30°/>60° jumps
entirely in the back-toward-camera pose. **Live test result: a real but
INSUFFICIENT improvement** — user reports rotation quality with the back
of the hand facing the camera is "slightly better but not yet solving the
issue." **TODO remains OPEN.** Kept in place (it's a measured net
improvement, not a regression), but this is now four attempts (three
geometric, one temporal) that have each helped without fully resolving
it — worth treating the residual as looking increasingly like a genuine
floor of this pipeline's single-monocular-RGB-camera setup (see the
"out of scope" stereo/IMU note above) rather than assuming a fifth
software-only attempt will fully close the gap. If picking this up again:
check whether `ROTATION_SLERP_FACTOR` (raised 0.25→0.35 the same session,
for unrelated general responsiveness) changed the felt severity before
concluding anything new about the filter itself, and consider whether
further tuning of `CONDITIONING_ALPHA_LOW`/`CONDITIONING_ALPHA_HIGH`
(not yet tuned beyond the initial data-derived guess) or a wider
angular-velocity averaging window (currently a single-frame delta, no
smoothing of `omega` itself) are worth testing before reaching for a
fifth fundamentally different approach.

**Ported to production (2026-08-01)** — `HandsTriggeredActions.py`/
`CubeWindow.py` and the wire protocol (`VisionPipeline.py`→`Server.py`→
`PythonApp_Main.py`, new `"hands_world"` packet type, 21×3×2=126 floats,
sent before `"hands"` each frame) now carry the exact same design verified
in `LiveSnapDebug.py`: relative-to-grab quaternion math, the
better-conditioned landmark pair, and the predictive/reliability-weighted
filter, ported essentially verbatim rather than re-derived. Offline-
verified end-to-end with synthetic landmark data before ever touching a
real camera (same discipline as everything else in this section): snap +
no-pop-at-grab confirmed; rotation tracking a moving synthetic target
converged to EXACTLY the theoretically-predicted steady-state slerp lag
(0.000° error against the closed-form `Δ×(1-α)/α` formula) — a strong
signal the ported math is bit-for-bit equivalent to the debug tool's,
not just superficially similar. `CubeWindow.py`'s orientation gizmo
(`_draw_orientation_gizmo`) was also ported and smoke-tested (opens,
draws, closes cleanly).

**NOT YET tested against a real camera or the real wire protocol** — only
offline/synthetic verification so far. One specific item is genuinely
new, untested code with no prior verification anywhere: the world-landmark
mirroring/x-negation convention in `utils_for_remapping_coordinates_and_
output_formatting.py`'s `remap_world_keypoints` (`invert_x=True` default).
`LiveSnapDebug.py` never needed this — it runs detection on an
already-mirrored frame, so MediaPipe's own output was already mirror-
consistent there. The production pipeline mirrors pixel coordinates AFTER
detection on an un-mirrored frame, so world landmarks need an explicit
x-negation to represent the same visually-mirrored hand — this negation
was added by inference/reasoning, not verified live. If rotation feels
mirrored/inverted on any axis once live-tested, check this exact function
first, same "verify the sign convention live before trusting it"
discipline as the thumb-outward rule's calibration (§13.6).

**Real 3D cube rendering (2026-08-01, direct request, live-confirmed
working)** — once rotation was confirmed working end-to-end, the
flat-square + axis-gizmo placeholder no longer made sense: replaced with
actual rotating 3D cubes in `CubeWindow.py`'s `_draw_cube_3d` (8 local
vertices rotated by the cube's orientation quaternion, weak-perspective
projected, 6 faces backface-culled then painter's-algorithm depth-sorted
farthest-to-nearest). Each cube's 6 faces are 3 opposite-pair color
families, one side of each pair a computed darker shade (`_darken`) of the
other, not hand-picked separately — guarantees the pairing stays
consistent. **Large** cube: yellow/violet/turquoise, exactly 2x the
**small** cube (green/red/blue) in every dimension. Cube identifiers
renamed "blue"/"red" → "large"/"small" (the old names stopped describing
anything once every cube got 3 face colors and different sizes).
Renaming surfaced a real, now-fixed issue: grab radius previously used a
single shared `cube_window.cube_size`, which stopped making sense once
cube sizes actually differ — `_try_snap` now scales grab radius to EACH
candidate cube's own size (`PART_ONE.md` §5's long-open "grab radius
scaled to object size" item, resolved as a side effect). Offline-verified
(sizes, face-color pairing, no-pop-at-grab and rotation-vs-theory checks
all re-run and passing after the rewrite).

**Morphing bug found live and fixed (2026-08-01)**: the first version of
`_draw_cube_3d` reused the axis-gizmo's per-vertex scale formula
(`1/(1+K*rz/half)`), which is only ever safe for a point at distance
<= half from the origin (true of a gizmo's axis endpoints, NOT of cube
corners, whose distance from the origin is the body diagonal,
`half*sqrt(3)`). Verified numerically: at some rotations a corner's
denominator went NEGATIVE (worst case -0.039 with K=0.6), flipping that
vertex to the wrong side of the cube -- exactly the reported "vertices
moving so faces morph and the cube doesn't stay a cube." **Fixed** with a
proper, physically-correct perspective projection instead: a virtual
camera at a FIXED distance (`CUBE_PERSPECTIVE_DISTANCE_RATIO = 3.0` times
cube.size, comfortably beyond the half-diagonal) using the standard
pinhole-camera divide `scale = camera_distance / (camera_distance + rz)`.
Verified via a full rotation sweep (9 axes x 180 angle steps, both cube
sizes): the projection scale never drops below ~0.71x camera_distance
(nowhere near the old bug's zero-crossing), and small rotation steps
produce correspondingly small, continuous screen movement (max ~1.7px per
2° step, no discontinuities) — ported the same fix into `LiveSnapDebug.py`
(same design, cv2 primitives instead of pygame) so the combined video +
landmarks + transparent-cube-overlay debug view (`debug_snap.bat`) stays
an accurate, synchronized stand-in for production while it's still in
active use for testing (direct request 2026-08-01: keep this debug view
around for now, remove only once final production no longer needs
landmark-level debugging).

### 13.7.1 Filter audit (2026-08-01, later conversation) — keep for now, TODO: re-test for redundancy after future improvements

Direct request: audit all accumulated filters/smoothing across the
gesture pipeline (rotation, translation) and strip anything that didn't
measurably contribute to solving rotation quality or "Object Jump
Correction" (§14.1.4), or that only helped marginally at the cost of
complexity/lag — the stated goal being to keep the game logic pure and
simple, not accumulate filters that don't earn their keep.

**Audit result, translation: nothing to strip.** Checked the actual
shipped code, not just what was discussed — the Object Jump Correction
investigation's candidate mitigations (exclude out-of-bounds candidate
landmarks + renormalize + freeze-if-too-few-remain; light temporal
smoothing on the combined position) were never merged into
`LiveSnapDebug.py`/`HandsTriggeredActions.py`. The first was built and
verified against real data to make no measurable difference and was
correctly discarded before shipping (§14.1.4); the second was proposed
but left conditional on data that never arrived, and was never built.
Today's translation mechanism is exactly the weighted-average + no-pop
residual, nothing layered on top.

**Audit result, rotation: one real filter exists** (the predictive/
reliability-weighted mechanism — "Attempt 3" above `CONDITIONING_ALPHA_LOW`),
with no dead code left over from its two earlier, abandoned attempts
(both were fully replaced in place, confirmed via grep — no orphaned
`GEOMETRIC_DEGENERACY_NORM`/`RAW_ORIENTATION_GLITCH_DEG` constants remain,
only historical comments referencing them). This filter's impact is
**measured and substantial, not marginal**: eliminates all `>30°` jumps
(4%→0%) and all `>60°` jumps (3%→0%) in the recorded back-toward-camera
test data, mean jump 11.4°→7.8° — on top of an earlier geometric fix that
had already reduced it from ~20.6°→12.1°. `ROTATION_SLERP_FACTOR` (basic
easing, not bug-specific — already confirmed via a direct live test to
not be the noise source, §13.7 above) was flagged separately as an
ordinary responsiveness knob, not "accumulated complexity," and isn't in
scope of this audit.

**Decision (direct request): KEEP the predictive rotation filter for
now.** The back-of-hand rotation-quality TODO remains open (this filter
substantially reduces but doesn't eliminate it), so removing it now would
be a real regression, not a simplification of dead weight. **New TODO,
added to the future-improvements queue**: once future improvements land
(candidates: "Object Jump Correction," Z-axis translation / the proposed
startup depth-calibration step, or anything else that touches monocular
depth ambiguity), **re-test whether this filter has become redundant** —
if a later fix resolves the underlying depth-ambiguity problem at its
source, the filter may no longer be pulling its weight and should be
re-audited with the same cost-benefit discipline used here, not kept out
of inertia.

**TRIGGER NOW IDENTIFIED (2026-08-02, perception-spec integration — §15,
and `PERCEPTION_LAYER_SPEC.md` A6)**: that "re-test for redundancy" TODO
is no longer open-ended. **M6's quaternion UKF with anisotropic covariance
subsumes this filter** — it is a hand-rolled, simplified instance of
exactly what M6c + M7 describe (a predictive angular-velocity model
blended against the raw reading, weighted by a conditioning-derived
reliability signal). **When M6 ships, this filter is deleted, not kept
alongside it** — two overlapping predictive filters is precisely the
accumulation this audit exists to prevent. Its removal is a listed
deliverable of M6 (merged queue item 2.3), justified by an A/B diff rather
than assumed. Related: M6b's `observability` overlaps with this filter's
`conditioning_norm` — reconcile into one metric, don't ship both.

### 13.8 Mesh-generic 3D rendering (2026-08-01) — the cube is a placeholder for future imported 3D objects

Direct request, immediately after the morphing-bug fix above was
confirmed live: "make sure what you have done for the 3d representation
of the cube can be later applied to any 3d object which is imported into
the scene. The cube should act as a placeholder for 3d complex objects
which will be imported later on." This was a real architectural gap in
the first version — `_draw_cube_3d` hardcoded the cube's 8 vertices and 6
quad faces directly (`CUBE_VERTICES`/`CUBE_FACES` module constants) and
looked up colors via a cube-specific `{"+x": color, "-x": color, ...}`
dict keyed by axis-aligned face direction — none of which would extend to
an arbitrary imported mesh (different vertex/face counts, triangulated
faces, real per-face materials, no "+x"-style axis-alignment).

**Refactored (both `CubeWindow.py` and its `LiveSnapDebug.py` mirror) to
separate geometry from rendering**, so an imported object later needs
only a new geometry constructor, not a single change to the
rendering/projection/culling/sorting code:

- **`MeshFace`**: `vertex_indices` (a tuple of ANY length — 3 for a
  triangle, 4 for a quad, so this scales directly to real imported meshes,
  which are almost always triangulated), a local outward `normal` (for
  backface culling after rotation), and its own `color` stored directly on
  the face (not looked up via an axis-keyed dict) — an imported mesh's
  faces will carry real per-face colors/materials the same way.
- **`Mesh`**: local-space (unit-scale, ±1-ish per axis) `vertices` +
  `faces`. This is the piece meant to be swapped out later.
- **`_make_cube_mesh(color_x, color_y, color_z) -> Mesh`**: the ONE
  cube-specific construction function left in either file — builds the
  placeholder cube's 8 vertices / 6 quad faces (darker-opposite color
  pairing per `_darken`, unchanged from §13.7's cube-color work). A future
  "import a 3D object" step needs an equivalent factory (e.g. loading an
  OBJ/glTF file into vertices+faces+materials) — nothing else changes.
- **`Cube.mesh: Mesh`** replaces the old `face_colors` dict field. `Cube`
  keeps its name (every object today IS cube-shaped) but is really "the
  snappable scene object, whatever `mesh` says it looks like."
- **`CubeWindow._draw_object_3d`** (renamed from `_draw_cube_3d`) and
  `LiveSnapDebug.py`'s mirrored `_draw_cube_3d` now iterate `obj.mesh.faces`
  generically — rotate `obj.mesh.vertices`, perspective-project (same
  fixed-camera-distance formula as §13.7's bug fix), backface-cull via each
  face's own rotated `normal`, depth-sort, draw each face's own `color`.
  Zero cube-specific logic remains in either drawing function.

**Verified concretely, not just asserted**: after the refactor, all
previously-passing checks (sizes, color pairing, no-pop-at-grab,
rotation-vs-theory, rigidity) were re-run and still pass in both files.
Additionally, in both `CubeWindow.py` and `LiveSnapDebug.py`, a completely
different `Mesh` (a 4-vertex, 4-triangular-face tetrahedron, arbitrary
per-face colors) was assigned to a live `Cube` instance at runtime and
rendered successfully with **zero changes to any rendering code** — direct
proof the pipeline is genuinely object-agnostic, not just cube-shaped code
that happens to also technically accept other inputs.

**What a real future "import a 3D object" step would still need** (not
built, just the scoped remaining gap): (1) a loader for an actual 3D file
format (OBJ is the simplest — plain text, vertex/face lists, easy to
parse without a new dependency; glTF is more capable but needs a real
parser library) that produces a `Mesh`; (2) if imported meshes are large
(hundreds+ of triangles), the current O(faces) per-frame Python loop and
painter's-algorithm sort may need a faster depth-sorting or GPU-backed
approach — not a concern for a cube (6 faces) or anything of similarly
modest complexity, but worth flagging before importing something detailed;
(3) real per-face colors from the imported file's own materials, instead
of `_make_cube_mesh`'s procedural light/dark color-family assignment.

<!-- VERBATIM-END -->
