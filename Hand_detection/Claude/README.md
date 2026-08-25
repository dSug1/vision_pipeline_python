# READ THIS FIRST — the map

⭐ **This file is the single entry point.** It is a MAP, not a copy: it tells you
what the system is, what is live, what was tried and rejected, and which of the
other ten documents answers which question. **Every fact of record still lives in
those documents** — this file must never become a second source of truth.

⛔ **THE BUILD QUEUE IS `PART_ONE.md` §3.1 AND NOWHERE ELSE.** It is one ordered
table of ~62 rows and it is well maintained. Do not summarise it here, do not
start a second list, do not "helpfully" reorder it. This file points at it.

---

> ✅ **2026-08-22 — U7 IS FIXED AND SHIPPED.** `HANDEDNESS_LABEL_DEFECT.md` is now
> a RESOLVED write-up: the label is still wrong 10.8% of the time, but nothing
> chirality-sensitive reads it any more — geometry does. ⚠ Read it anyway before
> touching chirality: it records **three distinct defects with one appearance**,
> and the two cheaper fixes that were measured and failed.
>
> ⛔ `POSTMORTEM_4_1_IDENTITY_MIGRATION.md` still stands — 4.1's identity
> migration: built, patched five times, **reverted** (`TRACK_OWNERSHIP = False`,
> nothing deleted). ⭐ **T3 was instead fixed NARROWLY** (`Resources/owner_remap.py`):
> ownership stays a slot NAME and only follows its track across a relabel, so
> there is no seam of the kind the post-mortem blames. Read it before any wider
> attempt.

## 1. Read order

