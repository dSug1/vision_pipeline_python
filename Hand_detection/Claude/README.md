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
| **start a build session** | this file → `PART_ONE.md` §3.1's "YOU ARE HERE" block → that item's row |
| know **why** something failed | `GESTURE_PIPELINE_SPEC.md` — the authoritative record of what failed and why |
| know the **forward design** below the gesture layer | `PERCEPTION_LAYER_SPEC.md` (⚠ read its §0.1 amendment log BEFORE any module body) |
| know how the **game behaves** | `GAME_RULES.md` — the behavioural statement of record |
| find the **evidence** for a number | `Local_pc/Movement_with_hand_detection/analysis/README.md` maps every claim to the script that produced it |

⚠ `Specification.md` is the ORIGINAL build handoff (Part Zero era). Its §11 build
order is historical — **the queue superseded it.** Keep it for the goal,
constraints and prior-art scan; do not take build order from it.

⚠ `HANDOFF_*.md` are per-session briefs, now closed. `_archived_old_*` is dead.

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
  └─ Resources/CubeWindow.py              ── pygame renderer (mesh-generic)

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
| **A depth calibration screen** (min/max reach) | **not needed** — absolute scale is unobservable AND cancels in the ratio form; `d0` is per-grab; the envelope is already 3.59x |

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

---

## 7. Running and verifying

| | |
|---|---|
| production | `launch.bat` (or `PythonApp_Main.py`) |
| debug, one window mirroring production | `debug_snap.bat` / `LiveSnapDebug.py` |
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
| golden vectors | `analysis/verify_*.py` — 23 suites |

⚠ **One webcam, and DSHOW is exclusive across processes** — production and the
debug tool cannot run at the same time. Compare them back-to-back. (Two capture
handles inside ONE process both succeed; that is a misleading test.)

⚠ **Fixtures run on RECORDINGS, not the live server.** §13.6.1 shipped inverted
while passing an "end-to-end confirmed" claim. Automated green is necessary, not
sufficient — a live look is what closes a change.
