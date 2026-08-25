# T6 — the orientation investigation, verbatim

> **history · §2.0–§2.0.19, twenty sections of measurement on the yaw lean**
> **SOURCE** · `HANDOFF_T6_ORIENTATION_FROM_2D.md` §2.0–§2.0.19 — extracted verbatim, not edited

⭐⭐ **Read §2.0.4 before proposing any rotation fix** — *where three rejects
leave it*. The short version: **Horn's flaw is BIAS, every per-frame
replacement's flaw is VARIANCE.** ⚠ Also here: the Google patents, the
distortion measured at source, and the anisotropic fit's derivation.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/HANDOFF_T6_ORIENTATION_FROM_2D.md lines 105-1139
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
### 2.0 ⭐⭐⭐ ROOT CAUSE, 2026-08-24 — IT IS **TWO** CAUSES, AND §2.1 BELOW IS PARTLY SUPERSEDED

⚠⚠ **Read this before §2.1 and §2.2.** A re-analysis of the CARD takes, requested by
the owner, found the yaw lean has **two independent contributors of similar size**.
T6 attacked only one of them — and by a route that made things worse — which is why
it failed.

**CAUSE 1 — MEDIAPIPE FABRICATES THE PALM'S DEPTH. Corpus-wide, 61 sessions,
3131 frames that are FACE-ON BY PIXEL EVIDENCE** (projected palm area ≥95% of that
session's own p99, so the test never assumes what it measures):

| quantity | should be | measured |
|---|---|---|
| world palm normal vs the camera axis | ~0° | **median 24.9°** (p75 43.9°, p95 50.4°) |
| \|world z\| / \|world xy\|, wrist→middle_MCP | ~0 | **median 0.40** (p75 0.99, p95 1.18) |

⭐ **And the x,y are FINE** — on the checked face-on frame the long axis reads
**1.2° from vertical in pixels and 1.1° in world x,y**, then **47.3°** once z is
included. So Horn's **GRAB REFERENCE is already tilted ~25° out of plane before the
hand rotates at all**, and a subsequent turn about the true vertical is fitted as a
turn about a tilted axis. ⭐ This finally explains, in one mechanism, why roll is
accurate (gain 1.02 — it lives in the image plane where x,y are good), why yaw and
pitch err in OPPOSITE directions (both consume the bad z), and why scaling z slides
the tilt 14.5°→0.6° (it shrinks exactly this fabricated component).

**CAUSE 2 — THE CAMERA IS ROLLED ~11°, AND THE CARD TAKES ARE WHAT REVEAL IT.**
In a card take the operator clamped a card with its **long edge vertical**, so the
hand's long axis was held at **true world vertical by a physical reference** — the
only gravity datum a landmark-only corpus can offer. Its residual **image** tilt is
therefore the camera's roll. Measured from pixels only:

| take | long-axis image tilt | IQR |
|---|---|---|
| `..._203307_yaw_card_axis_check_b` | **−10.8°** | 7.0° |
| `..._202153_yaw_card_axis_check` | **−11.1°** | 2.4° |
| no-card yaw takes | **+2.5° / +5.8° / −4.0°** | — |

⭐⭐ **The two card takes agree to 0.3°**, which is the signature of something
systematic rather than operator noise. ⭐ **And the no-card takes sit near ZERO** —
with no physical reference the operator aligned the hand to what *looked* vertical,
i.e. to the IMAGE.

⛔⛔ **BUT "CAMERA ROLL" IS THE WRONG READING OF IT — OWNER, 2026-08-24: *"Camera
roll is not the issue. Camera pitch is the issue, and cannot be measured at the
moment (portable webcam)."*** The −11° is a real, reproducible measurement; its
INTERPRETATION was wrong, and the owner knows the physical rig. With no camera roll,
image-vertical **is** world-vertical projected, so the −11° means **the hand/card was
consistently held ~11° off vertical** — operator posture, not optics. ⭐ That is
corroborated by the owner's own earlier remark about the card takes: *"I had to tilt
the hand and arm to keep the card straight up."* ⚠ **So the card takes are NOT a
usable gravity datum after all**, and the "camera roll" line is retracted rather than
deleted, because the *measurement* stands even though the inference did not.

⭐⭐ **AND THE ACTUAL CAMERA CONCERN — PITCH — IS CONFOUNDED WITH CAUSE 1, WHICH IS
THE REAL OBSTACLE.** A pitched camera tilts the world vertical **toward or away from
the lens**, so it appears as a **z-component** in the rotation axis — and z is
exactly the coordinate MediaPipe fabricates (cause 1). **With a landmarks-only
corpus the two are not separable, even in principle**: there is no gravity datum and
no pixels were ever recorded. ⚠ Note also that the documented lean signature is
**95% IN THE SCREEN PLANE** (axis x 0.212 / y 0.974 / z 0.064), which is an
x-component — *not* what a pure camera pitch produces. So camera pitch is real,
matters for the world-referenced requirement (**T7**), and is **not** what the
existing measurements are seeing.

⭐ **WHAT WOULD SETTLE IT — and it is small.** The project has never captured a
single pixel by design. **One photo** from the webcam containing a plumb line or a
known-vertical edge (a door frame) measures camera pitch AND roll directly; a printed
checkerboard in one frame gives full intrinsics too, which would also retire the
assumed-FOV cost measured at **~2–4° of axis error per 10° of FOV error**. That is a
one-off calibration capture, not a change to the landmark-only recording policy.

⚠ Excluded from the −11° estimate: `roll_card_axis_check_b`, whose long axis rotates
by design (IQR 131°). ⚠ The owner also moves the camera between recordings, so no
per-session extrinsic generalises.

⭐ **HOW THEY COMBINE, and it matches the observations**: on the no-card take the
hand sat at +2.5° in the image and the fitted axis came out 14.5° → ~12° from
cause 1. On the card take the hand sat at true vertical and the fitted axis came out
21.2° → ~11° of camera roll plus ~10° from cause 1. **The two add or partly cancel
depending on posture, which is why the "same" defect measured 13° on one take and
21° on another.**

⛔⛔ **TWO HYPOTHESES THE OWNER RAISED WERE TESTED AND ARE NOT SUPPORTED**, recorded
so they are not re-run: **(a) the palm rotating about a different axis than the
card** — the hand IS upright in the image (−1.2° on the reference frame), so posture
is not the estimator's problem; **(b) the WRIST landmark dragging the axis** because
the card tracked only the knuckles — a knuckles-only fit `(5,9,13,17)` is *better* on
two takes (21.2→20.7, 39.5→27.6) and *worse* on two (14.5→23.5, 49.5→59.2). Not a
consistent contaminator.

### 2.0.1 ⭐⭐ LITERATURE, SECOND PASS (2026-08-24) — and it says T6 failed for a NAMEABLE reason

⚠ The FIRST literature pass produced T6 (PnP / IPPE / EPro-PnP). This pass was run
deliberately along **different axes** — MediaPipe's own depth defect, algebraic 2D→3D
lifting, and multi-frame rigid reconstruction — at the owner's instruction.

⭐⭐ **THE OWNER'S PROPOSAL IS A PUBLISHED METHOD, AND IT IS GOOGLE'S OWN.**
*Fast Lifting for 3D Hand Pose Estimation in AR/VR* (Google Research) treats 2D→3D
lifting as an **algebraic** problem: generate 3D keypoints that satisfy hand skeleton
**bone-length constraints** and perspective-project back onto the observed 2D. ⭐ **No
3D training data**, super real-time on **one core** (so the port contract survives),
and it **estimates bone lengths automatically when unknown** — which would also
retire the per-user hand-shape worry. ⚠ It explicitly notes some parts of the hand
lift accurately and others are **ambiguous**, and proposes remedies. No code or
licence stated; we would implement from the paper (same posture as T6's stdlib IPPE).

⭐⭐ **A GENUINELY NEW AXIS: USE TIME, NOT JUST THE FRAME.** *Structure from
Articulated Motion* (SfAM, Sensors 2019, **CC BY**) recovers 3D joints **and**
bone proportions from 2D tracks across a window (~200 frames) by alternating a linear
3D update with a nonlinear bone-length-consistency solve. **No training data.**
⭐ **Why it fits here better than it fits its own paper**: during a grab-and-rotate the
hand presents **many viewpoints of a rigid body** — that is a stereo baseline in
TIME, and the palm's rigidity is already measured at **2.76 mm** (§0.2). ⛔ **This is
NOT another 2.3/B8.** Those SMOOTHED a bad signal; this **triangulates** a new one
from geometry the pipeline currently throws away.

⛔⛔ **AND THE FINDING THAT EXPLAINS T6's FAILURE — READ THIS BEFORE THE NEXT
ATTEMPT.** A **planar** rigid body is degenerate for depth-from-2D **by any method**:
PnP, homography or SfM alike inherit the two-fold / bas-relief ambiguity, and it is
worst exactly when the plane faces the camera. That is not a T6 implementation bug —
`verify_planar_pnp.py` §2.4 measured it as **7.0° of out-of-plane error at face-on
against 0.6° at 75° of tilt**. ⭐⭐ **So the fix is to STOP MODELLING THE PALM AS
PLANAR: add `THUMB_CMC` (landmark 1), which sits ~15 mm OFF the palm plane** and
breaks the degeneracy. The project already relies on exactly that fact elsewhere —
U7's chirality works **because the thumb is off-plane**, and the README records that
*"3D alone does not remove the chirality dependence; the **thumb** is what does."*
⚠ Do not confuse this with B4's rejected `PALM_AND_TIPS`: that added **finger TIPS**,
which move and were fitted as rotation (p95 9.85→27.79). The thumb **CMC** is a base
joint on the rigid plate, not a tip.

⭐ Corroboration for cause 1, though weaker than our own data: MediaPipe issues
**#5571** (*"Hand 2D landmarks are accurate, but hand world landmarks are bad"*,
**still awaiting a Google response**), **#3156** (world-landmark width shrinkage) and
the already-cited **#5156** (palm/MCP world landmarks collapse on back-of-hand).
⚠⚠ **None of them quantifies anything. Our measurement — median 24.9° of normal tilt
over 3131 pixel-verified face-on frames — is more quantitative than anything public,
so DO NOT WAIT FOR AN UPSTREAM FIX.**

### 2.0.2 ⛔⛔ THE 6-POINT (THUMB) MODEL WAS BUILT AND IS **ALSO** AN A10 REJECT — 2026-08-24

The planarity diagnosis in §2.0.1 was acted on immediately: `THUMB_CMC` added to the
model (in-plane x,y **measured** from 43 sessions / 2792 face-on frames at
`(−0.5394, −0.1834)` breadths, x IQR 0.040), `planar_pnp.solve` generalised to
non-planar models (homography still initialises from the coplanar palm subset; the
refinement and both reprojection errors use every point), and the off-plane depth
**swept** because face-on 2D cannot reveal it.

⭐ **AND ON AXIS FIDELITY IT WORKED — genuinely, on all three axes:**

| arm | YAW mean / med / gain | PITCH (08-02) | ROLL mean / med / gain |
|---|---|---|---|
| Horn (ships) | 14.5 / 13.0 / 1.13 | 5.5 / 20.2 / 0.74 | 6.7 / 9.4 / 1.02 |
| **pnp+T60** | **4.0 / 9.1 / 1.07** | 7.0 / 7.8 / 0.92 | **6.3 / 4.4 / 1.02** |

⛔⛔ **AND THE JITTER BAR KILLED IT, EXACTLY AS THE ANATOMY PREDICTED.** On the
production take, `step()` p95: **Horn 25.51° → pnp+T60 62.79°** — **2.5× worse**, on
the very criterion that rejected the 9-point constellation for a mere **+4.9°**.
Same on the yaw take (14.32 → 35.52). ⚠ `pnp planar` and `pnp+T20` additionally
**REFUSED to freeze** on the production take's first frame.

⚠⚠ **THE TELL WAS VISIBLE BEFORE THE MEASUREMENT AND IS THE REUSABLE LESSON.** The
axis error fell **monotonically** as the thumb was pushed to **60–110 mm** off the
palm plane — but the real `THUMB_CMC` offset is **~10–20 mm**, and 60 mm is most of a
palm width. **A winning parameter that is anatomically impossible is not modelling
the hand; it is a free parameter absorbing error.** Axis fidelity on a scripted sweep
is cheap. Jitter in real handling is what it costs.

⭐⭐⭐ **THE STRUCTURAL CONCLUSION THAT SHOULD DIRECT THE NEXT ATTEMPT — and it is the
most useful thing to come out of T6.** Two rejects now point the same way:

* **Horn's problem is BIAS.** It consumes a fabricated z, so its grab reference is
  tilted ~25° before the hand moves — but it averages five 3D points and is
  therefore **stable** (p95 25.51°).
* **Every PnP variant's problem is VARIANCE.** A per-frame algebraic solve from five
  or six noisy 2D points has no such averaging, so it wins the bias and loses the
  jitter by 2.5×.

⛔ **So STOP REPLACING THE FIT.** The remedy has to keep Horn's averaging and attack
only its bias — which is precisely the owner's own **GATE** proposal.

### 2.0.3 ⛔ THE GATE WAS BUILT TOO, AND IS THE **THIRD** A10 REJECT — 2026-08-24

`palm_rotation.gate_world_z` + `GatedHorn`: Horn untouched, fed world landmarks whose
z is clamped to `sqrt(L² − inplane²)` — the right-triangle bound from the hand's own
proportions. Scale is recovered parameter-free (foreshortening only shortens, so the
largest observed-per-true span ratio is the un-foreshortened one). ⭐ **It may only
ever REDUCE |z|, never invent it**, so it cannot manufacture a new defect.

| arm | YAW mean / med / gain | PITCH (08-02) | jitter p95 (production) |
|---|---|---|---|
| Horn (ships) | **14.5 / 13.0** / 1.13 | **5.5 / 20.2** / 0.74 | **25.51°** |
| GatedHorn | 18.1 / 16.2 / **1.02** | 25.8 / 33.6 / 0.82 | 29.78° |

⭐⭐ **THE BIAS/VARIANCE READING WAS CONFIRMED — the gate DID keep Horn's stability**
(jitter 25.51 → 29.78, versus PnP's 62.79). ⛔ **But its correction is not accurate
enough**: worse than Horn on yaw AND pitch, so it is a reject on accuracy rather than
on jitter. The mechanism was right; this particular correction is not.

⚠⚠ **AND A REAL BUG WAS CAUGHT AND FIXED MID-BUILD, worth keeping**: the first scale
estimator ranged only over **wrist→MCP** spans. Every one of those carries a length
component, so a PITCH foreshortens **all of them at once**, leaving no
un-foreshortened reference — the scale came out low, z was over-clamped, and pitch
mean-axis went **5.5 → 43.0°**. Ranging over **all pairs** (the knuckle row 5↔17 is
untouched by pitch) recovered it to 25.8°. ⛔ Still not enough, and the reason is
structural: **under pitch the true z is near its geometric maximum, so the clamp
bites hardest exactly where z is largest and any scale error becomes an error in the
answer.** A bound is fragile precisely where the quantity it bounds is extreme.

### 2.0.4 ⭐⭐⭐ WHERE THREE REJECTS LEAVE IT — read this before attempt four

| attempt | fixes bias? | keeps stability? | verdict |
|---|---|---|---|
| planar PnP | no (worse) | **no** (62.79) | reject |
| PnP + thumb | **yes** (yaw 4.0) | **no** (62.79) | reject |
| z gate | no (worse) | **yes** (29.78) | reject |

⭐ **All three are PER-FRAME corrections**, and that is the common thread: each frame's
estimate is derived independently, so landmark noise enters the answer directly.
Horn only escapes it by averaging five points, which buys stability at the cost of
consuming a biased z.

⭐⭐ **The one approach that is NOT per-frame is the multi-frame rigid reconstruction
flagged in §2.0.1** (SfAM-style): the palm is rigid to **2.76 mm**, a grab-and-rotate
presents **many viewpoints of it**, and that is a stereo baseline in TIME. It
averages over hundreds of frames — so it should have **low variance like Horn** while
**removing the bias like PnP**, which is exactly the gap the table above describes.
⭐ It also **composes with the owner's enrolment idea**: the reconstruction *is* the
progressive harvest (measured feasible — real play yields usable samples at ~10% of
frames, converging in 40–860 frames).
⚠ It is the biggest build of the four and it may also fail. Price it before starting.

### 2.0.5 ⛔⛔ PATENTS — GOOGLE HOLDS TWO, ACTIVE TO 2038/2039, AND THEY BITE HERE

⚠⚠ **N13 IS BINDING (the game will be commercialised), SO READ THIS BEFORE ANY
FURTHER WORK IN THE LIFTING FAMILY.** The Fast Lifting paper is by Onur Guleryuz
(Google Daydream) and Google patented it under the same inventor:

| | US **11544871** B2 | US **12353637** B2 |
|---|---|---|
| title | Hand skeleton learning, lifting, and denoising from 2D images | *(same)* |
| assignee | **Google LLC** | **Google LLC** |
| priority | 2017-12-13 | 2017-12-13 |
| granted | 2023-01-03 | **2025-07-08** |
| expires | ~2038-08-24 | ~2039-02-10 |
| status | **Active** | **Active**, continuation of '871 |

⛔⛔ **THE CONTINUATION'S CLAIM 1 IS THE BROADER AND MORE DANGEROUS ONE, because it
DROPS the lookup tables.** As granted it recites, in substance: identify keypoints on
a hand in a 2D image; identify a **thumb triangle** (wrist, thumb palm knuckle, index
palm knuckle) and a **palm triangle** (a vertex at the wrist, a side connecting
palm knuckles); determine the **3D pose from the orientations of those triangles**.
⚠ **That reads onto a very large part of "lift a hand to 3D from 2D using a wrist +
knuckle-row triangle"** — which is what T6's `PlanarPnP` does, and what any Fast
Lifting implementation would do. '871 adds the LUT and the training-image step.

⚠ **The paper being published grants nothing.** Publication is not a licence, and
these expire ~2038/2039 — beyond any plausible ship date.

⭐ **What is probably NOT affected, though a lawyer must say so, not this file**: the
SHIPPED `Horn` path consumes MediaPipe's **3D world landmarks** and fits a rotation
to them. It does not *lift* 2D keypoints into 3D, which is the operation both claims
are built around. ⭐ Note also that MediaPipe itself is Apache-2.0, whose §3 grants an
express patent licence **for MediaPipe** — that does not extend to implementing a
separate patented algorithm.
⛔ **ACTION: this is the N13 "check the licence before proposing any model" rule
arriving as a PATENT question rather than a licence one. Professional advice is
needed before the lifting family is built, not after.**

### 2.0.6 ⭐⭐⭐ THE PAPER, READ IN FULL — AND T6 GOT THE GEOMETRY BACKWARDS

⚠⚠ **CORRECTION TO §2.0.1 AND TO T6 ITSELF.** With the full paper in hand, **T6's
`PlanarPnP` is NOT an implementation of Fast Lifting, and its failure does NOT
indict the method.** They are different mathematics with **opposite degeneracies**.

⭐⭐ **THE INVERSION, which is the single most useful thing in the paper.** Fast
Lifting models the four MCP knuckles as **COLLINEAR** — eq. (2),
`x₃ = λx₂ + (1−λ)x₅`, `x₄ = ρx₂ + (1−ρ)x₅` — and then leans on **Proposition 2.2:
"three or more points on a line can be unambiguously lifted whenever the line does
not project to a single point."** Collinearity is the **SOURCE of unambiguity**.
⛔ **T6 assumed the exact opposite.** `palm_rotation` models the knuckle row as
**BOWED** (10.55 mm) and `verify_planar_pnp.py` §7 asserts that bow, on the
reasoning that four collinear points are degenerate **for a homography**. That is
true for a homography — and irrelevant to a method that never computes one.

| | T6 `PlanarPnP` | Fast Lifting |
|---|---|---|
| mechanism | rigid-body pose fit minimising reprojection (homography → Zhang → twin → Gauss-Newton) | **algebraic lift along projection rays** with known lengths; collinear row first, then the wrist by a **circle** constraint (Fig. 6 iii/iv) |
| knuckle row | must be **non-collinear** | must be **collinear** |
| **worst case** | **FACE-ON** — the two-fold ambiguity merges (measured 7.0° vs 0.6° at 75°) | **row projecting to a POINT** — i.e. pointing at the lens, an extreme pose |
| ambiguity | two candidates, needs U7 to choose | singular cases **enumerated and detectable**, remedies proposed |

⭐⭐ **So the degeneracy that killed T6 — worst exactly face-on, the commonest pose —
does not exist in Fast Lifting, whose palm lift is WELL conditioned face-on and
fails only when the knuckle row points at the camera.** That is the opposite regime.
⭐ Their noise robustness is also measured and graceful: AUC 0.96 clean → **0.92 at
σ=3 px → 0.88 at σ=5 px**, and our own reprojection residual is **2.1–2.6 px**, i.e.
inside their tested band. T6 blew up at that noise level; they do not.
⚠ Other details worth carrying: they use **true perspective, explicitly rejecting
weak perspective**; output is **up to overall scale** (footnote 2 — matches our own
scale-free finding); bone lengths are estimated by **quadratic programming**
iterated with the lift (Algorithm 1), which is the owner's enrolment idea in its
published form; **>300 fps on one core**, so the port contract would survive.

### 2.0.7 ⭐⭐⭐ T6's REAL DEFECT WAS THE **REFERENCE FRAME**, NOT THE SOLVER (2026-08-24)

⚠⚠ **THIS OVERTURNS §2.0.2's DIAGNOSIS. The A10 REJECT of the planar arm was scored
against a reference frame chosen the worst possible way for it.**

⭐⭐ **THE MIRROR-REVERSE ARGUMENT, TURNED ON OURSELVES.** Fast Lifting is WELL
conditioned face-on and degenerate only when its structure projects to a point.
Planar PnP is the exact mirror — **degenerate FACE-ON** (the twins merge; 7.0° of
out-of-plane error at 0° tilt against 0.6° at 75°, branch pick a coin flip) and well
conditioned at TILT. ⛔ **And T6 freezes its reference at the MOST FACE-ON frame.**
That rule is measurement trap #2, derived for **HORN**, where it is correct. For a
planar PnP it is **exactly backwards**: the grab pose is frozen at the noisiest,
most ambiguous frame available and **every later delta inherits that error** —
which is the otherwise-unexplained finding that T6 lost in *every* rotation band.

**Sweeping the reference frame's foreshortening, clean yaw take:**

| reference at | HORN mean / med | **PnP mean / med** |
|---|---|---|
| 0° tilt (face-on — **what T6 used**) | 16.2 / 14.8 | 20.1 / 30.9 |
| 18° | 9.9 / 8.9 | 15.5 / 26.1 |
| **46°** | 11.2 / 11.6 | **2.2 / 10.9** |
| **57°** | 11.4 / 12.3 | **4.8 / 10.2** |
| **66°** | 13.9 / 13.8 | **6.6 / 10.1** |

⭐⭐ **PnP goes from 20.1° to 2.2° mean-axis, and beats Horn at EVERY tilted
reference.** The solver was never the problem.

⚠⚠ **BUT IT DOES NOT REPRODUCE ON THE CARD TAKE** — 69.8 → 26.5 as the reference
tilts, an improvement, yet still worse than Horn's 15.9 there (and the 32° reference
failed to freeze at all). ⛔ **One take is not a result.** The card take is the one
the owner had to contort to shoot (*"I had to tilt the hand and arm"*), and Horn is
also worse on it — but this must be settled before anything is claimed.

⭐⭐ **AND THERE IS A PRACTICAL WRINKLE THAT MATTERS MORE THAN THE NUMBER: IN THE
GAME THE REFERENCE IS THE **GRAB** FRAME, WHICH THE PLAYER CHOOSES.** We cannot ask
for a grab at 46° of tilt. So the fix cannot be "pick a tilted reference"; it has to
be either **re-referencing opportunistically when a well-conditioned frame arrives**,
or **refining the reference pose over the first frames of the hold** — which is the
owner's own progressive-enrolment idea arriving for the third time, now as the
mechanism that makes T6 viable rather than as a convenience.

⭐ **NEXT: re-run the FULL A/B with a conditioning-aware reference** — pitch, roll and
the jitter bar, on both yaw takes. ⛔ Until then §2.0.2's reject stands as recorded;
this is a reason to re-open it, not a result that replaces it.

### 2.0.8 ⛔⛔ CONTINUITY AND ERROR-CORRECTION ARE IN TENSION — the re-reference no-op

The conditioning-aware reference of §2.0.7 was built as **opportunistic
re-referencing**: migrate to a better-conditioned reference mid-hold, carrying the
accumulated rotation across so the output stays continuous. ⛔ **It produced
BIT-IDENTICAL numbers to the un-referenced arm on every take** (yaw 19.6/29.8 both;
T60 4.0/9.1 both), which is proof rather than a weak effect.

⭐⭐ **AND THE ALGEBRA SAYS IT HAD TO.** Carrying the accumulation means
`base = R_switch · R₀ᵀ`, so the emitted delta becomes
`(R · R_switchᵀ) · (R_switch · R₀ᵀ) = R · R₀ᵀ` — **exactly what it was before.**
Preserving continuity preserves the ERROR along with it.

⛔ **SO THE LESSON IS GENERAL AND WORTH KEEPING: a re-reference can only improve
accuracy by DISCARDING the bad reference's contribution, and discarding it is
precisely what creates a discontinuity.** The two goals are the same quantity with
opposite signs. §2.0.7's measured 20.1° → 2.2° came from *starting* at a
well-conditioned frame, never from migrating to one.

⭐ **TWO DESIGNS SURVIVE THAT, AND BOTH ARE PRECEDENTED HERE**:
1. **Delay the reference** — at grab, emit identity and refuse to rotate until a
   well-conditioned frame arrives, then reference there. Pure suppress-don't-guess
   (DR-2, U8, 4.2 decision 1). ⚠ Risk: a hold may never reach 46–66° of tilt.
2. **Re-reference WITH a blend** — take the correction and absorb the step over a few
   frames. ⭐ **Phase D already ships exactly this machinery** (the 150 ms coast +
   **3-frame resync blend**), so it is a reuse, not a new mechanism.
⚠ Both trade a managed, brief discontinuity for a correct axis. Which is acceptable
is a FEEL question and therefore the owner's, not a measurement's.

⭐⭐ **OWNER DECISION 2026-08-24: option 2 (RE-REFERENCE WITH A BLEND) IS THE FAVOURED
FALLBACK.** ⚠⚠ **WITH A CAVEAT THAT MUST BE DESIGNED FOR NOW, NOT DISCOVERED LATER**:
*"currently we grab with open hand in proximity of the cube, but the re-reference
with a blend method may be impacted if we change the method of grab later on (for
example, if we grab by closing the fingers, we need a re-reference with a blend which
is compatible with fingers positions changing during the grab frames)."*
⭐ **Why that bites specifically**: the blend assumes the constellation it references
is RIGID across the blend window. That holds for `PALM_LANDMARKS` today — the palm is
rigid to 2.76 mm and the grab is an open-hand proximity trigger, so nothing moves.
⛔ **It stops holding the moment the grab gesture itself deforms the hand** — a
close-the-fingers grab changes finger landmarks *during* exactly the frames the
re-reference would run in. ⭐ Two consequences to carry into **4.4 + B5** (the
grab/release-from-arcs project, which is where a finger-based grab would arrive):
**(a)** the re-reference must key on the **rigid palm plate only**, never on anything
finger-derived, so that a deforming grab cannot corrupt it; **(b)** the blend window
must not overlap the grab transient — either delay it until the fingers settle, or
gate it on the arcs being stable. ⚠ Note this is also why `PALM_AND_TIPS` was
rejected (B4: finger motion fitted as rotation) — the same failure mode arriving
through a different door.

### 2.0.9 ⭐⭐⭐ THE BIAS **IS** A REPEATABLE FUNCTION OF POSE — but only within one recording

⭐⭐ **THE OWNER'S EXPERIMENT, AND IT IS THE RIGHT DESIGN.** The camera is FIXED for
the duration of one take, so any camera pitch/roll is a CONSTANT there and cannot
explain variation *inside* it. That converts an unanswerable cross-take question into
an answerable within-take one. Sweep takes revisit the same poses 9–12 times, so
"does the same pose give the same bias every time it recurs?" is directly measurable.

**YAW clean — the cleanest case:**

| pose bin | bias | within-bin scatter | 1st half | 2nd half | out vs return |
|---|---|---|---|---|---|
| 40–60° | 27.0° | 3.5° | 27.1 | 27.1 | 3.0 |
| 60–80° | 22.6° | 5.0° | 24.4 | 19.2 | 0.9 |
| 80–100° | 17.0° | 2.7° | 17.4 | 15.7 | 1.5 |
| 120–140° | 11.2° | 1.9° | 13.8 | 10.0 | 0.4 |

⭐ Between-bin spread **15.8°** against a within-bin scatter of **3.1°** — ratio
**5.17**. The bias is repeatable at a fixed pose, varies systematically with pose,
agrees across the first and second halves of the recording, and shows **no
hysteresis** (outbound vs return 0.4–3.0°). ⭐ Same verdict on YAW-cube (**4.32**),
PITCH-validated (**4.08**) and PITCH-suspect (**5.19**).
⛔ The lone failure is **YAW-card (1.44)** — the take the owner had to contort for,
and whose halves disagree by 14–25°. Consistent with everything else known about it.
⚠ Note the bias *falls* as the turn grows (27° → 11°); the within-bin scatter of
1.9–3.5° rules out the axis noise floor as the explanation.

⛔⛔ **BUT THE OBVIOUS EXPLOITATION DOES NOT WORK — the SHAPE does not transfer.**
The natural model is `bias(pose) = f(pose) + C_session`, with `f` a property of
MediaPipe (learnable offline from scripted takes, where the true axis IS known) and
`C_session` the unmeasurable camera tilt (one number, estimable per session). Tested
by removing each take's own mean and comparing only the shape:

| | YAW | PITCH |
|---|---|---|
| shape amplitude | 21.7° | 14.5° |
| worst disagreement | **13.4°** | **13.4°** |

**Refuted in both groups.** ⚠ The YAW comparison rests on only **3 shared pose bins**,
so it is thin — but PITCH has 6 and fails just as clearly.
⭐ A plausible reading: MediaPipe's depth error is a function of the hand's pose
**relative to the CAMERA**, so moving the camera does not merely offset the curve, it
**re-indexes** it. That would explain both results at once.

⭐⭐⭐ **THE CONSEQUENCE, AND IT IS THE MOST ACTIONABLE THING IN THIS FILE.** The bias
is real, systematic and pose-indexed — but its map is **per-session** and therefore
**cannot be learned offline and shipped**. Correcting it requires ground truth *in
that session*, i.e. frames where the INTENDED axis is known. **That is a calibration
motion** — "turn your hand about the vertical" at the start — which is exactly
**U12**, and it now carries a **hard technical justification instead of a playability
one**. ⚠ It is also the one thing the owner's progressive-enrolment idea cannot do
unaided: enrolment can measure hand SHAPE from ordinary play, but a bias map needs a
known intended axis, and only a deliberate motion supplies that.

### 2.0.10 ⛔ REGRESSION ON THE BIAS — the k family STAYS dead, and a harness bias was found

**FAMILY A — the physical model.** The mechanism is that MediaPipe inflates the
palm's out-of-plane extent, so `z_measured = k·z_true` is the one-parameter model
that folds the session constant into `f`. Swept finely, every take, optimum per take:

| take | k=1 (ships) | best k | best dev |
|---|---|---|---|
| YAW clean | 15.3° | 0.35 | 7.5° |
| YAW cube | 42.1° | 0.00 | 15.7° |
| YAW old | 35.7° | 0.00 | 14.4° |
| **PITCH valid** | 13.8° | **1.15** | 12.2° |
| PITCH suspect | 26.2° | 1.15 | 25.6° |

⛔ **Optima span 0.00 – 1.95, and yaw wants k < 1 while pitch wants k > 1.** The best
compromise (k=0.85) buys −2.0/−0.9/−3.1 on the yaw takes and **costs +2.3 on the
validated pitch take**. ⭐⭐ **So the recorded rejection of the "weight z less" family
STANDS, now on six takes and a fine sweep rather than two takes and six k values.**

⛔⛔ **AND A SELECTION BIAS IN THE HARNESS WAS FOUND ALONG THE WAY — IT NEARLY
PRODUCED A FALSE RE-OPENING.** The first pass gated frames on the **FITTED** rotation
magnitude. **Scaling z SHRINKS the fitted angle**, so a fixed fitted-angle floor
admits a *different subset of frames at every k* — the arms are not scored on like
with like. Under that biased gate k=0.40 looked like a triumph (**YAW clean
14.9 → 4.6**). Re-gated on the depth-free **TRUE** foreshortening angle, which does
not move with k, the same take reads **15.3 → 13.4** and the effect evaporates.
⚠ **`analysis/t5i_zscale_sweep.py` HAS THIS BIAS** (`MIN_ANGLE_DEG` is applied to the
fitted angle). ⭐ The *conclusion* is unaffected — both gates reject the k family —
but the *numbers* are not comparable, and the validated pitch take's k=1 baseline
moves **5.4° → 13.8°** purely with the gate. That is trap #3 again: **print the
aggregation, and never compare figures produced under different gates.**

**FAMILY B — the empirical model.** `bias(pose)` regressed on
`[1, cos p, sin p, cos 2p, sin 2p]`, with the constant absorbing the unknown camera
term. ⛔ **Own-fit RMS (0.5–1.8°) is not evidence** — five free parameters on six to
nine binned points will always fit. On the transfer test that matters, using another
take's SHAPE and refitting only the constant, the residual runs **25–46% of the
take's own spread** among the trusted takes (e.g. PITCH-valid shape → YAW-clean,
7.2° against a 15.8° spread) and **exceeds the spread** wherever an anomalous take is
involved. ⭐ **Partial and real, not universal** — the shape explains perhaps half the
pose dependence. ⚠ Family B has NOT yet been re-run under the corrected gate; given
how much the gate moved Family A, it must be before anything is built on it.

