# SLANT/TILT ORIENTATION, AND REPAIRING `z` AT THE SOURCE

> **STATUS** · drafted 2026-08-27 · **Strategy A's ESTIMATOR IS BUILT** the same day
> (`Resources/palm_slant.py` + golden vectors); **not wired to anything, and
> Strategy B is untouched** · **OWNS** · the two strategies that come out of `T6`
> §4.3's split verdict
> **READ IF** · you are about to touch orientation estimation or the world landmarks
> **BACKGROUND** · [`../../00_CORE/queue_notes/T6.md`](../../00_CORE/queue_notes/T6.md)
> §4.3, and [`RATIO_TABLE_CALIBRATION_PROTOCOL.md`](RATIO_TABLE_CALIBRATION_PROTOCOL.md)

⛔ **Strategy B is still a draft. Nothing here is measured except where it says so.**

⚠⚠ **§1.3(a)'s floor is now MEASURED, and it narrowed the scope of this whole
document.** MediaPipe's landmark noise alone puts `σ` at **0.94–0.96 on a hand that
has barely moved**, i.e. **17–20° of false tilt at rest**, because `arccos` is nearly
vertical as `σ → 1`. Averaging the canonical over 31 frames recovers only 3°.
⭐ So Strategy A is a **LARGE-ANGLE CORRECTION, not a replacement for Horn** — which
is fine for what `T6` exists for (the yaw lean is worst at 60–90°, where the curve is
steep) but is a real ceiling, and §1.5's acceptance criteria must be read with it.
Measurement and consequences: [`../../00_CORE/queue_notes/T6.md`](../../00_CORE/queue_notes/T6.md),
step 3 and step 2.

---

## 0. Why the ratio table is the wrong shape, in one paragraph

`Rwl = ‖P₅−P₁₇‖ / ‖P₀−P₉‖` measures compression along **one fixed direction**. Under
combined rotation it carries `(W/L)·cos θ_yaw / cos θ_pitch` — **one number, two
unknowns**, so it cannot tell *"compressed a lot along x"* from *"compressed a
little along y"*. ⛔ That is not a weak ratio, it is a **lossy projection**: no
choice of two fixed lengths recovers what was discarded. It is also exactly why
§4.1 measured cross-talk near 1.0, and the owner's bijectivity question is what
made it visible.

⭐ The recoverable quantities are the ones the projection actually preserves, and
they have standard names.

---

## 1. STRATEGY A — SLANT AND TILT FROM THE AFFINE SVD

### 1.1 What is measured

Fit the 2×2 affine map from a canonical palm to the observed palm, on centred
points, and take its SVD:

```
A = argmin Σ ‖A·(pᵢ − p̄) − (qᵢ − q̄)‖²
A = U · diag(σ₁, σ₂) · Vᵀ
```

For a rigid plane whose normal is tilted away from the camera:

```
σ₂/σ₁       = cos(SLANT)      how far it is turned
V minor axis = TILT            which way it is turned  (in the PALM frame)
```

and the two game axes fall out **bijectively**:

```
tan θ_yaw   = tan(slant) · cos(tilt)
tan θ_pitch = tan(slant) · sin(tilt)
```

⭐ `U` absorbs the palm's roll, which is what makes this roll-invariant — provided
the tilt is read in the palm's own frame, not the image frame.

### 1.2 ⭐ MEASURED ALREADY, on the `dB` pair

| take | hold | σ₂/σ₁ | tilt |
|---|---|---|---|
| yaw | 0 / 30 / 60 / 90° | 0.992 / 0.858 / 0.531 / 0.238 | 76 / 75 / 91 / 102° |
| pitch | 0 / 30 / 60 / 90° | 0.992 / 0.940 / 0.827 / 0.341 | 151 / 7 / 177 / 176° |

⭐ **`σ₂/σ₁` falls monotonically on BOTH axes** — unlike `Rwl`, which falls for yaw
and rises for pitch — and **the tilt separates them**: yaw compresses near 90°,
pitch near 0/180°, orthogonal as the geometry requires.

⚠ Yaw at a declared 90° reads `σ₂/σ₁ = 0.238`, i.e. slant 76°, not 90°. It still
under-reads, because a hand is not a plane and its **thickness** fills in what the
projection should flatten. ⭐ But that is now ONE scalar with a known physical
cause, instead of a confound smeared across the axis question.

### 1.3 The three degeneracies, and a remedy for each

**(a) SMALL SLANT — the tilt is undefined.** At `σ₂/σ₁ → 1` the projected shape is
isotropic and the tilt direction is noise. Visible in the table above: pitch at 30°
reads `7°` between neighbours reading `151°` and `177°`, because `σ₂/σ₁ = 0.940`
there is almost no compression at all.

