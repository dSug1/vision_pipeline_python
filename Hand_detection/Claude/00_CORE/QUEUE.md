# THE BUILD QUEUE — one list, every subsystem

> **STATUS** · live · **OWNS** · what gets built next, for the whole project
> **READ IF** · you are starting any build, or wondering where an item stands
> **LAST VERIFIED** · 2026-08-25

⛔ **THIS IS THE ONLY QUEUE.** It replaces `PART_ONE.md` §3.1, which was its
address until 2026-08-25. Do not start a second list, in a subsystem folder or
anywhere else. Do not reorder it to be helpful.

⭐ **Each row's FULL history — every measurement, retraction and decision that
produced its status — is in `queue_notes/<ID>.md`, verbatim.** The `Notes`
column here is a pointer, not a summary of record. When a row's status changes,
update the one-line status here *and* append to its dossier.

**`Sub`** says which folder a row belongs to, so a session can filter to its own
subsystem: `HAND` = 10_HAND_TRACKING · `GAME` = 20_GAME_RULES ·
`3D` = 30_OBJECTS_3D · `INPUT` = 40_INPUT_SYSTEM · `PORT` = 50_PORT_WEB_MOBILE ·
`SEC` = 60_SECURITY_COMPLIANCE · `CORE` = cross-cutting.

The queue's governing rules and the reason it was merged into one list are in
[`queue_notes/_QUEUE_PREAMBLE.md`](queue_notes/_QUEUE_PREAMBLE.md) (verbatim).
The binding one, restated: **A10 — measure or revert.**

---

## ⭐⭐⭐ YOU ARE HERE (2026-08-27, evening)

✅✅ **`F1` IS SHIPPED AND LIVE** — fingertip grip, `A1`'s motion-masked walk, depth
anchoring at grab, footprint grab radius. ⛔ **The rotation TRIM was REMOVED**:
§10.1 measured it non-monotonic in the declared finger angle at every gain and
clamp. `A10` reproduces exactly, `parity_replay` clean on four takes.

✅✅ **`R1` IS SHIPPED TO BOTH TOOLS** — depth-ordered occlusion as ONE rule for every
object, per-landmark and per-SEGMENT bone occlusion, a SOLID near-face occluder, and
⭐ **landmarks drawn in PRODUCTION for the first time**. A **FREEZE** damper ships for
rotation AND translation (`RELEASE 60 / FREEZE 1`) — *damping is not stillness*, and
three softer designs were live-rejected before it. ⛔ The defect the owner found by
eye was OUR logic: cube **x,y** from the fingertips, cube **z** from the palm.

⛔⛔ **`T6` IS SPENT. BOTH LIVE BUILDS WERE OWNER-REJECTED THE DAY THEY WERE BUILT.**
The ratio table died first (`Rwl` is a **lossy projection** — one number, two
unknowns), and the slant/tilt regression that replaced it scored genuinely better
than Horn on both axes. Then the axis correction drew *"the feel is very bad …
discontinuities everywhere"*, and the owner's own halves 1+2 drew *"much worse than
panel 1 … lot of jumps, lot of jitter"*.

⭐⭐ **THE SCORES WERE GOOD, WHICH IS THE POINT.** Halves 1+2 produced the best yaw
this project has ever measured — **lean 27.2° → 8.6°** — and were rejected anyway,
because per-frame orientation jump p95 went **12.6° → 30.3°** while the MEDIAN
improved. **Smoother most of the time, occasionally much worse; the tail decides the
feel, every time.** Three 2-D-shape estimators have now died of exactly that.

⭐⭐⭐ **THE METHOD RULE THIS COST, and it outlives the row: A CORPUS WHOSE MOTION
DOES NOT MATCH THE PRODUCT'S CANNOT VALIDATE AN ESTIMATOR FOR THE PRODUCT.** All six
`T6` takes are OPEN hands; the game GRIPS. Every offline score in that row was earned
on a motion the product never performs, and the gap was named before the first wiring
and not closed — twice.

⛔ **THE GATE ON ANY FOURTH ATTEMPT OF THIS SHAPE**: demonstrate a per-frame
orientation jump **at or under shipped Horn's, on a GRABBING take, BEFORE** any lean
number is quoted. Nothing in this family has come within 1.8x. **The lean score is
not the gate and never was.**

✅ **Nothing was reverted** — both builds defaulted to gain 0, production never
constructed them, `parity_replay` is clean. `Resources/palm_slant.py`,
`palm_slant_axis.py`, `palm_slant_pose.py` and their harnesses are kept and
regenerable. ⭐ Strategy B (reconstruct `z` from a validated orientation) is
**untouched and now unsupported**: it needs an orientation that survives live, and
none does.

⛔ **Still the owner's show-stopper: the yaw lean** (~27° at a 60–90° turn). `F1` did
not fix it — the apparent improvement was the trim's constant offset, now removed.

⭐⭐⭐ **THE NEXT BUILD IS NOT CHOSEN — it is the owner's call.** What is actually
ready, with nothing blocking it:
* ⭐ **The PLATFORM decision is DUE.** [`DECISIONS.md`](DECISIONS.md) sequenced it
  *right after `F1`*, and `F1` has shipped. Everything renderer-shaped waits on it —
  `U2`, `U12`, `T7`, the game layer — and `IS4` is its prerequisite.