### 2.0.11 ⭐⭐ THE DISTORTION MEASURED AT SOURCE — and why a scalar model cannot hold it

⭐⭐⭐ **THE MEASUREMENT TRICK THAT SHOULD HAVE COME FIRST.** Instead of fitting the
rotation-axis bias (which needs a known true axis, only exists above the axis noise
floor, and is polluted by the unknown camera pose), measure the distortion at its
source: `theta_measured = f(theta_true)`, where
* `theta_true` is the palm's tilt from face-on, **depth-free**, from the projected
  palm AREA (a planar patch projects as `area_faceon · cos θ`) — pixels only, works
  for tilt about ANY axis, needs no scripted motion;
* `theta_measured` is the angle between MediaPipe's world palm normal and the camera
  axis.
⭐⭐ **BOTH ARE CAMERA-RELATIVE, SO THE UNKNOWN CAMERA TILT CANCELS EXACTLY** — the
thing that wrecked every cross-session comparison simply drops out. **58 sessions,
21 761 frames**, versus the handful of scripted takes everything else used.

| true tilt | measured (median) | IQR |
|---|---|---|
| 0–5° | **28.0°** | 22.5° |
| 10–15° | **42.9°** | 24.7° |
| 30–35° | 23.7° | 20.3° |
| 60–65° | 53.5° | 22.0° |
| 85–90° | 74.5° | 24.3° |

