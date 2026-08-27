# SESSION LOG — every "YOU ARE HERE", newest first

> **history · the narrative of how the project got here, 2026-08-03 → 2026-08-25**
> **SOURCE** · `PART_ONE.md` §3.1's YOU-ARE-HERE blocks — extracted verbatim, not edited

⭐ **This is where a session's story goes on the day it happens.** The current
status lives at the top of
[`../../00_CORE/QUEUE.md`](../../00_CORE/QUEUE.md); everything below the first
block here is superseded and marked so.

⚠ New entries go **above** the verbatim block below, never inside it.

---

## 2026-08-26 — the licence questions, and a distribution duty nobody was discharging

Two owner questions — *"is the 1euro filter license-free?"* and *"is the Unity
input system architecture prior art or is it patented?"* — and neither answer was
the interesting part.

⭐ **1€ filter: clear, twice over.** BSD-3-Clause on the reference implementation,
no known patent on the algorithm (published CHI 2012 by its authors, who
distribute the code themselves; any 2011–12 filing would expire ~2031). ⭐ And the
project already ships an **independent** implementation of the same filter without
having noticed: MediaPipe's `landmarks_smoothing_calculator` carries a
`OneEuroFilter` message, Apache-2.0, in the venv today. Google ships it
commercially at scale in the dependency this pipeline is built on.

⛔⛔ **THE FINDING IS DOWNSTREAM, AND IT IS `SEC6`.** `N13` is rigorous about
*may we use this* — it killed `0.5`, it chased the model bundle to Google's own
Model Card rather than accept a third-party assertion. Every one of those is an
**acquisition** question. But permissive licences also impose a **distribution**
duty, and the repo had **no `LICENSE`, no `THIRD_PARTY_NOTICES`, and attribution
living only in source docstrings**. ⭐ **That is compliant today and stops being
compliant at exactly the step the project is committed to taking**: BSD-3 clause 2
and Apache-2.0 §4(d) attach to *binary* redistribution, and the minifier erases
the docstring in the same pass that creates the obligation. `THIRD_PARTY_NOTICES.md`
+ `licenses/` now exist ([`SEC6`](../../00_CORE/queue_notes/SEC6.md)).

⚠⚠ **One line was deliberately left BLANK rather than guessed — and the blank is
why it is now RIGHT.** The 1€ upstream copyright holder could not be read without
network access, so it was marked pending instead of written from recollection: a
guessed copyright line in a notices file is `SEC5`'s failure mode with worse
consequences, because the file *looks* authoritative. ⭐ It was then **fetched and
filled the same day — `Copyright 2023 Inria`** — and the fetch turned up something
a guess would have buried: **the licence is at `casiez/OneEuroFilter/python/LICENSE`,
not the repo root, which 404s.** The path is now recorded so the next person does
not repeat the dead end.

⭐⭐ **Unity's input system is prior art several times over, and it is not
Unity's.** Semantic actions bound to physical controls is **DirectInput action
mapping (DirectX 8, 2000)**; the `Started`/`Performed`/`Canceled` machine is
**`UIGestureRecognizer` (iOS 3.2, 2010)**; callback-with-context is `EventArgs`
(2002) and DOM `Event` (1998); the closest living relative is **OpenXR's action
system (Khronos, 2019)**, royalty-free by Khronos IP policy. Unity's package
shipped ~2019, *after* most of it. ⚠ Its **code** is under the Unity Companion
License and was never copyable — but architecture is not copyrightable anyway
(**CJEU C-406/10, SAS v. WPL**, 2012), and `handinput/` was written from scratch.
⭐ The description became **"action-based input, in the style of OpenXR and Unity's
Input System"** (owner instruction; `DECISIONS.md`), which is both safer and more
accurate.

⛔ **The rename could only be applied in TWO files, and that is the doc
architecture working, not failing.** `handinput/README.md` and
[`../../40_INPUT_SYSTEM/INDEX.md`](../../40_INPUT_SYSTEM/INDEX.md) are live text.
Every other occurrence sits inside a `<!-- VERBATIM -->` block — `SPEC_17`,
`IS1`, `IS3`, and this log — or is the **owner's own quote** (*"mimicking the
input system of Unity"*), which is never rewritten. Each carries a dated pointer
to the new wording instead. ⭐ Nothing was rewritten to look tidier; the record
still says what it said, and now says where it was superseded.

---

## 2026-08-26 — `F1`'s mechanism is complete; the six ratio-table takes are recorded

**`F1` steps 1, 2, 4 and the sliders are BUILT** and committed (`05c316c`); the
three-window rig `f1_rig.bat` is ready. ⛔ **Live take still owed** — and until it
happens **both `F1` switches are OFF in the game** (`USE_TIP_BARYCENTER=False`,
`TRIM_GAIN=0.0`), so production is pre-`F1` and every change lives in the rig
where it can be compared. ⚠ Step 2 was briefly live in production while
unconfirmed; the owner's last production sign-off predates it.

⭐⭐ **The 1€ filter's golden vectors caught a real divergence from the paper on
their first run** — the speed term was built from the last FILTERED value where
the published algorithm uses the last RAW one. It converged and looked right,
which is what would have made it expensive to find in a JS or Swift port. ⚠ Had
the suite generated its expectations from the implementation, as golden vectors
usually are, all three failing checks would have passed.

⭐ **The trim's "not `PALM_AND_TIPS`" property is now a test, not a claim**: a
rigidly rotated hand produces **0.0000°** of trim across 20 poses.

⛔ **A divergence the slider wiring nearly introduced**: `TRIM gain %` first
started at 100, which would have made the single-arm debug tool run the trim while
production ran without it. ⚠ **`parity_replay` could not have caught it** — that
harness never creates a trackbar, so the bug would have lived only in the live
tool. Fixed by starting at production's 0 and having `--f1-rig` raise it.

⭐ **`parity_replay` now guards POSITION**, which it never did — it compared
ownership and palm facing but never where the object actually is. 0.0000 px over
3026 samples, so the tolerance is zero deliberately.

---

**AND THE SIX `T6` RATIO-TABLE TAKES ARE RECORDED** — 1680 frames, every one
on-axis, 3 depths × 2 axes, right hand declared.

⛔⛔ **CAVEAT ZERO, from the owner, and it governs everything else:** *"the
distance to the camera was not very reliable and the hand very likely moved
during the takes."* ⭐ **Fine for what the takes are FOR** — the ratio table
indexes **foreshortening ratios**, which are **scale-free**, so a wandering hand
does not touch them. ⛔ **Fatal to anything depth-derived**, and two claims built
on exactly that were made and retracted in one afternoon:

* *"take 6 is the anomaly"* — the shape reported for it did not exist; the 0°
  value had been read off a truncated console instead of the `meta.json` holding
  it. ⚠ **Do not read a number off a console when the file has it.**
* *"four of six peak at 180° and never return, which geometry forbids"* — ⛔ geometry
  permits it perfectly well **if the hand moved**, and a hand drifting away across
  a seven-pose sweep produces precisely a monotone climb. No estimator mystery.

⭐ **Both would have survived if caveat zero had been asked for first.** The
recurring lesson: *a trend measured along an axis the operator could not hold is a
measurement of the operator, not of the pipeline.*

**Two corrections to the METHOD did survive, and they are the durable output:**

1. **The grid is 30°**, not the protocol's 25.71°. The owner could not set 25.71°
   by feel, and the DECLARED angle is this table's ground truth — a table built on
   an angle the operator cannot hit is `U7`'s circularity in another costume. **A
   hittable grid beats a tidy one.**
2. ⛔ **The ratio the recording tool PRINTS is not the scale bias.** It uses the
   take median, and the depth estimate climbs through every sweep. Use the 0° hold
   — already stored per position, so nothing needs re-recording.

⭐ **And one measurement finding that is scale-free, so caveat zero cannot touch
it**: `edge_on_measure` is **BLIND TO PITCH** — 0.13–0.28 at yaw-90° but
**0.94–1.00** at pitch-90°. Not a defect: it measures the knuckle-row squareness
that governs the palm/back SIGN, and pitch does not foreshorten the knuckle row,
so `DR-2` correctly stays silent. ⚠ But the `Rsq`/`Lsq` HUD aid therefore **cannot
judge a pitch take**, and every pitch take in this corpus was held without a
working squareness readout — worth holding next to the still-unexplained 3× axis
error on `t5i`'s second pitch take.

⚠ **`U12` gets a tape measurement for the first time but not a usable one.** Only
*"the estimator is in the right ballpark"* survives — genuinely new, never checked
before. What `U12` actually needs is a **HELD** distance: the hand braced against
something, a single 0° hold, no sweep. Rotation is what invites the arm to drift.

⚠ Two tool bugs fixed on the way, both the same shape — **a symbol in console
output on a cp1252 terminal**. `--help` died outright in `LiveSnapDebug`, and
`RecordRatioCalibration` crashed **after writing a take but before printing "wrote
N frames"**, so a complete recording looked like a failure. ⛔ The second was
dormant for takes 1–2 and armed for the other four, because that print only runs
when a depth is declared. `| tail` reported exit code 0 over the traceback.

---

## 2026-08-25 (night) — `F1` is specified, Step 0 is measured, rule 3 is gone

**The owner specified `F1`** in eight points (fingertip barycentre drives the
transform; grab on barycentre proximity; tip plane drives the quaternion with the
palm supporting; release unchanged; ⭐ **the back-of-hand snap restriction
removed**; a jitter slider; and — stated mid-specification — **τ = 20 ms is not to
be disturbed**). Design, acceptance bar and build order:
[`../spec/F1_FINGERTIP_TRANSFORM_SPEC.md`](../spec/F1_FINGERTIP_TRANSFORM_SPEC.md).

⭐⭐ **The architecture is a palm-frame DEFORMATION feeding a bounded trim** —
`ΔR = R_palm·R_trim·R_palm(grab)⁻¹`, tips expressed in the palm frame so whole-hand
rotation cannot enter the tip channel **by construction**, and **gain 0 must be
bit-identical to shipped Horn**. That is the A10-dead rigid arm respected rather
than avoided.

⭐⭐ **The coplanarity question came back with its premise inverted.** Coplanar
tips+palm is the **safe, redundant** case and needs no handling — `R_trim → I` and
today's behaviour is reached automatically. The dangerous geometry is
**COLLINEARITY**, a different condition, and the remedy is the house rule:
suppress, do not guess. ⛔ The owner's *"assume z from palm width rotated 90°"* is
routed to `T6`'s ratio table, not built here — it is the `acos` fold plus "a
threshold must not be computed from a quantity that is noisy where the threshold
acts".

⛔⛔ **A PATENT changed which arm to build.** `US9696795B2` (contacts → object
rotation, filed 2015, term ~2035) was **reassigned 2026-01-16 from Ultraleap to a
holding entity**. The contact-point arm is dropped; the chosen design reads on
Horn 1987 / Kabsch 1976.

⭐⭐⭐ **STEP 0 MEASURED** (`analysis/f1_tip_census.py`, 123 takes) — and it pushes
back on two of the owner's four points:

1. ✅ **Tip noise floor is 1.5 mm**, held only **5–10%** worse than free. The
   feared held-state collapse did not happen; the design survives.
   ⚠⚠ **The raw number said 21–31 mm and was nearly reported.** Splitting on
   frames where the palm itself barely moved shows almost all of that is the
   operator moving — a factor of ~15. State which one you mean.
2. ⛔ **The rigid tip residual swings 75–95° inside half a second**, and the
   short-horizon column barely differs from the long one, so it is neither drift
   nor noise: it is **the rigid model being wrong**. The clamp must sit far below
   the data's own spread.
3. ⛔ **The plain barycentre drifts 1 cm median / 6 cm p95** with the palm still.
   `g_pos = 1` — the specification taken literally — needs a clamp.
4. ✅ Collinearity is rare; a 0.20 floor costs **1.89%** of frames.

⛔ **And the recorder carries no per-landmark confidence**, so question 1 had to
become "what did the tips do", not "what did the model claim".