| you want to… | read |
|---|---|
| ⭐⭐ **START THE NEXT BUILD (`F1` — the cube's transform from the FINGERTIPS)** | `PART_ONE.md` §3.1's `F1` row. ⛔ Read its trap first: a rigid palm+tips fit is A10-dead twice |
| ⭐ **plug the hand tracking into ANOTHER game / a port / a lens** | `Local_pc/Movement_with_hand_detection/handinput/README.md` — the input-system package (built 2026-08-25). Record: `GESTURE_PIPELINE_SPEC.md` §17; rows `IS1`–`IS4` |
| **start any other build session** | this file → `PART_ONE.md` §3.1's "YOU ARE HERE" block → that item's row |
| know **why** something failed | `GESTURE_PIPELINE_SPEC.md` — the authoritative record of what failed and why |
| know the **forward design** below the gesture layer | `PERCEPTION_LAYER_SPEC.md` (⚠ read its §0.1 amendment log BEFORE any module body) |
| know how the **game behaves** | `GAME_RULES.md` — the behavioural statement of record |
| find the **evidence** for a number | `Local_pc/Movement_with_hand_detection/analysis/README.md` maps every claim to the script that produced it |

⚠ `Specification.md` is the ORIGINAL build handoff (Part Zero era). Its §11 build
order is historical — **the queue superseded it.** Keep it for the goal,
constraints and prior-art scan; do not take build order from it.

⚠ `HANDOFF_*.md` are per-session briefs and **all of them are now CLOSED**, including `HANDOFF_T6_ORIENTATION_FROM_2D.md` (T6 rejected 2026-08-24 — keep it for its DIAGNOSIS, which still stands, not for its remedy). `_archived_old_*` is dead.

---

## 2. What the system actually is

Two Python processes talking over a local socket, plus one debug tool that
mirrors production.

```
webcam
  │
  ▼
Local_pc/Python_Server_MediaPipe_vision_pipeline/VisionPipeline.py   ── SERVER
  ├─ cv2.flip  ⭐ MIRRORS THE FRAME BEFORE DETECTION (spec §14.3.4.3)
  ├─ MediaPipe HandLandmarker (VIDEO mode)  → pixel + world landmarks
  ├─ Resources/hand_identity.py  ── DR-1: track identity by POSITION,
  │                                  overrides MediaPipe's per-frame label
  └─ socket 127.0.0.1:5050 ──► "meta", then per frame: "hands_world", then "hands"
                                   │
                                   ▼
Local_pc/Movement_with_hand_detection/                              ── CLIENT
  ├─ Resources/Client.py → PythonApp_Main.py (decodes the packets)
  ├─ Resources/HandsTriggeredActions.py   ── ALL gesture logic: snap, translate,
  │                                          rotate, release, ownership
  ├─ Resources/CubeWindow.py              ── pygame renderer (mesh-generic)
  └─ handinput/                           ── ⭐ THE INPUT SYSTEM (2026-08-25):
                                             actions + phases + callbacks over
                                             HandState v2. ⚠ OBSERVES ONLY —
                                             it drives no cube. Both tools feed it.

LiveSnapDebug.py — ONE window, no socket, deliberately mirrors production.
```

**Launcher**: `PythonApp_Main.py` → `Launcher_for_Server_and_Client.py` → spawns
both. ⚠ The parent exits immediately; the children keep running. `stop.bat` kills
strays. ⚠ Each script also appears TWICE in the process list — the `.venv` python
here is a Windows-Store redirector that re-launches the base interpreter. Benign.

**Estimator modules** (client `Resources/`, stdlib-only and numpy-free by
contract, so they can be ported by transliteration): `palm_geometry`,
`palm_rotation` (Horn), `hand_blocks`, `hand_state`, `orientation_filter`,
`palm_anchor`, `hand_skeleton`, `frame_gate`, `block_predictor`,
`confirmation_gate`.

⭐ **N6 — shared, never copied.** Any module both production and the debug tool
need is IMPORTED by both (`hand_identity` lives in the server's `Resources/` and
the debug tool adds it to `sys.path`). A copy is how the two drift.

**`Web/`** holds Part Zero-bis only (the browser proof of the minimal loop).
Nothing from Part One runs there yet — that is U3.

**Recordings** live on `E:\Python\Recordings for vision_pipeline\…` (415 files,
33 perception sessions). ⚠ **Never `--local`.** ⚠ The corpus contains **no image
data** — landmarks only — so no image-based model can be run over it
retroactively. ⚠ The drive currently reports `Full Repair Needed` and its first
access after an idle gap fails; `wake_e_drive.py` retries past that.

---

## 3. Where the project stands (2026-08-22)

**Live and owner-confirmed**: snap acquisition + arbitration; grab-relative
translation (§14.1); rotation while snapped (Horn least-squares over the palm,
grab-referenced); release on tracking loss; DR-1 track identity; DR-2 edge-on
sign freeze; Phase D's 150 ms dropout coast + 3-frame resync blend; `horn-palm`
anchor; and — newest — the **mirror fix** that made production and the debug tool
the same pipeline.

**✅ THREE FIXES SHIPPED AND OWNER-ACCEPTED LIVE (2026-08-22)** — *"fix is
working. I believe this is good to ship."* All three presented as the same
symptom (**a back-of-hand hand ends up with the cube**) and were only separable by
recording them:

| | fix | flag |
|---|---|---|
| **U7** | chirality from GEOMETRY, not the 10.8%-wrong label — `sign(det[index_MCP−wrist, pinky_MCP−wrist, thumb_CMC−wrist])` over `world_landmarks`, in `palm_geometry.py` and wired into `PalmFacingTracker.update()`, the one place the label entered the cue in **either** tool | `GEOMETRIC_CHIRALITY` |
| **T3** | a held cube's owner SLOT follows its DR-1 TRACK across a relabel (`Resources/owner_remap.py`) — closes the **silent handover**, where the cube changed physical hand with no release, no snap and rule 3 never consulted | `OWNER_FOLLOWS_TRACK` |
| **U8** | rule 3 refuses to snap while a newly entered hand's chirality is still **provisional** — **200 ms**, gated on ELAPSED TIME so it is correct at any capture rate (no fps estimate, no per-frame sampling). ⭐ Measured: the *dispute* condition, not the window, is the primary guard — the recorded failure is refused at every window from 400 down to 100 ms | `CHIRALITY_CONFIRM_MS` |

| **U9** | every object is confined to a **play area** — the display window inset by **60 px** (half a hand width at 40 cm), so it can never be pushed to the edge. ⛔ TWO hand-side *triggers* were built and reverted first: **a trigger cannot enforce an invariant** (translation is grab-relative, so the object keeps its own offset and creeps outward on every grab-push-drop cycle). ✅ **SUPERSEDED BY 4.2 (2026-08-23)**: the play area is now a **world-space volume, frustum-aware** — the clamp works in world coordinates and the on-screen boundary moves with depth. ⭐ The margin never changed: it was always half a hand breadth = **42.5 mm**, and 60 px was only its projection at 40 cm | `EDGE_MARGIN_PX` |
| **recorders** | both tools now log the cue AND cube position/size, sampled at the same point in the frame (`recorder_schema: 2`). Production used to sample cubes a frame earlier than debug, which silently skewed any harness pairing hands with cubes | — |

✅ **All of the above are live-confirmed in BOTH tools (2026-08-23).** The recorder
rework is verified end to end: the play-area invariant is now read **straight from
a recording** — 0 of 1018 cube-frames outside — with no replay and no
re-derivation, which is exactly what it was for. ⛔ One thing is NOT closed: U7's
declared-ground-truth acceptance take. The attempt used both hands, so its
declaration was retracted in that session's `meta.json`; U7 is shipped and
behaviourally confirmed, but the known-hand measurement still needs a take with
one hand throughout.

Also: **production now RECORDS the cue it used** (`thumb_outward`,
`chirality_confirmed`, `orientation_valid`, `snap_allowed`) instead of forcing a
recomputation — a recomputation is a second implementation that can silently
disagree with the real one, and twice tonight it did.

⛔ **The original write-up's mechanism ("use the 3D palm normal") was wrong** — 3D
alone does not remove the chirality dependence; the **thumb** is what does.

⚠⚠ **Four times this session a harness reported CLEAN on a take the owner had just
watched fail.** Every time the instrument was wrong, not the owner. That is why
production now RECORDS what it ran instead of forcing a recomputation, and why
the recorders have their own parity guard. See `PART_ONE.md` §3.1's YOU-ARE-HERE
block for all four.

⭐⭐ **THE INPUT SYSTEM IS BUILT (2026-08-25, rows `IS1`–`IS3`)** —
`Local_pc/Movement_with_hand_detection/handinput/`: five actions, Unity's five
phases, `+=` callbacks with a context, a polling API, and `HandState` v2 as the
serialisable contract, so the hand pipeline can be lifted into another game, a
port or a lens. ⚠⚠ **IT OBSERVES AND DRIVES NOTHING** — every value it publishes
was already computed by the gesture logic that frame, so behaviour cannot change
(`parity_replay` NO DIVERGENCE, 24 existing suites pass, 95 new checks).
⛔ **BUILT, NOT SHIPPED: the owner's live look in both tools is still owed**
(deferred by the owner to the evening of 2026-08-25). ⭐ Scope, deliberately:
Unity splits *Input System* from *XR Interaction Toolkit* and this is the first
only — `grab_ready` is ELIGIBILITY, never "grab what", which needs a scene.
Extracting the interaction tier is row **IS4**, open and owner-deferred. Full
record: `GESTURE_PIPELINE_SPEC.md` §17; usage: `handinput/README.md`.

⭐⭐⭐ **NEXT BUILD IS STILL `F1` — THE CUBE'S TRANSFORM (Vector3 POSITION *and* ROTATION
QUATERNION) DRIVEN BY THE FINGERTIPS** (owner, 2026-08-24; to be specified in its own
conversation). The palm + knuckle-arc anchor is **too coarse BY DESIGN**, not
mis-tuned: it cannot express the small fingertip motions that rotate a real object
held in the hand, which is what assembly-style alignment needs. ⭐ The palm is KEPT,
demoted to a SUPPORT role — reference frame, sign, chirality. ⛔⛔ **The one trap: do
NOT build it as a rigid-body fit over palm+tips.** That arm is A10-dead twice
(B4's `PALM_AND_TIPS`, and the 9-point constellation on 2026-08-23) because finger
motion gets fitted as whole-object rotation — **which is the same physical fact this
build wants to exploit, from the other side**. Full row and the open design
questions: `PART_ONE.md` §3.1, row **F1**.

✅✅ **AND THE LAG IS FIXED AND SHIPPED FIRST (row `L1`, spec §14.3.6)** — the owner
called it *"very uncomfortable"*, and subtle fingertip control would have been
unjudgeable under it. **One constant**: the cube's slerp, a fixed **0.35 per FRAME**
since 2026-08-01, measured at **128 ms** of lag. It is now **τ = 20 ms** with
`1 − exp(−dt/τ)`, so settling is constant in real time (verified 20.0 ms across a 4×
frame-rate range) instead of moving with the room's lighting — the old form ran
111 ms in good light and 149 ms in poor. ⭐ **And the predictive orientation filter
above it was DEAD**: Horn replaced its output on **9091/9091** measured frames. It is
removed from both tools and archived in
`Resources/_archived_predictive_orientation_filter.py`.

⛔⛔ **T6 (the estimator replacements) WAS BUILT AND A10-REJECTED ON 2026-08-24 — the
yaw lean is STILL OPEN and still the owner's show-stopper.** Read T6's row and
`HANDOFF_T6_ORIENTATION_FROM_2D.md` §9 before proposing anything here: four
explanations for its failure were measured and refuted, and the project's own
premise (*"the 2D landmarks are good"*) is now amended — that was an inference from
roll, which was measured with Horn over WORLD landmarks and never tested 2D alone.
⭐ Production is untouched; `PlanarPnP` lives in `estimators()` only. The section
below is the ORIGINAL brief, kept because its diagnosis of the DEFECT (as opposed
to its proposed remedy) still stands.

⭐⭐ **NEXT BUILD WAS T6 — ORIENTATION FROM 2D, AND THE OWNER WANTED IT BEFORE ANYTHING
ELSE** (*"I want to implement the fix before anything else is built"*). The object
does not turn purely about the vertical — **it LEANS up to ~27°** at a 60–90° hand
turn, which the owner calls a show-stopper. ⭐ **The cause is PROVEN twice over**
(scaling world z slides the tilt 14.5°→0.6°; ROLL — the axis needing no depth —
measures gain 1.02 while yaw and pitch err in opposite directions), and the fix is
a **2D↔3D planar PnP** replacing the 3D↔3D Horn fit. ⛔ No MANO needed. ⭐ Full
brief: **`HANDOFF_T6_ORIENTATION_FROM_2D.md`**; design: §14.3.4.11; row: **T6**.

⭐⭐ **NEW ROW `T7`, OWNER-REQUESTED 2026-08-24 — WORLD-REFERENCED ROTATION, AND IT
IS NOT WHAT T6 FIXES.** A tilted camera makes the cube lean too, and **T6 cannot
correct it**: a planar PnP recovers pose in *camera* coordinates exactly as Horn
does. ⛔ **It was tested as an alternative cause of the current 27° lean and
REJECTED by measurement** — a fixed tilt cannot be undone by scaling world z, yet
both the in-image and out-of-plane components of the yaw axis **collapse** with k
(0.241→−0.011 and 0.072→0.000), which also bounds this rig at **≤4.2° of camera
pitch**. ⚠ **But on a phone (routinely pitched 20–40°) it is first-order: 20° of
tilt alone reproduces the entire show-stopper.** The fix is **one conjugation**,
`ΔR_world = C·ΔR_cam·C⁻¹`, and `C` is only **two DOF** (camera pitch and roll —
camera yaw is irrelevant). ⭐⭐ **OWNER DECIDED WHERE `C` COMES FROM, 2026-08-24: the
IMU was offered and DECLINED** (*"i don't want to introduce a different behavior
between desktop and mobile"*) — `C` comes from **U12's start-of-game calibration**,
identically on every platform, and **defaults to identity (level) = today's
behaviour** until then. ⛔ **So T7 ships WITH U12, not after T6** (with `C` =
identity it is a no-op), and **T6 must not anticipate it** — no `C`, no world
frame, no gravity hook inside `PlanarPnP`. ⚠ The IMU stays a recorded second-order
fallback whose trigger is specific: **a camera that MOVES DURING PLAY** (a
hand-held phone), which no start-of-game calibration can track. ⚠ Also new: **the
camera MOVED between corpus recordings**, so same-take A/B stays valid but
cross-take absolute axis numbers do not — record the tilt in `meta.json` from now
on. Rows: **T7**, and **U12** now owns the tilt alongside the FOV.

✅✅ **4.2 IS SHIPPED AND OWNER-CONFIRMED LIVE IN BOTH TOOLS (2026-08-23)** —
debug *"yes. this is working properly"*, production *"this is working fine"*.
Z-axis translation, the 3D snap gate and the world-space play volume are live; 23
golden-vector suites pass and `parity_replay` reports **no divergence**. The
production take proves Z was genuinely exercised (objects swept **0.316–0.850 m**,
10 snaps under the 3D gate, 0 play-area violations) and independently reproduced
the constant it was built on: its hand depth medians **0.502 m** against the
0.497 m corpus median. Full account: `GESTURE_PIPELINE_SPEC.md` §14.3.5; behaviour:
`GAME_RULES.md` rules 7–10; status: `PART_ONE.md` §3.1's YOU-ARE-HERE block.

⭐⭐ **The one finding worth carrying out of it — a constant that was about to be
wrong.** An object's resting depth was first set to 0.40 m on the strength of
U9's own row (*"40 cm IS the closest the operator actually works"*). **That
sentence reads the corpus's p99 palm width — it is about the CLOSEST APPROACH.**
Measured over 86 109 trusted hand-frames across 65 sessions
(`analysis/m9_working_distance.py`): median **0.497 m**. An object at 0.40 m is
reachable on 70.9% of frames; at the measured median, 91.2%. ⛔ A quarter of all
frames unable to pick anything up would have read as a **broken build**, not a
mis-sized constant. ⭐ **A constant borrowed from another row's derivation
inherits that row's QUESTION, not just its number.**

⚠ Two more that a reader will otherwise re-derive wrong: the 3D gate is an
**ellipsoid, not a sphere** (a sphere would be un-grabbable for anyone whose
hands are off the anthropometric median), and `cube.size` is now the extent at
the **resting depth only** — the centre, the clamp, the grab radius and both
renderers read `palm_geometry.projected_size_px`.

⭐ **4.1's DEPTH ESTIMATOR is wired** (`Resources/palm_depth.py`) — 4.2 drives an
object's depth from it. ⭐ **No depth calibration step is needed** — the reach
envelope measures 3.59x and the baseline is captured per grab. ⚠ 4.2 added a
SECOND estimator, `HandDepthTracker`, and the two are not redundant: the ratio
form drives a HELD object (scale cancels exactly), the absolute form answers the
snap gate's question, which has no grab to baseline against and therefore carries
a per-user scale bias. ⛔ The absolute one gates snapping and nothing else.
⚠ **4.1's `trackId` OWNERSHIP MIGRATION IS REVERTED** (`TRACK_OWNERSHIP = False`);
the wire still carries the id, and T3 is now fixed by the NARROW remap instead —
see `POSTMORTEM_4_1_IDENTITY_MIGRATION.md` and `Resources/owner_remap.py`.

**Open, deliberately not next**: the two-hand swap (spec §0.4), N8 cube-stealing
**palm-first** (routed to B5 — snap is pure proximity; only the back-of-hand and
relabel routes are closed), T1 back-of-hand rotation quality, T4 yaw/palm-sink,
N12 pitch-crossing jump, U5 occlusion coast.

✅ **RESOLVED 2026-08-22 — T3 and U7 shared one root cause, and BOTH are fixed.**
The handedness label is still **10.8% wrong**, but nothing now reads it as
identity (T3 → `owner_remap.py`) or as chirality truth (U7 → geometry). ⚠ The
lesson survives the fix and is the reusable part: **the label was doing two jobs
it was never fit for**, and patching either symptom alone fixed neither — paid for
seven times. ⚠ A third defect of the *same appearance* remained after both
(**U8**: a newly entered hand's chirality is undefined until the thumb is in
view), so "same symptom" never meant "same cause".

✅ **U6 is DECIDED — two pipelines are KEPT** (owner, 2026-08-22). So divergence is
prevented mechanically, not by refactoring: run `analysis/parity_replay.py` when
either tool's gesture logic changes, or whenever "it does not happen in
production" comes up. ⚠ One camera means the two can never run at once, so such a
claim always compares separate sessions of a possibly intermittent defect.

---

## 4. ⛔ Tried and REJECTED — do not re-propose without new evidence

This is the section that saves the most time. Each was measured, not guessed.

| what | verdict |
|---|---|
| **Pinch classification** | archived 2026-08-01; the project pivoted to snap/rotate/release |
| **MediaPipe's built-in `Open_Palm`/`Closed_Fist`** | live-tested unreliable across hand positions, **reverted** (§13.5) |
| **M2 bone-length calibration** (1.4) | **DEAD**, audited and upheld — `worldLandmarks` do not encode a pose-consistent skeleton (0/21 bones inside target) |
| **MANO / HaMeR / WiLoR** (0.5) | **licence** — non-commercial, and the game will be commercialised (N13, binding) |
| **Quaternion UKF / anisotropic covariance** (2.3) | 5 attempts, all null; audited and confirmed genuine |
| **B7 confirmation gate** | park **confirmed under a blind test** — measurable but invisible |
| **B8 quadratic optimisation** | every fit **loses to "hold the last value"** |
| **1.7 imposed skeleton** | built, then parked — cannot affect orientation *by construction* |
| **T3 client-side ownership transfer** | built, live-tested, **REVERTED** — it inferred "same hand" from POSITION, and two hands in the same place are indistinguishable by position. Re-pointed at v2's `trackId` |
| **D4 grace period** | **DECLINED** by the owner after seeing D2/D3 live. Not deferred |
| **§16.14 "SINK"** | **RETRACTED** — the metric was self-measuring |
| **N11 left/right asymmetry** | **not reproduced**; direction reversed on clean takes |
| **Post-hoc `invert_x` mirroring** | **falsified 2026-08-22** — MediaPipe is not mirror-equivariant (7.7–10 mm, 12–20°). Replaced by flipping the frame before detection |
| **Ownership keyed on the handedness label** | **replaced 2026-08-22** by the stable track id. Live A/B, 3 sessions: label orphaned a held cube 794/377/15 frames, track 0 every time |
| **A hand-side TRIGGER to keep an object off the display edge** | **built twice, reverted twice** — translation is grab-relative, so the object keeps its own offset from the hand and creeps outward on every grab-push-drop cycle. **A trigger cannot enforce an invariant**; U9 ships a positional clamp instead |
| **An ADAPTIVE edge margin (half the CURRENT palm width)** | **failed live** — the measured width collapsed 45% in ONE frame, the margin collapsed with it, and the object was carried out of frame. A threshold must not be computed from a quantity that is noisy where the threshold acts |
| **A thumb-plane-thickness gate on chirality** | **measured null, NOT shipped** — sweeping 0→7 mm changed nothing to 5 mm and was WORSE at 3–5 mm; at the production failure the bad frames sat at 11–16 mm, **above** the 8.8 mm median. Good conditioning, wrong answer |
| **Falling back to the handedness label while chirality is unconfirmed** | **measured backwards** — at track age 0 geometry is **89.7%** and the label **76.8%**. The label is WORST exactly at hand entry |
| **Temporal voting to fix a newly entered hand's chirality** | **cannot work** — the wrong value was stable for **5 consecutive** frames, so any majority picks it |
| **Resolving the two-hand chirality contradiction by trusting one hand** | **near chance** — the contradiction is real (191 of 14460 two-hand frames) but trust-the-older is 46.6%, squarer 53.4%, thicker 63.9%. **Detection yes, resolution no — suppress, do not guess** |
| **Down-weighting MediaPipe's world z to fix the rotation axis** | ⛔ **REJECTED 2026-08-23** — the k that makes yaw good doubles the pitch error. Yaw and pitch need OPPOSITE things from the same coordinate, so the whole 'weight z less' family is closed (cf. 2.3's five nulls). ⭐ It DID establish the diagnosis: the tilt is caused by world-z error |
| **The 9-point palm+tips constellation for rotation** | ⛔ **A10 REJECT 2026-08-23** — +1.4° of axis fidelity for +4.9° of p95 jitter in real handling. Its "wins in every take" reputation rested on the axis-CONTAMINATED 2026-08-04 yaw take |
| **A physical card held in the hand to remove yaw wobble** | ⚠ **the method controls the SWEEP well** (best contamination score ever measured) **but reads the TILT HIGHER** (17–19° vs the card-free 12.6–13.0°). Keep it for cleanliness, never for axis magnitude |
| **A depth calibration screen** (min/max reach) | **not needed** — absolute scale is unobservable AND cancels in the ratio form; `d0` is per-grab; the envelope is already 3.59x |
| **T6d — the ANISOTROPIC 2×2 fit** (`g(ψ) = a + b·cos2ψ + c·sin2ψ`) | ⛔⛔ **BUILT, LIVE-TESTED OVER FOUR SESSIONS, REJECTED BY THE OWNER 2026-08-24** — *"very minor improvement and I don't want to ship it"*. ⭐ **Nothing to revert: production never ran it**, every arm sat behind a toggle measured byte-identical to shipped Horn (975/975 frames). ⭐ The measured reason it was invisible: the two A/B panels' cube orientations differ by a median of **4.83°** (p90 17.4), **flat across every palm-tilt band** — below what an eye resolves on a 40–80 px cube. ⚠ The ψ finding survives as a fact about MediaPipe, not as a fix: from pixels alone a yaw take piles up at ψ≈0/180 and a pitch take at ψ≈90 |
| **The predictive / reliability-weighted orientation filter** (§13.7) | ⛔ **REMOVED 2026-08-24 as DEAD CODE, not as a failure** — it was a real fix for the Gram-Schmidt estimator it was built against (max 144° single-frame excursions), but Horn has replaced its output since 2026-08-17 on **9091/9091** measured hand-frames. Archived whole in `Resources/_archived_predictive_orientation_filter.py`. ⚠ `_reliability_alpha` was KEPT — different thing, still drives the on-screen conditioning readout |
| **A fixed PER-FRAME rotation smoothing factor** | ⛔ **REPLACED 2026-08-24 by a time constant.** 0.35/frame = 2.32 frames of settling, so the feel moved with the camera: **111 ms in good light, 149 ms in poor** (webcam auto-exposure). ⭐ The frame rate was proved camera-bound, not compute-bound, because the inter-frame gap is identical with and without a hand in view |
| **T6 — orientation from 2D (planar PnP)** | ⛔⛔ **BUILT AND A10-REJECTED 2026-08-24.** Yaw, the defect it existed to fix, gets WORSE (median/frame **13.0° → 29.8°**); pitch **gain is fixed** (0.74 → 0.99). Four explanations tested and all refuted — the edge-on planar degeneracy, twin-branch flips, model shape, and the assumed FOV. ⭐ **It amends the project's own diagnosis**: *"the 2D landmarks are good"* was an INFERENCE from roll, and roll was measured with Horn over WORLD landmarks — T6 is the first direct test of 2D-only pose and it is worse. Code stays in `estimators()`; call sites unchanged |

⚠ **Retractions are kept on purpose.** A claim that was overturned is more useful
than one silently deleted — several were overturned *twice*. When a spec section
contradicts a later one, **the later one wins**; check for a `14.3.x`-style
follow-up before acting on any older section.

---

## 5. Decisions

**Taken and binding**: build the perception layer in Python under `Local_pc/`;
no non-commercially-licensed dependencies (N13); recordings stay on E:;
rotation stays permanently ungated by open-palm; `GAME_RULES.md` rule 2 is the
dropout behaviour of record.

⚠⚠ **SHIPPING, not yet started (queue U10/U11, 2026-08-23)**: **camera privacy is
the real exposure, not licensing.** Everything runs client-side and no frames
leave the device — the corpus is landmarks-only and never held a pixel — **but
that has to be WRITTEN DOWN**: a privacy policy saying exactly that, per-store
camera declarations (Steam / App Store / Google Play each differ) and platform
permission strings.

✅⛔ **AUDIENCE DECIDED (owner, 2026-08-23): ALL PUBLIC, INCLUDING YOUTH — so COPPA
and GDPR-K are LIVE**, and Play's Families / Apple's Kids Category apply. Three
things follow that are **binding on architecture, not preferences**: **no
third-party analytics or ads SDKs**; **the local-only, no-transmission design is
now load-bearing for compliance** (anything that transmits is a compliance event,
raised before it is built); and **`VISION_RECORD=1` must be compile-time-disabled
in shipping builds**, not merely default-off. ⛔ Professional advice is not
optional here — but those three are actionable today and are what protects the
position.

✅ Already verified, no action: the MediaPipe model AND its WASM runtime are
bundled, not hot-linked, on both platforms (N13). ⚠ 16 MB of dead model files to
strip at package time (U11).

⭐ **DECIDED 2026-08-23**: **4.4 (release trigger) and B5 (grab from finger arcs) are ONE
project, not two queue items** — same mechanism from both ends, same finger
signal, and N8 (stealing an object) rides on it. The whole **5.x block is an
optional MENU for future improvement**, nothing scheduled and nothing waiting on
it. And a **start-of-game calibration step is recorded as queue U12** — to build
later, when a real game exists and playability starts to matter, NOT now.
⚠ U12 is NOT the depth calibration that 4.1 measured as unnecessary; read its row
before reopening that.

**Still the owner's to make**: U1 open-palm/fist priority; U2 real 3D-file import
(**blocked on the platform choice, not on effort** — do not build it against the
pygame renderer); U3 the web/mobile port; and, new on 2026-08-22, whether cube
ownership should follow the *physical* hand — today the cube the pipeline calls
"left" is driven by the operator's right hand, which the `trackId` migration in
4.1 would dissolve.

---

## 6. The rules that bind every build

1. **A10 — measure or revert.** Every module must show a measured improvement on
   the M0 metrics via replay A/B on identical recorded input, or be reverted. A
   null result is recorded, not shipped hopefully.
2. **An anchor metric must not share an expression with the anchor** (B4). A
   metric built from the thing it is judging measures nothing.
3. **Blind tests use the balanced `--blind-series`** (B4).
4. **Never key a stream on the raw MediaPipe label** — build via `build_v2()`.
5. **N6 — shared modules are imported, never copied.**
6. **Golden vectors BEFORE a port exists**, not after (U3 precedent — the very
   first run caught a real banker's-rounding bug).
7. **Check the licence before proposing any model**, and state it (N13).
8. ⭐ **Anything that needs an object's ON-SCREEN size uses
   `palm_geometry.projected_size_px`, NEVER `object.size`** (4.2, owner-captured
   2026-08-23). Since Z-translation shipped, `size` means only *"how big it is at
   the resting depth"*; the real extent depends on where the object currently is.
   This binds the centre, the play-area clamp, the grab radius and both
   renderers. ⚠ `_top_left_for_center` was DELETED from both tools for exactly
   this reason — it converted with the nominal size, and a surviving copy makes
   an object drift sideways as it moves in depth. Do not reintroduce it.

---

## 7. Running and verifying

| | |
|---|---|
| production | `launch.bat` (or `PythonApp_Main.py`) |
| debug, one window mirroring production | `debug_snap.bat` / `LiveSnapDebug.py` |
| ⭐ tune the **rotation smoothing** by feel | `LiveSnapDebug.py` — a second window carries one slider, `SMOOTH ms` (0–150, and its integer IS τ in ms). `--smooth-ms N`, `--no-sliders` |
| ⭐ the **lag A/B** — same estimator, smoothing the only difference | `LiveSnapDebug.py --slerp-ab` — panel 1 = the old per-frame 0.35, panel 2 = the τ slider |
| debug + record (cube visible, writes a session) | `LiveSnapDebug.py --record` |
| record a scripted take | `record_perception_sequence.bat <sequence>` |
| ⚠ wake the capture drive first | `wake_e_drive.py` |
| record a PRODUCTION session | `VISION_RECORD=1 VISION_RECORD_TAG=<name> ... PythonApp_Main.py` — same JSONL schema, so every `analysis/` harness reads it |
| the 4.1/T3 ownership A/B rig | `LiveSnapDebug.py --ownership-ab` — two panels, label vs track keying |
| chirality guard (run after ANY mirroring/handedness change) | `VerifyChiralityFixture.py` |
| the back-of-hand steal / rule-3 audit | `analysis/n8_back_steal.py` — silent handovers, back-steals, back-snaps, with COVERAGE printed |
| the T3 remap A/B on a recording | `analysis/t3_remap_ab.py` |
| re-derive U8's window if the frame rate moves | `analysis/u8_entry_settling.py` |
| the two recorders must not drift apart | `analysis/verify_recorder_parity.py` |
| the play area / volume (an object may never reach the display edge) | `analysis/verify_play_area.py` |
| ⭐ the same invariant read STRAIGHT from a recording, schema-aware | `analysis/verify_play_volume_from_recording.py` |
| where the operator's hand actually sits, and whether an object is reachable | `analysis/m9_working_distance.py` |
| golden vectors | `analysis/verify_*.py` — **26 suites, all passing** |
| ⭐ the audit's guards (tags, camera stalls, loopback, the `meta` clamp) | `analysis/verify_hardening.py` — 51 checks |
| ⭐ the INPUT SYSTEM: boundary, contract, vectors, action trace | `analysis/verify_handinput.py` — 95 checks |
| record live action events from either tool | `HANDINPUT_TRACE=1 HANDINPUT_TRACE_TAG=<name> …` |
| write the input system out as a standalone folder | `handinput/export_package.py <target-dir>` |
| ⚠ known, pre-existing and NOT from the input system | `analysis/verify_planar_pnp.py` passes all its vectors then dies printing a `⚠` under cp1252. Fails identically before the change |

⚠ **One webcam, and DSHOW is exclusive across processes** — production and the
debug tool cannot run at the same time. Compare them back-to-back. (Two capture
handles inside ONE process both succeed; that is a misleading test.)

⚠ **Fixtures run on RECORDINGS, not the live server.** §13.6.1 shipped inverted
while passing an "end-to-end confirmed" claim. Automated green is necessary, not
sufficient — a live look is what closes a change.

---

## 8. Security posture (audited 2026-08-25 — `GESTURE_PIPELINE_SPEC.md` §18)

⭐⭐ **The claims the store declarations and the COPPA/GDPR-K position rest on are
now CHECKED, not assumed** — and the strongest one is a negative: **there is no
network egress anywhere in the pipeline.** Not one HTTP call, so *"nothing leaves
the device"* is verifiable **by absence**. Also: no `eval`/`exec`/`pickle`/
`shell=True`/`yaml.load` (no deserialisation or injection surface), both
`subprocess.Popen` calls in list form, models loaded by absolute path.

| control | where |
|---|---|
| the landmark socket is **loopback-only**, refused otherwise | `Server.py` / `Client.py`, override `--allow-remote` **only as a deliberate transmission decision** |
| a session tag can never escape the capture root | `Resources/session_paths.py`, shared by both recorders |
| the wire cannot size an allocation or inject a non-number | `PythonApp_Main.receive_float_array` |
| a camera stall does not end a take | `capture_policy.py`, shared by both capture loops |

⛔ **Four open items are DECISIONS, not omissions.** Each has a queue row saying
what was measured, what was deliberately not done, and what would close it:

| row | state |
|---|---|
| **`SEC3`** | ⛔ **a face detector runs every frame and nothing consumes it** (`elif datatype == "face": pass`), and the debug tool has none at all. `--face off` exists; **the default was deliberately not flipped** — turning it off is visible in the preview, so it is the owner's call |
| **`SEC2`** | ⭐ **half done**: `requirements.lock.txt` now RECORDS the environment, because 24 of 26 packages float and had already drifted past what mediapipe 0.10.14 was built against (numpy 2.4.6, OpenCV 5.0). Hash pinning + the licence inventory **N13** needs are packaging work (U10/U11) |
| **`SEC5`** | ⚠ both tools feed MediaPipe a fake 33 ms clock. ⛔ **The first write-up of this overstated its effect and was retracted the same day** (§18.4) — the clock is wrong, the output effect is **unmeasured**. ⚠ The corpus cannot test it (no pixels); the test is two detectors on the same frames |
| **`SEC4`** | the debug recorder buffers a whole session in RAM where production streams — not restructured on the eve of a live take |

⚠⚠ **The reusable lesson from `SEC5` is the audit's own**: a mechanism that
sounds right became a recorded fact for one day. **An audit is not exempt from
A10 because its other findings are code-shaped.**
