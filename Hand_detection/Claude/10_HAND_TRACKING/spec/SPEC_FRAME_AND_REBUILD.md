# THE FRAME, AND THE `1.7.42` REBUILD (`RB0`–`RB6`)

> **STATUS** · ⭐ live — the design of record for branch `1.7.42-`
> **OWNS** · the coordinate frame every consumer reads, and the order the hand
> → object control is rebuilt in
> **READ IF** · you are touching landmarks, chirality, depth, occlusion, the camera
> mount, or the object's rotation
> **LAST VERIFIED** · 2026-08-29

⚠ The archive of what came before is commit `4dd0fc5` on `1.7.42-`
(`trial finished`), and `2cdf9f7` before it. Nothing below is a patch on that work;
it replaces the frame handling and rebuilds the control law from the landmarks up.

---

## 1. Why a rebuild rather than another fix

> **Owner, 2026-08-29:** *"I think we have patched too much this script … I want to
> build the control by hand detection delta increment from scratch. Strip all the
> filters and multiplicators, etc.: we will rebuild them as we need them."*

⛔⛔ **THE SYMPTOM THAT JUSTIFIES IT: THE COMPOSITE MAPPING HAD BECOME A
REFLECTION.** `camera_mount` reversed pitch+yaw, then `delta_orbit.AXIS_SIGN`
reversed pitch back — net, **yaw reversed alone**, which has determinant −1. A rigid
hand→object correspondence cannot do that. Each layer was locally reasonable and the
stack was not, which is `METHOD`'s *no heuristic pile-up* arriving in the one place
nobody was measuring: the composition.

## 2. ⭐⭐⭐ THE PHYSICS, AND IT IS THE OWNER'S ARGUMENT

> *"if the hand is rotating around the vertical axis, any observer which watches the
> hand will see the hand rotating in the same direction … Roll and pitch will be
> reversed if the camera and the user are watching in opposite directions."*

Two observers facing each other are related by a **180° rotation about the
vertical** — `Ry180 = diag(−1, 1, −1)` — **not** by a mirror:

| axis | camera vs user |
|---|---|
| **yaw** (0,1,0) | ⭐ **unchanged — the vertical is SHARED** |
| pitch (1,0,0) | reversed |
| roll (0,0,1) | reversed |

⭐ **`det(Ry180) = +1`.** It is a proper rotation, and that single fact decides §3.

⛔⛔ **THE INVARIANT, AND IT IS NOW A TEST**: *any viewpoint setting that changes
the sign of YAW is wrong by construction.* The shipped `pitch_yaw` reverses yaw. One
assertion would have killed it on day one; there was no such assertion.

## 3. ⭐⭐ THE DECISION: THE VIEWPOINT IS APPLIED TO THE **LANDMARKS**, AS A ROTATION

`V1` applied the viewpoint as a **quaternion conjugation**, to the orientation only.
Chirality, depth, occlusion and rendering all kept reading the raw frame — so the
hybrid `V1` existed to remove was not removed, it **moved one layer down**.

⛔ `V1` rejected "negate the landmark z" for correct reasons: it inverts `U7`'s
chirality determinant and `R1`'s camera-referenced occlusion. ⭐⭐ **But negate-z was
never the right operation.** It is a reflection (det −1). The right one is `Ry180` —
negate **x AND z** — and a rotation cannot change handedness:

| | negate z alone | **`Ry180`** |
|---|---|---|
| determinant | −1, reflection | **+1, rotation** |
| chirality determinant | **inverted** | **preserved** |
| occlusion ordering | broken | consistent (z flips coherently) |
| per-axis effect | pitch + yaw reversed | **pitch + roll reversed, yaw untouched** |

⭐ So the hybrid is fixable at source, cheaply, and every consumer reads ONE frame.
⚠ The owner's first proposal was `z = 1 − z`. Horn centres its point sets, so the
`+1` vanishes and `1 − z ≡ −z` — **measured identical to the shipped conjugation to
the decimal**, and therefore not a fix. The missing half was negating `x`.

## 4. ⛔⛔ THE IMAGE MIRROR LEAVES THE DETECTION PATH

A mirror is det −1. Composing it with a rotation is **exactly the determinant
mismatch that IS the hybrid**. Mirroring is a **display** choice and belongs at draw
time, nowhere else.

⭐ Today's build is wrong on both counts at once — `pitch_yaw` **and** a pre-detection
mirror — and the two errors partially masked each other. That is why single-axis
live verdicts kept disagreeing, and why `camera_mount`'s own history records three
mutually inconsistent reports on the same question.