✅✅ **STEP 3 SHIPPED AND LIVE-CONFIRMED** — rule 3's back-of-hand snap block is
removed from both tools, `handinput`, the recorder schema, the conformance traces,
both record tools and the parity harness. Owner ran both: *"debug working fine"*,
*"production working fine"*. Debug is **measured**: **9 of 15 snaps back-of-hand**,
15 releases, nothing stranded.

⚠ **Three things this removal exposed, all worth keeping:**
* **Rule 3 had exactly one test** — the scripted conformance trace. 26 suites
  passed *before* the removal was finished, which proves only that they never
  covered it. The trace's rule-3 steps are kept and **inverted** as the guard.
* **Two latent breaks**: `parity_replay` compared the deleted state, and
  `verify_state_follows_hand` drove it — and that suite is **skipped while
  `TRACK_OWNERSHIP=False`**, so it passed while broken and would only have failed
  whenever `4.1` is retried.
* ⛔ **The production take recorded nothing** (`N4`: the drive slept; production's
  recorder disables itself on first failure instead of retrying). Production's
  evidence is the live verdict plus `parity_replay`, **not numbers of its own**.

⚠ **`N8` is re-opened and widened** — rule 3 had been suppressing part of it
incidentally (it refused **8.3%** of free-hand frames). ⛔ Not to be answered with
a facing gate; still routed to `B5` + `4.4`.

---

## 2026-08-27 (late) — the ratio table dies, a regression replaces it, and the owner's architecture is validated

⭐⭐⭐ **`T6` STOPPED BEING A TABLE.** The owner's bijectivity question is what
killed it: `Rwl` measures compression along ONE fixed direction, so under combined
rotation it carries `cos(yaw)/cos(pitch)` — one number, two unknowns. ⛔ That is a
**lossy projection**, not a weak ratio, and no pair of fixed lengths recovers what
it discards. It explains §4.1's cross-talk of ~1.0 and §4.3's dead yaw transfer at
a stroke.

⭐ **The replacement is fitted, not derived** — the owner's second correction:
*"start from regression from the data directly."* Every closed form tried omitted
something real (thickness, the knuckle bow, perspective) and the data refused it. A
regression absorbs all of them because they are present in the frames it is fitted
to. Slant/tilt from the trimmed affine SVD, **beating Horn on both axes: yaw 8.7°
vs 11.5°, pitch 17.6° vs 30.7°** — and bijective by construction.

⭐⭐ **AND THE OWNER'S ARCHITECTURE IS VALIDATED**: freeze a matrix at grab,
compose, invert, subtract. It works for a reason that was not obvious — **the
cube's rotation is already grab-relative, so the absolute error at grab cancels.**
⛔ The composition must be MULTIPLICATIVE (`σ_abs = σ_rel × σ₀`); done additively it
scores 20.3° on yaw, worse than Horn. The composition IS the trick.

⛔⛔ **FOUR THINGS I GOT WRONG AND THE OWNER CAUGHT OR THE DATA DID:**

1. **"There is no reason it should lose on the back half"** — right. The cause was
   my own data partition: splitting exclusively at 90° left the back branch with
   three angles, so a hold-out had to EXTRAPOLATE and clamped at exactly 30.0°. I
   had blamed `T1` (back-of-hand quality) from plausibility. Sharing the 90° knot
   fixed it: yaw 12.3° → 8.7°.
2. **Leave-one-DEPTH-out scored 1.2° and was meaningless** — the 30° grid means the
   held-out angle is present at the other depths, so a monotone fit BINS to it.
   Caught before reporting. Only holding out the ANGLE asks it to interpolate.
3. **The exact-C1 cubic mend was rejected by measurement** — it fixed the
   extrapolation but cost the front half badly (yaw 60°: 1.7° → 6.4°). Two
   parameters per branch cannot follow the real curve. ⭐ Flexibility was doing more
   work than smoothness.
4. **The "pitch collapse" was retracted** — the established z-free ground truth
   under-reports pitch too, so the DECLARATION is the outlier, and §4.3's pitch
   verdict went with it. The takes cannot ground-truth the 30–60° band at all.

⭐⭐ **THE FINDING THAT OUTLIVES THE ROW: the landmark set matters more than the
model.** No-thumb + 25% trim halves the cross-take feature spread against the
palm-5 that every earlier attempt used (0.067 vs 0.162). ⛔ **But it does not
survive a gripping hand** — under grip the finger feature jitters 0.013–0.458 per
frame against palm-5's 0.004–0.070. So palm-only for orientation, fingers as their
own channel, which is the split the owner proposed independently.

⚠ **One assumption is still smuggled in**: the multiplicative composition
re-imports the orthographic `cos` model the regression exists to avoid. The
empirical fix — a 2-D fit on hold PAIRS — is next and needs no new take.

---

## 2026-08-27 — `F1` ships, the trim is removed, and parity takes six fixes

✅✅ **`F1` SHIPPED**: the object is carried by the **fingertip barycentre**,
settles onto it with a walk that only advances while the hand moves and never
out-runs it, has its depth **anchored to the hand at every grab**, and is picked up
only inside the object's **projected footprint**. Settled live over two evenings.

⛔⛔ **THE ROTATION TRIM WAS REMOVED, AND THAT IS THE RESULT WORTH REMEMBERING.**
`§10.1` — a metric the project did not have, built this session with its own
recorder — measured the trim **non-monotonic in the declared finger angle at every
gain and clamp**: 15.71° / 12.56° / 20.29° for a declared 10 / 20 / 40. At 20° of
finger rotation it moved the object LESS than at 10°. The clamp had been masking
that by pinning every answer to exactly 10.00°.

⚠ **It retracts the rig's headline.** The 21.2°-vs-32.9° lean improvement was a
constant 10° offset that happened to sit in a helpful direction — not the fingers
steering the cube. ⛔ A lower number is not a better answer when the thing producing
it cannot be aimed. ⭐ Step 0's `M2` had already named the cause a day earlier: the
rigid fit over five non-rigid points *tumbles*.

⚠⚠ **The owner asked for the trim removed TWICE and was refused both times**, on
the grounds that it would discard a measured improvement. The improvement was real
and was not what it appeared to be. ⭐ The metric they asked for is what settled it
— which is the entire argument for building §10.1 rather than shipping on feel.

✅ **`A10` reproduces exactly** — yaw 14.5°/1.13 · pitch 5.5°/0.74 · roll 6.7°/1.02
· **jitter p95 25.41°**. With the trim at gain 0 the rotation channel is
byte-for-byte the shipped pipeline; measured anyway rather than argued. ⛔ Its
harness had been crashing partway through the sweep on an aborted take, so the
takes after it had never been measured and nothing flagged the half-run.

✅ **`parity_replay` NO DIVERGENCE on four takes, after SIX fixes.**
⭐⭐ **The reusable finding: every per-hand estimator must die with its track.**
Three were missing that reset in the debug tool — absolute depth (reset a frame too
early instead), the tip trim (invisible until the gain went to 1.0), and the
relative depth baseline, which carried a **6% depth error** into the next grab and
moved the object through the play-area clamp.
⛔ The other three were HARNESS asymmetries, all the same rule that file had
already recorded as having bitten four times: it never compared **orientation**,
never passed **`rotation=`**, and never set **`slerp_mode`/`slerp_tau_ms`** (so it
compared τ = 20 ms against the legacy 149 ms default).

⭐ Two instruments were corrected only AFTER doing their job: the port-contract
guard that refused a `now_ms` argument (the fix was a caller-supplied `dt`, not a
weaker guard), and the orientation comparison, which now tests exact component
equality because `2·acos(dot)` is singular at dot = 1.

⭐ **`hand_state.frame_dt_ms`** lands as a shared, clamped frame interval — the
owner expects to need `dt` elsewhere, and the estimator layer may not read a clock.
It replaces a per-frame depth rate limit whose real meaning moved with the room's
brightness: the `L1` defect, second occurrence.

⭐ **Next: `T6` §4.3, the transfer test** — the protocol's own deciding test.

---

## 2026-08-25 (late) — the platform decision is shaped, and the Model Card lands

