# DELTA-ORBIT — the object's rotation as an INTEGRAL of hand motion (`DO1`–`DO4`)

> **STATUS** · ⭐ live — the design of record for branch `1.7.41-Hand-delta-orbit`
> **OWNS** · how the object's ROTATION is driven, from `1.7.41` onward
> **READ IF** · you are touching the object's rotation, the rate curve, or the window
> **LAST VERIFIED** · 2026-08-30
>
> ⛔⛔ **PARTLY SUPERSEDED 2026-08-30 BY `RB5`.** The owner specified one **fixed gain
> matrix, independent of hand rotation speed** — *"no fine vs. rapid coarse rotation
> control"* — so **§6 (the rate curve `RATE lo/hi/knee`) and §7 ("the curve IS the
> clutch") are DELETED, not deferred**; grab/release becomes the only clutch. ✅ The
> rest of this file stands and is still the reasoning of record — especially §3 (error
> integrates), §4 (a deadzone is WORSE), §5 (noise and slow signal are the same size),
> §8bis (the gate must be signed) and §9 (no Euler). → `SPEC_FRAME_AND_REBUILD.md`
> §8sexies.

⚠ **Position is NOT in scope and does not change.** The object's position keeps
following the hand exactly as `F1` shipped it (fingertip barycentre, `A1`'s
motion-masked walk, depth anchoring at grab). This spec changes **rotation only**.

---

## 1. What the owner asked for