* **`B5` + `4.4`** — the grab signal from the finger arcs and the hand-open release
  trigger, ONE project, and `N8` (⚠ re-opened and widened by `F1`) rides on it.
* **`T1` / `T4` / `N12`** — the open pipeline defects, deliberately not next.

⭐ The full block, and every superseded one back to 2026-08-03, is
[`10_HAND_TRACKING/history/SESSION_LOG.md`](../10_HAND_TRACKING/history/SESSION_LOG.md) — newest first.

---

## Phase 0 — instrumentation

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [0.1](queue_notes/0.1.md) | M0 recorder / replay / metrics harness | HAND | perception | partly done — frame capture + stop-reason landed 2026-08-04 | — |
| [0.2](queue_notes/0.2.md) | M0 baseline metrics on current pipeline | HAND | perception | ✅ done 2026-08-02 | — |
| [0.2b](queue_notes/0.2b.md) | Record the scripted sequences | HAND | perception | ✅ 7 takes done 2026-08-02 | — |
| [0.3](queue_notes/0.3.md) | End-to-end latency measurement | HAND | perception | queued | — |
| [0.4](queue_notes/0.4.md) | S1 predictor evaluation harness | HAND | perception | optional, parallelisable | — |
| [0.5](queue_notes/0.5.md) | ~~S8 offline oracle over the corpus~~ | HAND | perception | ⛔ dropped 2026-08-04 — two blockers, one permanent (licence) | — |

## Phase 1 — kill the singularities

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [1.1](queue_notes/1.1.md) | M5d `K` fixture test | HAND | perception | ✅ done 2026-08-03, 13 checks | 0.1 |
| [1.2](queue_notes/1.2.md) | M5a `edgeOnMeasure` | HAND | perception | ✅ done 2026-08-03 | — |
| [1.3](queue_notes/1.3.md) | M6a no Euler in the estimation path | HAND | perception | ✅ already satisfied | — |
| [1.4](queue_notes/1.4.md) | M2 bone-length calibration | HAND | perception | ⛔ **DEAD** — audited and upheld; replaced by 1.7 | — |
| [1.5](queue_notes/1.5.md) | M3a hard anatomical constraints | HAND | perception | ✅ done 2026-08-04 — 0.00% FP on the control | 1.4 |
| [1.6](queue_notes/1.6.md) | M4 precision weighting + χ² gating | HAND | perception | ✅ built 2026-08-04, A10 passes; 2 of 4 cues measured out | 1.5 |
| [1.7](queue_notes/1.7.md) | M2b impose a skeleton | HAND | perception | ⚠ built then **parked** — cannot affect orientation by construction | 1.5, 1.6 |

## Phase 2 — temporal identity

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [2.1](queue_notes/2.1.md) | M5c DR-1 chirality lock | HAND | perception | ✅ done, live-confirmed 2026-08-02 (shipped early as N5) | 1.1 |
| [2.2](queue_notes/2.2.md) | M5e DR-2 edge-on band | HAND | perception | ✅ built + live-tested 2026-08-03 | 1.2, 2.1 |
| [2.3](queue_notes/2.3.md) | M6b–e quaternion UKF, anisotropic covariance | HAND | perception | ⛔ **deprioritised** — 5 attempts all null, audit confirmed genuine | 2.1 |
| [R](queue_notes/R.md) | Re-measure M0; decide whether Phase 3 precedes features | HAND | gate | open | 2.3 |

