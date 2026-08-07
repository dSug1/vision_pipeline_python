# HANDOFF — the six-arm anchor/rotation decision

**Written 2026-08-07 for a fresh conversation.** Self-contained: read this, run
the session, decide, wire. You should not need to re-derive anything below.

> ⚠ **This is NOT a TODO list.** The build queue stays `PART_ONE.md` §3.1, whose
> **B4** row points here. This file holds the *session plan and the decision
> criteria* for that one row.

---

## 0. What is already true (do not re-measure)

Three things were built, verified and measured on **seven purpose-built takes**
(2026-08-06/07) — the first in this project that contain the conditions the
anchor argument is about. §16.4 measured this on takes containing neither a
sustained yaw nor a pitch crossing and produced a confident wrong answer that
§16.5 had to overturn; that hole is now closed.

| thing | where | status |
|---|---|---|
| **ARM B** — 2D palm-frame anchor | `Resources/palm_anchor.Arm2D`, §16.14 | built, 27 golden vectors |
| **HORN** — least-squares rotation | `Resources/palm_rotation.py`, §16.15 | built, 25 golden vectors |
| **B7** — confirmation gate | `Resources/confirmation_gate.py`, §16.9.1 | ⛔ **PARKED** by the owner |

**ARM B kills the systematic sink on every axis** — yaw 0.000, pitch −0.000,
depth −0.001, back-of-hand 0.000 — against §14.1's −0.656 / **−0.807** / −0.589 /
−0.083. Cost: p95 jitter +30–70% (unchanged on depth); the worst **still-hand**
step does not degrade.

**HORN cuts the held cube's worst ORIENTATION step** 39.94° → 9.64° on pitch and
58.86° → 8.40° at back-of-hand (still-hand 36.54° → 3.48°).

⚠ **Nothing is in production. A7 holds: §14.1 does not change until the owner
accepts a live look.** All of the above is *replay* evidence, one operator, one
camera, one session.

---

## 1. The session to run — the owner drives, you record and analyse

The owner runs the tool; **you cannot open GUI windows on their desktop** (tried,
repeatedly — a spawned process runs but its windows never surface). Give the
command, let them run it, then analyse.

```
debug_prediction.bat --arms 6 --sequence <take_name> --prompt "<instruction>"
```

Six windows, 3 rows × 2 columns, scale auto-fits:

| | no gate | + B7 gate | |
|---|---|---|---|
| **row 1** | §14.1, shipped rotation | + B7 | production today |
| **row 2** | **ARM B**, shipped rotation | + B7 | anchor changed |
| **row 3** | **ARM B + HORN** | + B7 | rotation changed |

⭐ **Each row is a one-variable change on the row above, verified not assumed**:
the anchor moves ONLY cube position, the rotation estimator moves ONLY cube
orientation (pitch take: row 1→3 position 5.09→8.11 with orientation identical
at 6.22/37.57; row 3→5 position identical at 8.11 with orientation 6.22→3.82).
**Nothing leaks between rows**, so a visible difference has exactly one cause.

### The takes to record

⚠ **Hold a cube throughout every take. One hand only. Keep it fully in frame.**
The tool counts down 3 s (not recorded, trackers warm up) then shows `REC 12.3s`.
The first 10 s and last 7 s are excluded from analysis automatically.

| # | `--sequence` | what to do | why |
|---|---|---|---|
| 1 | `six_pitch_crossing` | ⭐ nod from the **wrist only**, fingers up → through horizontal → down, ~4 s per half-cycle, 10–12 cycles | **the target defect** |
| 2 | `six_yaw_hold` | slow yaw to edge-on and back, ~4 s per half-cycle, 10–12 cycles | the other sink axis |
| 3 | `six_back_of_hand` | palm-away and back, ~2 s dwell at back-of-hand, 8–10 cycles | where §0.18 says the sensor floors |
| 4 | `six_free_play` | ordinary game-like grabbing, moving, rotating, releasing | ⚠ the acceptance test the metrics cannot replace |

~60 s each, `q` to stop. Fingers relaxed and still on takes 1–3 (take 3 of the
2026-08-07 set achieved arc spans of 0.12; that is the benchmark).

### Then

```
.venv/Scripts/python.exe analysis/b4_six_arm_verdict.py
```

It scores all six arms **from the live recording — no replay**, per take, and
ranks by |sink| with jitter as the tie-break.

---

## 2. How to decide — fixed BEFORE the data arrives

**Ship the row that minimises the SINK on the pitch take**, provided:

1. its **still-hand** position step is not materially worse than §14.1's;
2. its cube **orientation** max is not worse than §14.1's;
3. the owner accepts how it looks in `six_free_play`.

⭐ **Sink first, jitter second — and this ordering is not negotiable.** §16.5:
*"a systematic drift is the defect the operator actually reported; jitter is
not."* A row that wins on jitter and loses on sink has not won.

⚠ **The owner's eye outranks the table.** B7 passed every criterion that had been
measured against observable harm and was still parked, correctly, because the
improvement was not visible. Ask what they saw before presenting a ranking.

### Then wire it

- **Debug**: already wired — `debug_prediction.bat`, rows 2 and 3.
- **Production**: `Resources/HandsTriggeredActions.py` (+ `CubeWindow.py`). ⚠ It
  carries its OWN copy of the snap/translate logic, deliberately duplicated from
  `LiveSnapDebug.py`. Both must change together or they silently diverge — that
  duplication already produced the §13.6.1 handedness inversion.
- ⚠ **A7**: §14.1 must not be modified until this decision is accepted.

---

## 3. ⚠⚠ WHAT THE 2D ANCHOR WILL COST LATER — read before shipping it

