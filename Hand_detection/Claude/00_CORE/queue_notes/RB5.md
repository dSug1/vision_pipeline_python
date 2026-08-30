# `RB5` — the delta, integrated, no filters

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ⭐ SPECIFIED + BUILT 2026-08-30 (law, gate, 85 golden vectors, 2 harnesses) · ⛔ UNCALIBRATED — the take is owed, then wiring, then the live look · **SUB** · HAND · **KIND** · perception

Design of record:
[`../../10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`](../../10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md).

---

## 2026-08-29 — opened by the rebuild

> **Owner:** *"I think we have patched too much this script … I want to build the
> control by hand detection delta increment from scratch. Strip all the filters and
> multiplicators, etc.: we will rebuild them as we need them."*

⛔⛔ **What justified a rebuild rather than another fix**: the composite mapping had
become a **REFLECTION**. `camera_mount` reversed pitch+yaw, `delta_orbit.AXIS_SIGN`
reversed pitch back — net, yaw reversed alone, det −1. A rigid hand→object
correspondence cannot do that. Every layer was locally reasonable and the stack was
not: `METHOD`'s *no heuristic pile-up*, arriving in the one place nobody measured —
the composition.

See the spec for the full design. This dossier carries what is specific to `RB5`.

---

## 2026-08-30 — ⭐⭐⭐ THE CONTROL LAW, SPECIFIED BY THE OWNER

Full design: [`../../10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`](../../10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md)
§8sexies. This dossier carries the decisions and the reasoning behind them.

> **Owner, 2026-08-30:** *"the user hand shall provide inputs when the hand is in
> these ranges (convention: 0 degree is vertical, palm facing camera when camera is
> facing user): pitch 15 to 50 · yaw 0 to 60 · roll −45 to +45. These ranges shall
> control the cube's ranges: pitch −90 to +90 · yaw −90 to +90 · roll −90 to +90
> (similar to a mouse in 2d: moving the mouse a couple of mm drives the cursor across
> the screen). When the hand is outside these ranges, the delta increment shall not
> fire (smoothly and rapidly decaying to zero gain). For the moment, do not build two
> different gains based on velocity of hand rotation: just fix one matrix of gains,
> independently of hand's rotation speed. No fine vs. rapid coarse rotation control."*

### What it settles, and what it deletes

