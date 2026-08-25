# `F1` — THE OBJECT'S TRANSFORM FROM THE FINGERTIPS — SPECIFICATION

> **STATUS** · live · **OWNS** · the design of `F1`, from the owner's ask to the
> acceptance bar
> **READ IF** · you are building `F1`, or judging whether a fingertip proposal is
> one of the arms already measured dead
> **LAST VERIFIED** · 2026-08-25
> **SOURCED FROM** · the owner's specification of 2026-08-25 (below) ·
> [`../../00_CORE/queue_notes/F1.md`](../../00_CORE/queue_notes/F1.md) ·
> [`../REJECTED.md`](../REJECTED.md) ·
> [`ROTATION_ACCEPTANCE_AND_TRAPS.md`](ROTATION_ACCEPTANCE_AND_TRAPS.md) ·
> the MediaPipe Model Card (`60_SECURITY_COMPLIANCE/evidence/`)

⛔ **Read [`../REJECTED.md`](../REJECTED.md) first.** Three of the four obvious
fingertip designs are already measured dead, and this spec is shaped around
their graves rather than around a blank page.

---

## 1. The owner's specification, 2026-08-25

Verbatim, as given:

1. The object's transform follows the transform of the **barycentre of the
   fingertips**.
2. **Grab condition**: the barycentre is close to the object — as before, but the
   fingertip barycentre replaces the palm centre.
3. The **plane of the fingertips** helps define the object's quaternion. The palm
   helps further, especially when the fingers are curled and the tip plane is
   **not** coplanar with the palm. *(What to do when it IS coplanar — §6.)*
4. While held, if the fingertips move, the object follows the barycentre's
   transform.
5. **Release conditions unchanged** — out of window, clamp within a margin, etc.
6. ⭐ **The back-of-hand snap restriction is REMOVED.** An object may be grabbed
   with the back of the hand to the camera, including on re-entry into frame.
7. **Fingertip jitter**: suppress spurious position changes, with a **live slider**
   for the filter value.
8. ⭐ **Keep τ = 20 ms** (owner, mid-specification): `L1`'s shipped rotation time
   constant is not to be disturbed by this build.

---

## 2. ⛔ What this spec may not be, and why

Four arms are already paid for. Every one of them is a natural reading of "drive
the object from the fingertips", which is why they are listed before the design.

| dead arm | the measurement |
|---|---|
| **A rigid fit over palm ∪ tips** (`PALM_AND_TIPS`) | `B4`, 2026-08-17 — jitter p95 **9.85° → 27.79°** in real play |
| **The 9-point palm+tips constellation** | A10 REJECT 2026-08-23 — **+1.4°** of axis fidelity bought **+4.9°** of p95 jitter. Its "wins every take" reputation came from an axis-**contaminated** take |
| **Down-weighting world z** | REJECTED 2026-08-23 — the `k` that fixes yaw **doubles** pitch. Closes the whole "weight z less" family |
| **Fitting anything, rather than holding it** | `B8` — every fit **loses to holding the last value** |

⭐ **The single sentence that explains all four**: the fingertips move *relative to
the palm*, and a rigid fit is obliged to explain that motion as **whole-object
rotation**. It has nowhere else to put it.

⭐⭐ **And that is exactly the signal the owner is asking for, seen from the other
side.** So the design rule is forced, not chosen:

> **The tips must enter as a DEFORMATION measured in the palm's frame — never as
> extra points in one rigid constellation.**

### ⚠ The second, independent reason — Google's own evaluation

The Model Card, landed 2026-08-25:

> *"per-joint MNAE is the smallest at the base of each finger, and gets larger
> toward the fingertip… the prediction is easier around the palm which is more
> rigid than the fingers."*