Arm B is **2D by design and that is why it wins** (§16.14: the 3D-native variant
rides the palm quaternion, which degenerates at edge-on — pitch p95 27.80 vs
arm B's 8.11). But 2D has two known future costs, and they are cheap now and
expensive later.

### 3.1 The Z-axis (queue item: Z-axis translation, designed 2026-08-01)

Arm B freezes `R = (d·ex/s, d·ey/s)` — a **2-vector in palm-frame units**. It has
no z component, so **a cube cannot be held in front of or behind the palm.**

When Z arrives, three changes:

| | now | with Z |
|---|---|---|
| `R` | 2-vector `(a, b)` | **3-vector `(a, b, c)`** — c is the out-of-plane offset |
| frame | `ex`, `ey` from pixels | needs a third axis: `ez = ex × ey` in a 3D palm frame |
| scale | palm width, px | a real projection |

⭐ **The single decision that makes this cheap: `R` IS ALREADY SCALE-FREE**, in
palm widths rather than pixels. That is what survives the transition; a pixel
offset would not. Adding a third component is additive.

⚠ **But the third axis reintroduces exactly what arm B avoids.** `ez` can only
come from the palm's 3D reconstruction — the channel that degenerates at edge-on.
So the Z retrofit is **not** "add a component": it is *"add a component whose
axis is unreliable in precisely the band arm B was built to survive."*
`Resources/palm_anchor.PalmAnchor` (the 3D-native class, kept, measured, not
recommended) is the record of what that costs — pitch still-max 36.43 vs arm B's
4.64. Plan for `c` to need its own reliability treatment (freeze in the edge-on
band, à la DR-2), not just a slot in a tuple.

⛔ **And the real blocker is unchanged and is NOT the formula: absolute depth.**
MediaPipe's world landmarks are hand-RELATIVE — metric shape, origin at the hand,
no world position — so the cube's depth does not exist anywhere in the data.
Every anchor design faces this identically, including §14.1's.

### 3.2 The web/mobile port (target: iOS/Android/Windows)

`palm_anchor.py` and `palm_rotation.py` already meet the port contract —
**stdlib only, numpy-free, deterministic, no side effects**, same as
`palm_geometry.py` / `hand_identity.py`. Three things to carry across:

1. ⭐ **Golden vectors before the port exists, not after** (queue U3). They are
   in `analysis/verify_palm_anchor.py` (27) and `verify_palm_rotation.py` (25).
   A reimplementation is correct when it reproduces them and **untrusted until it
   does**. ⚠ Do not edit the expectations to match a port — that discipline
   already caught a real banker's-vs-half-up rounding divergence.
2. ⚠ **`palm_rotation` contains a Jacobi eigen-decomposition.** It is the one
   numerically delicate thing in either module. Power iteration was tried and is
   WRONG (the positivity shift drives λ₂/λ₁ → 1; up to 2.0 of element error).
   A port that "simplifies" it back will silently return wrong rotations at large
   angles — `verify_palm_rotation.py` §1 is the test that catches it.
3. ⭐ **Horn, not SVD.** A quaternion cannot express a reflection, so handedness
   cannot silently invert. A port that swaps in an SVD-Kabsch **must** add the
   `det` sign correction; §13.6.1 shipped that bug once. `verify_palm_rotation.py`
   §4 proves the property on mirrored input (§0.9: a physical right hand is
   labelled "Left").

⚠ **JS `Math.round` is half-up, Python's `round()` is banker's.** Neither module
rounds today. If a port adds rounding, use `hand_identity._round_half_up`'s
convention.

---

## 4. Where everything is

| file | role |
|---|---|
| `Resources/palm_anchor.py` | ⭐ `Arm2D` = **arm B, the winner**. `PalmAnchor` = the 3D-native null result, kept |
| `Resources/palm_rotation.py` | ⭐ Horn least-squares rotation, chirality-safe by construction |
| `Resources/confirmation_gate.py` | ⛔ B7, parked; revive config in its docstring |
| `LiveBlockPredictionDebug.py` | the six-window tool, records all six arms |
| `analysis/b4_six_arm_verdict.py` | ⭐ **tomorrow's script** — scores six live arms, per take |
| `analysis/b4_anchor_rotation_ab.py` | the offline replay A/B (§16.14/§16.15) |
| `analysis/verify_palm_anchor.py` | 27 golden vectors incl. arm B and the Z reduction |
| `analysis/verify_palm_rotation.py` | 25 golden vectors incl. chirality |

**Takes**: `E:\Python\Recordings for vision_pipeline\Recordings_anchor_study`
⚠ Written **local-first** (`%LOCALAPPDATA%\vision_pipeline_staging`) then
migrated — E: drops out mid-session and cost a completed take once. If a capture
root ever refuses writes, **test its parent directories before blaming the
drive**: it was one corrupted directory entry, not the volume.

---

## 5. ⚠ Traps this session already paid for — do not re-pay them

1. **The trim removes the grab.** A replay fed trimmed records never acquires a
   cube and returns all-NaN. Replay the FULL take, gate the metrics by timestamp.
   (`b4_six_arm_verdict.py` avoids this entirely — the arms ran live.)
2. **Stale loop variables.** A leaked `raw`/`win` made seven takes print
   IDENTICAL rows, which reads like a finding. There is now an assertion.
3. **Do not invent an axis metric.** `edge_on_measure` drops under both yaw and
   pitch; an `e1.z` classifier reads frame *degeneracy* as yaw and mislabelled a
   pure pitch take. **The take name is ground truth.**
4. **A classifier that shares an expression with the thing it judges measures
   itself** — that produced a triumphant "100.0% teleport" that meant nothing.
5. **Ask what level a criterion is evaluated at.** Two of B7's four criteria were
   measured one level above the defect and both verdicts inverted when measured
   on the cube.
