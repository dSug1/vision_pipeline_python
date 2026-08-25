# GLOSSARY — the project's private vocabulary

> **STATUS** · live · **OWNS** · what the codenames mean
> **READ IF** · a document uses a term you cannot decode
> **LAST VERIFIED** · 2026-08-25

The docs are dense with local shorthand. This is the decoder ring; the authority
for each item is its queue dossier or spec section.

## Item prefixes in the queue

| prefix | meaning |
|---|---|
| `0.x`–`5.x` | the perception-layer phases (instrumentation → singularities → identity → latency → features → optional) |
| `M0`–`M10` | the perception-layer **modules** from `PERCEPTION_LAYER_SPEC.md`; a queue row usually implements one |
| `T1`–`T7` | pipeline **defects** carried over from the gesture pipeline |
| `B1`–`B8` | the **block representation** phase (palm transform + finger arcs) |
| `D0`–`D4` | **dropout** mitigation |
| `N1`–`N18` | items **surfaced by measurement**, not planned |
| `S1`–`S12` | items adopted from the **literature audit**; each folded into a numbered row |
| `U1`–`U12` | **unscheduled**; owner's call or later |
| `IS1`–`IS4` | the **input system** |
| `SEC1`–`SEC5` | the **security / robustness audit** |
| `L1`, `F1` | one-off rows: rotation **lag**, and the **fingertip** transform |
| `A1`–`A10` | amendments/rules in the perception spec — **`A10` is the binding one** (measure or revert) |

## Mechanisms

| term | what it is |
|---|---|
| **DR-1** | track hand identity by **position**, server-side, overriding MediaPipe's per-frame handedness label. `Resources/hand_identity.py` |
| **DR-2** | freeze the palm-facing **sign** through the edge-on band, where it is genuinely ill-posed |
| **Horn** | the shipped rotation estimator: a least-squares rigid fit (Horn/Kabsch) over the 5-point palm, grab-referenced. Exact to 0.000° on synthetic input |
| **`horn-palm`** | the shipped **anchor**: Horn over `PALM_LANDMARKS = (0, 5, 9, 13, 17)` — wrist + four MCPs |
| **chirality** | which way the palm faces / which hand it is, derived from **geometry** (`signed_palm_volume`), not from the label. `U7` |
| **the yaw lean** | the open show-stopper: turning the hand like a page tips the object out of upright, ~27° at 60–90°. ⚠ **Never state it as "13° of axis deviation"** |
| **grab-relative** | translation carries the object's own offset from the hand at grab time, rather than snapping it to the hand |
| **the play volume** | the world-space region an object may occupy — the frustum inset by half a hand breadth (42.5 mm) |
| **golden vectors** | hand-checkable `analysis/verify_*.py` fixtures, written before the port |
| **parity replay** | `analysis/parity_replay.py` — proves production and the debug tool still compute the same thing |
| **A10 reject** | built, measured, did not beat the baseline, **reverted**. Not a failure to record — a result |

## Files and tools

| | |
|---|---|
| **production** | `PythonApp_Main.py` / `launch.bat` — server + client over a loopback socket |
| **the debug tool** | `LiveSnapDebug.py` / `debug_snap.bat` — one window, no socket, deliberately mirrors production |
| **`handinput/`** | the standalone input-system package: actions, phases, callbacks, `HandState` v2 |
| **`analysis/`** | every harness; its `README.md` maps each claim to the script that produced it |
| **the corpus** | 415 recording files, 33+ perception sessions, on `E:`. **Landmarks only — never any pixels** |
| **a "take"** | one recorded session, named `YYYY-MM-DD_HHMMSS_<tag>`, with a `meta.json` the operator annotates |
