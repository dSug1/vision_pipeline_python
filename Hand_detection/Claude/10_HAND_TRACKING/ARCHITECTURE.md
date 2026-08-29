# ARCHITECTURE — what the system is, and how to run it

> **STATUS** · live · **OWNS** · the process/module layout, and every command
> **READ IF** · you are about to change code, run a tool, or verify a change
> **LAST VERIFIED** · 2026-08-25
> **SOURCED FROM** · the old `README.md` §2 and §7 (verbatim in
> [`../_archive/README_2026-08-25_pre_reorg.md`](../_archive/README_2026-08-25_pre_reorg.md))

## The shape of it

Two Python processes over a loopback socket, plus one debug tool that
deliberately mirrors production.

```
webcam
  │
  ▼
Local_pc/Python_Server_MediaPipe_vision_pipeline/VisionPipeline.py   ── SERVER
  ├─ cv2.flip  ⭐ MIRRORS THE FRAME BEFORE DETECTION (§14.3.4.3)
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
strays. ⚠ Each script also appears **twice** in the process list — the `.venv`
python here is a Windows-Store redirector that re-launches the base interpreter.
Benign.

## The estimator layer

Client `Resources/`, **stdlib-only and numpy-free by contract** so it can be
ported by transliteration ([`../00_CORE/CONSTRAINTS.md`](../00_CORE/CONSTRAINTS.md) §2):

`camera_mount` (⭐ where the camera sits; every camera-dependent sign derives from it) ·
`lean_trim` (⭐ `V2`'s swing/twist yaw-lean correction, gains 0.66/0.66) ·
`palm_geometry` · `palm_rotation` (Horn, and `PlanarPnP` for A/B only) ·
`palm_depth` · `planar_pnp` · `hand_blocks` · `hand_state` · `palm_anchor` ·
`hand_skeleton` · `frame_gate` · `block_predictor` · `confirmation_gate` ·
`owner_remap`

⭐ **`N6` — shared, never copied.** Any module both tools need is **imported** by
both (`hand_identity` lives in the server's `Resources/` and the debug tool adds
it to `sys.path`). A copy is how the two drift.

⚠ Archived, not deleted: `Resources/_archived_predictive_orientation_filter.py`.

## Two depth estimators, and they are not redundant

* `DepthRatioTracker` — **ratio** form, drives a **held** object. Scale cancels
  exactly, baselined per grab, so **no calibration is needed**.
* `HandDepthTracker` — **absolute** form, answers the **snap gate**'s question,
  which has no grab to baseline against and therefore carries a per-user scale
  bias. ⛔ It gates snapping and nothing else.

## Where the other pieces live

| | |
|---|---|
| **`Web/`** | Part Zero-bis only — the browser proof of the minimal loop. Nothing from Part One runs there; that is `U3` |
| **the corpus** | `E:\Python\Recordings for vision_pipeline\…` — 415 files, 33+ sessions. ⚠ Never `--local`. ⛔ **No image data, ever** |
| **the evidence index** | `Local_pc/Movement_with_hand_detection/analysis/README.md` — every claim → the script that produced it |
| **the input system's own doc** | `Local_pc/Movement_with_hand_detection/handinput/README.md` — kept beside the code by `N6`, linked not copied |

---

## Running

| | |
|---|---|
| production | `launch.bat` (or `PythonApp_Main.py`) |
| ⭐ the CAMERA MOUNT (`V1`, shipped 2026-08-28) | **the default is `facing_user`** — nothing to set. ⛔ `CAMERA_MOUNT=legacy` is a DIAGNOSTIC BASELINE only: it reproduces the pre-2026-08-28 build bit-for-bit, which is what `A10` and `parity_replay` compare against. `head_worn` is for vision glasses and ships UNVALIDATED — no glasses, no head-worn corpus |
| debug, one window mirroring production | `debug_snap.bat` / `LiveSnapDebug.py` |
| ⭐ tune **rotation smoothing** by feel | `LiveSnapDebug.py` — a second window carries one slider, `SMOOTH ms` (0–150; its integer **is** τ in ms). `--smooth-ms N`, `--no-sliders` |
| ⭐ the **lag A/B** — same estimator, smoothing the only difference | `LiveSnapDebug.py --slerp-ab` — panel 1 = the old per-frame 0.35, panel 2 = the τ slider |
| debug + record (cube visible, writes a session) | `LiveSnapDebug.py --record` |
| record a scripted take | `tools
ecord_perception_sequence.bat <sequence>` |
| ⚠ wake the capture drive first | `tools/wake_e_drive.py` |
| record a PRODUCTION session | `VISION_RECORD=1 VISION_RECORD_TAG=<name> … PythonApp_Main.py` — same JSONL schema, so every `analysis/` harness reads it |
| the ownership A/B rig | `LiveSnapDebug.py --ownership-ab` — two panels, label vs track keying |
| record live action events from either tool | `HANDINPUT_TRACE=1 HANDINPUT_TRACE_TAG=<name> …` |
| write the input system out as a standalone folder | `handinput/export_package.py <target-dir>` |

⚠ **One webcam, and DSHOW is exclusive across processes** — production and the
debug tool **cannot run at the same time**. Compare them back-to-back. (Two
capture handles inside *one* process both succeed; that is a misleading test.)

## Verifying

| | |
|---|---|
| golden vectors | `analysis/verify_*.py` — **26 suites, all passing** |
| the two tools must still agree | `analysis/parity_replay.py` |
| ⭐ the CAMERA MOUNT's wiring, on a recording (no camera needed) | `analysis/mount_ab.py <session>` — does the switch take EFFECT, and in which direction |
| ⛔ **the LEAN TRIM's gate** — run BEFORE quoting any lean number | `analysis/lean_trim_ab.py <session>` — per-frame orientation jump vs shipped Horn, judged PER TAKE |
| what contaminates yaw, and whether depth matters | `analysis/lean_decomposition.py <session>` |
| the slider panel's wiring (arity, globals, descriptions) | `analysis/verify_slider_wiring.py` — static AND it executes both slider functions |
| chirality guard (after ANY mirroring/handedness change) | `tools/VerifyChiralityFixture.py` |
| the audit's guards (tags, camera stalls, loopback, the `meta` clamp) | `analysis/verify_hardening.py` — 51 checks |
| the INPUT SYSTEM: boundary, contract, vectors, action trace | `analysis/verify_handinput.py` — 96 checks |
| the two recorders must not drift apart | `analysis/verify_recorder_parity.py` |
| the play area / volume | `analysis/verify_play_area.py` |
| ⭐ the same invariant read STRAIGHT from a recording | `analysis/verify_play_volume_from_recording.py` |
| the back-of-hand steal / rule-3 audit | `analysis/n8_back_steal.py` — with COVERAGE printed |
| the T3 remap A/B on a recording | `analysis/t3_remap_ab.py` |
| re-derive U8's window if the frame rate moves | `analysis/u8_entry_settling.py` |
| where the operator's hand actually sits | `analysis/m9_working_distance.py` |
| rotation axis fidelity (yaw + pitch / roll / jitter) | `analysis/t5i_zscale_sweep.py`, `t5j_roll_axis.py`, `t5h_constellation_ab.py` |

⚠⚠ **Fixtures run on RECORDINGS, not the live server**, and §13.6.1 shipped
**inverted** while passing an "end-to-end confirmed" claim. **Automated green is
necessary, not sufficient — a live look in both tools is what closes a change.**
See [`../00_CORE/METHOD.md`](../00_CORE/METHOD.md).