## Pipeline defects

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [T1](queue_notes/T1.md) | Back-of-hand rotation quality | HAND | pipeline | open — belongs to the **landmark** layer, not the estimator (§16.17) | 1.5, 1.6, 1.7 |
| [T2](queue_notes/T2.md) | Pitch-plane crossing | HAND | pipeline | partly fixed — DR-2 closed the sign-flip half | 2.2, 1.5–1.7 |
| [T3](queue_notes/T3.md) | Object jump / silent handover | HAND | pipeline | ✅✅ **fixed 2026-08-22** by the narrow remap, owner-accepted live | 2.1, N5 |
| [T4](queue_notes/T4.md) | Yaw / palm-sinking in translation | HAND | pipeline | deferred | 1.4, 1.2, 4.1 |
| [T6](queue_notes/T6.md) | Orientation from 2D (planar PnP) | HAND | perception | ⛔⛔ **built and A10-rejected 2026-08-24** — yaw got worse; code in `estimators()` only. ⭐⭐ **A 2D-RATIO-TABLE correction is OPEN and NOT covered by §2.0.12** (owner 2026-08-25) — clean depth-free index, yaw/pitch kept separate, declared ground truth. §2.0.9's refutation used a *contaminated* index so it does not carry. ✅ **ALL SIX TAKES RECORDED 2026-08-26** — 1680 frames, every one on-axis, 3 depths × 2 axes, right hand declared. ⛔ **CAVEAT ZERO (owner): the distance was NOT reliable and the hand very likely moved during the takes.** ⭐ Fine for the ratio table — foreshortening ratios are **scale-free** — but it invalidates every depth-derived reading, and two claims built on one were retracted the same day. ⚠ Grid is **30°** (7 positions), not the protocol's 25.71°: the owner could not set 25.71° by feel, and the declared angle IS the ground truth. ⛔ **Before analysing, read the dossier**: the ratio the tool prints is the take MEDIAN and is contaminated by the sweep — use the 0° hold. ⛔ **TWO claims made and retracted on this data in one afternoon** — "take 6 is the anomaly", then "four of six never return, which geometry forbids". ⭐ Caveat zero answers both: a drifting hand produces a monotone climb, no mystery required. ⭐ The one finding that SURVIVES (it is scale-free): `edge_on_measure` is **blind to pitch** — 0.94–1.00 at pitch-90° vs 0.13–0.28 at yaw-90° — so `Rsq`/`Lsq` cannot judge a pitch take. ✅✅ **§4.1/§4.2/§8.1/§8.2 ANALYSED 2026-08-26** (`analysis/t6_ratio_analysis.py`): magnitude does NOT separate the axes (orthography forbids it), but the **SIGN** of `Rwl`'s 0°→90° excursion splits yaw from pitch **3/3** — so the table must be **2-D**, and `Rdiag`/`Rbow` did not deliver the second observable. ⭐⭐ **THE DEPTH ARM PAID FIRST**, and a verification pass sharpened it: at the **square** pose the four palm spans imply depths **13–22% apart** (drift-free — one frame), `min` over them IS the absolute estimator, so its output **STEPS whenever rotation changes which span wins**. `NOMINAL_SPAN_M[(5,17)]` is the outlier. ⛔ The snap gate inherits it: within-take excursion reaches **0.161 m against a 0.15 m tolerance**. ⚠ Two claims RETRACTED the same day — the drift bound (premise refuted) and a "distance-free" ratio that was distance-SQUARED; the corrected statistic is the product, ≤ **1.209**. **Next: §4.3 transfer, §8.3 inversion**  ⛔⭐ **§4.3 THE DECIDING TEST RAN 2026-08-27 AND SPLITS BY AXIS.** **YAW: DEAD** — mean **+2.4°** recovered, and ASYMMETRIC (near→far +8..12°, far→near −8..15°), so the ratios carry a depth dependence and one table does not serve all depths (§4.4 answered for free). ⚠ The verdict was nearly cherry-picked: reading the BEST pair would have said *"needs calibration"*. ⭐⭐ **PITCH: apparently transformative** (mean +41.4°, 6/6 pairs) — but because **HORN COLLAPSES**: at a declared 60° pitch the shipped estimator reports **5.3°**. ⛔ UNCONFIRMED, on a one-day-old instrument; **cross-check against the established pitch harness before building anything**.  ⭐⭐⭐ **THE RATIO TABLE IS DEAD; A REGRESSION REPLACED IT (2026-08-27).** `Rwl` is a LOSSY PROJECTION (one number, two unknowns), so §4.3's yaw transfer failed and §4.1's cross-talk was ~1.0. ✅ **Slant/tilt from the trimmed affine SVD, fitted from the takes**, beats Horn on both axes (**yaw 8.7° vs 11.5°, pitch 17.6° vs 30.7°**) and is **bijective** by construction. ✅ **The owner's freeze-at-grab architecture is validated** (10.6°/17.4°) — the composition is MULTIPLICATIVE, and additively it scores worse than Horn. ⛔ Palm-only under grip: the finger gain does not survive a closed hand. ⛔ The pitch collapse and §4.3's pitch verdict are RETRACTED — the declaration is the outlier. ✅ **THE COMPOSITION FIT RAN and the data KEPT the multiplicative model** (α=β=1), so freeze-at-grab is measured rather than assumed — 9.2°/9.8° vs Horn 13.2°/24.3° excluding near-edge-on grabs. ⛔⛔ **THEN THE INDEPENDENT-TRUTH SCORE NARROWED THE WHOLE ROW (2026-08-27).** Against `t5j`'s depth-free in-image truth on `roll_card_axis_check_b`: roll invariance HOLDS (~7–8° added across 40–103° of real roll), but there is a **static 17–20° FALSE-TILT FLOOR at rest** — `σ` sits at 0.94–0.96 on a hand that barely moved, because `arccos` is nearly vertical as `σ → 1`. Averaging the canonical over 31 frames recovers only 3°, so it is landmark noise, not sampling. ⚠ The six declared-angle takes **structurally could not** have shown it (medians over 40-frame holds at large angles). ⭐ **So this is a LARGE-ANGLE CORRECTION, not a replacement for Horn** — harmless for the yaw lean, which is worst at 60–90° where the curve is steep. ✅✅ **THE ESTIMATOR IS BUILT 2026-08-27** — `Resources/palm_slant.py` + `analysis/verify_palm_slant.py` in the same change, stdlib-only/numpy-free/clock-free, **with the authority fade in from the start** (0 at σ 0.94, 1 at 0.80). Golden vectors pass; `A10` unchanged (axis 13.0°, gain 1.11); `parity_replay` clean on 3868 frames. ⭐ The vectors caught **three real bugs on their first run**, one of them `authority()` inverted — full confidence at exactly the noise pose. ⛔ **The `σ → angle` table is NOT in the module** (it carries hand thickness, so it is per-user — `U12`). ⚠ **WIRED TO NOTHING YET.** ⭐⭐⭐ **`t5f`'s OWN WORDING UNBLOCKED THE ROW (2026-08-27): THE DEFECT IS THE *AXIS*, NOT THE ANGLE** — *"the cube turns about as far as the hand; AXIS is not"*. Every design here aimed at turning `σ` into an ANGLE, which was already fine, and which is the half needing the per-user thickness table. ⭐ **Correcting the AXIS needs NO table, so `U12` is off the critical path.** Under orthography the palm foreshortens ALONG the turn, so `affine_svd`'s major direction IS the in-image rotation axis — measured **10.4° vs Horn's 22.8°** at ≥40° palm-facing. ⛔⛔ **TWO HARNESS BUGS were caught first, either of which printed the OPPOSITE verdict**: freezing the canonical on `frames[0]` (these are SWEEPS, not holds), and comparing `tilt` to the truth in the WRONG FRAME — tilt is an axis in the CANONICAL PALM's frame, so scoring it against an image-frame truth measures the hand's ROLL, and the first run printed "REFUTED". `t5j`'s knuckle-row angle reconciles them. ⭐ The collapse past ~100° is **the FOLD**, and `signed_palm_area` — independent, pixels only (`B4`) — flips at the same rotation; off-branch the module hands the frame back to Horn untouched. ✅✅ **BUILT AND A10-SCORED**: `Resources/palm_slant_axis.py` + golden vectors; **yaw lean 22.0° → 13.6°, pitch 14.8° → 10.0°, with NO rise in axis wander** (pitch p95 45.0 → 22.1 — it improves). `gain 0` is bit-exact shipped Horn. `parity_replay` clean; production untouched. ⚠ Differs from `planar_pnp` (A10-rejected) in kind: nothing is replaced — Horn still computes the rotation and only its axis DIRECTION is steered, `z` untouched, angle preserved exactly. ⛔⛔ **BOTH BUILDS LIVE-TESTED AND OWNER-REJECTED 2026-08-27.** The axis correction: *"the feel is very bad. there is no consistency in the rotation axis, discontinuities everywhere"*. Then the owner's OWN strategy (`palm_slant_pose` — the six-take regression on a grab-frozen canonical, HALVES 1+2, both feature sets): *"panels 2 and 3 are much worse than panel 1 ... lot of jumps, lot of jitter"*. ⭐⭐ **THE SCORES WERE GOOD, WHICH IS THE POINT**: halves 1+2 produced the best yaw this row ever measured (**lean 27.2° → 8.6°**) and was still rejected — per-frame orientation jump p95 12.6° → 30.3° (2.4x), while the MEDIAN improved (2.98 → 2.41). **Smoother most of the time, occasionally much worse; the tail decides the feel every time.** Three 2-D-shape estimators have now scored better on the lean and worse on the tail. ⛔ Rescues all failed: one geometric fade for both hard gates (1.90x → 1.84x), a tau sweep 40–400 ms (**no tau works** — 400 ms is still 1.08x and the lean decays), sign hysteresis (2.63x → 2.39x). The noise is `σ` itself — **0.11 p95 per frame on a GRIPPING hand**, against a curve steepest where `σ` is highest. ⭐⭐⭐ **THE METHOD RULE, and it is the row's most reusable output: A CORPUS WHOSE MOTION DOES NOT MATCH THE PRODUCT'S CANNOT VALIDATE AN ESTIMATOR FOR THE PRODUCT.** All six takes are OPEN hands; the game GRIPS. Every offline score here was earned on a motion the product never performs, and the gap was named before the first wiring and not closed — twice. ✅ Nothing to revert (both default OFF, production never constructed them, `parity_replay` clean); everything kept and regenerable. ⚠ Also fixed: the A/B's own jitter metric measured AXIS DIRECTION, undefined for a near-identity rotation — it reported smoothing as making jitter worse. **⛔ GATE FOR ANY FOURTH ATTEMPT: demonstrate a per-frame orientation jump at or under shipped Horn's on a GRABBING take BEFORE quoting a lean number. Nothing in this family has come within 1.8x.** | 4.2 |
| [R1](queue_notes/R1.md) | Rendering: occlusion, depth order, steady damper | HAND | render | ✅✅ **SHIPPED TO BOTH TOOLS 2026-08-27.** Depth-ordered occlusion as ONE rule for every object (`Resources/depth_order.py`), per-landmark depth and PER-SEGMENT bone occlusion, a SOLID near-face occluder (a cube is 7.2 cm deep -- treating its centre as the occluding plane left its near half transparent), and ⭐ **landmarks drawn in PRODUCTION for the first time** -- it had none, so nothing there could ever be occluded. ⛔⛔ **THE OWNER FOUND THE REAL DEFECT BY LOOKING**: with a palm-forward hand every fingertip drew in front of the cube except the thumb, which cannot be if the cube follows the tip barycentre. It was OUR logic -- cube **x,y** came from the FINGERTIPS and cube **z** from the PALM, so a gripping hand's fingers (measured 3.6 cm nearer than the hand origin) always landed in front. Fixed by anchoring `cube.grab_hand_depth_m` on the grip point; no jump at grab, because the offset is measured against the same value. ⛔ **TWO OF MY CLAIMS RETRACTED**: "MediaPipe puts palm-forward fingertips on the wrong side of z" was an artifact of splitting a TWO-HAND take by `signed_palm_area`, whose sign is CHIRALITY-DEPENDENT (`U7`'s error class, committed again); and the whole-hand depth-reversal hypothesis was tested (`analysis/z_depth_flip.py`) and REFUTED -- chirality is 100% consistent across palm and back, and a reversal would flip it. ⭐⭐ **A YAW FINDING FELL OUT FOR FREE**: the palm quad's own z spread is **0.0658 m face-on and 0.0681 m at 90 deg** -- essentially constant, where it should go from ~0 to ~its own width. So Horn's z input carries almost NO yaw information. That is `T6`'s 24.9 deg finding by an independent route, and it also proves fixing fingertip depth cannot help yaw (Horn fits `PALM_LANDMARKS`; the tips are not in it). ⭐ **THE DAMPER: three designs rejected before one stuck.** *"Damping is not stillness"* -- even at 4500 ms the blend factor is 0.015 and the cube creeps. What ships is a FREEZE: exactly 0.0 below the threshold, shipped tau above it, hysteresis between. `RELEASE 60 / FREEZE 1`, and **the same numbers serve translation** because the two speed distributions nearly coincide while held (p50 27 deg/s vs 26 px/s) -- measured, not assumed. ⛔ **THE COHERENCE GATE WAS BUILT TWICE AND REMOVED TWICE**, including the owner's own whole-hand matrix form. The Frobenius correlation is the better MEASURE (still **-0.26** vs slow **+0.54**, with a principled zero threshold) and a bad TRIGGER: coherence says the hand is moving SOMEHOW, the freeze needs to know HOW MUCH. It cost 7-11 points of slow-turn following for ~1 point of stillness on 6038 frames of natural use. ⚠ Both implementations were computing every frame with the result DISCARDED -- the reason to delete rather than park. ⚠ **Known limit**: the object is 7.2 cm and the operator's grip aperture measures ~2 cm, so with the solid occluder on, holding hides every fingertip. Not a bug -- it is what "solid" plus "centred on the tips" jointly mean. | F1 |
| [T6d](queue_notes/T6d.md) | The anisotropic 2×2 fit | HAND | perception | ⛔⛔ built, 4 live sessions, **owner-rejected 2026-08-24** — production never ran it | T6 |
| [L1](queue_notes/L1.md) | Rotation smoothing — a **time constant** | HAND | responsiveness | ✅✅ **shipped 2026-08-24**, owner-settled live at τ = 20 ms | — |
| [F1](queue_notes/F1.md) | ⭐⭐⭐ **The cube's transform from the FINGERTIPS** | HAND | perception + gesture | ⭐⭐⭐ **SPECIFIED + STEP 0 MEASURED + STEP 3 SHIPPED 2026-08-25** (⛔ live take owed). Design = **palm-frame deformation + bounded trim**, gain 0 ⇒ bit-identical to Horn; τ = 20 ms untouched; ⛔ contact-point arm dropped on a **patent** finding. **Census (`analysis/f1_tip_census.py`)**: tip noise floor **1.5 mm** ✅ workable (held only 5–10% worse) · ⛔ rigid tip residual **75–95° inside 0.5 s** — not noise, the rigid model is wrong ⇒ clamp far below it · ⛔ plain barycentre drifts **1 cm median / 6 cm p95** ⇒ `g_pos = 1` needs a clamp · ✅ collinearity floor 0.20 costs 1.9%. ⭐⭐ **Steps 1, 2 and 4 BUILT 2026-08-26** — 1€ filter, fingertip barycentre for snap+translation, and the palm-frame ROTATION TRIM (gain 0 = shipped Horn; a rigidly rotated hand yields **0.0000°** of trim). ⭐ **`f1_rig.bat` runs all three side by side on one camera** for the live take. ⛔ **Live take owed** — and until it happens **BOTH F1 switches are OFF in the game** (`USE_TIP_BARYCENTER=False`, `TRIM_GAIN=0.0`), so production is pre-F1 and every change lives in the rig where it can be compared. ⭐ **Step 1 landed 2026-08-26**: the **1€ filter** + 30 golden vectors, inert until step 2 (⚠ the vectors caught a real divergence from the paper immediately — the speed term used the filtered, not the raw, value). **Back-of-hand snap rule REMOVED** ✅ **live-confirmed both tools 2026-08-25**; debug measured **9 of 15 snaps back-of-hand** (⚠ re-opens `N8`; the rule was refusing **8.3%** of free-hand frames; ⚠ production recorded nothing — `N4`) → [`spec/F1_FINGERTIP_TRANSFORM_SPEC.md`](../10_HAND_TRACKING/spec/F1_FINGERTIP_TRANSFORM_SPEC.md)  ⭐⭐⭐ **RIG-ACCEPTED LIVE 2026-08-26** — owner *"I like the feel, this is better than the palm grip"*, and *"this is good"* at **tau 70 ms**. Trim measures **21.2° lean against the shipped 32.9°** at large yaw. ✅ **`A1` shipped into both tools**: the object now settles ON the fingertip barycentre (a **115.6 px** constant offset, faded at 150 px/s after a teleport and an exponential both FAILED the gate) and its depth is re-seated on the hand at every grab — it had been **ratcheted into the 0.30 m floor for 57.4% of every hold** while the hand was never once that near. ⛔⛔ **TAKE 1 WAS VOID**: two module-global gates left panels 1 and 2 **bit-identical (0.00 px)** — the switch had been verified where it was SET, not where it took EFFECT. ⛔ **Both switches still OFF in the game**: the `A10` bar and §10.1's trim-resolution metric are still owed, and the 21.2° is DAMPING until a declared take says it is fidelity.  ✅✅ **SHIPPED 2026-08-27.** `USE_TIP_BARYCENTER=True` — the fingertip grip, `A1`'s motion-masked re-centring walk, depth anchoring at grab, and a grab radius that is the object's PROJECTED FOOTPRINT. ⛔ **The rotation TRIM was REMOVED** (`TRIM_GAIN=0.0`): §10.1's take measured it **non-monotonic in the declared finger angle at every gain and clamp** — 15.7/12.6/20.3° for a declared 10/20/40 — so it is not a fine control at any setting, and the rig's 21.2° lean was a constant 10° offset, not finger steering. ✅ `A10` reproduces EXACTLY (yaw 14.5/1.13 · pitch 5.5/0.74 · roll 6.7/1.02 · **jitter p95 25.41**). ✅ `parity_replay` NO DIVERGENCE on four takes after **six** fixes — three per-hand estimators that did not die with their track, three harness asymmetries. | L1 ✅ |
| [T7](queue_notes/T7.md) | World-referenced rotation (tilted camera) | HAND | perception | designed 2026-08-24 — ⭐ ships **with U12**, not after T6; no-op until then | T6, U12 |