**Owner decisions**: ship **both** browser and native · the platform decision is
sequenced **right after `F1`** · **Unity stays out**, re-affirmed rather than
inherited (*"if ever we will move to Unity, we will do another project to port it
to C#"*). Architecture and the agreed six-step sequence:
[`../../50_PORT_WEB_MOBILE/INDEX.md`](../../50_PORT_WEB_MOBILE/INDEX.md).

⭐⭐ **The cost of "both" is not double, and the reason is structural**: the
platform-specific part is the landmark **SOURCE**, not the core. One TypeScript
core serves browser *and* native; only a thin per-platform module over
MediaPipe's first-party SDK differs. `handinput/sources/` was already that seam.
⛔ Consequence: **`IS4` is promoted from optional to a prerequisite of the port** —
with two hosts, an interaction tier outside the core means every host
reimplements snap, arbitration and ownership.

⭐⭐⭐ **AND THE MODEL CARD ARRIVED, which is the substantive event of the night.**
The owner supplied it as `.docx`; it is archived and transcribed under
`60_SECURITY_COMPLIANCE/evidence/`. Four findings, in order of how much they
change what we do:

1. ⛔⛔ **FINGERTIPS ARE THE MODEL'S WORST LANDMARKS, by Google's own evaluation** —
   *"per-joint MNAE is the smallest at the base of each finger, and gets larger
   toward the fingertip… prediction is easier around the palm which is more rigid
   than the fingers."* **`F1` proposes driving the whole transform from exactly
   those landmarks.** It does not kill the row; it reframes it — tips are noisy
   *measurements*, not truth. A second, independent reason not to build a rigid
   fit over palm+tips.
2. ⭐⭐ **THE WORLD-Z DIAGNOSIS IS CORROBORATED AT SOURCE** — *"metric x, y, z…
   provided using **synthetic data**, obtained via the GHUM model fitted to 2D
   point projections"*, and Google evaluates **only 2D** because of it. **The
   depth channel the yaw lean rides on has never been accuracy-tested by its
   authors.** Months of measurement here reached the same conclusion.
3. ⛔ **THE GAME'S CORE ACTION IS LISTED OUT OF SCOPE** — *"Not appropriate for…
   occlusions. For example **when the hand is holding objects**."* Not a reason
   to stop; it is the honest ceiling under `T1`/`T2`/`N12`.
4. ⚠ **Mobile is untested by the model's authors** — *"not tested in
   'in-the-wild' smartphone camera conditions, including low-end devices, low
   light, motion blur"*. A port risk with a cheap mitigation: `analysis/` runs on
   any JSONL take, so a phone take can be scored on day one.

✅ And the licence gap closes: *"LICENSED UNDER — Apache License, Version 2.0."*
The whole dependency set now clears `N13`.

---

## 2026-08-25 (night) — ✅ U7 IS CLOSED: the declared known-hand take finally ran

**The last open item on U7 was never a code change — it was a measurement.** The
fix shipped 2026-08-22 and was behaviourally confirmed, but the *specified*
acceptance test had never validly run: the 08-23 attempt used both hands, so its
declaration was retracted in its own `meta.json`.

**Take**: `2026-08-25_171814_known_right_reentry_acceptance` — physical **RIGHT
hand only, declared before the first frame**, 1925 frames / 1127 single-hand,
18.2 fps, repeated full re-entries, both facings. Re-entries are the point: the
label is worst at track age 0.

| | MediaPipe label | geometry |
|---|---:|---:|
| this take (n=1127) | 93.2% | **98.0%** |
| corpus, valid declarations only (n=3682) | 97.1% | **99.2%** |
| inside the DR-2 edge-on band (n=20) | 80.0% | **85.0%** |

⭐ **The declaration is corroborated rather than trusted.** The retracted take
dropped **540** multi-hand frames (64% of its hand frames); this one dropped
**8** (0.7%). Two hands versus one, readable straight off the coverage line.

⭐ **And those 8 are not a second hand.** The two detections sit **0.10–1.00 palm
widths apart** — on top of each other. MediaPipe duplicate-detected one hand and
gave it both labels: fresh live evidence for `N9` / §0.4, on a take where the
physical truth is known.

⛔⛔ **AN INSTRUMENT DEFECT, FOUND WHILE USING IT — the reusable part of the
night.** `u7_geometric_chirality.py` discovers sessions by matching `known_` in
the name, and `declared()` fell through to that name whenever `meta.known_hand`
was absent. The retracted take is called `u7_acceptance_known_right`, which
**contains `known_right`** — so a take whose ground truth is recorded as **false**
was scored as if it were true, and its 302 frames sat inside every corpus figure
this row has ever quoted. Fixed; the numbers moved 95.5%/98.8% → **97.1%/99.2%**.
⚠ **An instrument that cannot honour its own retraction is the B4 problem wearing
a new costume** — the anchor and the metric agreeing because both are wrong.

---

## 2026-08-25 (late) — ✅✅ THE INPUT SYSTEM IS SHIPPED, and the app root is tidy

**Second live pass, both tools back to back, after the folder tidy-up.** Debug
clean; production clean — server accepted the client, hands tracked at 15–23 fps,
identity locked on both hands, four track-ends re-decided normally, socket closed
cleanly at both ends, no errors in either log. Owner: *"ship current build"*.

⭐ **`IS1`–`IS3` move BUILT → SHIPPED.** The live look they had been waiting on
since the morning is done. The package (`handinput/`) observes and drives
nothing, so this was always a low-risk ship; what it buys is that the hand
pipeline can now be lifted into another game, a port or a lens behind a stable
action/phase/callback surface. Record: `40_INPUT_SYSTEM/`.

⚠ **What the SHIPPED claim rests on**, so it is not read as more than it is: two
clean live sessions plus the owner's instruction, on top of 26/26 golden vector
suites, 96 handinput checks, 51 hardening checks and `parity_replay` clean. **No
harness can see the HUD** — if the green `handinput …` line misbehaved on screen,
that status is the first thing to revert.

⭐⭐ **THE APP ROOT WENT FROM 35 FILES TO 9**, in three categories: `tools/`
(recording, troubleshooting, verification — live and runnable), `_archive/`
(the pinch era; B7/B8's prediction gate; six stale local recordings), and the top
level, which now holds **only what debug and production actually run**.

⚠ **Reachability was traced from the four real process roots**, not guessed —
`PythonApp_Main`, the launcher, `Client`, `VisionPipeline`, plus `LiveSnapDebug`.
That caught two things a naive sweep would have broken: `analysis/verify_edge_on.py`
imports `AnalyzePerceptionSequences` (the single definition of `edge_on`), and
`analysis/b7_live_ab.py` imports `LiveBlockPredictionDebug`. Both were given the
new path — **a harness that cannot be re-run is an assertion, not a finding**, and
that applies to the archived directions too.

⭐ Everything moved stays runnable: each `.py` that resolved paths from `__file__`
now anchors on `_APP_ROOT` one level up, and each `.bat` `cd`s back to the app
root. The real proof was `tools/VerifyChiralityFixture.py` — it resolves
`Resources/` through the new anchor and still reports ALL CHECKS PASSED.

---

## 2026-08-25 (evening) — the live look, and one regression it caught

**Both tools were run back to back.** Production ran a full clean session: server
accepted the client, 22–33 fps, identity locked on both hands, one `Left→Right`
switch confirmed after 12 frames, and — worth keeping — **a transient identity
glitch REJECTED after 7 confident mismatched frames with the lock held.** DR-1
doing exactly what it was built to do. Clean shutdown at both ends.

⛔⛔ **THE OWNER FOUND A REGRESSION NO HARNESS COULD HAVE FOUND: the debug tool
had lost its white contour highlight on a HELD object.**

* **Cause**: `febd3fa` ("debugged done") stripped T6d's anisotropic A/B rig out
  of `LiveSnapDebug.py` — 756 lines. The snap-highlight loop sat **directly
  under** the ghost-wireframe block that commit was deleting and **went with it
  as collateral**. Only the ghost was meant to go.
* **Two tells were left in the file for two days**: `_draw_cubes()`'s own
  docstring still described *"a bright snap-highlight outline … for whichever
  cube(s) are held"*, and `SNAP_BORDER_COLOR` / `SNAP_BORDER_WIDTH` were defined
  but **never read**.
* **Production was never affected** — `CubeWindow.py` kept its equivalent
  (`edge_color` / `edge_width`). So the two tools had silently diverged on what a
  held object **looks like**.
* **Fixed** by restoring the five-line loop verbatim; owner confirmed live,
  *"outline came back"*.

⭐⭐ **THE LESSON, AND IT IS A GAP IN `U6` RATHER THAN A FAILURE OF IT.**
`parity_replay` reported **NO DIVERGENCE** throughout and was **right to** — it
compares **gesture logic**, not drawing. Every automated check was green while a
visible difference between the two tools persisted: 26/26 suites, 96 handinput
checks, 51 hardening checks, parity clean. **Renderer parity is unguarded**, and
nothing in the project currently would have caught this. It took a person
looking at the screen.

⚠ This is the *inverse* of the session that produced the recording rework: there,
four harnesses were **wrong** about takes the owner had watched fail. Here the
harness was **right and simply not pointed at this**. Both land in the same
place — **a live look is what closes a change.**

⚠ Still owed from this session: the owner's verdict on the **input system**
(`IS1`–`IS3`) — the green `handinput` HUD line with `RDY`/`ROT`. Until that,
they stay **BUILT, not SHIPPED**.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 277-1140
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
### ⭐⭐⭐ YOU ARE HERE (2026-08-25, LATEST) — **INPUT SYSTEM BUILT (`IS1`–`IS3`) + A ROBUSTNESS/SECURITY AUDIT SHIPPED (`SEC1`). THE NEXT BUILD IS STILL `F1`.**

⭐⭐ **THE AUDIT'S HEADLINE IS THE CLEAN HALF, and it is the compliance evidence,
not a formality**: **no network egress anywhere in the pipeline** (not one HTTP
call — *"nothing leaves the device"* is verifiable **by absence**), no `eval` /
`exec` / `pickle` / `shell=True` / `yaml.load`, both `subprocess.Popen` calls in
list form, models loaded by absolute path, and the socket already on loopback.
Full account: `GESTURE_PIPELINE_SPEC.md` **§18**. Suite:
**`analysis/verify_hardening.py`, 51 checks**.

**Seven fixes shipped, each mirrored into BOTH tools where both have the code:**
off-loopback now **refused** unless `--allow-remote` is passed deliberately (S1);
session tags **sanitised** so a name cannot escape the capture root, in one shared
module (S2); the `meta` resolution **clamped** and every wire value **type-checked**
before it reaches arithmetic (S3); the receive buffer **capped** and decoded per
packet rather than per chunk (R1/R2); ⭐ **a single failed camera read no longer
ends the session in either tool** (R3 — it used to cost a whole `--record` take);
a clear message when the port is already held by a stray (R4); and the
permanently-red `verify_planar_pnp.py` fixed — **all 26 suites now pass, for the
first time** (R5).

⛔ **Four things were found and deliberately NOT fixed**, each with a queue row so
it is a decision rather than an omission — read the rows, not this summary:

* **`SEC3`** — the face detector runs every frame and **nothing consumes it**
  (`elif datatype == "face": pass`), and the debug tool has none at all, so it is
  a divergence AND a disclosure question for a youth audience. `--face off` was
  added; **the default was deliberately not flipped**, because turning it off is
  visible in the preview and that is the owner's call.
* **`SEC2`** — ⭐ **half done since 2026-08-25.** Measuring it corrected the row's
  own framing: the risk is not an attack, it is **reproducibility of the rig** —
  24 of 26 packages float and had **already drifted past what mediapipe 0.10.14
  was built against** (numpy 2.4.6, OpenCV 5.0), so the environment the corpus's
  numbers came from was unrecorded. `requirements.lock.txt` now records it. Hash
  pinning and the **licence inventory N13 requires** are packaging work (U10/U11).
* **`SEC5`** — both tools feed MediaPipe a fake 33 ms clock. ⛔⛔ **The first
  write-up asserted a mechanism it had not measured and was RETRACTED the same
  day** (§18.4): the clock is wrong, the effect on the output is **unmeasured and
  may be nil**. ⚠ The corpus cannot settle it — **no image data, nothing to
  replay** — but two detectors on the same frames can, with no pixels stored.
* **`SEC4`** — the debug recorder buffers a whole session in RAM where production
  streams; not restructured on the eve of an unvalidated live take.

⚠⚠ **`SEC5` carries the audit's own lesson and it is worth more than the finding:
a mechanism that sounded right was written down as a fact for one day. An audit is
not exempt from A10 just because its other findings are code-shaped.**

⚠ `parity_replay` reports **NO DIVERGENCE** after the mirrored edits — which is
what says the two tools did not drift apart while being corrected.

---

### ⚠ Superseded: YOU ARE HERE (2026-08-25) — **THE INPUT SYSTEM IS BUILT (`IS1`/`IS2`/`IS3`). THE NEXT BUILD IS STILL `F1`: THE CUBE'S TRANSFORM FROM THE FINGERTIPS.**

> **Owner, 2026-08-24:** *"I want to be able to later ship independently this hand
> detection system as an input system (for my game, or for any other purpose such as
> a filter on Snapchat for example) ... mimicking the input system of Unity."*
> And: *"No need for TypeScript for the moment, no need for C# for the moment."*

⭐⭐ **WHAT LANDED, AND WHY IT COULD LAND WITHOUT RISK.**
`Local_pc/Movement_with_hand_detection/handinput/` — five **actions**, Unity's five
**phases**, `+=` **callbacks with a context**, a **polling** API, and `HandState` v2
as the wire contract. ⚠⚠ **IT OBSERVES AND DRIVES NOTHING**: every value it
publishes was produced by the gesture logic that already ran that frame, so no cube
is snapped, moved or released by it and the change **cannot** alter behaviour.
Package: `handinput/README.md`. Record: `GESTURE_PIPELINE_SPEC.md` **§17**.

| evidence | result |
|---|---|
| new suite `analysis/verify_handinput.py` | **95 checks pass** |
| the 24 existing `verify_*` suites | pass |
| `parity_replay` on `2026-08-24_220415_prod_tau20` | **NO DIVERGENCE**, 454 frames |
| a real recording replayed through the input system | 454 frames → **785 events** |
| `export_package.py` → run standalone, no repo on the path | **works**; 9 modules, 4 416 lines |

⛔⛔ **NOT CLOSED: THE OWNER'S LIVE LOOK IN BOTH TOOLS.** Deferred by the owner to
the evening of 2026-08-25 (*"I will run the debug and production this evening"*).
⚠ **Automated green is necessary and not sufficient** — §13.6.1 shipped inverted
while passing an "end-to-end confirmed" claim. **Until that take happens, treat
`IS1`–`IS3` as BUILT, not SHIPPED.** What to look for: the debug HUD's green
`handinput …` line (per hand: the `tracked` phase, `RDY` when `grab_ready` is
performing, `ROT` when a rotation reference is frozen), and that everything else
behaves exactly as it did last night.

⚠ One pre-existing failure found while running everything, and it is **not** from
this work: `analysis/verify_planar_pnp.py` prints `ALL GOLDEN VECTORS PASS` and
then dies on a **console encoding error** writing a `⚠` character (cp1252). It
fails identically with the change reverted. Left alone deliberately — fixing an
unrelated file inside this change would have muddied the parity evidence.

⭐⭐⭐ **THE NEXT BUILD IS UNCHANGED: `F1`.** The input system is orthogonal to it —
it publishes what the pipeline produces, so a better transform underneath simply
makes the same actions better. Read `F1`'s row, and its one trap (a rigid-body fit
over palm+tips is A10-dead twice).

---

### ⚠ Superseded: YOU ARE HERE (2026-08-24) — **T6 IS CLOSED, THE LAG IS FIXED AND SHIPPED, AND THE NEXT BUILD IS `F1`: THE CUBE'S TRANSFORM FROM THE FINGERTIPS.**

> **Owner, after four live T6d sessions and a lag hunt:**
> 1. *"the anisotropic fit bring very minor improvement and I don't want to ship it."*
> 2. *"the grab and rotations with the anchor to the palm and limited knuckles arc as
>    it is currently designed is too coarse: it does not render subtle movements of
>    the fingertips ... I want to keep it, but as an indication (for orientation, for
>    sign, for chirality, etc.) in support to the fingertips."*
> 3. *"there is a slerp introduced somewhere ... the cube is lagging the hand and
>    this feels very uncomfortable."*
> 4. **NEXT BUILD, to be specified in its own conversation:** *"control the transform
>    (Vector3 position and rotation quaternion) of the cube from the fingertips."*

⛔⛔ **1. THE WHOLE T6 LINE IS CLOSED — REJECTED, NOT PAUSED.** Five arms were built
and all five failed A10 or the owner's feel test: planar PnP, the 6-point thumb
model, the world-z gate, the trustworthy-halves rebuild, and T6d's anisotropic 2×2.
⭐ **NOTHING HAD TO BE REVERTED, and that is the process win worth keeping**: every
arm lived in `palm_rotation.estimators()` and the debug tool behind a toggle that was
**measured byte-identical to shipped Horn** (975/975 and 1084/1084 replayed frames),
so production never ran a line of it. **A rejected experiment cost one flag flip, not
a revert.** ⭐ The DIAGNOSIS stays on the record and is still the best account of the
defect (`HANDOFF_T6_ORIENTATION_FROM_2D.md` §2.0–§2.0.16): MediaPipe reports a
physically face-on palm as **24.9° tilted**, its world x,y are faithful, only z is
fabricated, and it gets the tilt BEARING right while the MAGNITUDE is wrong.
⚠ **It is SUPERSEDED, not merely rejected** — decision 2 changes what the estimator
is being asked to do.

✅✅ **2. THE LAG IS FIXED AND SHIPPED TO PRODUCTION.** Full account: **§14.3.6**.
In one line: **one constant, found by measurement, and the filter above it was dead.**

| what | before | after |
|---|---|---|
| rotation smoothing | fixed **0.35 per FRAME** | **τ = 20 ms**, `1 − exp(−dt/τ)` |
| settling at 48 ms/frame | 111 ms | **20 ms** |
| settling at 64 ms/frame | 149 ms | **20 ms** |
| predictive orientation filter | ran every frame | **removed** (dead: Horn replaced it on **9091/9091** frames) |

⭐⭐⭐ **3. THE NEXT BUILD IS `F1` — THE CUBE'S TRANSFORM (POSITION *AND* ROTATION)
FROM THE FINGERTIPS.** To be specified by the owner in its own conversation. Read
`F1`'s row before starting; the one thing that must not be re-tried is a rigid-body
fit over palm+tips, which is A10-dead twice over for a reason that is now the whole
point of the new design.

---

### ⚠ Superseded: YOU ARE HERE (2026-08-24) — **T6d IS BUILT. THE NEXT STEP IS A LIVE SESSION, NOT CODE.**

> **Owner:** *"The immediate next build will be a debug run which implements this
> anisotropic fit, so I can feel the behaviour during run time. In this debug run,
> add sliders to modify the anisotropic fit parameters, so I can modify them during
> runtime and feel the resulting changes in behaviour."*

✅ **BUILT 2026-08-24.** `debug_snap.bat` now opens a second window with the four
sliders and the toggle; `t` toggles the rebuild, `0/1/2` load identity / the fitted
yaw / the fitted pitch parameters. ⭐ **The toggle starts OFF and OFF is MEASURED to
be the shipped estimator** — byte-identical cube orientations on 975/975 replayed
frames, 953/975 differing once it is on, so `t` is a true one-variable A/B.
⭐⭐ **RUN IT WITH `--record`.** The session is not only a feel test: it is the
measurement the corpus lacks. Every frame now stores its own `ratio`, `ψ`, gain and
applied tilt **and the parameters in force**, and `meta.json` logs every slider move
with its frame — so the take can be cut into per-setting segments. **What is needed
from it is TIME SPENT AT INTERMEDIATE ψ** (turn *and* tip together, slowly): the yaw
takes sit at ψ≈0/180 and the pitch takes at ψ≈90, which is precisely why `b` and `c`
are unconstrained today.
⚠ Changing a parameter while a cube is HELD gives the cube a one-off offset (the grab
reference was frozen under the old values) — the HUD says so; release and re-grab.

⭐⭐ **READ `HANDOFF_T6_ORIENTATION_FROM_2D.md` — its top block is how to run it, and
§2.0.17 records what was built and the four decisions inside it** (including one that
would silently break a port: ψ must come from the principal-axis closed form, since
the textbook eigenvector row collapses to noise at exactly pure yaw and pure pitch).
Then §2.0.16 for the fit, §2.0.9/§2.0.12 for why it is shaped that way.

**WHERE T6 ACTUALLY GOT TO.** Four estimator replacements were built and all four
were A10-rejected (planar PnP, PnP+thumb, the z gate, the normal rebuild) — but the
rejections mapped the problem precisely, and the fifth approach works:

| finding | number |
|---|---|
| ⭐⭐ **ROOT CAUSE**: MediaPipe reports a physically FACE-ON palm as tilted | **24.9° median**, 61 sessions, 3131 pixel-verified frames |
| ⭐ its world **x,y are FAITHFUL**; only z is fabricated | 1.1° vs the pixels' 1.2° |
| ⭐ it gets the tilt **BEARING right** — only the MAGNITUDE is wrong | 10.6° median vs 45° for chance |
| ⭐⭐ the bias is a **repeatable function of pose WITHIN a recording** | between/within ratio **5.17** |
| ⛔ but its map is **per-session** and does not transfer | shape disagreement 13.4° vs 14–22° amplitude |
| ⭐⭐⭐ **yaw-like and pitch-like tilt need DIFFERENT gains** | **1.15** vs **1.55** |

⭐⭐⭐ **THE ANISOTROPIC 2×2 FIT IS THE RESULT THAT SURVIVED.** Because yaw compresses
the palm's WIDTH and pitch its LENGTH — perpendicular directions — a gain that depends
on the compression direction ψ can treat them oppositely where no scalar can:
`g(ψ) = a + b·cos2ψ + c·sin2ψ`, which IS a symmetric 2×2 evaluated on that direction.
Fitted per recording against camera-independent objectives: **PITCH drift 76.4° →
23.6°** and scatter 44.4° → 21.2°; **YAW scatter 9.5° → 7.4°**, gain 0.82 → 0.95.
⛔ **Open**: each take exercises only its own ψ, so `b`/`c` are unconstrained — which
is exactly what the slider run is for.

⚠ **Production is UNTOUCHED throughout.** Everything lives in `estimators()`; both
golden-vector suites pass.

---

### ⚠ Superseded: YOU ARE HERE (2026-08-23) — **NEXT BUILD IS T6, AND THE OWNER WANTS IT BEFORE ANYTHING ELSE.**

> **Owner:** *"I want to implement the fix before anything else is built."*
> And on the defect: *"this is a show-stopper for me as I can't tolerate a cube
> which rotates differently than what it should to reflect the physical world."*

⭐⭐ **READ `HANDOFF_T6_ORIENTATION_FROM_2D.md` — it is a COMPLETE brief written so a
fresh session can start implementing immediately.** Then T6's row below, then
`GESTURE_PIPELINE_SPEC.md` §14.3.4.7 → §14.3.4.11.

**THE DEFECT**: when the hand turns like a page, the object does not turn purely
about the vertical — **it LEANS, up to ~27° at a 60–90° turn**. ⚠ Always state it
that way, never as "13° of axis deviation": same fact, but the degrees-of-axis
framing is why an earlier pass wrongly recommended accepting it.

**THE CAUSE IS PROVEN BY TWO INDEPENDENT ROUTES** — scaling MediaPipe's world z
slides the yaw tilt 14.5°→0.6°, and **ROLL, the one axis needing no depth,
measures gain 1.02** while yaw (1.13) and pitch (0.74) err in OPPOSITE directions.
Horn, the quaternion maths, the frame conventions and the renderer are all
exonerated. **The 2D landmarks are good; the predicted depth breaks rotation.**

**THE FIX (T6)**: replace `palm_rotation.Horn`'s 3D↔3D fit with a **2D↔3D planar
PnP** — fit the pose that best PROJECTS a canonical palm onto the PIXEL landmarks.
⭐ The integration point already exists: `freeze(px, world)` / `delta(state, px,
world)` already receive pixels and ignore them, so T6 is a **sibling class behind
the same interface**, swapped at two call sites. ⛔ **No MANO needed** (N13 safe).
⭐ The planar mirror ambiguity is already solved here by U7's chirality.

⭐⭐ **AND THE MEASUREMENT RIG IS FINALLY COMPLETE** — `t5i` (yaw+pitch),
`t5j` (roll, depth-free), `t5h` (jitter). All three axes, recorded takes, one
variable. Baselines to beat are tabulated in the handoff §5.

⚠ **4.2 is DONE and owner-confirmed live in both tools** — see the superseded
block below for it. Nothing about T6 depends on it, or it on T6.

---

### ✅ Superseded: YOU ARE HERE (2026-08-23) — **4.2 IS BUILT AND OWNER-CONFIRMED LIVE.**

> Owner, debug tool: ***"yes. this is working properly"***
> Owner, production: ***"this is working fine"***

**Read this block, then 4.2's row, then `GESTURE_PIPELINE_SPEC.md` §14.3.5.**

| | |
|---|---|
| **state** | Z-axis translation, the 3D snap gate and the world-space play volume are BUILT in BOTH tools and **CONFIRMED LIVE in the debug tool** |
| **automated** | 23 golden-vector suites PASS · `parity_replay` NO DIVERGENCE (509 frames) · `VerifyChiralityFixture` ALL PASS · the play-area invariant reads clean straight from every recording that carries cube rows |
| ✅ **live** | **BOTH TOOLS, back to back, 2026-08-23** — debug *"yes. this is working properly"*, production *"this is working fine"*. Both takes recorded at `recorder_schema: 3`, the first sessions ever written at it |

| what shipped | where | flag / constant |
|---|---|---|
| **Z translation** — a held object's depth follows the hand's grab-referenced span ratio | both tools, driving `Cube.depth_m` from `palm_depth.DepthRatioTracker` | `Z_TRANSLATION` |
| **3D snap gate** — close on X, Y **and** Z | `_try_snap` in both tools, axial term from the new `palm_depth.HandDepthTracker` | `GRAB_Z_TOLERANCE_M = 0.15` |
| **DECISION 1** — no snapping while depth is frozen | `can_snap` in both tools | `SNAP_REQUIRES_VALID_DEPTH` |
| **DECISION 2** — the play area is a world-space VOLUME, frustum-aware | `palm_geometry.clamp_to_play_volume`, from both `set_target_center`s | `PLAY_AREA_MARGIN_M = 0.0425` |
| **projection** — on-screen extent = real size AT ITS DEPTH | `palm_geometry.projected_size_px` | `REFERENCE_DEPTH_M = 0.50` |
| **recorders** | `depth_m` + `projected_size` per object, `hand_depth_m` + `depth_valid` per hand | `recorder_schema: 3` |

⭐⭐ **THE ONE THING WORTH READING IF YOU READ NOTHING ELSE — a constant that was
about to be wrong, and the shape of the mistake.** An object's resting depth was
first set to **0.40 m**, on the strength of U9's own row: *"40 cm IS the closest
the operator actually works"*. **That sentence reads the corpus's p99 palm width
— it is about the CLOSEST APPROACH.** The typical distance is 10 cm further, and
the typical distance is what an object must sit at to be reachable. Measured over
**86 109 trusted hand-frames across 65 sessions**
(`analysis/m9_working_distance.py`): median **0.497 m**, p1–p99 0.309–0.837.
Against 4.2's own axial gate, an object at 0.40 m is reachable on **70.9%** of
frames; at the measured median, **91.2%**. ⛔ **A quarter of all frames unable to
pick anything up would have read as a broken build, not a mis-sized constant.**

⭐ **The reusable form: a constant borrowed from another row's derivation inherits
that row's QUESTION, not just its number.** U9 asked "how big is a hand near the
edge"; 4.2 asked "where does the hand live". Same corpus, different statistic.

**Three more decisions that are recorded rather than obvious** — full reasoning in
spec §14.3.5:

1. ⛔ **The 3D gate is an ELLIPSOID, not a sphere, and a sphere would have shipped
   an un-grabbable object.** The axial term compares against a depth scaled by
   NOMINAL anatomy, so a user 20% off the median reads ~80 mm away from where they
   are, *constantly*; the small object's spherical tolerance would have been 43 mm.
2. ⭐ **§14.3's "absolute, not relative-delta" and §14.1's no-pop rule only LOOK
   contradictory.** `cube.depth_m = grab_depth_m / ratio`, and the ratio's own
   `d0` is captured at the grab — so it is memoryless (decision 2 satisfied) AND
   exactly 1.0 on the grab frame (no pop). Reading decision 2 as "snap the object
   to the hand's depth" would have put a Z teleport into the gesture this project
   has worked hardest to remove.
3. ⚠ **It is the play volume's WALLS, not the tolerance, that bound
   re-grabbability.** Release freezes an object in all three axes, so a wall beyond
   the operator's reach would let one be parked where it can never be picked up.
   The walls are therefore the measured p1–p99 of the hand's own working distance.

⚠ **`cube.size` is now the extent at the RESTING DEPTH only.** The centre, the
clamp, the grab radius and both renderers read `projected_size_px`.
`_top_left_for_center` was DELETED from both tools — it converted with the
nominal size, and a stale copy is how an object's centre would silently drift as
it moved in Z.

⭐ **DECISION 1's cost has a number from day one**, which is what the owner asked
for before it is ever re-tuned: the edge-on band covers **1.6%** of hand-frames
corpus-wide — and that is a *ceiling*, counting every edge-on frame rather than
those where a hand was also within grab radius of a free object.


**LIVE ACCEPTANCE, BOTH TOOLS, RECORDED SO THE CLAIM IS CHECKABLE:**

| | debug `193716_4_2_zaxis_debug_first_look` | production `194406_4_2_zaxis_production_check` |
|---|---|---|
| owner | *"yes. this is working properly"* | *"this is working fine"* |
| coverage | 2274 object-frames | 771 frames, 963 hand-frames, 1542 object-frames, 46 s |
| Z actually exercised | — | large **0.316–0.850 m** (346 distinct), small 0.346–0.850 |
| snaps under the 3D gate | — | **10**, both hands, 778 held object-frames |
| S10 freeze fired | — | **2.0%** of hand-frames |
| play-area invariant | **0 violations** | **0 violations** |

⭐⭐ **TWO INDEPENDENT CONFIRMATIONS FELL OUT OF THAT TAKE, NEITHER OF THEM ASKED FOR:**

1. **The measured constant reproduced itself live.** The hand depth in this
   session runs p5 0.349 / **median 0.502** / p95 0.707 m — against the corpus
   median of **0.497 m** that `REFERENCE_DEPTH_M = 0.50` was derived from. A
   constant measured over 65 old sessions predicted this new one to 5 mm.
2. **DECISION 1's cost landed where it was predicted.** The freeze fired on 2.0%
   of hand-frames against the corpus-wide ceiling of 1.6% — same order, and
   nothing was reported as un-grabbable.

⚠⚠ **AND THE HARNESS CRIED WOLF ONCE MORE — the fifth time this pattern has
appeared, and again the instrument was the suspect.**
`verify_play_volume_from_recording.py` reported **361 violations** on the take the
owner had just watched work. Worst magnitude: **0.0115 px.** ⭐ The cause is that
the harness compared RECORDED values, which the recorder rounds (`position` and
`projected_size` to 2 dp, `depth_m` to 4), against an UNROUNDED boundary — and
an object pinned exactly on that boundary, which is the correct outcome, rounds a
hundredth of a pixel outside. ⭐ **THE GENERAL RULE, now written into the harness:
compare at the precision the INPUT carries, not at the precision the arithmetic
can produce.** Tighten it by recording more digits, never by asserting below what
was recorded.

⛔ **Still open and unchanged by this build**: U7's declared-ground-truth
acceptance take (see the block below) and T4's yaw/palm-sink — 4.2 drives an
object's depth, it does not correct the translation anchor's yaw swing.

---

### ✅ Superseded: YOU ARE HERE (2026-08-23) — **FIVE FIXES SHIPPED AND LIVE-CONFIRMED. NEXT BUILD IS 4.2.**

> Owner, at the end of the session: ***"the build now is good."***

**Start here, then read the rows for U7 / U8 / U9 / T3. Nothing is committed —
the working tree holds all of it.**

| what shipped | where | flag / constant |
|---|---|---|
| **U7** — chirality from GEOMETRY, not the 10.8%-wrong handedness label | `palm_geometry.signed_palm_volume` / `geometric_chirality` / `ChiralityResolver`, wired into `PalmFacingTracker.update()` | `GEOMETRIC_CHIRALITY` |
| **T3** — a held object's owner SLOT follows its TRACK across a relabel | `Resources/owner_remap.py`, called by both tools | `OWNER_FOLLOWS_TRACK` |
| **U8** — rule 3 may not act on a PROVISIONAL chirality | `ChiralityResolver.confirmed`, gating `can_snap` in both tools | `CHIRALITY_CONFIRM_MS = 200` |
| **U9** — an object may never reach the display edge | `palm_geometry.clamp_to_play_area`, from both `set_target_position`s | `EDGE_MARGIN_PX = 60` |
| **recorders** — both log the cue AND cube position/size, sampled at the same point in the frame | `_record_flush` (production), the debug recorder | `recorder_schema: 2` |

✅ **ALL FIVE ARE LIVE-CONFIRMED IN BOTH TOOLS (2026-08-23 evening).** Owner:
*"Production is OK as well."* The recorder rework is verified end to end on
`2026-08-23_173029_schema2_production_check` (509 frames, 21.4 fps): schema 2
present, all eight hand fields and all four cube fields written, and — the point
of the whole change — **the play-area invariant was read STRAIGHT FROM THE
RECORDING, with no replay and no re-derivation: 0 of 1018 cube-frames outside,
closest approach 0.0 px slack** (the large cube at x=500, exactly the computed
boundary).

⛔⛔ **STILL OPEN, AND NOT WHAT ITS FILENAME SUGGESTS — U7's ACCEPTANCE TAKE.** An
attempt was made (`2026-08-23_172804_u7_acceptance_known_right`) and the operator
then reported that **BOTH hands were used**, so the declared `known_hand` was
FALSE. ⭐ **The declaration is RETRACTED in that session's `meta.json`**: the field
is renamed `known_hand_RETRACTED` and `ground_truth_valid: false` added, so no
harness can read it as ground truth (`u7_geometric_chirality.py` looks for
`known_hand`). ⚠⚠ **Trusting a wrong declared label is exactly the circularity
that hid the handedness defect through seven patches — do not resurrect that
field.** The take is still useful as an ordinary session and as the first debug
take carrying schema 2. ⭐ **U7's behaviour was observed correct live** (exit
palm / re-enter back / re-grab refused) — real evidence, but NOT the specified
acceptance test. **U7 acceptance remains OPEN** and needs a take where ONE
physical hand is used throughout.