**`F1` drives the transform from the landmarks the model estimates worst**, and
*"the normalized absolute error is larger for blurry or occluded joints"* — while
a hand closing on an object occludes its own tips. Independent literature puts
numbers on it: MediaPipe holds ~90% landmark precision to occlusion level 10, but
**recall falls by about half at level 8**, and a dominant failure mode is fingers
occluded by the palm from the camera's viewpoint — which is the *closed grab pose*
([Robustness Evaluation in Hand Pose Estimation Models using Metamorphic
Testing](https://arxiv.org/pdf/2303.04566), [MediaPipe issue
#3008](https://github.com/google/mediapipe/issues/3008)).

⛔ This does not kill `F1`. The palm genuinely is too coarse for assembly-style
alignment, which is the owner's whole point. It sets the **error budget**: tips
are noisy *measurements*, the palm is the *reference*, and the tips' authority
must be bounded.

---

## 3. The architecture — two channels, one of them bounded

```
                  ┌─ R_palm(t) ── Horn over the 5 palm landmarks ── UNCHANGED, SHIPPED
   landmarks ─────┤                    (coarse, reliable, low-resolution)
                  └─ tips ── express in palm frame ── R_res(t) ── gain ── CLAMP ── R_trim(t)
                                                     (fine, noisy, high-resolution)

   ΔR(t) = R_palm(t) · R_trim(t) · R_palm(grab)⁻¹        [R_trim(grab) = I]
   R_obj(t) = ΔR(t) · R_obj(grab)
   displayed  ← existing τ = 20 ms slerp                  ── UNCHANGED
```

This is a **complementary fusion**: each channel supplies the band it is good at.
It is directions 1 + 2 of [`F1.md`](../../00_CORE/queue_notes/F1.md)'s brainstorm
list, merged — palm as frame, tips as a bounded deformation.

### ⭐ The five properties that make it safe to ship

1. **Whole-hand rotation is removed from the tip channel by construction.** The
   tips are expressed in the palm frame, so `R_res` cannot contain wrist motion —
   the failure mode that killed both rigid arms is structurally absent, not tuned
   away.
2. **`R_trim(grab) = I`, so there is no pop at grab.** Same guarantee `4.2` gets
   for depth by making its ratio 1.0 at the grab frame.
3. ⭐⭐ **Gain 0 ⇒ byte-identical to shipped Horn.** `R_trim ≡ I` collapses the
   expression to today's `ΔR = R_palm(t)·R_palm(grab)⁻¹`. **This must be *proved*,
   not asserted** — replay a recorded take with the gain at 0 and require
   bit-equality on every frame. `T6d` established the method (975/975 frames), and
   it is what made that build revert-free when the owner rejected it.
4. **It fails safe.** Every degeneracy, dropout and low-confidence path in §6
   resolves to `R_trim ← last good value` or `→ I`, i.e. to current behaviour.
5. **τ = 20 ms is untouched.** The trim enters *before* the slerp, so it is
   smoothed by the same shipped time constant. ⛔ **No second orientation
   smoothing stage may be added** — after the predictive filter was removed as
   dead on 2026-08-24, the slerp is the only smoothing in the rotation path, and
   that is precisely why its time constant is the whole of the felt lag.

### 3.1 Why a Horn fit over the tips, rather than an explicit plane

The owner's framing is *"the plane of the fingertips defines the quaternion"*. ⚠ A
plane supplies only **2 of 3 DOF** — its normal. The third, roll about that
normal, comes from the *in-plane arrangement* (where the thumb sits relative to
the pinky). Fitting the tip cloud directly returns all three at once and never
needs the normal to be named, so it cannot be destabilised by the normal flipping
— which matters, because a normal from a nearly-degenerate point set is exactly
what `palm_observability` was written to detect.

### 3.2 ⭐ The fit doubles as a coordination detector — this is a feature

The 5 tips are not a rigid body either. So `R_res` is *"the best rigid explanation
of how the tip cloud moved relative to the palm"*, and that is the right quantity:

* all five tips rotating together — the user **turning the object in their
  fingers** — produces a large, coherent `R_res`;
* one finger twitching produces a small `R_res` with a large residual, further
  suppressed by the gain and the clamp.

⚠ Log the fit **residual** per frame from day one. It is the natural
confidence signal and there is no way to recover it after the fact.

---

## 4. Position

### 4.1 What already ships — read this before changing it

`TRANSLATION_CANDIDATE_LANDMARKS` is **already 5 fingertips + 4 non-thumb MCPs**
([`HandsTriggeredActions.py:75`](../../../Local_pc/Movement_with_hand_detection/Resources/HandsTriggeredActions.py#L75)),
inverse-distance-weighted to the object's position **frozen at grab**, plus a
`grab_residual_offset` applied every frame after. So the shipped anchor is *not*
the palm centre — the fingertips are already in it. The owner's request is a
**re-weighting**: from a 9-point frozen inverse-distance blend to the 5-tip
barycentre.

⚠ That reframes the risk. The change is smaller than it sounds, and the specific
thing it alters is **how much finger articulation leaks into translation**.

### 4.2 ⚠ The amendment — articulation moves the barycentre

Extending one finger moves the tip barycentre by roughly **one fifth of that
fingertip's excursion**. A finger straightening through ~8 cm therefore
**translates the object ~1.6 cm while the user is trying only to rotate it.**

This is the translation analogue of the contamination that killed the 9-point
rotation fit, and it is worth stating plainly: *nothing in the owner's
specification is wrong here* — a real held object does move when you reposition
your fingers on it. The question is only whether the **measured** amount matches
the intended feel. §9 measures it before a line is written.

### 4.3 The form — one slider spans the owner's request and the safe fallback

Decompose the barycentre into palm motion and articulation:

```
u(t)       = R_palm(t)⁻¹ · ( c_tips(t) − c_palm(t) )     tip barycentre IN THE PALM FRAME
u_drift(t) = u(t) − u(grab)                              pure articulation, zero at grab

obj_pos(t) = c_palm(t) + R_palm(t)·[ u(grab) + g_pos · clamp(u_drift(t), r_max) ]
             + offset_grab
```

* `g_pos = 1`, `r_max = ∞` → **exactly the plain tip barycentre the owner asked
  for**.
* `g_pos = 0` → palm-anchored, i.e. articulation-immune.
* `offset_grab = obj_pos(grab) − (…)|grab` preserves today's no-pop residual
  exactly.

⭐ So the owner's request is the **default**, the safe arm is the **same code with
one number changed**, and the live take picks the value instead of an argument
doing it. Depth continues to come from `palm_depth`'s ratio over the **rigid palm
quad** — ⛔ never from a fingertip span, which has no fixed baseline because
fingers bend.

---

## 5. Grab and release

### 5.1 Grab — the barycentre replaces the palm centre

`_try_snap`'s `hand_pos` becomes `c_tips` (filtered, §8). Everything else in that
function is **unchanged**: per-cube `GRAB_RADIUS_MULTIPLIER = 1.5` scaled to the
object's `projected_size_px`, plus `4.2`'s axial `GRAB_Z_TOLERANCE_M` gate.

⚠ **One consequence to check live, not to reason about**: the tip barycentre sits
distal to the palm centre and **moves toward the palm as the hand closes**. Grab
therefore triggers at a slightly different hand pose than today. Expect
`GRAB_RADIUS_MULTIPLIER` to need re-tuning on the live take; it is already
flagged in-code as a live-tuned value.

### 5.2 Release — unchanged, with one thing to protect

Release conditions stay exactly as they are: tracking loss (after `D2`'s 150 ms
coast and `D3`'s resync blend), `_release_stranded_cubes`, the play-volume clamp,
the arbitration order.

⛔ **The one hazard**: during `D2`'s coast a tip may be missing, and a barycentre
computed over 4 tips instead of 5 **jumps**. Coast must therefore freeze the tip
configuration — hold `u(t)` and `R_trim(t)` at their last good values for the
duration (`B8`: holding beats every fit). ⚠ A barycentre that silently changes its
denominator is the same class of defect as the adaptive edge margin, which failed
live when its input collapsed 45% in one frame.

### 5.3 ⭐ Removing the back-of-hand snap restriction

**Well-founded, and the evidence already supports it.** Rule 3 blocks snapping
while thumb-outward unless the hand was thumb-outward at its last release
(`_last_known_thumb_outward` / `_thumb_outward_snap_allowed`). It rests on
`is_thumb_outward`, which applies a **handedness-dependent** correction — so it
**inverts on a wrong label**, and the label was wrong 10.8% of the time until
`U7`. Separately, back-facing frames measure **better**, not worse, on both
control takes (16.8° vs 23.5°, and 11.8° vs 24.5°).

Three consequences, none of them blocking:

1. ⛔ **Delete the state machine, do not orphan it.** `_last_known_thumb_outward`,
   `_thumb_outward_snap_allowed` and the release-site write at
   `HandsTriggeredActions.py:1329` all go. Dead gating state that still updates is
   how a rule comes back to life by accident.
2. ⚠ **This re-opens `N8`** (an object stolen by occluding the holding hand) —
   rule 3 was incidentally suppressing part of it. `N8` is already routed to `B5`,
   which with `4.4` is the real fix. Record it, do not patch it here.
3. ✅ **`U8` STAYS.** Refusing to snap on a *provisional chirality* is a different
   rule, shipped and accepted live 2026-08-22. Removing the back-of-hand block
   must not remove the 200 ms settling gate with it.

---

## 6. ⭐⭐ The coplanarity question — answered, and the premise inverted

> *"if the plane of the fingertips is coplanar with the palm (fingers fully
> extended), advise what to do"*

### 6.1 Coplanar is the SAFE case. It needs no special handling at all

When the fingers are extended, the tips and the palm belong to one near-rigid
slab. In the §3 form that means `R_res ≈ I`, so `R_trim ≈ I`, so the object is
driven by `R_palm` alone — **today's shipped behaviour, reached automatically**.

⭐ And that is *correct*, not a fallback: with extended fingers there is no
independent fingertip signal to extract. Coplanarity means the tip channel is
**redundant**, not ambiguous. The palm is the well-estimated part of that slab
(Model Card), so deferring to it is the right answer.

⛔ **Do not add a rigid palm+tips fit for this case.** It is tempting — the
constellation really is rigid there, and bigger — but it is the A10-dead arm, and
switching *into* it on a posture test would inject rotation at the switch, which
is the changing-driver-set hazard `F1.md` flags.

### 6.2 The dangerous case is COLLINEARITY, and it is a different geometry

The tip cloud's own eigenvalues decide observability. Using the machinery already
in `palm_geometry.palm_observability` (`1 − S₃/S₂` from a 3×3 scatter matrix, no
numpy), on the tip set in the palm frame, with `λ₁ ≥ λ₂ ≥ λ₃`:

| quantity | meaning | degenerate when |
|---|---|---|
| `spread = √(λ₂/λ₁)` | **collinearity** | → 0: tips lie on a line. Rotation **about that line is unobservable** |
| `flat = 1 − √(λ₃/λ₂)` | planarity | → 0: cloud is fully 3D (fine); → 1: perfectly planar (fine) |
| `scale = √λ₁ / palm_width_px` | absolute size | → 0: **fist** — tips clustered, every angle ill-conditioned |

⛔ **`spread` is the gate, not `flat`.** This is the whole correction to the
premise: a *planar* tip set is perfectly well-conditioned — a plane has plenty of
rotational information. A *collinear* one is not, and it arises in two ways that
matter here:

* **fingers extended and the hand edge-on** — the five tips project to nearly a
  line;
* **a precision pinch** (thumb + index only) — two contact points define a line,
  and rotation about it is unobservable *from the contacts*. Inherent to the
  gesture, not a sensor defect.

**The remedy is the house rule, and it is already three-times validated:
`DR-2` freezes the sign in the edge-on band, `U8` refuses to snap on provisional
chirality, `4.2`'s decision 1 refuses without depth — suppress, do not guess.**
So: fade the trim's authority out continuously as `spread` falls, and hold the
last good `R_trim` below the floor. ⚠ Fade, never switch — a hard gate is itself a
rotation step.

### 6.3 ⛔ On inferring z from palm width or finger length rotated 90°

> *"the position on z has to be assumed from the palm width rotated 90° (yaw) or
> finger lengths rotated 90° (pitch)"*

**The instinct is right and it is already a queue row — but it must not be built
inside `F1`.** Three measured reasons:

1. ⛔ **The `acos` fold** (trap #1): *any* foreshortening-derived angle folds past
   edge-on — 140° reads as 40°. It has produced bogus gains of **3.57, 2.41 and
   21.5** in three separate sessions. Recovering an angle from a width ratio is
   precisely this operation.
2. ⛔ **A threshold must not be computed from a quantity that is noisy where the
   threshold acts.** The adaptive edge margin was built from the *current* palm
   width, the measured width collapsed **45% in one frame**, and the object was
   carried out of frame. Edge-on is exactly where palm width is least reliable,
   and this proposal reads palm width exactly there.
3. ⚠ **Finger length is not a rigid baseline.** Fingers bend; the palm quad is the
   only rigid span on the hand, which is why `palm_depth` uses it.

⭐⭐ **The disciplined version of this same idea already exists and is ready to
run**: `T6`'s **2D ratio table** — a declared-ground-truth lookup with yaw and
pitch kept **separate**, captured **on-axis**, the fold handled by `DR-2`'s sign,
and the runtime off-axis compensation derived rather than fitted. Protocol:
[`RATIO_TABLE_CALIBRATION_PROTOCOL.md`](RATIO_TABLE_CALIBRATION_PROTOCOL.md);
tool: `tools/RecordRatioCalibration.py`; six takes.

⭐ **Keep the layers separate.** If the ratio table validates, it improves
`R_palm`, and `F1` inherits the improvement **with no change to this spec** —
because §3 consumes `R_palm` as a black box. That is the entire benefit of putting
the palm in the frame position rather than in the constellation.

---

## 7. What the palm brings to the fusion

Each of these is measured, and each is a reason the palm stays load-bearing:

| asset | evidence |
|---|---|
| Most accurate region of the model | Model Card, per-joint error smallest at the finger bases |
| Horn's 5-point averaging is *why* it is stable | Horn's flaw is **bias**; every per-frame replacement's flaw is **variance** |
| `horn-palm` won a six-arm live A/B | `B4`, 2026-08-17 |
| ⭐ The palm normal's **bearing** is trustworthy | direction error median **10.6°** vs 45° chance — only the out-of-plane *magnitude* is corrupt |
| Depth, with scale cancelling exactly | `palm_depth`'s ratio form, baselined per grab |
| Chirality | `U7` — geometry **98.0%** vs the label's 93.2% (n = 1127) |
| Conditioning is measurable | `edge_on_measure`, invariant under pure roll |

---

## 8. Fingertip jitter — an adaptive filter, ⛔ not a deadband

### 8.1 Why not the threshold the specification asks for

A fixed threshold ("ignore motion below *x* px") is a **deadband**, and its
failure mode is **stiction**: the object does not move at all until the input
crosses the threshold, then moves by the whole accumulated amount at once. That
converts jitter into **small pops** — the exact artefact this project has spent
the most effort removing, and the worst possible trade for *assembly-style fine
alignment*, which lives entirely at small amplitudes. A deadband is precisely
wrong in the band `F1` exists to serve.

### 8.2 ⭐ The state of the art, and it fits this project's own rules

The standard answer is the **1€ filter** (Casiez, Roussel & Vogel, CHI 2012) — a
first-order low-pass whose **cutoff frequency rises with speed**: a low cutoff at
rest kills jitter, a high cutoff in motion kills lag. The paper's own result is
*less lag for a reference amount of jitter reduction* than the alternatives, and
it is the filter used across hand- and fingertip-tracking systems.

* **Two parameters, both intuitive** → exactly two sliders: `f_cmin` (lower ⇒ less
  jitter at rest) and `β` (higher ⇒ less lag when moving).
* ⭐⭐ **It is time-based, not per-frame.** This is `L1`'s hard-won lesson in
  another form: a fixed per-frame factor made the feel move with room lighting
  (**111 ms** in good light, **149 ms** in poor) because the frame rate is
  **camera-bound**. A per-frame deadband would reintroduce that dependency.
* **Licence: BSD-3-Clause**, and it ships as a third-party component in Qt
  WebEngine — clears `N13`.
* ⛔ **Transliterate it, do not add the dependency.** It is a few dozen lines, and
  `Resources/` is **stdlib-only and numpy-free by contract** (`CONSTRAINTS` §2).
  It also has to survive the port, so it lands with golden vectors (§3 of
  `CONSTRAINTS`).

### 8.3 Where it sits, and the lag budget

⛔ **On the tip positions only — the input side.** The τ = 20 ms slerp stays the
sole orientation smoothing (owner, this session).

⭐ The two stages do not simply add: at rest the 1€ filter is aggressive but
**nothing is moving, so its lag is unobservable**; in motion its cutoff opens and
it approaches a pass-through. That is the property that makes it nearly free here.
⚠ *Nearly* is not *provably*: measure end-to-end lag with the filter in and out at
the speeds the hand actually reaches during fine alignment, and state the number.
`L1` measured the felt lag once already; this must not quietly give it back.

### 8.4 Slider discipline — already learned the hard way

`LiveSnapDebug.py:151` carries it: **a slider whose displayed number is not the
applied value is worse than an unlabelled one** — a discrete ladder once showed
"3 ms" while applying something else. The existing `SLIDERS` panel is continuous
in real units; add `f_cmin`, `β`, and the §3 trim gain to it in the same style.

---

## 9. ⭐⭐ STEP 0 — measure before building. It is free, and it decides four numbers

The corpus is **415 landmark takes** and can answer all of this **today**, with no
new recording and no code shipped. `A10` is the house rule; this is what applying
it before the build looks like.

| # | question | why it decides something |
|---|---|---|
| 1 | **Per-tip INSTABILITY while an object is held** vs. while it is not — frame-to-frame tip motion in the palm frame, per tip, split on `cubes[*].owner` | The Model Card says tips degrade under occlusion, and a closing hand occludes its own tips. If tips are unusable exactly while an object is held, the trim clamp must be tight — and we learn it now, not from a live session |
| 2 | **How large is `R_res` in real handling?** Distribution of the tip-residual angle over the production takes | Sets `θ_max` from data. If real assembly-style motion is ±10°, a 45° clamp is decoration |
| 3 | **How far does the tip barycentre move under pure articulation?** (§4.2) | Decides whether `g_pos = 1` is shippable or wants a clamp |
| 4 | **How often is the tip set collinear or clustered?** `spread` and `scale` distributions, split by edge-on band | Sets §6.2's floors from measurement rather than taste |

⚠ Recorded takes carry **no images** (`N14`), so anything needing pixels cannot be
settled this way. All four above are landmark-only.

⛔⛔ **AND THE RECORDER CARRIES NO PER-LANDMARK CONFIDENCE — checked, not assumed.**
`_record_frame` writes exactly `landmarks` (x, y px) and `world_landmarks`
(x, y, z); MediaPipe's per-point `visibility`/`presence` are **not** stored, and
are not reliably populated for hands in any case. So question 1 **cannot** be
asked as *"what does the model say its confidence was"*.

⭐ **The substitute is better, not merely available.** Measuring the tips' actual
frame-to-frame **instability in the palm frame** scores the thing that damages the
trim — motion that is not the hand moving — instead of the model's opinion of
itself. It also keeps the house rule that made `_record_flush` what it is:
**record what ran, never re-derive it.** ✅ And the split is free: every row
carries `cubes[*].owner`, so *held* and *not held* separate exactly.

---

### ⭐⭐ ANSWERED 2026-08-25 — `analysis/f1_tip_census.py`, 123 takes

Full numbers and their derivation: [`../../00_CORE/queue_notes/F1.md`](../../00_CORE/queue_notes/F1.md).
The four results, and what each one settles:

| | result | consequence for this spec |
|---|---|---|
| **M1** | noise floor **1.28–1.62 mm** median, 3.6–4.7 mm p95 per tip; held vs free **1.05–1.10** | ✅ **The design survives.** The Model Card's occlusion penalty is real but is 5–10%, not a collapse |
| **M2** | residual **75–95°** at p90–p95 **inside ~0.5 s** | ⛔ **§3's trim cannot run at gain 1.** M1 rules out noise, so this is the rigid model being wrong — clamp **far below** the 16° short-horizon median |
| **M3** | barycentre drift **1 cm median / 6 cm p95** in ~0.5 s with the palm still | ⛔ **§4.3's `g_pos = 1` needs a clamp or a gain < 1.** The spec's own ~1.6 cm estimate was conservative |
| **M4** | `spread` p1 **0.172**; a 0.20 floor freezes **1.89%** of frames | ✅ **§6.2's floor is 0.20** — cheap, and above the p1 |

⚠⚠ **A trap was hit while measuring and is worth keeping.** Raw frame-to-frame tip
motion reads p95 **21–31 mm**, which looks like an unusable channel and was nearly
reported as one. Restricting to frames where the **palm itself barely moved**
(< 1°, < 2 mm) shows almost all of it is the operator genuinely moving their hand,
and the true floor is **1.5 mm** — a factor of ~15. ⭐ Any "the tips are too noisy"
claim must state which of the two it means.

⛔ **And the recorder carries no per-landmark confidence** (§9's note), so M1 is
what the tips *did*, not what the model *claimed*.

---

## 10. Acceptance

⛔ **`A10` in full.** The existing bar
([`ROTATION_ACCEPTANCE_AND_TRAPS.md`](ROTATION_ACCEPTANCE_AND_TRAPS.md) §5) is a
**non-regression** floor — `F1` is not permitted to buy fine control by spending
gross fidelity:

| metric | take | baseline | `F1` requirement |
|---|---|---|---|
| YAW axis, mean | `2026-08-22_134553_yaw_sweep_constant_depth` | 14.5° | must not regress |
| visible LEAN @60–90° | same | 23.4° | must not regress |
| PITCH axis, mean | `2026-08-02_191816_pitch_sweep_slow` | 5.5° | must not regress |
| ROLL axis / gain | `roll_card_axis_check_b` | 6.7° / 1.02 | must not regress |
| ⭐ **JITTER p95** | `2026-08-22_154426_production_4_1` | **25.41°** | ⛔ **the one that killed the 9-point fit** |

⚠ **Cross-take absolute axis numbers are not comparable** — the camera moved
between recordings. Same-take A/B only.

### 10.1 ⭐⭐ A metric the project does not yet have, and `F1` needs

Every metric above measures **gross sweep fidelity**. `F1` exists to buy **fine
alignment**. ⛔ **So `F1` could pass all of them and still deliver nothing the
owner asked for.**

Add a **trim-resolution** measurement: with the wrist held still and only the
fingers moving through a **declared** small rotation, measure (a) how much the
object actually rotates — the *gain* of the fine channel — and (b) the jitter
floor at that amplitude. The usable resolution is the ratio.

⚠ **`B4`'s binding method rule applies**: *an anchor metric must not share an
expression with the anchor.* The declaration must come from the operator before
the take, as `U7`'s acceptance take and the ratio-table protocol both do — never
from the estimator being scored.

### 10.2 The gates, in order

1. **Gain 0 ⇒ bit-identical to shipped Horn**, proved by replay (§3, property 3).
2. Step 0's four measurements, published before the design constants are fixed.
3. Golden vectors for the new estimator code, in the same change (`CONSTRAINTS` §3).
4. `analysis/parity_replay.py` — **NO DIVERGENCE** (`U6`; two pipelines are kept).
5. **A live take closes it, not the harnesses.** Both tools, back to back. §13.6.1
   shipped *inverted* while passing an "end-to-end confirmed" claim.
6. ⚠ `T6d` had the best numbers of any correction and was still rejected, because
   the panels differed by a median 4.83° — **below what an eye resolves on a
   40–80 px cube.** The bar is *visibly* better, not *measurably* better.

---

## 11. Literature and prior art

### 11.1 What the field does

* **1€ filter** — Casiez, Roussel & Vogel, CHI 2012. Adaptive-cutoff low-pass; the
  standard answer to the jitter/lag trade in interactive systems. BSD-3-Clause.
  [paper](https://direction.bordeaux.inria.fr/~roussel/publications/2012-CHI-one-euro-filter.pdf) ·
  [ACM](https://dl.acm.org/doi/10.1145/2207676.2208639) ·
  [reference code](https://github.com/casiez/OneEuroFilter)
* **Contact-point manipulation in VR** — the mainstream design is contacts, not
  constellations: two contacts infer a *rotate*, three or more a *grasp*, solved
  by preserving contacts and minimising finger penetration. See §11.2 before
  adopting it. [survey](https://arxiv.org/html/2504.00337) ·
  [grasping in VR](https://dl.acm.org/doi/fullHtml/10.1145/3574131.3574428)
* **Robust fitting over noisy landmarks** — Horn/Kabsch–Umeyama closed forms with
  **M-estimator soft weights** are the standard robustification; hard inlier/
  outlier switching (RANSAC-style) is the wrong tool at 5 points. This supports
  §12's continuous weights over a discrete driver set.
  [outlier-robust estimation](https://arxiv.org/pdf/2007.15109)
* **Degeneracy detection by eigenvalue ratio** — a best-fit plane is unique only
  while the smallest eigenvalue is separated from the others; collinear inputs
  make the solution non-unique. Standard practice, and it is what
  `palm_observability` already implements.
  [CGAL PCA fitting](https://doc.cgal.org/latest/Principal_component_analysis/group__PkgPrincipalComponentAnalysisDLLSF3.html)
* **MediaPipe under occlusion** — ~90% precision to occlusion level 10, but
  **recall roughly halves by level 8**; fingers occluded by the palm are a
  dominant failure mode. [metamorphic testing](https://arxiv.org/pdf/2303.04566)

### 11.2 ⛔⛔ A PATENT FINDING THAT CHANGES WHICH ARM TO BUILD

**`US9696795B2`** — *"Systems and methods of creating a realistic grab experience
in virtual reality/augmented reality environments"*, filed **2015-02-19**
(Leap Motion → Ultraleap), **reassigned 2026-01-16 to `SIM IP HXR LLC`**. Its
claims cover detecting contacts between a hand and a virtual object and computing
the object's **rotation** so the contact points are preserved. Term runs to
approximately **2035**. It sits in a family with `US10261594`, `US10429923`,
`US10607413`, `US9767613`, `US12131011`.
[US9696795B2](https://patents.google.com/patent/US9696795B2/en)

⚠ **A reassignment from an operating company to a holding entity is the pattern
that precedes assertion**, and this project's audience is commercial (`N13`) and
public-facing.

⭐ **Consequence — do not build direction 3 (the contact-point model)** from
`F1.md`'s brainstorm list. The §3 design is not exposed the same way: it is a
palm-frame deformation feeding a bounded trim, built from **Horn 1987 / Kabsch
1976** and ordinary complementary filtering — the same defensive posture that made
`T6`'s solver 1971/1997/2000 prior art rather than IPPE/OpenCV.

⚠ Not legal advice, and not a claim-by-claim reading. It is a **recorded risk
with a free alternative**, which is the cheapest moment to act on one.

---

## 12. ⭐ Amendments — the things that make it bullet-proof

Beyond the specification as given. Each closes a failure this project has already
paid for once.

1. ⭐⭐ **Continuous per-tip weights, never a changing driver set.** `F1.md` warns
   that a finger joining or leaving mid-hold moves the fit. ⛔ Do not solve it with
   a hysteretic in/out gate — solve it by **never switching**: weight every tip by
   a confidence that is **rate-limited**, so its contribution can go to zero but
   only smoothly. A continuous weight cannot inject a step; a gate always can. The
   robust-fitting literature agrees — soft M-estimator weights over hard inlier
   switching, especially at 5 points.
2. **Clamp in axis-angle, and clamp the *rate* as well as the magnitude.** A
   magnitude clamp alone still permits a full-clamp jump in one frame if the fit
   flips branch. Bound `‖R_trim‖` **and** `d‖R_trim‖/dt`.
3. **Freeze, do not extrapolate, on every dropout path** — `D2` coast, missing
   world landmarks, low `spread`, low `scale`. `B8` measured that holding the last
   value beats every fit; `D4`'s extrapolation was declined by the owner after
   seeing `D2`/`D3` live.
4. **Log `R_res`, its residual, `spread`, `scale` and the applied clamp per frame
   from the first commit.** ⚠ And **record what ran** rather than recomputing it
   later — four harnesses once reported CLEAN on takes the owner had just watched
   fail, and every one of them was a recomputation.
5. **One tuning constant, one module** (`CONSTRAINTS` §4). τ lives in
   `hand_state.py`, not in both tools; the trim gain, clamp and filter constants
   get the same treatment. Two tools, one copy.
6. ⚠ **Do not let `F1` anticipate `T7`.** World-referenced rotation ships **with
   `U12`**, and 20° of camera tilt alone reproduces the entire yaw show-stopper.
   `F1` works in camera frame like everything else.
7. ⚠ **Re-tune `GRAB_RADIUS_MULTIPLIER` on the live take** (§5.1), and expect to.
8. **Two open sub-questions stay open until the live take** — the owner has not
   answered them and they must not be guessed: whether **every tip** or **thumb +
   index only** drives the trim, and whether the object should follow the tips
   like a grasped object or take a bounded trim on top of the palm. ⭐ §3's form
   *contains* both — thumb+index is a weight vector, and "follows like a grasped
   object" is the clamp opened up. **Ship the sliders, let the live take decide.**

---

## 13. Build order

| step | what | gate |
|---|---|---|
| 0 | ✅ **DONE 2026-08-25** — §9's four measurements | `analysis/f1_tip_census.py`; results in §9 |
| 1 | 1€ filter, transliterated + golden vectors, on the tip barycentre only | filter OFF ⇒ bit-identical |
| 2 | `c_tips` replaces the palm centre for snap and translation (§4, §5.1) | `parity_replay`, then a live look |
| 3 | ✅ **SHIPPED 2026-08-25** — back-of-hand snap rule + its state removed (§5.3) | 26/26 suites · traces regenerated · `parity_replay` NO DIVERGENCE / 2978 frames · `N8` re-opened. ⛔ **live take owed** |
| 4 | The palm-frame trim (§3), gain slider defaulting to **0** | ⛔ gain 0 ⇒ **bit-identical to shipped Horn**, proved by replay |
| 5 | Conditioning fades (§6.2) | floors from step 0, not from taste |
| 6 | Live take, both tools, back to back | ⭐ *visibly* better, per §10.2's bar |

⭐ Steps 1–3 are the owner's specification with no fusion in them at all, and
each is independently shippable. Step 4 is the one that could regress jitter, and
it lands **switched off**.