## 5. The irreducible core — six pieces, nothing else

| # | piece | contract |
|---|---|---|
| 1 | **Landmark source** | 21 px + 21 world landmarks, real timestamp, detected on the **UN-MIRRORED** frame |
| 2 | **Viewpoint** | ONE function, landmark-level. `facing_user` → `Ry180`; `head_worn` → identity. ⛔ no mirror, no per-axis sign, no quaternion conjugation |
| 3 | **Chirality** | geometric determinant in the corrected frame. ⭐ frame-invariant, because the correction is a rotation |
| 4 | **Hand identity** | the same hand across frames, so per-hand state means something |
| 5 | **Orientation** | Horn over the palm landmarks — exact to 0.000° on synthetic input. Nothing wrapped around it |
| 6 | **Control law** | `Δ = q(t)·q(t−1)⁻¹`, integrated onto the object. No gains, no windows, no signs |

## 6. Stripped — rebuilt only when a measurement asks

`camera_mount`'s conjugation table and `mirror_frame` · `delta_orbit`'s `AXIS_SIGN`,
pose window and rate curve · `lean_trim` (`V2`) · `tip_trim` · `one_euro` /
`orientation_filter` · the slerp τ · `FREEZE`/`RELEASE` · `palm_slant*` ·
`planar_pnp` · `palm_depth`'s mount-dependent sign.

⚠ **Two will be needed back, and saying so now is not a discovery later**:
a **drift control** (integrating raw deltas measured **43/35/48°/min** with the hand
still, and a magnitude deadzone measured WORSE), and some **smoothing**.

✅ **KEPT (owner):** `CubeWindow` and its occlusion, `object_assembly`,
`mate_connector`, `object_extent`, `depth_order`, `handinput`.

## 7. ⚠ What this costs, named before it is paid

* **`is_thumb_outward` must be re-derived.** It is calibrated against the
  **mirrored/apparent** hand (788/788 frames) and its own docstring warns that
  passing the un-mirrored label inverts it. Un-mirroring changes what *apparent*
  means.
* **The 415-recording corpus becomes non-comparable** for anything chirality- or
  depth-referenced. Replay still works; cross-build comparison does not.
* **Occlusion and depth ordering need one re-check**, because `z` now points the
  other way — consistently, but differently.

## 8. The rebuild, one test per step