⭐ **The face-on defect is confirmed at corpus scale**: a palm that is physically
square to the lens is reported tilted **28°**. ⛔ **But the curve is NON-MONOTONIC**
(rises to 42.9° by 15°, falls to 23.7° by 35°, climbs again to 74.5°).

**Model fits to the binned medians** (the owner asked for a sinusoidal combined with
the `z = k·z_true` inflation):

| model | RMS |
|---|---|
| A `tan θm = 0.236·tan θt + 0.535` — the mechanistic z-inflation-plus-offset | 7.34° |
| B `θm = 0.471·θt + 19.8` — affine | 8.47° |
| **C `θm = −21.0·sin(2.60·θt + 0.40) + 46.9`** — ⭐ the owner's sinusoidal | **5.33°** |
| D `θm = 35.1·sin θt + 18.6` | 10.24° |

⭐ **The sinusoidal form does fit best** — but on **4 parameters against A's 2**, and
what it is fitting is the U-shape, not a saturation.

⛔⛔ **AND IT IS NOT A LAW, FOR TWO REASONS THAT MATTER MORE THAN THE RMS.**
**(1)** The per-frame **IQR is 16–41°** at every true tilt — the fits are to binned
MEDIANS, and the underlying data scatters several times wider than the model spans.
**(2)** Refitting A per session gives **k: p10 0.00, median 0.48, p90 0.94** — the
"constant" spans nearly its whole plausible range across sessions.