## Phase B — the block representation

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [B1](queue_notes/B1.md) | `hand_blocks.py` — the derived view | HAND | perception | ✅ done | — |
| [B2](queue_notes/B2.md) | Block separability | HAND | perception | ✅ done 2026-08-04 — anchor claim holds, outlier claim does not | B1 |
| [B3](queue_notes/B3.md) | Palm-transform predictor | HAND | perception | queued | B2 |
| [B4](queue_notes/B4.md) | Anchor + rotation A/B | HAND | decision | ✅ closed 2026-08-17 — `horn-palm` shipped, arm B rejected | B1 |
| [B5](queue_notes/B5.md) | Grab signal from arcs — ⭐ **one project with 4.4** | HAND | feature | queued | B1, B4 |
| [B6](queue_notes/B6.md) | Two-channel outlier test | HAND | perception | research — hypothesis, not evidence | B1, B2 |
| [B7](queue_notes/B7.md) | Confirmation gate | HAND | perception | ⛔ **park confirmed under a blind test** 2026-08-17 | B1 |
| [B8](queue_notes/B8.md) | Optimise the quadratic | HAND | perception | ⛔ done 2026-08-04 — every fit **loses to holding the last value** | B1 |

## Phase 3 — latency and grab

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [3.1](queue_notes/3.1.md) | M7 dual-pathway + forward prediction | HAND | perception | unblocked 2026-08-03 (the blocking warning was an artifact); first task done | 0.3, 2.3 |
| [3.2](queue_notes/3.2.md) | M8b RTS retrospective smoothing | HAND | perception | queued | 2.3 |
| [3.3](queue_notes/3.3.md) | M8a A/B vs §14.1 | HAND | decision | queued | 2.3, 4.1 |
| [3.4](queue_notes/3.4.md) | M8c predictive grasp onset | HAND | perception | blocked | 4.3 |