⭐ It answers `DO4`'s **one open number** — the outer edge — by **declaration**
instead of by the wide-range take that was deferred (*"we will record wide-range
later on"*). ⚠ So the edges are the owner's felt preference, not a measurement, and
should be read that way if a later take contradicts them.

⛔⛔ **`DO2`'s rate curve is DELETED, not deferred** — *"no fine vs. rapid coarse
rotation control"*. `SPEC_DELTA_ORBIT.md` §6 (the three sliders) and §7 (*"the curve
IS the clutch"*) are superseded. **Grab / release becomes the only clutch**, and
±90° per axis is the whole travel available in one grab.

### The four ambiguities, and the owner's answers

| # | the fork | answer | what it changes |
|---|---|---|---|
| 1 | absolute pose mapping vs integrated delta | ⭐ **integrated delta, mouse-like** | a closed gate CLUTCHES; error integrates, so drift is real |
| 2 | window numbers = real angles or estimator readings | ⭐ **REAL hand angles** | the build must MEASURE the real→reading map; the numbers do not go into the code verbatim |
| 3 | one axis out of range | ⭐ **zero that axis only** | keeps yaw and roll alive while pitch sits below its window — which matters, because the pitch window excludes neutral |
| 4 | pitch 15–50 excludes neutral | ⭐ **intended**; `+` = fingertips toward the camera, palm tilting UP | no pitch input from a resting grip until the hand pitches up |

⚠ **Why 2 is not a formality.** Three scales are in play — the real angle, the pose
gate's palm-normal reading, and Horn's delta — and the last two are compressed
against the first by **different, non-constant** amounts (~80° real yaw reads ~60°;
the declared zero reads −12°/−14°; Horn's yaw gain ramps ~0.5→1.2). ⛔ So `180/35`
is the gain in real-hand degrees and is **wrong** applied to a compressed delta. The
implemented gain is `180° ÷ (estimator degrees the real window spans)`, measured.

### ⚠ The three consequences named before building

1. ⛔⛔ **Drift multiplies by the gain.** Old-stack drift 43/35/48 °/min → **129 / 180
   / 96 °/min** at the specified gains, with the hand still. The old control
   (`FREEZE`/`RELEASE`) was stripped by this branch. **`RB6` is no longer
   conditional** if the rebuilt stack drifts like the old one — and `RB5` must
   measure whether it does rather than assume it.
2. ⛔ **Roll has no pose estimator today.** The gate reads the palm normal and a roll
   cannot move the palm normal. Roll's window needs the knuckle-row angle about the
   normal — `x, y` only, which is why roll is the precision axis.
3. ⚠ **A constant gain cannot both match the full-window sweep to ±90° and feel
   uniform locally**, because Horn's own gain is non-linear. The full-window match is
   what ships; the owner ruled out the curve that would fix the other half.

### ⛔ What is carried over unchanged, and must not be re-litigated

* **The HARD edge-on gate** (`DO3`) survives under every soft window: past edge-on
  the chirality sign flips, and in rate mode that is a permanent ~180° increment.
* **A magnitude deadzone is measured WORSE** (43 → 72 °/min). Scale small deltas,
  never reject them.
* **No Euler** — the delta is scaled in ROTATION-VECTOR space (`M6a`, queue `1.3`).
* **Position is not in scope.** It keeps following the hand as `F1` shipped it.

---

## 2026-08-30 — step 1's INSTRUMENT is built; the take is owed, and the dry run found a problem

### ✅ Built

| | |
|---|---|
| `Resources/hand_pose_window.py` | the pose readings + the window weights. ⭐ Carries the **new ROLL reading** the specification needed and the old gate could not provide |
| `analysis/rb5_window_calibration.py` | step 1 itself: declared real angle → pose reading (sets the WINDOW) and → Horn's delta (sets the GAIN), then prints the constants block |
| `analysis/verify_hand_pose_window.py` | **46 checks, 0 failures** — golden vectors before wiring (`CONSTRAINTS` §3) |
| `tools/RecordPerceptionSequence.py` | three new sequences, `rb5_pitch_window` / `rb5_yaw_window` / `rb5_roll_window` |

⭐ **The roll reading is the palm's LONG AXIS (wrist → middle MCP) in the image
plane — `x, y` only.** ⛔⛔ The obvious construction, the **knuckle row**, is
**chirality-ODD**: it points the opposite anatomical way on the two hands, so it
reads 180° apart between them. The suite keeps that as a **counter-example it must
FAIL on** (measured spread 173.6°), the way `hand_frame` keeps negate-z — a
chirality-odd palm normal was one of the four sign defects of 2026-08-29.

⚠ **And the suite caught me committing the project's own most expensive error.**
§2 was written as *"magnitude AND sign"* and compared `abs()` — it passed while yaw
came back **negated**. `METHOD`'s rule *a sign is not tested by any amount of testing
the magnitude*, broken by the suite written to enforce it. Now pinned signed:
polarity `pitch +1 · yaw −1 · roll +1`, plus a check that each sign is a function of
the rotation and not of its size.

### ⛔⛔ THE TAKE DOES NOT EXIST, AND IT CANNOT BE FAKED

**Every `hold_0…hold_90` take in the corpus is `detection_on_mirrored_frame: true`;
every UN-mirrored take of 2026-08-29 declares a DIRECTION (`hold_yaw_pos`), not an
ANGLE.** `1.7.42` detects un-mirrored, and post-hoc un-mirroring is **REJECTED** —
MediaPipe is measured *not* mirror-equivariant (7.7–10 mm, 12–20°). So the harness
runs on the old takes, marks every number **NON-BINDING**, and refuses to emit a
constants block. ✅ Owner is recording the three takes on the evening of 2026-08-30.

### ⚠ THE DRY RUN (mirrored, NON-BINDING) — and it vindicates the unit trap

| axis | POSE slope | HORN across the owner's window | gain implied | nominal | out by |
|---|---|---|---|---|---|
| yaw `0…+60` | 0.54 | 35.0° | **5.14** | 3.00 | **1.71×** |
| pitch `+15…+50` | 0.73 | **11.2°** | **16.08** | 5.14 | ⛔ **3.13×** |
| roll `−45…+45` | 0.88 | 74.4° | **2.42** | 2.00 | 1.21× |

⭐ **The nominal gains would have under-rotated by up to 3×**, exactly as §8sexies-b
predicted. This is the harness's own justification.

### ⛔⛔ AND THE PITCH WINDOW LANDS WHERE HORN IS LEAST RESPONSIVE

Two numbers, both from the dry run, both about `pitch +15…+50` specifically:

* **Horn moves only 11.2° across the whole window** — a *local* slope of **0.32**
  against a global 0.67, so the owner's window sits in the flattest part of the
  curve. Demanding ±90° of cube from it forces a gain of **~16×**.
* ⛔ **The window is ~12° wide in the units the GATE reads** (pose −1.7° → +10.5°),
  which is **narrower than the 15° fade**. A window narrower than its own edges is
  not a window.

⚠ **Gain multiplies noise, and pitch is the noisiest axis**: a per-frame delta p95 of
1.1–4.8° while gripping becomes **18–77° of cube per frame** at 16×. Drift likewise:
35°/min → **560°/min**.

⛔ **All of it is NON-BINDING** — mirrored capture, old stack. But the *shape* agrees
with two independent prior findings (Horn's yaw gain ramps ~0.5→1.2; pitch is the
weak axis below ~50–60°), so it is likely to survive tonight's take. ⭐ **If it does,
the pitch specification cannot be met as stated** and the owner has the call: a wider
pitch window, a smaller cube span on pitch, or accepting a noisier pitch axis.

### The take to record — `--no-mirror --mount facing_user`, in a BRIGHT room

    tools\record_perception_sequence.bat rb5_pitch_window   (28 s)
    tools\record_perception_sequence.bat rb5_yaw_window     (28 s)
    tools\record_perception_sequence.bat rb5_roll_window    (33 s)

⭐ **The angles BRACKET each window rather than filling it** — a hold at each edge
*and one beyond it*, because an edge read by interpolation is measured and one read
by extrapolation is a guess (the dry run flagged exactly that on roll). The
beyond-steps are also where the fade lives.
⚠ `hold_0` is the Horn REFERENCE every other hold is measured from, which is why
pitch keeps a `0` step even though its window starts at `+15`.
⚠ Paced capture idles the camera, so these takes will read ~10 fps. **Fine for
angles, useless for rates** — `RB5`'s DRIFT numbers need their own, un-paced take.

⭐ Fixed in passing: the recorder's auto-registration loop **overwrote** the custom
`prompt`/`unblocks` of the `rb3_*` sequences (visible in the 2026-08-29 `meta.json`
files, which all carry the generic `1.7.41` text). `setdefault` now, so an `RB5` take
is not filed under the wrong spec.

---

## 2026-08-30 (later) — the CONTROL LAW is built, and the golden vectors earned their keep

### ✅ Built

| | |
|---|---|
| `Resources/hand_control.py` | the law: `Δ = between(prev, now)` → rotvec → per-axis `gain × weight` → composed onto the object. No filters, no rate curve, no per-axis sign |
| `analysis/verify_hand_control.py` | **39 checks, 0 failures** |
| `analysis/rb5_drift.py` | step 5's instrument: drift with the hand STILL, at gain 1 **and** at the shipped gains |

⭐ **The law is CLOCK-FREE, and that is a consequence of the owner's decision rather
than an accident.** With no velocity term there is no `dt`, so nothing in it can move
with the frame rate — which in this project is camera-bound and shifts with the room
lighting (`L1`: 111 ms in good light, 149 ms in poor).

### ⛔⛔ THE VECTORS CAUGHT A REAL DEFECT BEFORE ANY CAMERA DID — the gate read only ONE end of the delta

The first version weighted each increment by the pose it **arrived at**. §5 failed
immediately: a hand that rolls out of its window and comes back **delivered the whole
return leg**, because the frame it lands on is inside the window. Measured **45° of
object rotation from an excursion that should have left nothing** — and 45° only
because `MAX_STEP_DEG` clamped it. Weighting by the **departure** pose alone has the
mirror defect on the way out.

⭐ **The fix: the effective weight is the per-axis MIN of the delta's two ends.** An
increment that touches the outside is attenuated by the outside. `min`, not a
product, so a wholly in-window increment stays at exactly 1.0. §5 now measures
**0.000°** across the same excursion, with **0 frames driven**.

⭐⭐ **This is the first defect of the gate/sign class in this project's record that a
SUITE caught rather than the owner, live.** That is what `RB0` was built for, and it
is the branch's premise paying out.

⚠ **A second, smaller one in the same pass**: `frames_driven` counted frames where
the *gate was open*, not frames where the object actually *moved* — so a fully gated
stream reported as driven. A counter that lies makes a silent gate look like a
working one. Fixed to count applied increments.

### ⛔⛔ AND A CORRECTION TO `RB5`'s OWN ACCEPTANCE TEST

The spec's step table says closure is *"hand returns to a pose → object returns"*.
**Measured: that is only true single-axis, or at unity gain.**

| path | gain 1 | gain 2 |
|---|---|---|
| single-axis out-and-back | 0.0000° | **0.0000°** |
| multi-axis loop returning by another route | 0.0000° | ⛔ **19.34°** left on the object |

⭐ **Scaling a rotation vector does not commute with composition**, so the scaled
integral is **path-dependent**. This is not a defect to fix — it is what a gain ≠ 1
means, and the owner asked for gains of 2–5×. ⛔ But the acceptance test must be run
**per axis** or **at gain 1**, or it will fail for a reason that is not a fault.
Recorded in the spec as §8sexies-k.

### ⚠ Drift, dry run (mirrored → NON-BINDING), and it is JITTER not slide

`window_yaw_grip`, hold frames only, 99% driven:

| | NET (what a player sees) | PATH (jitter) |
|---|---|---|
| gain 1 | **21.3 °/min** | 695 °/min |
| shipped nominal gains | **100.4 °/min** | **2906 °/min** |

⭐ **NET at gain 1 is better than the old stack's 43/35/48** — but ⛔ **PATH is 33×
NET**, so the object is shaking rather than sliding. At the shipped gains that is
**~48 °/s of continuous jitter**, which no player would accept. ⚠ Both numbers are
non-binding (mirrored capture, old frame handling) and the un-mirrored take settles
them — but they say the same thing the pitch finding did: **the gains the
specification implies are large enough that noise, not drift, is the binding
constraint.**

### What is still owed

1. ⛔ the un-mirrored calibration takes (owner, this evening) → the constants
2. then: paste, flip both `CALIBRATED` flags, re-run drift on a still-hand take
3. wire into both tools + sliders; `parity_replay`
4. ⛔ the live look in both tools, which is the only thing that closes it

---

## 2026-08-30 (review) — a full review of the new scripts, and it found two RE-INTRODUCTIONS

Robustness / logic / dead state / superfluous code / security, over the seven new or
changed files. **Seven findings, all fixed; the suites went 85 → 107 checks.**

### ⛔⛔ The two that mattered — both defects this project had already fixed once

1. **The palm normal was CHIRALITY-ODD.** It is built on the knuckle row
   (`index_MCP → pinky_MCP`), which points the opposite anatomical way on the two
   hands — so the normal, and with it **pitch and yaw**, came out negated on the
   left hand: the same +20° physical yaw read `-20` right, `+20` left. ⛔ With the
   owner's **asymmetric** windows that gates the OPPOSITE motion on the left hand.
   ⭐ Fixed by multiplying the normal by `sign(signed_palm_volume)`, which flips with
   exactly the same handedness. ⭐⭐ **And it buys mirror-invariance for free,
   measured**: a mirror flips the determinant *and* the normal, so corrected
   `nz > 0` means *palm toward the camera* on a mirrored and an un-mirrored capture
   alike — confirmed on `rb2_facing_right_palm` (201/201 frames) against the
   mirrored `window_yaw_grip` (839/839, both flipped).
2. **`abs(nz)` FOLDED the reading past edge-on.** With the back of the hand to the
   camera, yaw +180° read **−0.0° with weights (1, 1, 1)** — full gain in the most
   degenerate region there is, integrated permanently. ⛔⛔ Exactly the defect
   `SPEC_DELTA_ORBIT` §8bis records against `edge_on_measure`; dropping `sign(nz)`
   re-opened it. ⭐ Fixed: `palm_faces_camera()` is a **hard gate on every axis**.

⭐⭐ **And the fix landed on the owner's own convention**: with the corrected normal,
**fingertips toward the camera now reads POSITIVE pitch** — which is the owner's
stated sense. Asserted semantically in §2b, not as a matrix sign.

### The other five

| | |
|---|---|
| the paste block printed `CALIBRATED = True` **unconditionally** | a run missing an axis, or reading an edge by extrapolation, would have flipped the guard over a surviving PLACEHOLDER window. Now one testable `objections()` predicate, **all four branches exercised without a camera** |
| drift divided by **first-hold-to-last-hold**, including the MOVE intervals | the rate was **37% low** — and it is the number compared against 43/35/48 to decide `RB6`. Corrected: **33.9 °/min** at gain 1, not 21.3; **159.9** at the nominal gains, not 100.4 |
| the drift harness `continue`d past frames with no hand | so one increment bridged the dropout, measuring a law the product does not run. Now feeds `None` and exercises the module's own refusal path |
| both harnesses ignored the take's `declared_mount` | they ran on the process-wide `HAND_MOUNT`, so a `head_worn` take or a stale env var would have yielded constants off by `Ry180`, silently. ⚠ Related: the recorder's `--mount` only writes a LABEL — it does not affect capture |
| `hand_control` kept its own `_qmul` and exp map | an `N6` violation I introduced. The algebra now lives once, in `hand_orientation`, with the log/exp pair together |

### ⚠ And a fixture defect that had made the whole suite meaningless

The synthetic hand had a **perfectly planar palm** — zero triple product, no
chirality, a hand the shipped code REFUSES. Every vector was exercising a shape that
cannot occur. Fixed with a realistic 8 mm cup (|det| 5.8e-05, against the corpus's
4.5e-05 palm-take median and the 3.0e-06 floor), and §1 now asserts **both** that
this hand is accepted and that a flat one is not.

⭐ Two rules came out of it and are now in [`../METHOD.md`](../METHOD.md): **a golden
vector's FIXTURE must be a specimen the product would accept**, and **an invariant
tested on one axis is not tested**.

### ✅ Security — nothing to report, and it was checked rather than assumed

No network egress of any kind · no `subprocess` / `eval` / `exec` / `__import__` ·
no `pickle` or other unsafe deserialisation (only `json` over local corpus files) ·
**the scripts write nothing at all** · no credentials, no PII, and the corpus is
landmarks-only by `N14`. ⭐ One hardening anyway: the `.bat`'s camera-index argument
is now quoted, so a stray token cannot become another switch.
