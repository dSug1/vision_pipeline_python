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
| `RB2` | chirality | determinant matches the declared hand and is **unchanged** by the viewpoint |
| `RB3` | Horn orientation | a declared 30° pitch reads +30°, both hands |
| `RB4` | hand identity | two hands, no swap across a dropout |
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

## 9. Acceptance

1. `RB0` passes for both mounts and both hands before `RB1` is written.
2. ⛔ **No step may add a per-axis sign, gain or window** to make a later step pass.
   That is the pile-up this branch exists to undo; if a sign is needed, the frame is
   wrong and the frame gets fixed.
3. Golden vectors before wiring (`CONSTRAINTS` §3).
4. `parity_replay` clean, because both tools change (`U6`).
5. ⛔ **A live look in BOTH tools closes it, and nothing else does** (`METHOD`).
