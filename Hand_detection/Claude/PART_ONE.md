# Part One — gesture/pattern recognition design & matrix

Implements §7 of `Specification.md`: Pipeline A gesture recognition, developed
on PC against the existing Python MediaPipe pipeline. This file is the living
design reference for Part One's gesture vocabulary — **the matrix in §2 below
is meant to be enriched** as new gestures/objects are added; keep it in sync
with `rules.py`/`temporal.py` as they're built.

## 1. Scope decided so far

**Concrete first build**: two hands, two cubes (existing blue cube + a new
red cube), pinch-to-grab manipulation. This is a live, visually-tuned PC
prototype — not the offline-JSON-only R&D originally sketched in
Specification.md §2/§7 — because grab thresholds, rotation feel, and the
depth-proxy mapping all need to be tuned by eye against a live webcam feed,
the same way Part Zero-bis's coordinate mapping needed live verification
(see `PART_ZERO_BIS.md`). It's built as a direct extension of Part Zero's
`CubeWindow.py`, **in place, in the same `Hand_detection/Local_pc/` folder**
— not a new sibling folder and not a separate offline module. This matches
how Part Zero itself was built (modifying the pre-existing cursor-control
pipeline in place, with `PART_ZERO.md` documenting the delta rather than a
frozen copy being kept). `Part_Zero_local_pc/` and `Part_Zero_Bis_Web/` were
renamed to `Local_pc/` and `Web/` accordingly once Part One started —
history is in git, not in a parallel folder. See Specification.md §7.5 for
the pointer back to this file.

**Sequencing vs. the browser port**: built PC-only, first, in full — no
parallel JS implementation. See Specification.md §2 for why (avoids
maintaining tuned thresholds in two languages at once); portability is kept
cheap via pure-function `features.py`/`rules.py` and an engine-agnostic
`gesture_config.json` (§7.4), not by building both sides simultaneously.

## 2. Core architecture decisions

- **Two hands, independent pose classification.** Each hand's pinch state,
  translation, rotation, and depth proxy are computed purely from that
  hand's own landmarks — no gesture in the current matrix needs both hands'
  data fused together.
- **One cross-hand exception: grab arbitration.** Either hand can grab either
  cube (no fixed left→blue/right→red pairing), so a cube can only ever be
  held by one hand at a time. This needs a small shared registry both hands'
  grab logic can see: `{cube: holding_hand | None}`. Rule: on a pinch
  rising-edge, look at all **unowned** cubes within grab radius of the pinch
  point, claim the nearest one; skip cubes already owned by the other hand.
  This is the one piece of "combined" cross-hand logic the architecture
  needs — everything else stays per-hand.
- **Sticky grab.** Once acquired, a cube stays grabbed regardless of how far
  the pinch point drifts from it — only releasing un-pinches it (or losing
  hand tracking, see below). The initial proximity check only gates
  *acquisition*, not continued holding.
- **Release conditions**: un-pinch (thumb-index distance exceeds a release
  threshold, with hysteresis vs. the grab threshold to avoid boundary
  jitter), **or** loss of hand tracking. Either way: cube freezes in place at
  its last known position, ownership is cleared, state → idle. Re-acquiring
  always requires a fresh pinch rising-edge near the cube — tracking
  resuming mid-pinch does **not** auto-regrab.
- **Rotation — quaternion-based, gimbal-lock-safe.** Track hand orientation
  as a quaternion built from an orthonormal frame (Gram-Schmidt on
  `wrist→index_MCP` and `wrist→pinky_MCP` from `world_landmarks`), and slerp
  the cube's quaternion toward it each frame. **Never decompose into
  separate roll/pitch/yaw Euler angles at any point** — gimbal lock is a
  property of that decomposition, not of the underlying rotation itself.
  Smooth the whole quaternion uniformly (single slerp factor); don't smooth
  per-axis, since that would silently reintroduce the same problem through
  the back door.
  - Rotation about the axis **orthogonal to the camera plane** (the
    depth/Z axis — twisting the wrist while facing the camera) is easy to
    detect: it shows up as a clean 2D rotation in the landmarks' `x,y`
    image-space positions.
  - Rotation about axes **in the camera plane** (tilting the hand toward/
    away from the camera — pitch/yaw) is harder: it shows up mostly as
    changes in `world_landmarks`' `z` component and foreshortened landmark
    spacing, and MediaPipe's `z` is the least reliable of the three
    coordinates monocularly. Expect this to be noisier; verify empirically
    once built (same discipline as `PART_ZERO_BIS.md`'s `NOTES.md`) rather
    than assuming a fix in advance.
- **Depth proxy — apparent hand size, not raw MediaPipe `z`.** Use the
  hand's apparent span in normalized/pixel image coordinates (e.g.
  wrist↔middle-MCP distance) relative to a calibration baseline captured at
  grab time: `ratio = current_span / baseline_span`. Drives cube **scale**
  and **color gradient** only (bigger + darker = closer, smaller + lighter =
  farther) — **no Z-axis translation** for now (explicitly deferred).
  Active only while grabbed, bundled with translate/rotate as an effect of
  the grabbed state (not a hover preview).