**NEXT BUILD: 4.2 — Z-axis translation**, driving cube Z from 4.1's depth ratio
(`Resources/palm_depth.py`, A10-passed, wired to nothing). ⚠ It must also make
snap gating **3D** — `_try_snap`'s grab radius becomes a 3D check, a real change
to existing logic. ⚠⚠ **AND IT MUST REVISIT U9's PLAY-AREA CLAMP**, which is a 2D
rule: the display is the camera's FIELD OF VIEW (a frustum), so an object's
projected extent changes with depth, and `clamp_to_play_area`'s `size` term stops
being a constant — a NEAR object could otherwise overflow the play area. See 4.2's
row for the design question that comes with it, and pair the change with **U2**. ⚠ Read `GESTURE_PIPELINE_SPEC.md` §14.3 **and then §14.3.2,
which corrects it**, plus **S10** (the depth ratio must FREEZE inside the DR-2
band). ⭐ No calibration step is needed — the envelope is 3.59x and `d0` is
per-grab.

---

**⚠⚠ THE METHOD LESSONS OF THIS SESSION. They cost four reverted builds, and every
one is about an INSTRUMENT, not about the pipeline.**

1. ⛔⛔ **FOUR TIMES A HARNESS REPORTED CLEAN ON A TAKE THE OWNER HAD JUST WATCHED
   FAIL.** Each time the instrument was wrong, not the owner:
   - counted a SLOT change as a hand change (label-as-identity — the very
     confusion under diagnosis);
   - recomputed the palm/back cue with a slot-keyed tracker while production ran
     track-aware;
   - looked the hand up by the cube's owner SLOT, so a relabel made it skip;
   - paired `hands[i]` with `cubes[i]` when production sampled cubes a frame
     earlier — **11 phantom violations**.
   ⭐ **When the owner's eyes and the instrument disagree, the instrument is the
   suspect.**