⭐⭐⭐ **THE DIAGNOSIS, AND IT TIES EVERY PREVIOUS RESULT TOGETHER: THE MODEL IS
UNDER-PARAMETERISED, NOT NECESSARILY WRONG.** `theta_true` is a SCALAR — tilt
magnitude — and it throws away the tilt **DIRECTION** (which way the palm leans).
That single omission explains all three standing observations at once:
* **within a scripted sweep the bias is highly repeatable** (§2.0.9, ratio 5.17)
  — because a single-axis sweep holds the tilt DIRECTION fixed;
* **across recordings nothing transfers** (§2.0.9, §2.0.10) — because the direction
  differs;
* **the per-frame scatter here is enormous** — because pooling all directions into
  one scalar bin mixes systematically different distortions.
⭐ **NEXT MODEL: treat the tilt as a 2-VECTOR** (the palm normal's projection in the
image plane — magnitude *and* direction) and fit `normal_measured = F(normal_true)`
as a 2D→2D map. That is the smallest model that can hold what the scalar cannot, and
it remains camera-cancelling.
⚠ **NOT YET RUN: Family B (§2.0.10) under the corrected gate.** This measurement was
prioritised over it as strictly more informative; the re-run is still owed.

### 2.0.12 ⭐⭐⭐ THE DISTORTION AS A 2-VECTOR — one big finding, and the regression line closed