✅ **BUILT** as `palm_slant.authority()`, `SLANT_NOISE_FLOOR = 0.94` →
`SLANT_FULL = 0.80`, floor measured not chosen. ⭐ And it is load-bearing in the
shipped correction: the steer is `gain × authority`, never a bare gain.
⭐ **Remedy: fade, do not gate.** A near-square palm has little bias to correct, so
the correction's *authority* should rise with the slant — `smoothstep` on
`(1 − σ₂/σ₁)`, exactly the pattern `tip_trim` already uses for `spread`/`scale`.
That turns the degeneracy into a non-event rather than a decision, and it is
already a shipped, understood mechanism in this codebase.
⚠ The floor must be MEASURED from the six takes (where does the tilt stabilise?),
not chosen. The table above suggests it is somewhere between 0.94 and 0.86.
⭐ **RESOLVED 2026-08-27: 0.94**, and NOT from the six takes — they structurally
cannot show it (medians over 40-frame holds at large declared angles). It came from
`roll_card_axis_check_b` against `t5j`'s depth-free in-image ground truth.

**(b) SIGN — the two-fold ambiguity.** `cos(slant)` cannot distinguish tilting
toward from tilting away, and tilt is only defined mod 180°. This is the classical
planar-pose ambiguity: **Faugeras & Lustman (1988)** showed the decomposition
yields two physically plausible solutions, cut down by *visibility* and
*non-crossing* constraints.

⛔⛔ **PATENT FINDING — READ BEFORE CHOOSING A REMEDY.** The two most obvious
disambiguation routes are **actively patented**:

| approach | patent |
|---|---|
| resolve via **orientation sensors** | [US9305361B2](https://patents.google.com/patent/US9305361B2/en), [US20130063589A1](https://patents.google.com/patent/US20130063589) |
| resolve via **viewing-angle range** | [US20130064421A1](https://patents.google.com/patent/US20130064421A1/en) |

⭐ This is a **second, independent reason** to stay away from the IMU route the
owner already declined on behaviour grounds (`DECISIONS`: *"would split desktop and
mobile behaviour"*). The behavioural objection and the IP objection now agree.

✅ **Patent-free remedies, in the order I would try them:**

1. **Temporal continuity.** The solution pair can only exchange by passing through
   `slant ≈ 0`. So track the branch and forbid a switch except through the
   degenerate zone. Free, needs no new signal, and is the same shape as `DR-2`'s
   sign freeze — which this project has already built, shipped and lived with.
2. **The existing palm/back cue.** `palm_geometry.signed_palm_area` and `DR-2`
   already answer "palm or back", independently and from 2-D. ⛔ **It must stay
   independent** — see §2.4.
3. **The non-planar structure itself.** The 10.6 mm knuckle bow breaks the mirror
   symmetry in principle. ⚠ §4.1 measured `Rbow` sign-inconsistent, so this is the
   weakest of the three on current evidence and should not be leaned on.

**(c) EDGE-ON — `σ₂ → 0`.** Everything degenerates. ⭐ Reuse `DR-2`'s existing band
and freeze; one definition of "edge-on" in the codebase, not two.

### 1.4 Prior art, all decades old

* **Slant/tilt from the SVD of a local affine distortion** — the classical
  shape-from-texture result. The eigen/SVD directions of the affine matrix give
  tilt and slant directly:
  [Gårding-lineage framework, IJCV 1997](http://web.mit.edu/rruth/www/Papers/1997-SFT.pdf) ·
  [spectral/eigenvector formulation](https://eprints.whiterose.ac.uk/id/eprint/1991/1/hancocker7.pdf)
* **Affine factorisation under orthography** — Tomasi & Kanade, IJCV 1992
  ([paper](https://www.graphics.pku.edu.cn/docs/tomasi_kanade_sfm.pdf)): the
  measurement matrix is rank 3 and SVD factors it into shape and motion.
* **Planar pose ambiguity** — Faugeras & Lustman 1988.
* Already in the pipeline and already cleared: **Horn 1987**, **Kabsch 1976**.

⭐ Same posture as `F1`'s and the input system's: reach for the old, well-cited,
royalty-free result and record the lineage, rather than build on something a
holding entity can point a patent at (`N13`).

### 1.5 How it gets validated

Same-take A/B on the six ratio takes, scored against the **declared** angle — the
ground truth never comes from the estimator under test (`B4`). It must:

1. beat Horn on `|θ − declared|`, per axis and per depth;
2. **not regress `A10`** — yaw 14.5/1.13 · pitch 5.5/0.74 · roll 6.7/1.02 ·
   **jitter p95 25.41**;
3. keep `parity_replay` clean, and land with golden vectors (`CONSTRAINTS` §3).

---

## 2. STRATEGY B — REPAIR `z` AT THE SOURCE

### 2.1 The idea, and why it is architecturally right

Every consumer of the world landmarks currently carries its **own** workaround for
untrustworthy `z`: Horn tolerates it, `palm_depth` avoids metric scale entirely,
`edge_on_measure` exists to detect when it has collapsed, `tip_trim` fades on
conditioning. ⭐ **Four band-aids on one wound.** Repair `z` once, upstream, and
they all inherit the fix instead of each patching around it.

⭐ It also explains `T6` §4.3's pitch result: Horn under-reports pitch (a declared
60° reading **5.3°**) precisely because pitch moves the landmarks along `z`, the
one axis MediaPipe estimates worst. Yaw moves them along `x` and only *leans*.
**One rule: Horn's error grows with how much of the rotation is carried by `z`.**

### 2.2 The method

1. **Canonical palm.** Build the mean 3-D shape of the five palm landmarks
   (0, 5, 9, 13, 17) from the corpus, with its principal deformation modes. This is
   an Active-Shape-Model / rank-3 factorisation construction — Tomasi & Kanade's
   SVD applied to the corpus rather than to a video stream.
   ⛔ Not MANO, not HaMeR, not WiLoR (`N13`): the shape prior is built from **our
   own recordings**, which also makes it this operator's hand rather than a median
   one.
2. **Orientation from 2-D only** — Strategy A's slant/tilt. No `z` is consulted.
3. **Synthesise** `worldᵢ = s · R(slant, tilt) · pᵢ`, with `s` from the projected
   scale.
4. **Hand that to the pipeline unchanged.** Nothing downstream needs to know.

### 2.3 ⛔ Only the PALM may be synthesised

The palm quad is near-rigid; the fingers are not — Step 0's `M2` measured the rigid
tip residual swinging **75–95° within half a second**. ⛔ Synthesising fingertip
`z` from a rigid prior would manufacture a fiction and feed it straight to the grip
point and the trim. **Palm only; the tips keep whatever MediaPipe says.**

### 2.4 ⛔⛔ THE CIRCULARITY TRAP, AND IT IS THE ONE THAT WOULD BITE

`palm_geometry.geometric_chirality` reads the **signed volume** of the world
landmarks. If `z` is synthesised from an assumed palm shape, that sign is *whatever
the model assumed* — the check returns its own input and becomes self-fulfilling.

⛔ `U7` exists precisely because the handedness label was **confidently wrong
10.8%** of the time. Replacing a confidently-wrong label with a confidently-
circular geometry check is worse than either, because nothing would detect it.

✅ **Rule: chirality must keep reading a source the reconstruction did not
produce** — MediaPipe's raw world landmarks, or a 2-D-only formulation. Whichever
is chosen, `analysis/verify_geometric_chirality.py` must be extended to assert the
independence, so the trap cannot be re-entered silently.

### 2.5 ⚠ It must be measured against `planar_pnp`'s rejection

`T6`'s planar solver already reconstructed orientation from 2-D and was
**A10-rejected 2026-08-24 — "yaw got worse"**. Strategy B differs in a real way
(an empirical shape prior and slant/tilt, rather than an analytic PnP solve) but
the failure mode may be identical. ⛔ It is measured **against** that rejection, not
around it, and the comparison goes in `REJECTED.md` either way.

⚠ Note also that `T6` deliberately avoided IPPE/OpenCV for licence reasons
(`CONSTRAINTS` §1). Strategy B inherits that: classical factorisation and
Procrustes only.

### 2.6 How it gets validated

Cheapest decisive test, and it needs **no new recording**:

1. reconstruct `z` on the six ratio takes;
2. run the SHIPPED `palm_rotation.Horn` on the reconstructed constellation;
3. compare `|θ − declared|` against Horn on MediaPipe's `z`, per axis, per depth.

⭐ If the pitch collapse (5.3° at a declared 60°) closes, that single result
validates both strategies at once — which makes it the sharpest first experiment in
either draft.

Then the usual gates: `A10` non-regression, `parity_replay`, golden vectors, and a
live look in both tools (`§10.2` gate 5 — a live take closes it, not a harness).

---

## 3. Sequencing

1. ✅ **Cross-check the pitch collapse** against the established pitch harness.
   ⛔ **DONE, and the claim was RETRACTED**: the established z-free witness
   under-reports pitch too, so the **declaration** is the outlier, not Horn. The
   takes cannot ground-truth the 30–60° band at all.
2. ✅ **Slant floor and tilt stability** — done, see the ⚠⚠ note at the top.
   It cost the generality of this strategy and was worth knowing first.
3. ✅ **The estimator** — `Resources/palm_slant.py` + `analysis/verify_palm_slant.py`,
   2026-08-27. ⚠ Built and gated; **wired to nothing**.
4. ✅✅ **WHERE THE CORRECTION ENTERS — ANSWERED, AND NOT WHERE §1.1 EXPECTED.**
   ⛔ §1.1's `tan θ = tan(slant)·cos(tilt)` inverts the slant into an ANGLE. `t5f`
   measured the angle as **already fine** (*"the cube turns about as far as the
   hand"*) and the **AXIS** as the defect. ⭐ So the shipped correction keeps Horn's
   angle and steers only its in-image axis direction — which needs **no `σ` → angle
   table at all**, and therefore does not wait on `U12`.
   `Resources/palm_slant_axis.py`: yaw lean 22.0° → 13.6°, pitch 14.8° → 10.0°,
   axis wander flat-to-improved. ✅ §1.3(b)'s sign ambiguity is handled by remedy 2
   (the existing palm/back cue) and §1.3(c)'s edge-on band by reusing
   `edge_on_measure`, as both said to. ⏭ The remaining gate is §1.5's item 3, the
   live look — `slant_rig.bat`.
5. ⏸ Strategy B only if A's orientation is good enough to build a `z` on — and
   the floor above is a direct argument that it may not be.