## Phase D — dropout mitigation

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [D0](queue_notes/D0.md) | Dropout census | HAND | measurement | ✅ done 2026-08-21 | — |
| [D1](queue_notes/D1.md) | `HandState` tracking fields | HAND | perception | ✅ done 2026-08-21 — no behaviour change by construction | D0 |
| [D2](queue_notes/D2.md) | Hold-and-decay bridging (150 ms coast) | HAND | perception | ✅✅ shipped 2026-08-21, accepted live | D1 |
| [D3](queue_notes/D3.md) | Resync blend on reacquisition | HAND | perception | ✅✅ shipped 2026-08-21 — the arm the owner chose | D2 |
| [D4](queue_notes/D4.md) | Grace period before release | HAND | decision | ⛔⛔ **declined** by the owner 2026-08-21 after seeing D2/D3 live — answered, not deferred | D2, D3 |

## Phase 4 — unlock the features

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [4.1](queue_notes/4.1.md) | M9 metric depth | HAND | perception | ✅ estimator built + A10 passed 2026-08-22; ⚠ its trackId ownership half is **reverted** | 1.7 |
| [4.2](queue_notes/4.2.md) | Z-axis translation + 3D snap gate + play volume | HAND | feature | ✅✅ **shipped**, owner-confirmed live in both tools 2026-08-23 | 4.1 |
| [4.3](queue_notes/4.3.md) | M10 commitment dynamics | HAND | perception | M10.7 deferred by owner 2026-08-04 — do not build | 1.6 |
| [4.4](queue_notes/4.4.md) | Hand-open release trigger — ⭐ **one project with B5** | HAND | feature | designed, not built | 4.3 |