| step | build | the test that closes it |
|---|---|---|
| **`RB0`** | the **sign harness** | declared holds → expected sign, per axis, **both hands**, **both mounts** |
| `RB1` | landmarks un-mirrored + `Ry180` | ⭐ **yaw sign IDENTICAL in both mounts** (§2's invariant, as an assertion) |
| `RB2` | chirality | ✅ **done** — determinant matches the declared hand and is **unchanged** by the viewpoint. ⛔ `head_worn` unresolved |
| `RB3` | Horn orientation | ✅ **done offline** — invariants pass, all three axes agree between the hands (§8quater). ⛔ The live look is still owed |
| `RB4` | hand identity | ✅ **done** — 0 swaps / 1652 frames; degenerate hands REFUSED (§8quinquies) |
| `RB5` | the delta, integrated, no filters | closure: hand returns to a pose → object returns. Drift **measured** |
| `RB6` | drift control, then anything else | only when a measurement asks for it |

⭐⭐ **`RB0` IS THE POINT OF THE WHOLE BRANCH.** Every defect of 2026-08-29 — the
symmetric edge-on gate, the chirality-odd palm normal, the inverted `thumb_outward`
polarity, the reflected composite — was a **SIGN** error, and not one of them was
caught by a suite. They were caught by the owner, live, one at a time. A harness that
pins signs against declared truth catches all four before they reach a camera.

⭐ The material for it already exists: the three stepped **gripping** takes of
2026-08-29 (`window_yaw_grip`, `window_pitch_grip`, `window_roll_grip`), whose holds
are **declared** rather than inferred.

## 8bis. ✅ `RB0`–`RB2` BUILT 2026-08-29 — and the one thing still untested

| | |
|---|---|
| `Resources/hand_frame.py` | the whole viewpoint + chirality. Stdlib, clock-free |
| `analysis/verify_frame_signs.py` | §1–7. Keeps its OWN Horn fit and determinant so it can fail on the module, but takes the VIEWPOINT from it |

✅ **`RB0` — the invariant holds, measured**: yaw reads **+28.27° in BOTH mounts**,
identical rather than merely same-signed; pitch and roll flip cleanly
(+68.35/−68.35, +69.60/−69.60); the chirality determinant is unchanged by the
viewpoint on all three takes; and **negate-z alone inverts it**, kept as the
counter-example so nobody re-proposes the operation `V1` rightly refused.

✅✅ **`RB2` — chirality is SOLVED, on declared ground truth: 788/788.**

| take | declared | `is_right_hand` |
|---|---|---|
| `known_right_palm` / `_back` | Right | **198/198**, **199/199** |
| `known_left_palm` / `_back` | Left | **200/200**, **191/191** |

⭐ **And it is independent of FACING** — palm and back takes agree, which is what a
chirality must do and what `is_thumb_outward` (a palm/back cue) never could. That
conflation is exactly what produced the 2026-08-29 polarity defect.

⛔⛔ **MediaPipe's LABEL agreed on 0 of 788 frames.** It names the APPARENT hand of a
mirrored capture, i.e. systematically the opposite of the physical one. `METHOD`
rule 4 already forbids keying a stream on it; this is that rule with a number.
**Nothing in `1.7.42` reads the label**, and §7 asserts it stays that way.

✅✅ **AND THE FLIP IS NOW MEASURED, NOT PREDICTED.** Two un-mirrored takes were
recorded for it the same evening:

| capture | right hand | determinant |
|---|---|---|
| corpus, **mirrored** | 788/788 | **positive** |
| `rb2_facing_right_palm`, **un-mirrored** | 201/201 | **negative** |

A mirror is det −1 and the determinant duly flips, so `CAPTURE_MIRRORED = False` is
correct by measurement for the path `1.7.42` uses.

⭐⭐ **AND IT REFRAMES `U7`.** On that same un-mirrored take MediaPipe's handedness
label read **Right on 201/201 frames** — correct — against **0 of 788** on the
mirrored corpus. **The label was never broken; OUR MIRRORING was breaking it.**
`U7`'s *"10.8% wrong"* is largely self-inflicted. ⚠ Nothing here reads the label
regardless: a determinant needs no label and cannot be fooled by one.

### ⛔⛔ THE LIMIT THAT CAME WITH IT: `head_worn` HAS NO CHIRALITY

Three `rb2_worn_right_back` takes, all un-mirrored, all the declared RIGHT hand:

| attempt | \|det\| median | sign agreement | palm z-spread |
|---|---|---|---|
| #1 | 7.3e−07 | 57.6% | 30.0 mm |
| #2 | 8.4e−08 | 88.7% | 9.0 mm |
| #3 | 4.8e−08 | 58.3% | 17.1 mm |
| *palm take* | *4.5e−05* | *100.0%* | *38.8 mm* |

**60–950× weaker than palm-side, and the agreement WANDERS** (57.6 / 88.7 / 58.3)
instead of converging — which is what taking the sign of ~zero looks like. The five
palm landmarks go near-coplanar and the triple product loses the quantity its sign
comes from. That is `T1` / MediaPipe issue **#5156**, measured rather than cited.
⚠ The retakes got **worse**, which rules out *"one bad attempt"*.

⛔ **So `head_worn` gets no chirality convention, and one must not be invented from
a coin flip.** It matters because a head-worn camera mostly sees the **BACK** of the
wearer's own hand: the cue is not weak there, it is **ABSENT**. Whoever takes
`head_worn` forward needs a different cue (thumb geometry) or a rule that HOLDS the
last palm-side reading through the degenerate region.

⚠ **Unseparated confound, stated rather than buried**: every take that evening
measured **15.17 fps**, under the 20 fps floor. The mechanism does not need dim light
to explain it — the corpus's own *mirrored* back-of-hand take had 72 mm of spread and
read 100% clean — but lighting and geometry were not separated.

⭐ **Recorder change that made this possible**: `--no-mirror` and `--mount`, plus
`detection_on_mirrored_frame` in `meta.json`. ⛔ A take without that field is
ambiguous about chirality, because a mirror inverts the determinant.

## 8ter. ⚠ `RB3` — BUILT, AND HALF-CLOSED. The two-hand take is OWED.

`Resources/hand_orientation.py`: Horn over the palm, in the corrected frame, and
**nothing wrapped around it**. `horn_rotation` is imported, never re-derived
(`N6`) — it is exact to 0.000° on synthetic input and four estimator replacements
have died against it under `A10`. **The rebuild is about the FRAME and the CONTROL
LAW; the fit was never the problem.**

### ✅ What a suite CAN pin, and does (`verify_frame_signs` §9)

| invariant | result |
|---|---|
| pure **translation** produces no rotation | 0.00e+00° |
| **composition** A→C ≈ (A→B) then (B→C) | 0.191° over a 74° sweep |
| …and the **wrong order** is clearly worse | 2.548° — so the check tests something |
| every output **canonical** (`w ≥ 0`) | the 2026-08-29 double cover, asserted away |
| reference against itself | exactly identity |
| **mirroring the hand** mirrors the rotation | pitch keeps its sign; yaw and roll flip |

⚠⚠ **THE COMPOSITION CHECK WAS WRONG FIRST, AND THE TEST WAS AT FAULT, NOT THE
CODE.** It asserted composition was EXACT and failed by 0.191°. **The palm is not
rigid**: Horn fits a rigid rotation and leaves a measured **2.5–8.0 mm residual on a
91.5 mm palm** across that sweep, so `Horn(A→C)` genuinely cannot equal the two
halves composed. The difference IS the hand deforming.
⛔ The tolerance is therefore derived from that residual (under 1% of the sweep) and
**a wrong-order control proves the check still bites** — a tolerance widened until a
test goes green is how a build talks itself into shipping.

### ⛔ What a suite CANNOT pin, and why `RB3` is not closed

**Whether a pitch looks RIGHT on screen.** That needs a take with **both hands
performing the SAME world motion**, and every take in this project's rotation work
is single-hand — so the invariant that matters most has never been tested:

> ⭐⭐ **A rotation is a property of the WORLD, not of the hand.** If both hands
> pitch the same way at the same moment, the estimator must report the **same sign**
> for both. Two separate single-hand takes cannot test this: the operator cannot
> reproduce a motion exactly, so a disagreement would be indistinguishable from
> having moved differently.

⛔ It is the invariant that would have caught a chirality leak into orientation —
the class that gated one whole hand to zero on 2026-08-29.

### ⭐ The take, specified (recorder work already done)

`rb3_two_hands_axes`: both hands, **same world direction, never mirrored**, one axis
at a time, un-mirrored capture, `facing_user`.
⛔⛔ **SAME-DIRECTION IS LOAD-BEARING.** Hands naturally move as a mirror pair (both
rotating *outward*), and with mirrored input the CORRECT answer is opposite signs —
so a chirality leak would be indistinguishable from a correct result.
⚠ Prompts are **screen-relative**: *"toward you"* was ambiguous (with the camera
facing the operator it means AWAY from the camera) and the owner caught it. The
declared directions ride into `meta.json` as `declared_directions`, so the sign test
has ground truth rather than someone's memory.

⭐ **Recorder gained OPERATOR-PACED steps** (owner: *"I don't have time to read the
prompts. ask me to press space to start the take each time"*). Each step waits for
SPACE showing its prompt, and **records nothing while the operator reads**. The first
timed attempt produced a hand in only **429 of 1012 frames** — the operator was still
parsing each instruction while its window was already recording. **A prompt nobody
has time to read is not an instruction, it is a decoration, and the frames it labels
are junk.**
⚠ Two crashes came from that change and both were mine: overlay code reading
`elapsed` and then `record`, neither of which exists while a paced step waits. Fixed,
and the loop audited for a third.

## 8quater. ✅ `RB3`'s TWO-HAND TEST — and the edge-on trap it walked into

✅ **All three axes agree between the hands.** Pitch and roll from
`2026-08-29_212855_rb3_two_hands_axes`, yaw from `..._214029_rb3_yaw_only`:

| axis | LEFT | RIGHT | |
|---|---|---|---|
| pitch | −33.2° / +34.9° | −17.7° / +44.8° | ✅ |
| roll | −24.9° / +39.2° | −31.1° / +36.1° | ✅ |
| yaw *(small turns)* | −10.2° / +20.5° | −24.2° / +4.1° | ✅ |

⭐ Hand identity from **geometry**, never the label; **zero swaps** across every
step, each hand holding its own side of the screen (x≈150 vs x≈470).

### ⛔⛔ THE EDGE-ON TRAP, AND IT WAS THE OWNER WHO SPOTTED IT

The FIRST yaw attempts disagreed, and I reported that the right hand *"simply did
not turn"* — on the strength of three measures agreeing: the fitted rotation, the
projected/true knuckle width, and the palm z-spread.

> **Owner:** *"both hands did absolutely the same thing, but I think we catch the
> edge on issue."*

✅ **Correct.** With smaller turns every axis agrees. On the large-turn take one
palm's z-spread reached **56.8 mm** against the other's **8.7 mm** — one hand deep
in the degenerate region where the world landmarks collapse.

⚠⚠ **AND THE METHOD LESSON IS ABOUT MY EVIDENCE, NOT THE HAND: THREE MEASURES
SHARING A FAILURE MODE LOOK LIKE CORROBORATION AND ARE NOT.** All three of mine
derive from the world landmarks, so near edge-on they degrade *together* and agree
on a wrong answer. ⛔ The projected/true width ratio was the worst of them: it
divides a projected length by a 3-D length, so when the landmark cloud flattens both
shrink together and the ratio returns to ~1.0 — **reading "face-on" for a hand that
is anything but.** Independence has to be argued, not assumed from three numbers
lining up.

### ⚠ What this take does NOT say

* **Nothing about MAGNITUDE.** The hands do not turn equally (−10.2 vs −24.2,
  +20.5 vs +4.1). The invariant asserted is the SIGN and only the sign.
* **Nothing about timing.** 11.4 fps — operator-paced capture leaves the camera idle
  and auto-exposure winds down. Fine for signs, useless for rates.
* ⛔ **Nothing about whether pitch reads right ON SCREEN.** That is a live look.

### ⚠ And a correction to why this take was asked for

It was justified as *"the invariant that would catch a chirality leak into
orientation"*. ⛔ **It cannot**: `hand_orientation.between(a, b)` takes ONE hand's
own two poses and has no handedness argument, and the viewpoint is one fixed
rotation applied identically to both hands. Such a leak is **structurally
impossible** at this layer. The real exposure was in the deleted `delta_orbit`
GATING code, which read the chirality-odd palm normal. ⭐ The take still earns its
place — it is the project's only two-hand declared-motion recording, and it found
the edge-on trap — but the claim was too strong.

## 8quinquies. ✅ `RB4` — IDENTITY FROM CHIRALITY, HELD THROUGH DEGENERACY

`Resources/hand_identity.py`. **Zero swaps across 1652 two-hand frames**, each hand
holding its own side of the screen; and on the degenerate back-of-hand take it
**refuses all 151 frames** rather than guessing.

⭐⭐⭐ **IT IS FOUR SCREENS OF CODE INSTEAD OF A TRACKER, AND THAT IS THE RESULT.**
The old pipeline used DR-1 track ids plus a slot↔track resolution layer
(`hand_tracks.py`). ⛔ `4.1` was **built, patched five times and REVERTED**, and the
machinery around it — `_owner_hand_of_cube`, `_owner_absent_since`, the degrade
window — existed only to bridge *"ownership is track-keyed but its coast is
slot-keyed"*.

⭐ None of it is needed once `RB2` made chirality reliable: **a left hand and a right
hand are distinguishable by their own geometry, frame by frame** — no history, no
association step, nothing to drift. **Identity that cannot drift needs no machinery
to correct drift.**

### The two rules that make it safe

⛔⛔ **A FLIP REQUIRES CONFIDENCE *AND* DISAGREEMENT.** `RB2` measured the
determinant collapsing on a back-of-hand view (agreement wandering 57.6 / 88.7 /
58.3% — the sign of ~zero). A build that read it every frame would flip identity
mid-gesture and inherit the other hand's state: the `T3` / `U8` defect class exactly.
So identity is **HELD** through low confidence. `U9`'s rule — *a trigger cannot
enforce an invariant* — applied to a label instead of a gesture.

⛔ **A SAME-CHIRALITY COLLISION IS REFUSED, NOT MERGED.** Two hands reported as one
would share per-hand state. The less confident one returns `None`.

### ⚠ The floor, and why it is absolute

`CONFIDENT_DET = 3.0e-06`, placed in the **two-order-of-magnitude gap** between
palm-side p5 (**3.19e-05**) and degenerate p95 (**2.57e-07**) — measured, not chosen.
⚠ It is absolute, in metres cubed, so a port that changes landmark scale must
re-derive it. ⛔ A scale-free version was considered and is WORSE: normalising by the
palm size divides by a length that is itself collapsing in the degenerate case this
guards.

### ⚠ What it deliberately does not solve

**Two hands of the same chirality** (two people) collapse to one key and the second
is refused. The game is single-player with two hands; when that stops being true this
module must be **REPLACED, not patched**.

## 9. Acceptance

1. `RB0` passes for both mounts and both hands before `RB1` is written.
2. ⛔ **No step may add a per-axis sign, gain or window** to make a later step pass.
   That is the pile-up this branch exists to undo; if a sign is needed, the frame is
   wrong and the frame gets fixed.
3. Golden vectors before wiring (`CONSTRAINTS` §3).
4. `parity_replay` clean, because both tools change (`U6`).
5. ⛔ **A live look in BOTH tools closes it, and nothing else does** (`METHOD`).