## 3. Gesture / signal matrix

Build order = difficulty order (easiest first); each step mostly reuses the
previous step's code. **Enrich this table when adding new gestures/objects**
— add a row, keep the Order column meaningful (insert at the difficulty tier
it actually belongs to), and cross-check §7.4's engine-agnostic
`gesture_config.json` rule whenever a new row is added.

| Order | Signal / Gesture | Hand(s) | Input | Detection logic | Effect | Status |
|---|---|---|---|---|---|---|
| 1 | Scaffolding | both, independent | full 21-landmark list per hand | n/a — plumbing only | red cube added to scene; both hands' landmarks flow through (not just left); no ownership/grab logic yet | **Built, not yet live-verified** — code in `Local_pc/Movement_with_hand_detection/`; run `launch.bat` and confirm blue cube follows left hand, red cube follows right hand |
| 2 | Pinch detection | each hand independently | thumb tip (4), index tip (8) | `distance(4,8) < pinch_threshold` | candidate grab trigger (rising edge) | Not started |
| 3 | Grab acquisition + arbitration | each hand vs. shared registry | pinch (#2) + pinch-midpoint vs. cube positions | pinch rising-edge → nearest **unowned** cube within grab radius → claim in shared registry | idle/hover → grabbed | Not started |
| 4 | Release | each hand | pinch state, or tracking loss | un-pinch (falling edge past hysteresis) **or** hand tracking lost | grabbed → idle; cube frozen in place; ownership cleared; requires fresh pinch to reacquire | Not started |
| 5 | Translation | each hand, while grabbed | pinch midpoint (4+8) | cube position = mapped(pinch midpoint), X/Y only | cube follows pinch | Not started |
| 6 | Depth proxy → scale + color | each hand, while grabbed | apparent hand span (image coords) vs. calibration baseline | `ratio = current_span / baseline_span` | cube scale ∝ ratio; color lerps light↔dark by ratio | Not started |
| 7 | Rotation (quaternion) | each hand, while grabbed | `world_landmarks`: wrist(0), index_MCP(5), pinky_MCP(17) | orthonormal frame → quaternion → slerp | cube orientation follows hand orientation | Not started — **requires sending `world_landmarks` over the wire, not currently sent** (server only sends 2D pixel landmarks today, see §4) |

## 4. Known wire-protocol gap (relevant to step 7)

The existing socket protocol (`VisionPipeline.py` → `Client.py` →
`PythonApp_Main.py`) currently sends only 2D pixel-space landmarks (21
points × 2 hands × `(x_px, y_px)` = 84 floats per `"hands"` packet) — no `z`,
no `world_landmarks`. Steps 1–6 above only need 2D image-space data, so no
protocol change is needed until step 7 (rotation), which needs
`world_landmarks` (metric, hand-relative 3D) per the data contract in
Specification.md §6. Extend the `"hands"` packet then, not before —
resist adding it early since it's dead weight until rotation is built.

## 5. Open items to resolve empirically, not now

- Exact pinch/release threshold values and hysteresis margin — tune by eye
  once step 2 is live.
- Exact grab-radius value (likely scaled to cube size).
- Tie-break rule if both hands' pinch rising-edges land on the same free
  cube in the same frame (currently unspecified — low-probability edge
  case, revisit only if it's actually hit in practice).
- Exact hand-span metric for the depth proxy (wrist↔middle-MCP vs. a full
  bounding-box diagonal) — pick whichever is more stable empirically.