## Phase 5 — optional menu (nothing scheduled, nothing waits on it)

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [5.1](queue_notes/5.1.md) | M3b synergy subspace | HAND | perception | optional | 1.5 |
| [5.2](queue_notes/5.2.md) | M3 IK (26-DOF) | HAND | perception | optional | 5.1 |
| [5.3](queue_notes/5.3.md) | Trajectory gesture classification | HAND | perception | optional | 5.1 |
| [5.4](queue_notes/5.4.md) | Causal SmoothNet-class temporal refinement | HAND | perception | optional | 1.5–1.7 |
| [5.5](queue_notes/5.5.md) | Multi-hypothesis / uncertainty-aware prediction | HAND | perception | optional / research | 3.1 |

## Surfaced by measurement (N)

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [N1](queue_notes/N1.md) | Re-express frame-count parameters in ms | HAND | perception | queued | — |
| [N2](queue_notes/N2.md) | Pose-normalise the bone residual | HAND | perception | queued | 1.4 |
| [N3](queue_notes/N3.md) | Speed-threshold sweep | HAND | perception | ✅ closed 2026-08-03 | — |
| [N4](queue_notes/N4.md) | External capture drive is unreliable | CORE | infra | ⭐ **sleep half FIXED 2026-08-25** — it cost a real production acceptance take (recorded nothing). The retry now lives in `Resources/capture_drive.py` and **both recorders call it**; `wake_e_drive` delegates. Verified against the live fault. ⚠ The volume's `Full Repair Needed` flag is untouched | — |
| [N5](queue_notes/N5.md) | DR-1 track-level hand identity | HAND | perception | ✅ done, live-confirmed 2026-08-02 | — |
| [N6](queue_notes/N6.md) | Shared modules are imported, never copied | CORE | infra | ✅ resolved 2026-08-02 — now a binding rule | — |
| [N7](queue_notes/N7.md) | Drive `ASSUMED_FPS` from measured timing | HAND | perception | ✅ done 2026-08-04 (DR-1); ⚠ `palm_geometry` still to do | 0.1 |
| [N8](queue_notes/N8.md) | Cube stolen by occluding the holding hand | HAND | gameplay | ⚠⚠ **RE-OPENED AND WIDENED 2026-08-25** — `F1` removed rule 3, which had been suppressing part of it incidentally (measured: the rule refused **8.3%** of hand-frames where the hand held nothing). ⛔ Do **not** answer it with a facing gate; still routed to B5 + 4.4 | B5 |
| [N9](queue_notes/N9.md) | DR-1 duplicate-repair fires in normal use | HAND | perception | observed, **not diagnosed** — deliberately not tuned | 0.2b |
| [N10](queue_notes/N10.md) | Frame rate is environment-dependent (lighting) | CORE | infra | open — confirmed camera-bound by L1's measurement | — |
| [N11](queue_notes/N11.md) | Left/right asymmetry in sign-cue reliability | HAND | perception | ⛔ **not reproduced** — direction reversed on clean takes | — |
| [N12](queue_notes/N12.md) | Held cube jumps crossing the pitch plane | HAND | pipeline | observed live 2026-08-03, not fixed | 3.3 |
| [N13](queue_notes/N13.md) | No non-commercially-licensed dependencies | SEC | governance | ⛔ **BINDING** — owner decision 2026-08-04 | — |
| [N14](queue_notes/N14.md) | The corpus contains NO image data | CORE | infra | established by exhaustive scan 2026-08-04 | — |
| [N15](queue_notes/N15.md) | One take has no `raw_landmarks.jsonl` | CORE | infra | observed, not investigated | — |
| [N16](queue_notes/N16.md) | Two takes contained an unrequested second hand | CORE | infra | ✅ metadata corrected 2026-08-04 | — |
| [N17](queue_notes/N17.md) | `RecordTranslationPivotDebug.py` synthesises timestamps | CORE | infra | found 2026-08-04, not fixed | — |
| [N18](queue_notes/N18.md) | 2026-08-04 daylight corpus additions | CORE | infra | recorded | — |