> **Owner, 2026-08-29:** *"the cube's position still follows the hand as in
> 1.7.40 (i.e. no change in the cube's position) but the cube's rotation is
> incremented based on hand rotation delta (when the hand is in the range you
> identified as the best ranges for respectively yaw - pitch - roll, and with a
> smooth and rapid decay to zero when the hand is outside these ranges)."*

The owner supplied a Unity `OrbitMovement` as the pattern: a pointer-delta driven
orbit with a leaky accumulator, a clamp, and exponential smoothing.

## 2. ⭐⭐ WHAT ACTUALLY CHANGES — it is a CONTROL LAW, not new plumbing

Today's code is **already** a delta — just measured from the GRAB, not from the
previous frame (`HandsTriggeredActions` ~line 2004):

```
    delta       = q_eff(t) · q_eff(grab)⁻¹        ← absolute, w.r.t. the grab
    target_quat = delta · cube_at_grab
    cube.orientation = slerp(cube.orientation, target_quat, τ)
```

`DO` replaces the *source* of the delta:

```
    Δ(t)  = q_eff(t) · q_eff(t−1)⁻¹               ← per-frame increment
    cube.orientation ← scale(Δ(t), gain) · cube.orientation
```

⭐ That is **position control → rate control**, the same distinction as
mouse-absolute vs mouse-look. Everything below follows from it.

## 3. ⛔⛔ THE CONSEQUENCE THAT DECIDES THE DESIGN: ERROR INTEGRATES

In absolute mode a bad frame is a bad frame and the next good frame recovers.
In rate mode **every frame's error is added to the object permanently**.

⭐ **MEASURED, on the 2026-08-29 grip takes** (`analysis/delta_orbit_window.py`,
integrating the delta across declared holds — the hand is still, so every degree
is error the object keeps):

| | drift, no mitigation |
|---|---|
| YAW | **43°/min** |
| PITCH | **35°/min** |
| ROLL | **48°/min** |

⛔ Unusable as-is. §5 is the mitigation, and it already ships.

## 4. ⛔⛔ A MAGNITUDE DEADZONE MAKES DRIFT WORSE — measured, and it was my recommendation

| deadzone | YAW | PITCH | ROLL |
|---|---|---|---|
| none | 43°/min | 35°/min | 48°/min |
| 0.5°/frame | 58°/min | 45°/min | 52°/min |
| 1.0°/frame | **72°/min** | 55°/min | 72°/min |

⭐⭐ **Why**: the noise is a random walk whose small steps largely CANCEL. A
deadzone rejects the small steps, throwing the cancellation away and keeping only
the large excursions.

⛔⛔ **THE RULE: THE RATE CURVE MUST *SCALE* SMALL DELTAS, NEVER *REJECT* THEM.**
Scaling preserves the cancellation because it scales both directions equally.
⚠ This is exactly where the Unity reference must NOT be copied: its
`sqrMagnitude < 0.0001f → return` is a reject.

## 5. ⭐⭐ THE DRIFT CONTROL ALREADY SHIPS, AND NOTHING ELSE CAN DO IT

`RELEASE 60 deg/s` + `FREEZE 1` (shipped with `R1`, live-accepted) gates on **hand
speed**. During the measured holds the hand moved **14–24 deg/s** — comfortably
below the threshold — so the freeze suppresses the whole of §3's drift.

⛔⛔ **AND NO OTHER MECHANISM CAN, BECAUSE NOISE AND SLOW SIGNAL ARE THE SAME SIZE.**
Measured on the same takes, declared holds vs declared moves:

| | noise p50 / p95 | signal p50 / p95 |
|---|---|---|
| YAW | 0.62° / 1.45° | **0.66° / 1.50°** |
| PITCH | 0.98° / 3.14° | **1.16° / 3.22°** |
| ROLL | 0.71° / 1.86° | 1.00° / 2.78° |

⭐⭐⭐ **THERE IS NO KNEE THAT PASSES THE SIGNAL AND BLOCKS THE NOISE.** At the
~6.5 deg/s the operator used, deliberate motion is indistinguishable from jitter.
**Above ~80 deg/s you are clear of the noise; below ~50 deg/s you are inside it**,
and nothing downstream can recover what is not in the signal.

⚠ **So the rate curve is NOT a noise discriminator** — an earlier draft of this
design claimed it was, and the measurement above is what retracted that. Two jobs,
two mechanisms: **the FREEZE handles noise; the curve handles feel.**

⭐ **And it costs less than it sounds**: for fine control you do not move slower,
you use a lower gain — which is how a mouse has always worked. Precision is CD
gain, not creeping.

## 6. THE RATE CURVE — what it is, and why it is all sliders

`gain = f(|Δ|)`, applied to the delta before it is integrated.

| slider | what it does | constraint |
|---|---|---|
| **`RATE lo %`** | cube-per-hand for ordinary motion — the precision setting | owner's feel; < 100 % for assembly alignment |
| **`RATE hi %`** | cube-per-hand for fast strokes — travel and clutching | ≥ lo; the RATIO is the clutch strength |
| **`RATE knee deg/s`** | where the curve turns | ⛔ **must sit above ~80 deg/s**, or it opens the noise band |

⛔ **NO VALUE HERE IS DERIVED, AND NONE MAY BE HARD-CODED AS "RIGHT"** (owner,
2026-08-29: *"build sliders instead of fixing arbitrary values so I can finetune
the ranges later on during debug"*). Only the knee has a measured constraint, and
it is one-sided. The other two are feel, settled live — the way `V2`'s 0.66 was
settled over 19 homed trials and `L1`'s τ over a full sweep.

⭐ **`L1`'s rule still binds**: a tuning constant lives in **one** module. The
debug sliders write `delta_orbit`'s own constants; production reads the same
module and has no sliders. That is what keeps `parity_replay` meaningful.

## 7. ⭐⭐ THE CLUTCH, AND IT IS NOT A SEPARATE MECHANISM

Rate control without a clutch cannot travel: a stroke out and a stroke back cancel.
Mouse-look lifts the mouse; the Unity reference only has a delta while dragging.

⭐ **The curve IS the clutch**: a fast stroke out gets `hi` gain, a slow return gets
`lo` gain, and the difference is net rotation. It works *because* slow motion is
suppressed — §5's apparent cost is this section's mechanism. It is how everyone
already crosses a screen without lifting the mouse.

⚠ **The grab/release is a second, explicit clutch** and needs no new gesture.

## 8bis. ⛔⛔ THE v1 GATE WAS WRONG, AND THE OWNER FOUND IT ON THE FIRST RUN

> *"in yaw rotation, when the hand is almost edge facing the camera, it shall not
> contribute to any input ... I can still rotate the cube around yaw when hand is
> edge-on and even further palm facing the camera."*

⛔⛔ **THE CAUSE: `edge_on_measure` IS SYMMETRIC.** It measures knuckle-row
SQUARENESS — ~1.0 palm-on, ~0.15 at edge-on, and **~1.0 again with the BACK of the
hand toward the camera**. So §8's threshold killed a thin band at edge-on and then
**re-opened completely** past it. It cannot separate *palm toward me* from *back
toward me*, which is also the most likely source of the owner's second report — that
the cube's pitch sometimes runs opposite the hand's.

⭐ **THE REPLACEMENT: THE PALM NORMAL, SPLIT PER AXIS.**

    yaw_pose   = atan2(nx, |nz|)      horizontal swing of the normal
    pitch_pose = atan2(ny, |nz|)      vertical swing
    sign(nz)                          palm toward the camera, or away

The **sign is what v1 lacked**, and it makes past-edge-on a HARD ZERO on every axis
instead of a re-opened gate.

⭐ **MEASURED on the 2026-08-29 gripping takes**, per declared hold:

| take | `yaw_pose` | `pitch_pose` |
|---|---|---|
| YAW, declared 0 → ~80° | **−12° → −60°**, monotone | −14 → −36 (the known lean) |
| PITCH, declared 0 → ~90° | −14 → −10 (clean split) | **−14° → +60°**, monotone |

⚠⚠ **AND ITS HONEST LIMIT, measured the same way**: on the ROLL take the normal's
yaw reading wanders **27°** while the hand only rolls — and a roll cannot move the
palm normal at all, because the normal IS the roll axis. That is world-`z` error
leaking in. **Good enough for a soft gate with a ~15° fade; not good enough for a
measurement.**

⛔ **A degenerate or absent normal is a CLOSED gate, never an open one.** An
integrating build must refuse what it cannot vouch for.
⭐ **Roll is never gated by pose** — measured flat at every pose on both roll takes,
because roll never touches world `z`.

### ⚠ The thresholds, and why they are sliders

`WINDOW_YAW_DEG` 60 · `WINDOW_PITCH_DEG` 45 · `WINDOW_FADE_DEG` 15, exposed as
`YAW window deg` and `PITCH window deg`.
⛔ **They read in NORMAL-SWING degrees, which are COMPRESSED against the hand's real
angle** — the owner's ~80° of yaw measures ~60° here, the same compression every
depth-derived reading in this project shows. So the slider sets the FELT edge rather
than asking anyone to trust the mapping.
⭐ The fade is a **smoothstep**, so the weight leaves 1 and reaches 0 with zero
slope: `F1`'s own trim died (§10.1) on being non-monotone in the declared angle, and
a kink mid-gesture is felt.

### ⚠ On the reported PITCH INVERSION — what was checked, and what was not

✅ **No sign inversion exists inside the tested range.** On the pitch take the fitted
delta's pitch component is positive across **all six** declared moves while the pose
rises monotonically. So it is not a systematic sign bug in the delta path.
⚠ **The likely cause is therefore the region no take covers** — past `nz ≈ −0.5`
toward edge-on and beyond, where the normal flips and the landmarks collapse (`T1`).
⛔ **That is a hypothesis, not a finding**, and it stays one until `DO4`'s
wide-range take exists. The window excludes the region either way.

## 8. THE WINDOW — v1, superseded by §8bis

The owner asked for a gain that *"smoothly and quickly decays to zero"* outside the
reliable pose range. ⭐ **The measurement says the inside of that range needs no
fade at all**: on the 2026-08-29 grip takes the noise is FLAT across everything
tested — yaw 1.09–2.56°, pitch 1.09–4.77°, roll 1.35–2.55° p95.

⛔⛔ **BUT THE OUTER EDGE HAS NOT BEEN LOCATED**, and this is the row's one open
number. The grip takes reached only ~57° (yaw) / ~75° (pitch) of measured pose; the
region where the old corpus collapses is 120–180°, past edge-on. **The data says the
gain need not decay EARLY; it does not say where it MUST.**

✅ **So v1 ships a HARD GATE at the one edge that is already established**:
`palm_geometry.edge_on_measure < EDGE_ON_THRESHOLD` (0.15) → **delta = 0**.

⛔ **Hard, never a fade, and this is load-bearing**: past edge-on the palm/back
chirality sign flips. In absolute mode a flip is a visible glitch that recovers next
frame; **in rate mode it is a ~180° increment integrated permanently.** A fade would
admit a fraction of it. `DR-2` already owns this bit.

⚠ A graded per-axis fade is deferred until a wide-range take places it (`DO4`).

## 9. ⛔ NO EULER — the Unity reference must not be ported literally

The reference works in `desiredAngles.x/.y` and `Quaternion.Euler`. Porting that
reintroduces gimbal lock and breaks queue `1.3` (`M6a`, *no Euler in the estimation
path*), which is currently satisfied.

⭐ **The translation is the ROTATION VECTOR (log map)**, and it already exists in
this codebase: `lean_trim._to_rotvec` / `_from_rotvec`, stdlib, clock-free — and
`trim()` already scales per-axis components exactly this way.

⭐⭐ **It is well-conditioned here for a reason that does not hold elsewhere**: the
log map's three components are independent only for SMALL rotations, and a per-frame
delta is 0.3–2.4°. The decomposition that was hopeless for absolute pose is exact
enough for an increment.

## 10. WHAT THE SHIPPED ROTATION PATH ACTUALLY IS

⚠ **`tip_trim.TRIM_GAIN = 0.0`** — its rotation contribution is the identity. So the
object's rotation today is `Horn(PALM_LANDMARKS) ⊗ lean_trim`, and **the fingertips
drive POSITION only**.

⛔⛔ **This matters for `DO`, because the owner thinks in a different axis**
(2026-08-29: *"in my game, the angle is between the fingertips and the basis of the
palm"*). **The pipeline does not currently compute rotation in that axis.** Gating
`DO` on a fingertip angle would mean measuring something nothing produces yet.
⚠ Left as an open decision rather than silently resolved either way.

## 11. ⭐ `V2` STAYS IN THE DELTA PATH — measured, and it reverses an earlier claim

An earlier draft argued `V2` might become unnecessary, because a constant bias
cancels under differencing. **Measured: it costs +10 % on the yaw delta noise**
(1.45° → 1.60° p95) and exactly nothing on pitch and roll, where it is correctly
silent after the 2026-08-29 double-cover fix.

⛔ **But the lean is ~0.35 × the turn, so each increment carries ~35 % spurious
swing — and in an INTEGRATING design that accumulates instead of staying bounded.**
`V2` therefore matters MORE here, not less. The 10 % is worth paying.

## 11ter. ⛔⛔ DELTA-ORBIT IS THE BUILD — there is NO master gain, and no default to the old path

> **Owner, 2026-08-29, rejecting the first wiring:** *"ORBIT gain % at 0 is today's
> build: I do not understand: I do not want to have a mix of hand follow and
> integral of hand motion. I want pure integral of hand motion since the beginning
> with no interference of what we previously built."*

⚠ **The first draft was not, in fact, a blend** — `ORBIT_GAIN` was a HARD switch and
no frame ever had both paths contributing. But the objection stands on two counts
that were real:

1. ⛔ **IT DEFAULTED TO THE LEGACY PATH.** The build only became itself once a
   slider was moved, which is not a build — it is an option on top of the old one.
2. ⛔ **IT CARRIED A THIRD GAIN.** `ORBIT_GAIN` multiplied `RATE lo/hi`, so two
   controls did one job and a half-open master read as a partial mix. **A third
   gain is a blend by another name**, whatever the code does.

✅ **BOTH ARE GONE.** `delta_orbit.MODE` is `"orbit"` by default and that is the
only mode the product runs. `step()` takes no gain argument. The `ORBIT gain %`
slider is deleted; only the three `RATE` controls remain.

⭐ **`legacy` survives ONLY as a named diagnostic**, reached by `DELTA_ORBIT=legacy`
— because `A10` requires the pre-change build to stay reachable bit-for-bit and
`parity_replay` needs something to compare against. ⛔ **It is not a deployment.**
This is exactly `V1`'s shape, which the owner already accepted: `facing_user` is the
build, `CAMERA_MOUNT=legacy` reproduces the old one for measurement only.

⭐⭐ **WHAT IS *NOT* THE OLD PATH LEAKING IN, and it is worth being precise:**
* the **slerp / FREEZE** the target passes through is the DAMPER, and §5 shows it is
  the only thing that controls the drift an integrating build accumulates;
* `grab_hand_orientation` is used ONCE, to seed `orbit_prev_hand_q` so the first
  increment is the identity and the object cannot pop on pick-up;
* `lean_trim` (`V2`) still corrects the HAND's orientation before the increment is
  taken — §11 measures why that matters MORE here, not less. ⚠ If the owner wants
  it out of the delta path too, `LEAN pitch/roll %` at 0 does it live.

⛔ Nothing else from the 1.7.40 rotation path is on the live route.

## 11bis. ✅ WHAT WAS BUILT, 2026-08-29 — and the live look that is owed

| | |
|---|---|
| `Resources/delta_orbit.py` | `DO1`/`DO2`/`DO3`. Stdlib-only, numpy-free, **clock-free** (`dt_ms` passed in, like `hand_state` and `mate_connector`) |
| `analysis/verify_delta_orbit.py` | 10 sections, each documenting the wrong build it catches |
| both tools | one block, same shape, at the point `target_quat` is formed |
| the debug panel | the three `RATE` sliders, and **collapsing** (§11ter: there is no mode control) |

⭐⭐⭐ **THE WIRING'S ONE REAL DECISION: DELTA-ORBIT PRODUCES A `target_quat` AND
GOES THROUGH THE EXISTING SLERP, rather than composing onto `cube.orientation`.**
§5 says the drift control is the shipped FREEZE — and the freeze lives in the slerp
factor. Composing directly would bypass it and reinstate the 43/35/48°-per-minute
drift the row exists to avoid. ⚠ The cost is a constant: the effective CD gain is
`rate_gain × slerp_factor` (~0.86 at τ 20 ms and 40 ms frames), which the `RATE`
sliders absorb. A scale, not a distortion.

⛔ `orbit_prev_hand_q` is seeded at the grab, so the first increment is the identity
and the object cannot pop on pick-up — the same guarantee `grab_hand_orientation`
gives the absolute path. ⭐ It is also kept fresh **while the orbit path is OFF**, so
flipping the slider on mid-session starts from that frame instead of dumping the
whole accumulated difference in one increment.

### ⭐⭐ COLLAPSED SLIDERS (owner, 2026-08-29)

> *"any slider which is not in use for this build shall be collapsed in the sliders
> window (same as collapsing a row in a html file)."*

A 6th field on each `SLIDERS` row. A collapsed slider gets **no trackbar** (OpenCV
stacks trackbars above the canvas and cannot hide one individually, so not creating
it is the only way to actually shorten the panel), **keeps its constant** at the
module default, and still prints **one dim line** in the legend so the operator can
see it exists and what it is parked at.
⚠ Nine expanded, six collapsed (`GRAB radius %`, `FADE ms moving`, `WALK % of
hand`, `GRAB z margin cm`, `MATE snap r %`, `MATE preview r %`). Flipping one back
is a single `True`.
⛔ `_set_slider` replaces every raw `cv2.setTrackbarPos`: positioning a trackbar
that does not exist raises and kills the tool at startup — the same shape as the
2026-08-28 `NameError` that `verify_slider_wiring` was written for.

⚠ **THE GUARD ITSELF CARRIED THE FRAGILITY IT EXISTS TO CATCH**: `verify_slider_
wiring` built its fake trackbar map with a fixed **5-tuple unpack**, so the new 6th
field broke it — in a file whose own comments say *"INDEXED, NOT UNPACKED"*. Fixed,
and it gained a §6 covering collapsing.

✅ **Evidence**: 46/46 suites, `verify_delta_orbit` 10/10, `verify_slider_wiring`
green including the new §6.
⛔⛔ **THE LIVE LOOK IN BOTH TOOLS IS OWED, and nothing above closes it.**

## 12. Acceptance

1. **Golden vectors before anything is wired** (`CONSTRAINTS` §3):
   `analysis/verify_delta_orbit.py`. ⛔ Including **a negated quaternion**, per the
   rule the 2026-08-29 double-cover defect cost — `q` and `−q` are one rotation to
   the renderer and not to anything that reads an angle out of them.
2. ⭐ **CLOSURE DRIFT** is this row's own metric, and it is measurable offline:
   replay a take, integrate, and where the hand returns to a pose it held before,
   measure how far the object has moved from where it was. §3's table is the
   baseline to beat.
3. **`DELTA_ORBIT=legacy` reproduces the 1.7.40 path bit-for-bit**, so `A10`'s
   baseline stays reachable and `parity_replay` stays meaningful. ⛔ It is a
   diagnostic, never a deployment (§11ter).
4. `analysis/parity_replay.py` clean, because both tools change (`U6`).
5. ⛔ **A live look in BOTH tools closes it, and nothing else does** (`METHOD`).

## 13. Decisions taken

| | |
|---|---|
| ✅ **Orientation is UNBOUNDED** | owner, 2026-08-29. No clamp, no home pose. ⚠ Consequence accepted: *"hand flat = object upright"* is gone permanently |
| ✅ **All three constants are SLIDERS** | owner: *"build sliders instead of fixing arbitrary values"*. Only the knee carries a measured constraint |
| ✅ **All three axes integrate** | the pitch objection was withdrawn — it came from a POOLED statistic (§14) |
| ✅ **The window is a hard edge-on gate in v1** | §8; the graded fade waits for a wide-range take |

## 14. ⚠ WHAT THIS ROW ALREADY GOT WRONG, kept because each cost a turn

* **"Pitch is unusable for this design"** — from a POOLED ±29.3° figure that was
  almost entirely the 120–180° bin (past edge-on, the `T1` collapse). Per-pose,
  pitch is 1.1–2.1°. **A pooled statistic answered a question about a region.**
* **"The rate curve does double duty as a noise rejector"** — refuted by §5: noise
  and slow signal are the same size.
* **"A deadzone controls drift"** — §4 measured it making drift worse.
* **"`V2` may become unnecessary"** — §11 measured the opposite.
* **The harness's own pitch truth was the wrong axis** — the owner's fingertip axis
  is monotone where the palm length is not (`span(kind="tip_length")`).

* ⛔⛔ **EVERY ABSOLUTE PER-FRAME NUMBER IN THE FIRST DRAFT OF THIS SPEC WAS HALF
  ITS TRUE VALUE.** `lean_trim_ab.geo_deg` returned the geodesic on the quaternion
  sphere S³, which double-covers SO(3) — so it reported **half the rotation angle**,
  for the whole life of that file. ⭐⭐ **It survived because the gate it exists for
  is a RATIO, and a constant factor cancels exactly**: every `V2` verdict (1.072x,
  1.166x, 0.892x, 0.995x) is unchanged. ⭐ It was caught by this row's own golden
  vectors — `verify_delta_orbit` §4 asserts a hand-computed 20° instead of only
  asserting two things are close to each other. ⚠ The consequence here was concrete:
  the first `KNEE_DEG_S` default of 60 sat on the **wrong side** of the one measured
  constraint this design has, and is now 90.

⭐ The pattern in all six: **an aggregate hid a region, or an assumption stood in
for a measurement.** Every one was caught by measuring, and four of the five were
caught only because the owner pushed back on the conclusion.