Tilt taken as a 2-vector (magnitude **and** direction), both recovered depth-free from
the 2×2 shape map that carries the canonical palm onto the observed pixels: the
compression RATIO `σ₂/σ₁ = cos θ_true` and the small singular direction `φ_true`.
⭐ Using the ratio rather than the projected area removes the per-session face-on
reference the previous pass needed — area conflates compression with distance.
**19 064 frames, 62 sessions.**

⭐⭐⭐ **THE FINDING WORTH KEEPING, AND IT IS NEW: MEDIAPIPE GETS THE TILT *DIRECTION*
RIGHT.** `|φ_measured − φ_true| mod 180` is **median 10.6°** (p25 4.6°) against 45°
for chance. **So the palm normal's BEARING is trustworthy and only its out-of-plane
MAGNITUDE is corrupt.** That collapses the defect from "3D orientation is wrong" to
**one scalar per frame**, which is a far smaller problem than anything assumed so far.

⛔⛔ **BUT MY DIAGNOSIS THAT DIRECTION WAS THE MISSING VARIABLE IS REFUTED.** Binning
by direction reduces the magnitude IQR by a mean of **1.3°**, and in the 50–60° band
it makes it *worse* (10.8° pooled → 16.4° within-band).

| model | params | RMS | variance explained |
|---|---|---|---|
| predict the mean | 1 | 19.6° | — |
| θ only, affine | 2 | 11.5° | 41.2% |
| θ only + sin θ | 3 | 11.5° | 41.6% |
| + direction, linear | 4 | 10.0° | 49.1% |
| **sinusoidal in both** | 7 | **9.6°** | **51.1%** |

⚠ **The sinusoidal terms buy almost nothing** over affine (41.6 vs 41.2 alone; 51.1
vs 50.2 with direction) for triple the parameters. The best model leaves **RMS 9.6°**
— about half the scatter — which is far too coarse to invert into a rotation fix.

⛔⛔ **AND PER-SESSION CALIBRATION CANNOT RESCUE IT EITHER.** Removing each session's
own mean residual takes 9.6° → **8.5°**: session constants explain only **12%** of
what is left, offsets spanning −12.8..+8.1°. **The residual is WITHIN-session**, so no
calibration gesture, however good, can reach it.

⭐⭐ **CONCLUSION: THE REGRESSION LINE IS CLOSED for these features.** The distortion
is not a law of (tilt, direction) — roughly half of it is, and the rest is not
predictable from the palm geometry we can observe. ⚠ Untested features that could
hold the remainder: hand distance, in-plane rotation, finger configuration, detector
confidence. None is obviously promising.

⭐⭐⭐ **WHAT THE DIRECTION FINDING OPENS INSTEAD — a narrow, well-posed fix that no
previous attempt tried.** If the normal's **bearing is reliable** and its **magnitude
is not**, then rebuild the palm's orientation from two trustworthy halves:
* **bearing** — from MediaPipe's world normal (median 10.6° error);
* **magnitude** — from the **foreshortening ratio** `θ = acos(σ₂/σ₁)`, which is
  depth-free and never touches the corrupt coordinate.
⭐ That is a **two-line correction to the normal**, not a new estimator, and it keeps
Horn's five-point averaging intact — the property §2.0.2 identified as the reason
Horn is stable and every PnP variant is not. ⚠ It is the first candidate that uses
only quantities now *measured* to be reliable.

### 2.0.13 ⛔ T6c — THE "TRUSTWORTHY HALVES" REBUILD: best yaw yet, still an A10 reject

`palm_rotation.rebuild_world_normal` + `RebuiltNormalHorn`. Horn untouched; the palm
plate's WORLD points are rotated so the normal matches one rebuilt from the two
halves measured reliable in §2.0.12 — **bearing and SIGN from MediaPipe** (median
10.6° error), **MAGNITUDE from depth-free foreshortening** (`θ = acos(σ₂/σ₁)`).
⭐ The halves are genuinely complementary: foreshortening cannot give the sign
(±θ project identically), and only the measured normal can.

| bar | Horn (ships) | REBUILT (gated) |
|---|---|---|
| **YAW mean / median** | 14.5 / 13.0 | ⭐ **10.5 / 10.3** |
| PITCH (08-02) mean / median | **5.5** / 20.2 | 6.3 / **19.5** |
| **ROLL mean / median** | **6.7 / 9.4** | ⛔ 12.5 / 21.8 |
| **JITTER p95 (production)** | **25.51** | ⛔ 31.48 |

⭐ **The best yaw result of any arm tried** — and yaw is the show-stopper. ⛔ **But
roll and jitter regress, so it is a reject.**

⚠ **AN INTERMEDIATE FIX THAT WORKED, worth keeping**: the ungated first version cost
pitch (5.5 → 10.1) and roll (9.4 → 21.9) because `θ = acos(ratio)` has UNBOUNDED
sensitivity as ratio → 1 (`dθ/dratio` is 7.1 at 0.99 vs 1.4 at 0.70) — it was
recomputing a normal that should be static from the noisiest possible input. Gating
at ratio > 0.90 recovered **pitch to 6.3°**. ⭐ Suppress-don't-guess, again.

⛔⛔ **BUT ROLL DID NOT RECOVER, AND THE REASON IS THE REAL FINDING: THE COMPRESSION
RATIO IS CONTAMINATED BY SHAPE MISMATCH.** Measured ratio distributions:

| take | ratio median | implied tilt | gate blocks |
|---|---|---|---|
| **roll — palm FACE-ON throughout** | **0.889** | **27°** | only 36% |
| yaw sweep | 0.659 | 49° | 3% |
| production | 0.753 | 41° | 12% |

`t5j` independently measures that roll take at width collapse **0.904** and length
collapse **0.891** — i.e. almost no foreshortening. **A physically face-on palm reads
as 27° tilted**, because the 2×2 map must absorb the difference between the
OPERATOR'S palm and the CANONICAL model, and that shape difference is
indistinguishable from compression. The gate then barely fires, and the rebuild
injects a tilt that does not exist.

⭐⭐⭐ **SO THE METHOD IS NOT REFUTED — ITS REFERENCE IS.** The correction needs
`σ₂/σ₁` measured against **that operator's own face-on palm**, not against a corpus
median. That is precisely the owner's progressive-enrolment idea, and for this method
it is **not an optimisation but a precondition**: enrolment measured feasible
earlier — usable samples at ~10% of real-play frames, converging in 40–860 frames,
and between-session signal 2.8× within-session. ⚠ **Next step: re-run T6c with a
per-session face-on reference shape** before judging the approach.