2. ⭐ **RECORD WHAT RAN; DO NOT RE-DERIVE IT.** A recomputation is a second
   implementation that can silently disagree with the real one. Production now
   records `thumb_outward`, `chirality_confirmed`, `snap_allowed`, and cube
   `position`/`size`. `analysis/verify_recorder_parity.py` keeps the two
   recorders honest by SOURCE.
3. ⚠ **`parity_replay.py` reported a divergence THREE times and every time it was
   THE HARNESS**, feeding an input to one side only. A comparator must be
   symmetric in its INPUTS, not just its logic.
4. ⭐⭐ **A TRIGGER CANNOT ENFORCE AN INVARIANT** (U9). Two hand-side triggers were
   built and reverted before the positional clamp; see U9's row.
5. ⭐ **A threshold must not be computed from a quantity that is noisy in the
   regime the threshold governs** (U9's adaptive margin, 45% width jitter).
6. ⚠ **The count alone was not the guard it looked like** (U8): the dispute
   condition catches the recorded failure at every window from 400 ms down to
   100 ms; the window is a backstop.

---

### Superseded: YOU ARE HERE (2026-08-22, END OF SESSION) — **THREE FIXES SHIPPED AND OWNER-ACCEPTED LIVE.**

> Owner, after the production run: ***"fix is working. I believe this is good to ship."***

**Read this block, then the U7/U8/T3 rows. The next build is 4.2 (Z-axis translation).**

| what shipped | where | flag |
|---|---|---|
| **U7** — chirality from GEOMETRY, not the 10.8%-wrong handedness label | `palm_geometry.signed_palm_volume/geometric_chirality/ChiralityResolver`, wired into `PalmFacingTracker.update()` | `GEOMETRIC_CHIRALITY` |
| **T3 narrow remap** — a held cube's owner SLOT follows its TRACK across a relabel | `Resources/owner_remap.py`, called by both tools | `OWNER_FOLLOWS_TRACK` |
| **U8** — rule 3 may not act on a PROVISIONAL chirality | `ChiralityResolver.confirmed`, gating `can_snap` in both tools | `CHIRALITY_CONFIRM_MS = 200` |
| **production records the CUE** — `thumb_outward`, `chirality_confirmed`, `orientation_valid`, `snap_allowed` | `HandsTriggeredActions._record_flush()` | `VISION_RECORD=1` |
| **U9** — an object may never reach the display edge (play area = window inset 60 px) | `palm_geometry.clamp_to_play_area`, from both tools' `set_target_position` | `EDGE_MARGIN_PX = 60` |

**⭐ THREE DISTINCT DEFECTS, and they were only separable by recording them.**
All three presented as *"a back-of-hand hand takes the cube"*:

1. **Steal by RELABEL** (`n8_back_steal_b`, f478) — DR-1 swaps two tracks between
   slots; ownership is a slot NAME, so the cube changes PHYSICAL HAND with **no
   release, no snap and rule 3 never consulted**. Fixed by the remap.
2. **Back-grab by INHERITED STATE** (`t3_remap_debug_test`, f1050) — a track moving
   into a slot inherited the previous occupant's `PalmFacingTracker`, so its
   back-of-hand read as PALM for 2 frames. **Post-mortem §3.4, still live.** Fixed
   by resetting the tracker when the track in a slot changes.
3. **Back-grab by PROVISIONAL CHIRALITY** (`t3_remap_production_test`, f664) — a
   newly entered hand's chirality measured wrong for 5 frames. Fixed by U8.

⚠⚠ **THE METHOD LESSON, and it cost two wrong builds tonight:**

- ⛔ **Twice a harness reported CLEAN on a take the owner had just watched the
  defect in.** Both times the instrument was wrong, not the owner. The first
  treated a slot change as a hand change (label-as-identity — the very confusion
  under diagnosis); the second recomputed the cue with a slot-keyed tracker while
  production ran track-aware. ⭐ **When the owner's eyes and the instrument
  disagree, the instrument is the suspect.**
- ⭐ **This is why production now RECORDS the cue instead of re-deriving it.** A
  recomputation is a second implementation that can silently disagree with the
  real one. It did, immediately.
- ⚠ `parity_replay.py` reported a divergence **three times** this session and
  **every time it was the harness**, feeding an input to one side only. A
  comparator must be symmetric in its INPUTS, not just its logic.

**LIVE ACCEPTANCE (both tools, recorded so the claim is checkable):**

| | debug `202023_u8_gate_debug_test` | production `202329_u8_gate_production_test` |
|---|---|---|
| coverage | 1420 fr, 487 two-hand, 1328 held, 506 back | 928 fr, 258 two-hand, 721 held, 275 back |
| silent handovers | **0** | **0** |
| back-of-hand steals | **0** | **0** |
| back-of-hand snaps | 2 — **both legal** (rule 3's armed exception) | 1 — **legal**, `snap_allowed=True` recorded |

⭐ The production row is the first read from **recorded** cue fields rather than a
recomputation, and it settled the one back-snap immediately: the hand was
thumb-outward when tracking was lost, which ARMS rule 3's documented exception.

---

### Superseded: YOU ARE HERE (2026-08-22, LATEST) — **U7 IS BUILT. IT NEEDS ONE LIVE KNOWN-HAND TAKE.**

**The next action is not a build — it is a 30-second recording only the owner can make.**

| | |
|---|---|
| **status** | ✅ Built, all offline guards green. ⛔ **NOT accepted** — acceptance is a LIVE known-hand take, which needs the owner and the camera |
| ⭐ **run this** | `LiveSnapDebug.py --known-hand right` (then `left`): exit palm, re-enter **back-of-hand**, try to grab. Rule 3 must **refuse**. Then `analysis/u7_geometric_chirality.py` on the new session |
| **what changed** | `Resources/palm_geometry.py`: `signed_palm_volume`, `geometric_chirality`, `ChiralityResolver`, wired into `PalmFacingTracker.update()` — the **one** place the label enters the palm/back cue in either tool, so both are fixed by one edit (N6) |
| **A/B switch** | `palm_geometry.GEOMETRIC_CHIRALITY = False` restores pre-U7 behaviour exactly. No `world_landmarks` → falls back to the label, i.e. today's behaviour; never worse |
| ⭐ **measured effect** | at the 5 recorded snaps, rule 3's input changes on **exactly 1 — frame 122, the documented failing snap** — and the four sound snaps are untouched. Verified through the REAL tracker, not a reimplementation (STEP 9) |
| **green** | 19 verify suites; `VerifyChiralityFixture.py`; new golden vectors `analysis/verify_geometric_chirality.py`; `guard_sensitivity.py`; `parity_replay.py` **zero divergence on 5534 frames** across two sessions |
| ⚠⚠ **read this before believing the green** | the 4.1 post-mortem's decisive fact was that its final session **measured CLEAN and the owner still saw bugs**. Everything above is offline. It is evidence the change does what was intended, **not** evidence the defect is gone in play |

**⭐ TWO FINDINGS THIS BUILD PRODUCED THAT WERE NOT IN THE PLAN:**

1. **The conditioning gate earns nothing, and was NOT shipped.** Sweeping the
   thumb-plane-thickness threshold 0→7 mm changed the error count not at all
   between 0 and 5 mm, and made it **worse** at 3–5 mm (0 residual errors → 3),
   because suppressing observations stalls the debounce and lets a bad value
   persist. **Under A10 a null result is recorded, not shipped hopefully** —
   `palm_plane_thickness()` stays exposed as a diagnostic only. **The 3-frame
   debounce does all the work**, and it is free because *a hand cannot change
   chirality*: within a track the value is constant.
   ⚠ **Honest caveat**: debounce=3 was chosen against **5 residual errors in one
   session**. Small sample. Re-validate on the live take before treating it as settled.
2. ⛔ **`analysis/guard_sensitivity.py` had been DEAD since 2026-08-03.** It
   AST-compared `HandsTriggeredActions._is_thumb_outward`'s body against an inlined
   reference — but queue item **1.2 moved that logic into `palm_geometry.py` the
   same month**, leaving a one-line delegation. From that day the guard **could not
   pass**: it printed "GUARD IS BROKEN" on every run for 19 days, about **itself**.
   ⭐ **A guard that cannot pass is worse than no guard** — its failure carries no
   information and everyone learns to ignore it. Repointed at the functions that
   actually hold the logic, plus new U7 mutants and an N6 delegation check.

⚠ The DR-2 A/B harnesses (`dr2_ab.py`, `dr2_latency.py`, `n7_dr2_dwell_ab.py`)
are **deliberately left on the two-argument call**, so their recorded historical
numbers stay reproducible. That is a choice, not an oversight.

---

### Superseded: YOU ARE HERE (2026-08-22, LATE) — **U7 STEP 0 IS DONE. THE REMEDY IS MEASURED VIABLE. BUILD IT.**

**Read this block, then U7's row, then `Claude/HANDEDNESS_LABEL_DEFECT.md` §5
(whose mechanism was corrected by this measurement).**

| | |
|---|---|
| **next build** | ⭐ **U7 — replace the MediaPipe handedness label as the CHIRALITY source with a geometric one.** Not 4.2 |
| **why not 4.2** | 4.2's central change rewrites `_try_snap`'s grab radius into a **3D check** — i.e. it rebuilds snap gating, the exact rule U7 corrupts. Building it first means re-deriving snap logic on top of a gate known to be **10.8% wrong**, and every live test of 4.2 would be read through that error |
| ⭐ **the measurement** | `analysis/u7_geometric_chirality.py`, scored against the operator's **DECLARATION** (never `is_thumb_outward(px, label)` — that circularity is the whole B4 lesson). 7 sessions, 2555 single-hand frames |
| ⛔ **§5's mechanism was WRONG** | the doc proposed "use the 3D palm normal instead of the 2D cross product". **3D alone does not remove the chirality dependence** — the 2D signed area already IS that normal's z-component, and a left hand showing its palm is the mirror image of a right hand showing its back. **The THUMB is what separates them**, because it leaves the palm plane: `V = det[index_MCP−wrist, pinky_MCP−wrist, thumb_CMC−wrist]` is rotation-invariant and flips sign only under reflection |
| ⭐ **result** | corpus **99.8%** vs the label's 98.8%; on the one discriminating take **98.3% vs 89.4%** — 31 errors → 5, **84% fewer**. ⚠ **Quote the second row, not the first**: six of seven takes are steady holds where MediaPipe is already 100% |
| ⭐⭐ **it fixes the SNAP** | of the 5 snaps in that take, rule 3's input changes on **exactly 1 — frame 122, the documented failing snap** — from "palm, allowed" to "back, forbidden". **The four sound snaps are untouched.** That two-sided result is the deliverable, not the accuracy number |
| ⚠ **build notes** | give the new cue its **own conditioning gate** (thumb distance from the palm plane: median 8.8 mm, p10 7.9 mm, min 0.9 mm) exactly as the 2D sign has `edge_on_measure`; residual errors form runs of [2,1,1,1], so **3 of 4 are isolated frames a 2-frame debounce absorbs** |
| ⛔ **the honest gap** | the four declared-**facing** takes are all takes where MediaPipe never errs, so **they cannot demonstrate the facing fix**. **Acceptance stays a known-hand LIVE take** (`LiveSnapDebug.py --known-hand left|right`), never a replay that trusts the recorded label. Re-run `VerifyChiralityFixture.py` and `analysis/parity_replay.py` around the change |
| ⭐ **then** | 4.2 (Z-axis), then U5 — ⚠ **U5 and N8 want sequencing together**, since a longer hold widens N8's steal window by construction |

⚠ **One coverage note worth keeping**: `2026-08-04_054109_known_right_back` is
**excluded** — all 723 frames detect TWO hands on a declared one-hand take, so its
ground truth is ambiguous. The harness names it rather than averaging it in.

---

### Superseded: YOU ARE HERE (2026-08-22, END OF SESSION) — read this, then U7, then the two post-mortems.

**Two documents carry the whole story. Read them before touching ownership,
per-hand state, or anything chirality-sensitive:**
- `Claude/HANDEDNESS_LABEL_DEFECT.md` — ⛔ **the root cause of the defect that
  survived seven patches**: the handedness label is wrong **10.8%** of the time
  and every chirality-sensitive rule inverts on it. Queue item **U7**.
- `Claude/POSTMORTEM_4_1_IDENTITY_MIGRATION.md` — why 4.1's identity migration
  was built, patched five times, and reverted.

| | |
|---|---|
| **state of the pipeline** | ✅ **Both tools behave**, on the reverted baseline. Production and debug were live-checked and measure clean (production 18 snaps / 18 releases, freeze signature 3 frames) |
| **reverted** | 4.1's identity migration — one flag, `TRACK_OWNERSHIP = False` (mirrored in `LiveSnapDebug.py`). **Nothing deleted**; set it True to restore |
| ⭐ **KEPT from 4.1, all independently good** | `palm_depth.py` (depth estimator, A10-passed, **now with the owner's edge-on fallback** — 100% availability, false depth unchanged); the **DR-1 frame-edge fix**; **production recording** (`VISION_RECORD=1`); the `hand_tracks` wire packet (sent, unused) |
| **next build** | **4.2 (Z-axis translation)** — it does not depend on any of the above. ⚠ But **U7 is the deepest open defect**, and it makes rule 3 unreliable today |
| ⚠ **still open** | **U7** (label 10.8% wrong), **U5** (occlusion coast), **N8** (cube stealing), and **T3 is ACTIVE again** — with ownership back on the handedness label, a relabel orphans a held cube: in play, a cube **drops** for no visible reason while crossing hands or rotating through edge-on, and the operator re-grabs |
| ⭐⭐ **T3 and U7 are ONE root cause** | the handedness label is unreliable (**10.8% wrong**) and the pipeline uses it as **both** identity (T3 — who owns the cube) **and** chirality truth (U7 — which way the palm faces). **Fix the label, or remove the dependency on it, and both go; patch either symptom alone and neither does.** That is the single highest-value target on the board |
| ✅ **U6 DECIDED** | owner, 2026-08-22: ***"we will keep two: production and debug"***. The collapse proposal is CLOSED. ⚠ The obligation that replaces it: **divergence must be caught mechanically** — run `analysis/parity_replay.py` whenever either tool's gesture logic changes, and whenever "it does not happen in production" is said. That sentence meant a real divergence 3 times and sampling once this session |

**⚠⚠ THE METHOD LESSON, which cost most of this session:**

1. ⛔ **Reach for GROUND TRUTH the first time a chirality-sensitive claim is
   questioned, not the seventh.** Seven analyses reported "zero violations"
   because each compared the pipeline's belief against a formula fed **the same
   wrong label**. `LiveSnapDebug --known-hand left|right` now stores the operator's
   declaration in `meta.json`; the corpus's `known_left_*`/`known_right_*`
   sequences existed for exactly this.
2. ⚠ **Check session COVERAGE before reading any result.** Three sessions produced
   green numbers from ~0 cubes held or 0 two-hand frames.
3. ⚠ **Instrumentation reported success while behaviour regressed, twice** (a
   recorder key collision; a harness that skipped the session recorded to test the
   fix). **A green instrument you cannot trust is a reason to stop, not continue.**
4. ⭐ **When the owner says "it does not happen in production", build the
   comparator** (`analysis/parity_replay.py`) rather than hunting divergences by
   eye. It found three real ones this session — and then proved the fourth claim
   was sampling, not a divergence.

---

### Superseded: YOU ARE HERE (2026-08-22, end of day) — **4.1's IDENTITY MIGRATION IS REVERTED.**

**Read `Claude/POSTMORTEM_4_1_IDENTITY_MIGRATION.md` before touching ownership or
per-hand state. It is the whole story with measurements.**

| | |
|---|---|
| **reverted** | cube ownership keyed on the DR-1 track id, AND per-hand state following the track. Owner instruction after 5 live sessions: *"it is still full of bugs. Revert."* |
| **how** | one flag — `HandsTriggeredActions.TRACK_OWNERSHIP = False`, mirrored in `LiveSnapDebug.py`. **Nothing was deleted.** Ownership and per-hand state key on the handedness SLOT again, exactly as before 4.1 |
| **cost** | **T3 returns**: a held cube is orphaned when the label flips, 113 of 205 spurious releases. ⭐ That is a DROP the operator re-grabs; the migration traded it for FREEZES and rule violations, which are worse |
| ⭐ **KEPT, independent and good** | `palm_depth.py` (4.1's depth estimator — A10-passed, drives nothing), the **DR-1 frame-edge fix**, **production recording** (`VISION_RECORD=1`), the `hand_tracks` wire packet (sent, unused), and every harness |
| ⚠ **the decisive fact** | the final session measured **CLEAN** — 0 rule-3 violations across 21 relabels, 43 snaps, 1255 two-hand frames, no frozen cube — **and the owner still saw bugs.** The instruments were not capturing what breaks, so further patching could not be trusted |
| ⚠ **before retrying** | fix **U6** first (one pipeline) — 3 of the 5 defects were production/debug divergences. Then migrate ALL per-hand state at once, never seed a new track from a slot, and write the system-level property test BEFORE the first live session |

**Next build is still 4.2 (Z-axis translation)** — it does not depend on the
migration. ⚠ But **U5** (occlusion coast) and **N8** (cube stealing) are still
open, and T3 is back.

---

### Superseded: YOU ARE HERE (2026-08-22, end of day) — **4.1 IS BUILT. NEXT BUILD IS 4.2 (Z-axis translation).**

**Read this block, then 4.2's row, then `GESTURE_PIPELINE_SPEC.md` §14.3 and
§14.3.2. You should not need anything else to start.**

| | |
|---|---|
| **next build** | **4.2 — Z-axis translation (§14.3)**, driving cube Z from 4.1's depth ratio |
| ⭐ **4.1 is DONE, both halves** | the depth **estimator** (`Resources/palm_depth.py`, A10-passed) **and** the `HandState` v2 **wire migration** carrying `trackId` (ownership now keys on identity, not the handedness label) |
| ⚠ what 4.2 must add | §14.3's **3D snap gating** — `_try_snap`'s grab radius becomes a 3D check. That is a real change to existing snap logic, not an additive axis |
| ⚠ undecided, deliberately | what happens to snap gating when `depthValid` is False (the S10 freeze). §14.3.2 leaves this to whoever builds it |
| ⭐ no calibration step needed | measured: an ordinary push/pull spans **3.59x**, and `d0` is captured **per grab**, so every grab self-normalises. See spec §14.3.4.6 / `analysis/m9_depth_envelope.py` |

⛔⛔ **TWO DEFECTS FOUND ON THE FIRST RECORDED PRODUCTION RUN (2026-08-22) — READ
BEFORE 4.2.** Session `2026-08-22_154426_production_4_1` (5114 frames, 205 s).

**(1) THE STRAND IS STILL PRESENT IN PRODUCTION, WITH A SECOND ROOT CAUSE.**
Owner: *"the small cube was dropped but my free hand could not catch it again."*
Measured: cubes owned by an absent track for runs of **40 frames (~1.6 s)**,
repeatedly. ⚠ **NOT "the track ended"** — the hands were still DETECTED, their
**track ids went to -1** while landmarks kept arriving:

```
f1997  hands=[('Left', 3), ('Right', 2)]  owner=3
f1999  hands=[('Left',-1), ('Right',-1)]  owner=3   <- stranded
```

⭐ **Root cause, server-side**: `_normalized_to_pixel_coordinates` returns None for
any landmark outside [0,1] — a hand **partially out of frame**. One None makes
`palm_centroid` None, which fails `all(o[0] is not None ...)`, which **skips DR-1
entirely for that frame**, so NO hand gets a `trackId` and the wire carries -1 for
both slots. **Moving a hand near the frame edge is enough.** The cube is then owned
by an int matching no live key, while its governing slot still holds a DETECTED
hand — so `holds_track` is True and release never fires.

✅⭐ **ROOT-FIXED 2026-08-22 (owner: "fix it")**: `hands_visualizer.py` now builds
pixel landmarks by **plain multiplication** (`lm.x * width`), exactly as
`LiveSnapDebug.py` always has — so out-of-frame coordinates go negative instead of
becoming None, `palm_centroid` survives, DR-1 keeps running and `trackId` keeps
being published. ⭐ **This was a production/debug DIVERGENCE of the same class as
§13.6.1 and the mirror bug** — the debug tool never had either defect because it
never used the None-ing converter. ⭐ It also fixes a **second, separate** defect:
`remap_keypoints` turned a None into **(0, 0)**, so an out-of-frame landmark
reached the client at the TOP-LEFT CORNER, corrupting `_weighted_position`'s
translation average as well as identity. Guard:
`analysis/verify_offscreen_identity.py` (every palm landmark x all four edges,
plus "DR-1 really publishes an id in that state" and "garbage is still rejected").
⚠ The client-side safety net (`OWNER_ABSENT_RELEASE_MS = 700`) is KEPT as
defence-in-depth — a cube must never strand for any future reason.

**(2) ⭐⭐ D4 IS REOPENED BY MEASUREMENT — the recorded condition is now met.**
Owner: *"when the hands quickly pass in front of each other and one occludes the
other ... the cube grabbed by the occluded hand is ungrabbed and then grabbed
again ... which causes a jump."* Measured on the same take — gaps where one hand
vanishes **while the other is present** (i.e. crossing/occlusion):

| | |
|---|---|
| events | 60 |
| median gap | **402 ms** |
| p90 / max | 2130 ms / 3778 ms |
| **longer than D2's 150 ms coast** | **42 of 60 = 70%** |

⭐ D2's coast is **2.7x too short** for hand crossing, so the cube is released on
70% of them and re-snaps on reappearance — the jump the owner describes.
⚠ **D4 was DECLINED 2026-08-21** (*"I do not see the need"*), and the recorded
reopening condition was **"only a hand lost LONGER than the sensor gap"**. That
condition is now measured. **This is a legitimate reopening, not a re-proposal.**

⭐ **PARKED AS QUEUE ITEM U5 (owner decision 2026-08-22)** — *"mark the issue as an
improvement for later re-opening"*. **U5's row carries the observation, the
recording reference, the measurement and the explanation**, so the topic can be
reopened cold. ⚠⚠ **The remedy is a LONGER HOLD, not extrapolation**: the owner's
framing said "extrapolation", but **B8 already measured every fit LOSING to "hold
the last value"**. Owner's stated approach: extend D2's window and **pick it by a
RECORDING TEST**, not by feel. ⚠ Cost to price: a longer hold widens the window for
**N8** and for holding a cube the operator really released.

**⭐ WHAT 4.1 SHIPPED (2026-08-22)**

- **`Resources/palm_depth.py`** — `DepthRatioTracker`: `max4` over the rigid palm
  quad vs a grab-time baseline, S10 freeze inside the edge-on band, rate limit,
  clamp. **A10 PASSED**: responsive **3.68x** on `depth_sweep`; on rotation-in-place
  its OWN error is **1.30x worst case** vs a naive width-only **8.04x**.
  ⚠ **Quote the drift-floor-corrected number** — 1.40x of the clean yaw take's
  1.82x is the operator's arm genuinely moving. 24 golden vectors.
  ⛔ **It is wired to NOTHING yet — that is 4.2.**
- **The `trackId` wire migration** — `hand_tracks` packet, `_owner_key()`,
  ownership keyed on the stable DR-1 id. Live A/B over three sessions: label
  keying orphaned a held cube **794 / 377 / 15** frames, track keying **0** every
  time (session 2 had **24** relabels). `PERCEPTION_LAYER_SPEC.md` §2.2.1–§2.2.3.
- **Production and the debug tool are now the SAME pipeline** — the mirror fix
  (spec §14.3.4.3/§14.3.4.4), owner-confirmed live.
- **Production can now RECORD** (`VISION_RECORD=1`), same JSONL schema as the
  debug tool, so every `analysis/` harness reads a production take unchanged.

⚠⚠ **TWO BUGS I INTRODUCED AND THE OWNER FOUND LIVE — read before touching
ownership.** (1) **The stranded cube**: release read
`cube_owned_by(_owner_key(hand))`, which degrades to the LABEL once a track ends,
so an int-keyed cube was never found and stayed owned by a dead id — drawn as
grabbed, driven by nothing, un-regrabbable. **The fallback fired exactly when the
id was missing, which is exactly when release needed it.** Fixed by driving
release from the CUBES, governed by whichever slot the owning TRACK is in now.
(2) The hand **LABEL displayed inverted** — pre-existing, fixed DISPLAY-ONLY;
⛔ **never flip the internal label**, four things are calibrated to it.

⚠ **Still open on 4.1**: the **~13° yaw axis tilt** is real and unattributed
(spec §14.3.4.2) — the mirror, the frame convention, degeneracy, hand anatomy and
the Horn fit are all eliminated; MediaPipe's world-z error and residual operator
wobble remain. **ROLL has never been recorded.**

---

### Superseded: YOU ARE HERE (2026-08-22, morning) — PHASE D IS CLOSED. **NEXT BUILD IS 4.1 (M9 metric depth).**

**Read this section, then 4.1's row, then `GESTURE_PIPELINE_SPEC.md` §14.3.1. You should not need anything else to start.**

| | |
|---|---|
| **next build** | **4.1 — M9 metric depth**, leading to 4.2 (Z-axis translation) |
| ✅ **NOT blocked** (corrected 2026-08-22) | The yaw take **was recorded on 2026-08-04** — `2026-08-04_164647_yaw_sweep_constant_depth`, 741 frames, verified present on disk — and **§14.3.2 already analysed it** (`max4` CV 0.056 under yaw). The earlier "⛔ blocked on the owner: a YAW take must be recorded first" line was §14.3.1's wording carried forward past §14.3.2, which superseded it the same day. See row N18. ⚠ **§14.3.2 also REFUTED §14.3.1's prediction**: under yaw, width and length degrade *equally* (0.128 vs 0.125) — no anchor is immune — which **promotes S10's freeze from backstop to prerequisite**. |
| ⚠ read before building | §14.3.1 **and then §14.3.2, which corrects it** (multi-anchor), **S10** (the palm-width anchor COLLAPSES edge-on, so the depth ratio must FREEZE inside the DR-2 band — reuse `PalmFacingTracker`'s pattern — or Z-control inherits the pitch-crossing failure) |
| ⭐ the scale reference already exists | `hand_skeleton.palm_width_world()` (spec §0.18). 1.7's fit is NOT needed. |
| ⭐ do it **with** 4.1 | **the `HandState` v2 wire migration**, which is what makes v2's metric fields mean anything — and it now has a second, measured customer: **carry a `trackId` and key cube ownership on it** (see T3 below, and spec §2.2's 2026-08-22 addendum) |

⚠⚠ **NEW, 2026-08-22 — READ BEFORE 4.1 USES §14.3.2.** The owner reported that a
YAW hand rotation turns the cube about a tilted axis. **Measured and confirmed**
(`analysis/t5*`): yaw is **25.6° off vertical** at large rotation vs pitch's
**5.0°**. Two suspects were tested and **both cleared** — the `invert_x` mirror
(a reflection can only reverse an axis, never tilt one: `M R M⁻¹ = R(−Mn,θ)`;
empirically the tilt is bit-identical) and constellation degeneracy
(`palm_observability` never leaves 0.85–0.89). ⛔ **The cause is NOT yet
identified, and it cannot be from existing data**: the corpus's only yaw take is
**axis-contaminated** — the operator mixed pitch in (2D-pixel control,
`t5c`), so part of that 25.6° is the hand, not the estimator. **A clean yaw
retake settles both this AND §14.3.2's mechanism claim, which rests on the same
take** (spec §14.3.3/§14.3.4). §14.3.2's *recommendation* — `max4` + S10 freeze —
**is unaffected; build 4.1 as prescribed.** ⭐ One actionable result already:
**palm+tips beats palm-only on axis fidelity in every take** (pitch 8.1°→3.9°),
but production ships palm-only for measured JITTER reasons — that is an **A/B
under A10**, not a switch to flip. ⚠ **ROLL has never been recorded** and stays
unmeasured.

**What just shipped (2026-08-21/22), all owner-accepted live:**

- **D0–D3 — dropout mitigation.** A **150 ms tracking-loss coast** plus a **3-frame resync blend**, in production and the debug tool. Owner ran a three-arm rig (off / bridge / bridge+blend) and chose BLEND. `GAME_RULES.md` rule 2 is the behavioural statement of record.
- **D4 (M10.7 grace period) — DECLINED**, not deferred: *"I do not see the need."* Do not re-propose it.
- **T3 — defect confirmed and quantified (113 of 205 releases), client-side remedy BUILT, LIVE-TESTED AND REVERTED.** Re-pointed at the v2 track id. ⚠ **Do not rebuild it at the client layer** — see its row.

⚠ **Two open items that are NOT next, recorded so they are not rediscovered:** the
**two-hand swap** (both hands present, labels exchanged, cube silently follows the
wrong hand — spec §0.4) and **N8 cube-stealing by occlusion**, which the owner saw
live on 2026-08-21 and wants handled with **B5**'s grab/release mechanism rather
than patched now.

---

### Superseded: YOU ARE HERE (2026-08-04, end of day) — PHASE 1 IS CLOSED. All of 1.5/1.6/1.7 parked.

**Read `PERCEPTION_LAYER_SPEC.md` §0.18 before doing anything in Phase 1.**

Three items were built, measured and parked the same day. They are **one finding,
measured three ways**: the orientation frame is `wrist / index-MCP / middle-MCP /
pinky-MCP`, and when MediaPipe's palm reconstruction collapses (Google #5156,
back of hand) all four are wrong *together*. So filtering can't fix it (§0.13.2),
re-weighting can't (A5), constraining bone lengths can't (the frame doesn't use
them), and gating can't without destroying legitimate fast input (§0.17).

**T1 and T2 are reclassified from open bugs to a known single-camera sensor
limit.** Do not open a fifth attempt without a second camera.

⚠ **Binding rule added, and it cost the most to learn**: 1.6 initially PASSED its
A/B and had to be reversed — the metric counted removing the owner's *real fast
movements* as success. **Any module that rejects or suppresses data must CLASSIFY
what it removed, not merely count it.**

✅ **What survives**: `hand_skeleton.palm_width_world()` is the per-session scale
reference M9 needs (dead item 1.4 was supposed to supply it). It needs no
skeleton fit. **This unblocks 4.1 → 4.2 (Z-axis translation).**

**⭐ DIRECTION SET 2026-08-04 (owner): the BLOCK REPRESENTATION, Phase B below.**
The hand is 6 blocks for grab/rotate/translate — palm transform + 5 finger arcs
— and the corpus already measured both halves (palm rigid to 2.76 mm; PIP↔DIP
co-flexion 0.0% negative over 29k frames, so a finger is ONE DOF). Design:
`GESTURE_PIPELINE_SPEC.md` **§16**. This supersedes "what's next" below.

| order | item | why |
|---|---|---|
| **1** | **B1** `hand_blocks.py` derived view | costs nothing if it loses — a pure function over existing landmarks, no pipeline change |
| **2** | **B2** measure palm-transform predictability | position prediction error has NEVER been measured; this decides whether B3 is worth building, as the 1.5→1.6 gate did |
| **3** | **B3** palm predictor → **B4** the 3.3 three-arm A/B → **B5** grab from arcs | |
| — | 4.1/4.2 Z-axis | owner: later, not now. ⚠ read §14.3.1 first (multi-anchor; a yaw take must be recorded) |
| — | 4.3 M10.7 grace | **DEFERRED by owner** — no new layers of rules for now |
| — | U2 3D import | **POSTPONED by owner** — blocked on the platform choice, not on effort |

⚠ **3.4 ("brain-mimicking" endpoint/intent prediction, S12) is NOT available
yet** — it is blocked on 4.3 (M10) and on the §14.2 aperture gesture. The
*unblocked* prediction item is **3.1** (M7 render-latency prediction), which still
depends on **0.3** (end-to-end latency measurement, needs a 240 fps phone).

---

### Superseded: YOU ARE HERE (2026-08-04) — 1.5 is BUILT; next is 1.6

**Item 1.5 (M3a anatomical constraints) is built and measured** —
`Resources/hand_anatomy.py`, with `analysis/m3a_violations.py` and
`analysis/m3a_diagnose.py`. **0.00% false positives on 1446 control hand-frames**;
fires on 5–59% of frames in the poses MediaPipe is documented to fail.
Full account: spec **§0.16**. It is **not yet consumed by anything** — A10's
ship-or-revert test bites when **1.6** gates on it, so 1.6 is next.

**Item 0.5 (offline oracle) is DROPPED, not deferred** — two independent
blockers, one of them permanent. See its row below and the two new items N13/N14.

**Do not re-derive the constraint thresholds from the corpus.** They are clinical
goniometry norms on purpose (spec §0.16); fitting them to MediaPipe's own output
is precisely the circularity 0.5 existed to remove and no longer can.

| order | item | why it is next |
|---|---|---|
| **1** | **1.7** impose a skeleton via constrained IK (+S7) | **replaces dead 1.4**; supplies the pose-consistent skeleton and M9's scale reference. ⚠ **NOT with real MANO** — see N13 |
| **2** | **T1 / T2 retest** | the first honest re-test after attacking landmark quality at source |
| **3** | **R** reassess (owner decision point) | then Phase 3 (3.1 M7, now unblocked) or Phase 4 features |

**⚠ One owner decision is now outstanding, raised by 1.6's result (spec §0.17):
item 1.5 has no demonstrated consumer.** It was built to feed 1.6's gate; 1.6
measured that it should not be wired in, because M3a covers the *orientation*
failure class and M4 the *position* class and the two do not compose. 1.5 is not
disproven — its orientation signal is strong (92% coverage, 33.8× lift) — but
under A10 unconsumed code is a revert candidate. **Decide whether to keep it
pending an orientation-side consumer, or revert it.** Do not let it drift.

---

### Superseded: YOU ARE HERE (2026-08-03) — the M6 hand-off

**If you were working on M6 (item 2.3): STOP there — it is deprioritised, and
the audit CONFIRMED that verdict on corrected data.** Five attempts, all null;
the shipped `HandOrientationFilter` beat every one of them again on
identity-corrected streams. M6 cannot reach ~77% of the large orientation jumps
because those occur in *well-observed* frames — they are bad landmarks, not bad
pose filtering.

**Follow this order from here. Everything is in the table below.**

| order | item | why it is next |
|---|---|---|
| **1** | **1.5** M3a anatomical constraints (+S6) | the strongest published lever on the T1/T2 depth errors — measured as *halving* depth error; no longer blocked (1.4 is dead) |
| **2** | **1.6** M4 consistency gate (+S5) | rescoped: gates on consistency cues, not M2's dead residual. Anti-cascade rules are binding |
| **3** | **1.7** impose a skeleton via constrained IK (+S7) | **replaces dead 1.4**; supplies the pose-consistent skeleton, clean joint angles and M9's scale reference |
| **4** | **T1 / T2 retest** | the first honest re-test of back-of-hand + pitch crossing after attacking landmark quality at source |
| **5** | **R** reassess (owner decision point) | then Phase 3 (3.1 M7, now unblocked) or Phase 4 features |

Optional and parallelisable at any time: **0.4** (predictor eval harness, S1) and
**0.5** (offline oracle, S8). Neither blocks anything.

---

<!-- VERBATIM-END -->


---

# 2026-08-27 — rendering rebuilt and shipped; `T6`'s two estimators live-rejected

⭐ Two threads ran in one session. One shipped, one died. Full dossiers:
[`../../00_CORE/queue_notes/R1.md`](../../00_CORE/queue_notes/R1.md) and
[`../../00_CORE/queue_notes/T6.md`](../../00_CORE/queue_notes/T6.md).

## What shipped (`R1`)

`depth_order.py` — ONE occlusion rule for every object, per-landmark depth,
per-segment bone occlusion, a SOLID near-face occluder, landmarks in PRODUCTION for
the first time, `l`/`v` display toggles, the cube's depth anchored on the fingertip
barycentre, and a FREEZE damper for rotation AND translation at `RELEASE 60 /
FREEZE 1`.

## What died (`T6`)

Both orientation builds, live-rejected the day they were built — the axis
correction (*"discontinuities everywhere"*) and the owner's own halves 1+2
(*"much worse than panel 1"*). ⭐⭐ **The scores were GOOD**: halves 1+2 produced the
best yaw this project has measured (lean 27.2° → **8.6°**) and were rejected
anyway, because the per-frame orientation jump p95 went 12.6° → 30.3°. **The tail
decides the feel, every time.**

## ⭐⭐⭐ The method rules earned, and they generalise

1. **A corpus whose MOTION does not match the product's cannot validate an
   estimator for the product.** Every `T6` take is an OPEN hand holding a declared
   angle; the game GRIPS. Every offline score in that row was earned on a motion
   the product never performs. ⚠ The gap was named out loud before the first wiring
   and then not closed — twice. Sibling of `B4`.
2. **Measure the channel you are about to change, not the one that is easy.** The
   damper's first metric was per-frame axis WANDER on smooth instructed sweeps —
   the one motion that cannot make a gate chatter. It read "no jitter cost" for a
   build the owner rejected on sight.
3. **A good MEASURE is not automatically a good TRIGGER.** The Frobenius coherence
   separates still from slow-turning better than anything else tried, and still
   loses as a release test, because it answers "moving somehow" when the question
   is "moving how much".
4. **Ordering can be a defect.** The palm/back occlusion asymmetry was not
   MediaPipe's `z` — it was the cube taking its **x,y** from the fingertips and its
   **z** from the palm.

## ⚠ Mistakes worth not repeating

* A **verify FAIL was committed** once before being fixed. The suite is only worth
  running if a FAIL stops the commit.
* **Two claims retracted**: palm-forward fingertip `z` (an artifact of splitting a
  TWO-HAND take by a chirality-dependent cue — `U7`'s error class again) and the
  whole-hand depth-reversal hypothesis (refuted by a chirality check needing no
  ground truth).
* **Stripping code broke two PRE-EXISTING constants** unrelated to the removal.
  Restored verbatim from git. ⭐ When deleting a block, diff what left.
* Two dead subsystems were found **computing every frame with the result
  discarded**. Parking means removing the cost, not just the effect.

## ⭐ What `T6` gave the yaw question on its way out

The palm quad's own `z` spread measures **0.0658 m face-on and 0.0681 m at 90°** —
essentially constant, where it should run from ~0 to ~its own width. **Horn's `z`
input carries almost no yaw information at all.** That is the 24.9° finding by an
independent route, and the yaw lean remains UNFIXED.