## Unscheduled / not queued

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [U1](queue_notes/U1.md) | Open-palm / closed-fist detection | HAND | feature | **parked** — owner's priority call | — |
| [U2](queue_notes/U2.md) | Real 3D-file import (OBJ/glTF) | **3D** | feature | ⛔ postponed 2026-08-04 — blocked on the **platform decision**, not on effort | — |
| [U3](queue_notes/U3.md) | Web / mobile port | **PORT** | platform | deferred — `HandState` v2 is the contract it reinstates | — |
| [U4](queue_notes/U4.md) | Dangling §7.4 reference | CORE | docs | open | — |
| [U5](queue_notes/U5.md) | Extend D2's coast through hand-crossing occlusion | HAND | feature | ⭐ parked for later re-opening — owner decision 2026-08-22 | D2, D3 |
| [U6](queue_notes/U6.md) | Two pipelines are KEPT — divergence prevented mechanically | CORE | architecture | ✅ **decided 2026-08-22** — run `parity_replay.py`; do not re-propose collapsing them | — |
| [U7](queue_notes/U7.md) | Handedness label wrong 10.8% — chirality from geometry | HAND | perception | ✅✅✅ **CLOSED 2026-08-25** — the declared known-hand take finally ran: geometry **98.0%** vs the label **93.2%** (n=1127) | — |
| [U8](queue_notes/U8.md) | No snap on a **provisional** chirality | HAND | perception | ✅✅ shipped + accepted live 2026-08-22 (200 ms, elapsed-time gated) | U7 |
| [U9](queue_notes/U9.md) | Play area — an object may never reach the edge | HAND | feature | ✅ shipped 2026-08-23; superseded by 4.2's world-space volume | — |
| [U10](queue_notes/U10.md) | Camera privacy: policy + store disclosures (minors) | **SEC** | governance | open — before any store submission. Not a build | — |
| [U11](queue_notes/U11.md) | Shipping-build hygiene; hard-disable dev capture | **SEC** | shipping | open — at package time, not now | U10 |
| [U12](queue_notes/U12.md) | Start-of-game calibration (playability, FOV, camera tilt) | HAND | playability | open — build later. ⚠ **First tape measurements exist (2026-08-26) but do NOT carry**: the owner reports the distance was unreliable and the hand moved, so a "bias at depth Y" measures the drift as much as the estimator. ✅ Only "the estimator is in the right ballpark" survives — worth knowing, never checked before. ⛔ Adopt **no** correction. ⭐ What `U12` needs is a **HELD** distance (hand braced, a single 0° hold, no sweep), not a better tape | 4.2, U3 |
| [IS1](queue_notes/IS1.md) | Input system — the package boundary | **INPUT** | platform | ✅✅ **SHIPPED 2026-08-25** — owner ran both tools, clean | — |
| [IS2](queue_notes/IS2.md) | Input system — conformance as DATA | **INPUT** | platform | ✅✅ **SHIPPED 2026-08-25** | IS1 |
| [IS3](queue_notes/IS3.md) | Input system — the action layer, wired as an OBSERVER | **INPUT** | platform | ✅✅ **SHIPPED 2026-08-25** — owner ran both tools back to back, clean | IS1 |
| [IS4](queue_notes/IS4.md) | Input system — extract the **interaction** tier | **INPUT** | platform | ⭐⭐ **PREREQUISITE OF THE PORT** (2026-08-25) — no longer optional now that both hosts ship; do it in Python **before** any port | IS3 |
| [SEC1](queue_notes/SEC1.md) | Robustness + security audit of both tools | **SEC** | infra | ✅ done 2026-08-25 — 7 fixes shipped, 51-check suite | — |
| [SEC2](queue_notes/SEC2.md) | Pin the dependency **tree** | **SEC** | infra | ⭐ half done — environment now recorded; hash-pinning is packaging work | U10, U11 |
| [SEC3](queue_notes/SEC3.md) | Face detector runs every frame, nothing consumes it | **SEC** | privacy / perf | ⛔ **open — owner's call.** `--face off` exists, default deliberately not flipped | — |
| [SEC4](queue_notes/SEC4.md) | Debug recorder buffers a whole session in RAM | **SEC** | infra | open — deliberately deferred | — |
| [SEC5](queue_notes/SEC5.md) | Both tools feed MediaPipe a fake 33 ms clock | **SEC** | perception | open — ⚠ effect **unmeasured**; needs a live two-detector A/B, the corpus cannot settle it | — |
| [SEC6](queue_notes/SEC6.md) | ⭐ Third-party attribution notices at the **ship** boundary | **SEC** | governance | ⭐ **DRAFTED AND VERIFIED 2026-08-26** — `THIRD_PARTY_NOTICES.md` + `licenses/`; the 1€ copyright line (`Copyright 2023 Inria`) was fetched from upstream, **not** guessed. ⭐ `N13` cleared *may we use it*; **nothing cleared *what must travel with a binary***. ⛔ Closes only on a **built** artifact — the export path still does not copy the notices | U11 |

---

## Rows that belong to a future subsystem

Nothing is scheduled in `20_GAME_RULES`, `30_OBJECTS_3D` or `50_PORT_WEB_MOBILE`
beyond the rows above (`U2`, `U3`). When the game proper starts, add rows here
with the right `Sub` tag — **not** a second queue in that folder.