### 2.0.14 ⭐⭐⭐ PARAMETERISING THE INVERSION — §2.0.13's REJECT IS OVERTURNED

⚠⚠ **§2.0.13 REJECTED T6c ON A PARAMETER-FREE INVERSION AND THAT WAS TOO HASTY.**
It used `θ = acos(σ₂/σ₁)` — a rigid choice with no freedom — and then judged the
METHOD by it. Owner's objection, and it was correct. Fitting the inversion against
the A10 bars themselves (there is no independent ground truth for θ, so any proxy
would be circular) changes the outcome.

⭐⭐⭐ **THE WINNER IS PURE RENORMALISATION — one parameter, no damping.**
`θ = acos(min(1, ratio/r₀))` with **r₀ = 0.889**, the measured face-on baseline that
§2.0.13 identified as the shape-contamination offset:

| bar | Horn (ships) | renorm r₀=0.889 |
|---|---|---|
| YAW median / gain | 13.0° / 1.13 | ⭐ **8.3° / 1.13** |
| PITCH median / **gain** | 20.2° / **0.74** | ⭐ **12.5° / 1.00** |
| **ROLL median** | 9.4° | ⭐⭐ **0.8°** |
| JITTER p95 | **25.5°** | ⛔ 34.3° |

⭐ **Three axes improve, ROLL nearly perfectly (9.4 → 0.8), and PITCH GAIN is FIXED
(0.74 → 1.00)** — the under-turning that has been open since the beginning. **Only
jitter regresses.** ⚠ That is a far better position than "reject": accuracy is solved
on every axis and what remains is NOISE, the one failure mode with standard remedies
(the shipped `orientation_filter`, which this harness bypasses entirely, and B8's
hold-the-last-value).

⛔⛔ **AND A TRAP THAT MY OWN FIRST SEARCH WALKED INTO — KEEP THIS.** The sinusoidal
response the owner suggested **wins every ERROR metric outright**:
`SIN a=30, b=0.5` gives YAW **3.4°**, PITCH **9.5°**, ROLL **3.3°**, JITTER
**14.0°** — better than Horn on all four. ⛔ **It is an artefact: its PITCH GAIN is
0.48.** The map `30·sin(0.5·θ)` sends a 90° tilt to 21°, so it DAMPS the rotation —
and damping buys every error metric for free while the cube stops following the hand.
**My first grid omitted gain and would have reported it as a clean win.** ⭐ Every
damped arm shows the same signature (gain 0.48–0.79); the renormalised arm does not
(1.00–1.13), which is exactly what distinguishes a fix from a sedative. ⚠ B8 recorded
the general form of this trap already ("every fit loses to holding the last value").

⭐ **NEXT, AND BOTH ARE CONCRETE**: (1) **jitter** — re-score the renormalised arm
through the shipped `orientation_filter` rather than raw, since raw per-frame jitter
is not what reaches the cube; (2) **r₀ = 0.889 is currently a FITTED CONSTANT** taken
from one take. Its principled form is the **per-session observed face-on ratio**
(the p95/p99 of that session's own ratio distribution) — i.e. the owner's
progressive enrolment, which for this method supplies exactly the one number it
needs.

### 2.0.15 ⛔ THE MATRIX FORMULATION — and it RETRACTS part of §2.0.14

**The formulation is right and worth keeping.** Model points are `(x, y, 0)`, so a
camera point is `x·r1 + y·r2 + t` and, dropping z, the observed 2×2 map is
`M = s·[[r1x, r2x],[r1y, r2y]]` — **M is the top-left block of the palm's rotation
matrix, times scale.** Orthonormality then FORCES the missing z's: with
`p = |M[:,0]|²`, `q = |M[:,1]|²`, `w = M[:,0]·M[:,1]`, `λ = 1/s²`,
`(w² − pq)λ² + (p+q)λ − 1 = 0`, then `r1z = ±√(1−pλ)`, `r2z = −wλ/r1z`,
`r3 = r1×r2`. The ± is resolved by the sign of MediaPipe's normal (§2.0.12).

⛔⛔ **RESULT: WORSE THAN HORN, AND THE FIRST RUN'S APPARENT WIN WAS AN ARTEFACT.**

| variant | YAW / gain | PITCH / gain | ROLL | JITTER |
|---|---|---|---|---|
| Horn (ships) | **13.0 / 1.13** | 20.2 / 0.74 | **6.7** | **25.5** |
| matrix + S (correct) | ⛔ 34.2 / 1.17 | ⭐ **14.3 / 1.13** | 10.8 | ⛔ 55.0 |

⭐ It **does** improve pitch (20.2 → 14.3) and fixes pitch gain (0.74 → 1.13), which
is consistent with every other pass. ⛔ But it wrecks yaw and jitter: recovering the
full orientation per frame from a 2×2 map is extremely noise-sensitive, and near
edge-on the map is nearly singular.

⛔⛔ **THE ARTEFACT, AND IT IS THE IMPORTANT PART.** The first matrix run reported
**YAW 6.1° at gain 1.00** — the best number of the whole investigation. It was
false. The shape-correction `S` had been estimated by averaging RAW face-on maps,
and each map carries an arbitrary **in-plane hand rotation**; averaging them averaged
rotations, producing `S = [+0.917 −0.459; +0.469 +0.856]` — **determinant exactly
1.000, i.e. a 27° ROTATION wearing a shape correction's clothes.** Re-estimating `S`
by **polar decomposition** (strip the rotation, average only the stretch) gives
`S = [+0.985 +0.004; +0.004 +1.016]` — **essentially the identity** — and the 6.1°
becomes 34.2°.

⚠⚠ **AND THAT NEAR-IDENTITY S RETRACTS PART OF §2.0.14.** If the anisotropic shape
error is ~0, then `r₀ = 0.889` was **not** correcting a shape mismatch — it was
cancelling the **roll take's own average tilt**. That take's palm really is ~27° off
face-on on average (cos 27° = 0.89, matching `t5j`'s independently measured span
collapses of 0.904/0.891). ⛔ **So §2.0.14's roll 9.4 → 0.8 is a fit to one take, not
a correction**, and its headline must not be quoted as a general result.
⭐ What survives: **r₀ = 0.90**, a round value not fitted to anything, still gives
**YAW 8.3 / PITCH 12.5 with gains 1.12 / 1.00** — better than Horn on both axes and
both gains. The EFFECT is real; the MECHANISM I attributed to it was not.

⭐ **WHAT THIS NARROWS.** Three independent formulations — scalar renorm, matrix
recovery, planar PnP — all **fix pitch gain** (0.74 → ~1.0–1.13) and all **degrade
jitter**. Pitch gain is now the one thing every approach agrees on, and jitter is the
one thing none of them survives. That is a much smaller problem than where this
started.

### 2.0.16 ⭐⭐⭐ ANISOTROPIC 2×2 SINUSOIDAL FIT, PER RECORDING — the hypothesis holds

⭐⭐ **THE STRUCTURAL ARGUMENT, AND IT IS THE OWNER'S.** Yaw and pitch have always
demanded opposite corrections — the docs closed the whole "weight z less" family on
exactly that ("yaw and pitch need opposite things from the same coordinate"). **But
they foreshorten along PERPENDICULAR directions**: yaw compresses the palm's WIDTH,
pitch its LENGTH. So a correction that depends on the COMPRESSION DIRECTION ψ can
treat them differently with one model, which no scalar can. Since ψ is defined mod
180°, its natural function is `g(ψ) = a + b·cos2ψ + c·sin2ψ` — **exactly the quadratic
form of a symmetric 2×2 on that direction.** "Sinusoidal regression with a 2×2" is one
object, not two.

⭐⭐ **AND TWO CAMERA-INDEPENDENT OBJECTIVES MAKE PER-RECORDING FITTING POSSIBLE**, which
is what the owner asked for after cross-take comparison kept failing on the moving
camera:
* **SCATTER** — each frame's axis vs the take's OWN mean axis. A fixed camera tilt
  moves the mean but cannot touch the spread, so a pure rotation about ANY axis
  scores 0 whatever the camera does.
* **DRIFT** — mean axis at a LOW turn vs at a HIGH turn, within one take. ⭐ **This is
  the owner's complaint as a number**: the cube leans MORE the further you turn it, so
  a correct estimator has drift ≈ 0. ⚠ Bands are taken per recording (the card yaw
  stops at ~80° and never passes edge-on, so a fixed 100–150° band is empty there).
⛔ Neither is gameable by damping — gain is constrained to [0.85, 1.25].

**Takes, chosen on the owner's criteria**: YAW = `2026-08-23_203307_yaw_card_axis_check_b`
(the card retake); PITCH = `2026-08-04_054702_pitch_sweep_slow` — **most recurring
poses** (12 operator-counted cycles, 1069 frames vs 722), **highest within-recording
bias repeatability of any take** (ratio 5.19), and by trap #5's rule the **cleaner
pitch setup** (for a pitch sweep WIDTH is the contamination channel: 0.892 here vs
0.808 in the 2026-08-02 take).

| take | | scatter | drift | gain |
|---|---|---|---|---|
| **YAW** | identity | 9.5° | 4.0° | 0.82 |
| | **fitted** | ⭐ **7.4°** | 4.2° | ⭐ **0.95** |
| **PITCH** | identity | 44.4° | **76.4°** | 0.65 |
| | **fitted** | ⭐ **21.2°** | ⭐⭐ **23.6°** | ⭐ **1.24** |

⭐⭐⭐ **PITCH IS TRANSFORMED: scatter halved and DRIFT CUT FROM 76.4° TO 23.6°** — a
two-thirds reduction on the metric that encodes the owner's actual complaint. Yaw
improves more modestly (scatter −22%, gain 0.82 → 0.95); its drift was already only
4.0° because the card sweep stops at ~80°.

⭐⭐ **AND THE ANISOTROPY IS CONFIRMED, MEASURED SEPARATELY ON EACH RECORDING WITH NO
CROSS-TAKE CONTAMINATION**: the gain each take wants **at the ψ it actually
exercises** is **1.15 for yaw-like (ψ≈0)** and **1.55 for pitch-like (ψ≈90°)**. They
genuinely differ, which is precisely why every scalar attempt failed and why the 2×2
is the right object.

⛔⛔ **THE CAVEAT THAT MUST TRAVEL WITH THIS: EACH TAKE CONSTRAINS ONLY ITS OWN ψ.**
A yaw sweep never visits ψ≈90° and a pitch sweep never visits ψ≈0, so the fitted
`b` and `c` are largely **unconstrained** — the pitch fit happily puts gain **0.15**
at ψ=0, a region that recording never enters. ⚠ **So these are two valid
single-direction calibrations, NOT yet one validated 2×2.** ⭐ What is needed to close
it is a take that exercises INTERMEDIATE ψ — a diagonal tilt sweep — or a joint fit
that constrains each take only at its own ψ. **That is the next recording to make.**

### 2.0.17 ✅ T6d BUILT — what it is, and the four decisions that are NOT in §2.0.16

**WHERE IT LIVES.** `Resources/palm_rotation.py` — `_shape_axes` (ratio **and** ψ),
`AnisoParams` (the live `r0, a, b, c` holder), `rebuild_terms` (one function, read by
the estimator, the HUD and the recorder alike), `rebuild_world_normal(..., params)`,
and `RebuiltNormalHorn(params=...)`. `LiveSnapDebug.py` — the slider window, the two
HUD rows, the keys, and the recording fields. **Production imports none of it.**

⭐⭐ **DECISION 1 — ψ COMES FROM THE PRINCIPAL-AXIS CLOSED FORM, NOT FROM SOLVING AN
EIGENVECTOR ROW, and the obvious way is silently wrong.** The textbook
`v = (b, λ₂ − a)` is exact and useless here: whenever the compression aligns with the
model axes — i.e. for a **pure yaw or a pure pitch, the two cases this whole model
exists to separate** — both components collapse to rounding error and the direction
is noise. Measured on synthetic input: a pure 60° yaw reported **ψ = 163° instead of
0°**. `ψ = ½·atan2(2b, a−c) + 90°` has no such cancellation. ⚠ **A future port must
carry the closed form, not "simplify" it back** — the failure is invisible except at
exactly the poses that matter.

⭐⭐ **DECISION 2 — ψ IS FOLDED BY CHIRALITY, BECAUSE `c` IS CHIRALITY-ODD AND NOTHING
ELSE IS.** A left palm is the canonical model REFLECTED, so the shape map absorbs the
reflection and the same physical diagonal reports `180 − ψ`. `cos2ψ` survives that
(`a`, `b`, `r₀` are chirality-blind) but **`sin2ψ` CHANGES SIGN** — so without
folding the diagonal term acts **oppositely on the two hands**, and a session that
switches hands feels inconsistent with nothing on screen to explain it. That is the
U7 class of defect exactly, so ψ is folded into one convention (the apparent-RIGHT
palm frame) using U7's **geometric** chirality, never the label
(`palm_rotation.ANISO_FOLD_CHIRALITY`, and `aniso_mirrored` returns *do not fold*
rather than guessing when the volume is degenerate).

⚠⚠ **AND THAT MEANS §2.0.16's PUBLISHED `c` MUST BE NEGATED, WHICH IS WHY THE PRESETS
DO NOT MATCH THE NUMBERS ABOVE.** Its fits predate the fold, and **both of its takes
measure as apparent-LEFT on 973/975 and 1030/1075 frames** — so their `c` is stated
in the opposite convention. Presets carry `yaw c = −0.10`, `pitch c = −0.40`.
⭐ **`a`, `b`, `r₀` need no translation, and there is a clean check that they came
across intact**: ψ = 0 and ψ = 90° are the **fixed points of the fold**, so the gains
there are chirality-blind — and the presets reproduce §2.0.16's two measured
endpoints exactly, `yaw g(0) = a+b = 1.15` and `pitch g(90) = a−b = 1.55`.
⭐ `c` is also the parameter §2.0.16 calls least constrained, so of the four its sign
matters least — **and pinning it is what the slider session is for.**

⭐ **DECISION 3 — THE FACE-ON GATE NOW READS THE RENORMALISED RATIO `u = ratio/r₀`,
not the raw one.** The unbounded sensitivity `dθ/du = −1/√(1−u²)` lives in `u`, since
`u` is what `acos` is applied to; gating the raw ratio while renormalising by `r₀`
would leave the gate drifting away from the region it exists to protect. ⭐ At
`r₀ = 1` (the slider's start) this **is** the shipped test, so nothing already
measured moves.

⚠ **DECISION 4 — `recorder_schema` STAYS 3.** The schema marker is a contract
*between the two recorders* (`verify_recorder_parity` asserts both stamp the same
number) and production does not run T6d at all, so bumping it in one tool would claim
a shared format that does not exist. The T6d fields are additive and marked by
`aniso_debug: 1`; every existing `t5*`/`verify` harness reads these takes unchanged.

**WHAT IS GREEN.** All 23 golden-vector suites pass (`verify_palm_rotation`,
`verify_planar_pnp`, `verify_recorder_parity` among them); `parity_replay` reports no
divergence; and the toggle-OFF path is measured byte-identical to shipped `Horn` over
975 frames.

⚠ **WHAT IS NOT MEASURED, and must not be claimed**: nothing here has been through
A10. The slider run is a **feel test plus a data capture**; the numbers that would
accept or reject the anisotropic correction come afterwards, from the recording it
produces.

### 2.0.18 ⚠ FIRST LIVE SESSIONS (2026-08-24) — four takes, and the INSTRUMENT was the finding

**Takes, all on E:, all schema 3 + `aniso_debug`:** `2026-08-24_202454_t6d_psi_sweep`
(3665 f), `_203927_t6d_ab_before_after` (3396 f), `_204928_t6d_ab_before_after_b`
(3779 f), `_205729_t6d_ab_ghost` (3683 f). ⛔ **No A10 verdict was reached** — the
sessions were spent finding out that the rig could not be read.

⛔⛔ **FINDING 1 — THE TOGGLE IS THE WRONG CONTROL, AND THE FIRST TAKE PROVES IT.**
The owner made **150 logged slider moves — r0, then a, then b, then c,
methodically — with the rebuild OFF the entire time**, so not one of them changed
the cube; only **227 of 3665 frames** ever ran the rebuild. A grey "rebuild off"
caption was not enough. ⭐ **A control that silently does nothing must SAY SO at the
moment it is touched** — there is now a red on-panel banner and a console line. ⭐⭐
And the real remedy is the **`--aniso-ab` rig**: two panels off one camera, panel 1
= shipped Horn, panel 2 = the rebuild, sliders driving panel 2 only. **Separating
two behaviours in TIME asks the operator to remember a feeling; separating them in
SPACE does not.**

⛔⛔ **FINDING 2 — "I CAN'T SEE ANY DIFFERENCE" WAS CORRECT, AND THE NUMBER EXPLAINS
IT.** On `_204928`, both panels holding the same cube for 3553 frames:

| | |
|---|---|
| cube **position** difference between panels | **0.000 px** (max 0.000) |
| cube **orientation** difference | median **4.83°**, p90 17.4°, max 28.4° |
| frames differing by < 1° | **1.6%** |

⭐ And it is **FLAT across palm tilt** — median 5.3 / 4.9 / 5.9 / 4.5 / 4.2 / 4.3°
over the 0–15 … 75–90° bands. There is no regime where it becomes obvious.
⚠⚠ **~5° of rotation on a 40–80 px cube, split across two windows, is below what an
eye can resolve.** The estimator was diverging the whole time and the instrument
could not show it.
⭐⭐ **THE FIX RIDES ON THE POSITION PARITY**: because both cubes sit in bit-identical
places, they can be **SUPERIMPOSED** — panel 2 now draws panel 1's cube as a yellow
**wireframe cage** over its own solid one, plus a live `cage vs solid` angle. Any
gap between cage and solid IS the estimator difference, since position, depth, size
and translation are identical by construction. ⭐ **Report the number as well as
drawing it**: "no visible difference" and "no difference" are different claims, and
this project has already been burned four times from the other direction (a harness
reporting CLEAN on a take the owner had watched fail).

⚠ **FINDING 3 — THE GRAB-REFERENCE CANCELLATION, which is why 4.83° is small.** Horn
is grab-REFERENCED and each arm freezes its own reference *through its own
estimator*, so a constant tilt bias largely cancels between reference and current
frame. **The rebuild can only show up in what does NOT cancel** — the pose-dependent
part. That is consistent with the defect being a DRIFT, and it means an A/B judged
at small turns will always look like a null.

⚠ **FINDING 4 — TOGGLING OFF DOES NOT UNDO.** On `_202454` the cube first differed
from shipped Horn at frame 2663 (the toggle going on) and **stayed different to the
end of the take**, though the toggle went back off at 2890: the cube's orientation
is integrated, so an applied offset persists until it is re-grabbed. Do not read a
panel straight after a toggle.

### 2.0.19 ⛔ THE "STRONGER SLERP" — IT IS THE CAMERA'S FRAME RATE, NOT THE CODE

The owner reported the cube lagging more than on branch `1.7.-24-Z-axis-depth`.
Measured from each recording's own capture clock:

| take | frame gap | fps | gap, NO hand | gap, hand present |
|---|---|---|---|---|
| `..._211528_roll_card_axis_check_b` (23rd) | **48.0 ms** | 20.8 | — | 48.0 |
| `..._203307_yaw_card_axis_check_b` (23rd) | **64.0 ms** | 15.6 | — | 64.0 |
| `..._202454_t6d_psi_sweep` (24th) | 64.1 ms | 15.6 | 64.1 | 64.1 |
| `..._203927_t6d_ab_before_after` (24th) | 64.0 ms | 15.6 | 64.1 | 64.0 |

⭐⭐ **TWO THINGS SETTLE IT.** (1) **The gap is the same with and without a hand**
(64.1 vs 64.0) — MediaPipe's landmark pass and the whole gesture path only run when
a hand is present, so if computation were the limit those columns would differ. The
loop is waiting on the CAMERA. (2) **`yaw_card_axis_check_b` already ran at 64.0 ms**
and it predates all of T6d — the slower feel reproduces on the old branch.
⭐ The values are exact and quantised, the signature of a DSHOW webcam stepping its
frame interval under **auto-exposure** (darker room → longer exposure → 15.6 fps).

⛔⛔ **AND THE REASON IT READS AS "MORE SLERP" IS A REAL DEFECT, JUST NOT THIS ONE.**
`cube.orientation = _quat_slerp(..., ROTATION_SLERP_FACTOR)` uses a fixed **PER-FRAME**
factor with **no `dt`**, so the time constant is 2.32 *frames* — whatever the camera
makes it: **111 ms at 48 ms/frame, 149 ms at 64 ms/frame. +34% of lag from lighting.**
⚠ For a game targeting phones and desktops ([[target-cross-platform-app-deployment]])
this is first-order: the feel constant the owner tuned is only valid at the frame
rate it was tuned at. ⭐ The fix is `factor = 1 − exp(−dt/τ)` with τ ≈ 111 ms (to
reproduce the 20.8 fps feel) or ≈ 149 ms (the 15.6 fps one). **NOT BUILT — it
re-tunes a by-feel constant, which is the owner's call, and changing it mid-A/B
would confound the comparison.**

⚠ Also fixed here: `meta.json` recorded `"arms": args.arms` — the FLAG, not the
panels built — so a two-panel T6d take claimed one arm while `cubes` was keyed by
arm index. A reader trusting it would have stopped at panel 1 and never seen the arm
the session existed to test. It now stores the real count, the rig name and each
panel's estimator.

### 2.1 ⚠ PARTLY SUPERSEDED BY §2.0 — the earlier "camera tilt is not a cause" test

⭐⭐ **THE TWO SECTIONS LOOK CONTRADICTORY AND ARE NOT — the reconciliation is the
useful part, so do not "fix" either one.** §2.1's k-sweep says the axis error on the
clean take collapses with world z, therefore it is depth-induced and not a fixed
camera tilt. §2.0 says the camera is rolled ~11°. **Both are true, because of WHICH
TAKE each used.** The k-sweep ran on `2026-08-22_134553`, a **no-card** take, where
the operator had no gravity reference and aligned the hand to what *looked* vertical
— **measured at +2.5° in the image.** On that take the hand's rotation axis was
essentially the IMAGE vertical, so camera roll contributed ~nothing to the measured
deviation and the whole 14.5° really was cause 1. ⛔ **The camera roll only bites
when the motion is referenced to the WORLD** — which is what the card enforced
(fitted axis 21.2° there), and what a player naturally does. ⚠ So §2.1's conclusion
is correct *for its take* and must not be generalised to "the camera does not
matter".

Asked by the owner, 2026-08-24, and worth keeping because the confound is **real
and sharp**: `t5i` scores YAW against the *assumed* vertical `(0,1,0)`, but
`world_landmarks` are **camera-aligned** — so a camera mounting tilt would be
scored as estimator error. ⚠ Note the asymmetry that makes it plausible: the PITCH
take's expected axis is **measured from the image** (the knuckle row) and therefore
**absorbs** any tilt, while yaw's is assumed. That alone predicts *"yaw axis bad,
pitch axis good"* — which is exactly what is measured (14.5° vs 5.5°).

⭐⭐ **THE k-SWEEP ALREADY SETTLES IT, AT ZERO EXTRA COST.** A fixed camera tilt is a
**rigid rotation of the whole scene**, and scaling world z **cannot rotate an axis
that lies in the image plane** — so a tilt-induced component must SURVIVE `k → 0`.
Decomposing the fitted yaw axis against `k`:

| k | axis x (⇒ camera ROLL) | axis z (⇒ camera PITCH) | total dev |
|---|---|---|---|
| **1.00** | 0.241 (14.0°) | 0.072 (4.2°) | 14.5° |
| 0.60 | 0.135 (7.8°) | 0.022 (1.3°) | 7.9° |
| 0.20 | 0.013 (0.7°) | −0.031 (−1.8°) | 1.9° |
| **0.00** | **−0.011 (−0.6°)** | **0.000 (0.0°)** | **0.6°** |

**Both components collapse. So both are depth-induced, T6 owns them, and the
diagnosis stands.** ⭐ It also *bounds this rig*: implied camera pitch **≤ 4.2°**,
and that is an upper bound still contaminated by the depth error.

⚠⚠ **BUT THE OWNER'S UNDERLYING REQUIREMENT IS REAL AND IS NOW QUEUE ROW `T7`.**
A phone propped on a desk is routinely pitched **20–40°**, and a tilt θ produces a
lean of `acos(cos φ + cos²θ·(1−cos φ))` at hand-turn φ — **27.9° at θ=20°, φ=90°,
i.e. the whole show-stopper again, with a perfect T6 underneath.** ⛔ **T6 does NOT
fix that**: a planar PnP recovers pose in **camera** coordinates exactly as Horn
does, and neither knows where the world vertical is. **T7 is one conjugation**
(`ΔR_world = C·ΔR_cam·C⁻¹`) — read its row before assuming T6 covers it.

⭐ **BUT T7 DOES NOT BLOCK T6, AND IT IS NOT NEXT EITHER.** Owner, 2026-08-24: the
IMU was offered as gravity's source and **declined** — *"i don't want to introduce
a different behavior between desktop and mobile for the moment ... I would prefer
we later work on an initial calibration sequence"* — so `C` comes from **U12's
calibration**, identically on every platform, and **defaults to identity (level
camera) = today's behaviour** until U12 is built. **T7 therefore ships WITH U12,
not after T6**, because with `C` = identity it is a no-op. ⭐ It is also the better
architecture: an IMU is a **platform-conditional input into the estimator layer**,
which is exactly what the port contract and N6 exist to prevent.
⚠ **Nothing in T6 should anticipate T7** — do not add a `C` parameter, a world
frame, or a gravity hook to `PlanarPnP`. T7 is a conjugation applied to the
quaternion T6 already returns, and it belongs outside the estimator.

⚠⚠ **AND THE CAMERA MOVED BETWEEN CORPUS RECORDINGS** (owner, 2026-08-24: *"I move
my camera to capture the recordings"*). ⭐ **A/B on the SAME take is still sound** —
both arms carry the identical offset — **so §5's acceptance protocol is
unaffected**. ⛔ But **cross-take absolute axis numbers are not comparable**, which
is a live candidate for the unexplained pitch-take gap in §8, and it **cannot be
recovered retroactively** (gravity leaves no trace in landmarks; the corpus holds
no images). **Record the camera tilt in `meta.json` from now on.**

---

<!-- VERBATIM-END -->
