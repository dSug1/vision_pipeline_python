<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/HANDOFF_T6_ORIENTATION_FROM_2D.md lines 1140-1246
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 3. The fix

Today `palm_rotation.Horn` fits **3D↔3D**: the palm constellation against
MediaPipe's `world_landmarks`, depth included.

⭐ **Replace it with a 2D↔3D fit**: solve the pose that best **projects** a
canonical 3D palm onto the observed **pixel** landmarks. Predicted depth is then
never consumed at all.

This is what the current literature prescribes — *Monocular 3D Hand Pose
Estimation with Implicit Camera Alignment* (arXiv **2506.11133**) does exactly
this with a PnP formulation on MediaPipe 2D keypoints; *EPro-PnP* (arXiv
**2303.12787**) is the general end-to-end form. Depth ambiguity is the stated
motivation in both.

### 3.1 ⭐⭐ THE INTEGRATION POINT IS ALREADY THERE — this is not a re-plumbing

`palm_rotation.Horn` already has the right signature:

```python
def freeze(self, px, world)          # px is passed and currently IGNORED
def delta(self, state, px, world)    # same
```

Both call sites already pass pixels:

* `Resources/HandsTriggeredActions.py` — `_hand_rotation = palm_rotation.Horn(palm_rotation.PALM_LANDMARKS, "ref")`
* `LiveSnapDebug.py` — `PRODUCTION_ROTATION = _PRot.Horn(_PRot.PALM_LANDMARKS, "ref")`

⭐ **So T6 is a SIBLING CLASS behind the same interface** (e.g.
`palm_rotation.PlanarPnP`), swapped at those two lines. `palm_rotation.estimators()`
already exists as the A/B registry — add it there and every harness picks it up.

### 3.2 The model: five points, and we already own it

The fit needs only the **rigid palm**: `PALM_LANDMARKS = (0, 5, 9, 13, 17)` —
wrist + four MCPs.

⛔ **NO MANO. NO HaMeR. NO WiLoR.** They are licence-blocked (**N13**, binding —
the game will be commercialised). The papers use MANO; **we do not need it.** The
canonical palm's dimensions are **already in the codebase**:
`palm_depth.NOMINAL_SPAN_M` (added for 4.2) gives 5↔17, 0↔9, 0↔5, 0↔17 in metres.
Build the 3D model from those, in the palm plane.

### 3.3 ⭐ The planar ambiguity is ALREADY SOLVED HERE

A near-planar target has a two-fold pose ambiguity — a mirror flip about the line
of sight. This is expected, not a surprise, and both halves are handled:

* **IPPE** (Collins & Bartoli, IJCV 2014; `cv::SOLVEPNP_IPPE`) is built for planar
  targets and **returns BOTH solutions with their reprojection errors**.
* ⭐ **U7's geometric chirality is the disambiguator** —
  `palm_geometry.signed_palm_volume` / `geometric_chirality` is exactly a
  palm-front/palm-back decision, it is already live, and it was measured at
  **89.7%** even at track age 0 (vs the label's 76.8%).
* Temporal continuity is the tie-break of last resort.

⚠ This is also the "bas-relief / mirror hypothesis" parked as research under
**S11(c)** — it arrives here as a *solved* sub-problem, not a new one.

### 3.4 The camera model already exists

`palm_geometry.focal_px(frame_size)` and its documented `CAMERA_HFOV_DEG = 60.0`
assumption shipped with 4.2.

---

## 4. ⚠⚠ THE COSTS — read before starting

* ⛔ **THE PORT CONTRACT IS BINDING.** `palm_rotation`, `palm_geometry`,
  `palm_depth` etc. are **stdlib-only and numpy-free BY CONTRACT** so they can be
  transliterated to JS/Swift/Kotlin (**U3**). **`cv2.solvePnP` would break that.**
  IPPE's core is compact — a homography (DLT) plus a local analytic solve — and is
  implementable in stdlib. **Budget it, or the port debt is real.**
  ⛔ Do not quietly import cv2 into the client estimator layer.
  ⭐ Golden vectors BEFORE the port exists (**U3 precedent**, rule 6): write
  `analysis/verify_planar_pnp.py` with hand-checkable cases as you build.
* ⚠ **PnP NEEDS INTRINSICS, AND OURS ARE ASSUMED (60° FOV, never calibrated).**
  Focal-length error mostly corrupts the **out-of-plane** component — i.e.
  precisely yaw and pitch, the thing being fixed. ⭐ **This is the first hard
  technical reason for queue U12** (the start-of-game calibration step), which
  until now was only about grab reach. Measure the sensitivity: sweep the assumed
  FOV and see how much the axis error moves.
  ⭐⭐ **OWNER DECISION 2026-08-23 — NO CALIBRATION NOW, ANYWHERE, AND T6 MUST NOT
  INTRODUCE ONE**: *"make sure I do not need to recalibrate each time I run the
  debug or the production for the moment, nor on local pc nor on future web
  build. We will build the calibration by user at the beginning of the game later
  on."* So `CAMERA_HFOV_DEG = 60.0` stays a **compile-time constant** in
  `palm_geometry.py`, T6 reads the focal length **only** through
  `palm_geometry.focal_px()` (one source), and nothing prompts, persists, gates or
  blocks on a calibration in either tool or in the port. U12 will later *override*
  the default with one stored per-player number; it must never become required.
  ⭐ **AND THE SWEEP'S NUMBER IS OWED TO U12** (§9 step 7): a phone or laptop
  camera is **not** 60°, so the FOV sensitivity is exactly the **port risk for
  U3** — measuring it converts "the web build might read rotation wrong" from a
  worry into a figure, and tells U12 what a calibration step actually buys. Write
  the measured degrees-of-axis-error-per-degree-of-FOV-error into the **U12 row**
  when step 7 produces it.
* ⚠ **THIS IS NOT A RERUN OF 2.3.** Those five null attempts re-weighted the
  **fusion** of a bad signal. T6 replaces the **input**. Say so in any write-up so
  the history is not misread as a sixth attempt at the same thing.
* ⚠ **A10 APPLIES IN FULL.** It must beat Horn on **all three axes** AND not
  regress **jitter in real handling**. Jitter is the trap that killed the 9-point
  constellation (see §6).

---

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/HANDOFF_T6_ORIENTATION_FROM_2D.md lines 1374-1492
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 9. Suggested order of work

1. ✅ **DONE 2026-08-24 — the baseline reproduces to the digit** (14.5 / 1.13 /
   12.6 / 5.5 / 0.74 / 6.7 / 1.02 / 25.41). The instrument is trustworthy and this
   step's stop condition is cleared.
2. ✅ **DONE 2026-08-24 — `palm_rotation.canonical_palm()` + `analysis/verify_planar_pnp.py`
   §1, all green.** ⚠⚠ **BUT THIS STEP AS WRITTEN WAS UNDER-SPECIFIED, and a fresh
   session must not re-derive it the naive way**: `NOMINAL_SPAN_M` gives **four**
   distances while a planar 5-point model has **seven** shape DOF — 9 is
   under-constrained and **13 is not constrained at all** — and the tempting patch
   ("the MCPs lie on the 5→17 line") is provably inconsistent with |0-9| = |0-5|.
   ⭐ **Resolved by MEASURING the shape from the 2D pixel corpus** (59 sessions,
   2792 face-on frames) and keeping `NOMINAL_SPAN_M` as the **metric anchor plus an
   independent cross-check** — only the (5,17) breadth is shared, and the other
   three spans **agree to 10 mm**. ⭐ That 10 mm is comfortable rather than a defect
   because **a planar PnP's rotation is scale-free** (scale moves only the
   translation), which §5 of the golden vectors now pins.
   ⛔ **A face-on filter that is the exact opposite of one, kept so it is not
   re-tried**: `edge_on_measure >= 0.90` is |sin θ| *between the palm vectors*, so
   it PEAKS under length-foreshortening — a genuinely face-on palm scores ~**0.72**
   — and selecting on it reported the palm **45 mm too short**. Use "both spans
   within 5% of that session's own p99" instead: foreshortening only ever shortens.
3. ✅ **DONE 2026-08-24 — `Resources/planar_pnp.py`, stdlib and numpy-free;
   `verify_planar_pnp.py` §2 all green.** Recovers a known pose to **1e-6°** and
   **0 mm** across nine poses (face-on, yaw 30/60/75, pitch ±, roll, compound),
   returns **both** candidates sorted by reprojection error, and refuses degenerate
   input rather than guessing.
   ⭐ **THE ALGORITHM IS DELIBERATELY THE OLD, UNENCUMBERED ONE**: normalised DLT
   homography (Abdel-Aziz & Karara 1971; Hartley 1997) → Zhang-style decomposition
   (2000) → the classical planar twin `S·R·S` → Gauss-Newton on reprojection error.
   ⛔ **Not IPPE and not OpenCV** — decades-old prior art reaches the same two
   minima and keeps N13's licence question from ever arising. The Jacobi
   eigen-solver `palm_rotation` already needed was generalised to n×n and reused.
   ⭐⭐ **AND IT PRODUCED THE NUMBER STEP 6 WILL BE JUDGED ON. Conditioning vs tilt,
   400 draws at ±1 px** (medians):

   | palm tilt | out-of-plane err | in-plane (roll) err |
   |---|---|---|
   | 0° (face-on) | **7.0°** | 0.37° |
   | 10° | 4.6° | 0.43° |
   | 30° | 1.4° | 0.41° |
   | 60° | **0.71°** | 0.32° |
   | 75° | **0.60°** | 0.33° |

   ⭐ **Two pieces of good news for A10**: the defect T6 exists to fix lives at
   **60–90° of hand turn**, exactly where this is most accurate; and **ROLL is the
   in-plane component, flat-excellent at every tilt** — which is the axis Horn
   already gets right (gain 1.02) and A10 forbids regressing. ⚠ **The open risk is
   NEAR-FACE-ON handling** (p95 10–21° below ~30° of tilt) — that is the genuinely
   unobservable component there, not a defect, but it is **exactly what the jitter
   bar will measure**, and jitter is what killed the 9-point constellation. ⭐ If it
   bites, the house answer is already known: **suppress, do not guess** (DR-2, U8,
   4.2's decision 1), and B8 measured that **holding the last value beats every
   fit** — so hold the tilt at low tilt rather than inventing a better solver.
   ⛔⛔ **A MEASUREMENT-INSTRUMENT TRAP CAUGHT HERE, kept because it will recur**: an
   LCG (`1103515245·s+12345 mod 2^31`) was used as the noise source "for
   determinism". Its consecutive tuples lie on a lattice (Marsaglia) and this draws
   **ten values per frame**, so the noise was structured — reporting a p95 of
   **72°** at 60° tilt against a 0.67° median. **The tell was NON-MONOTONICITY**
   (fine at 45°, catastrophic at 60°, fine at 75°). Seeded Mersenne Twister is
   equally reproducible and actually distributed; the 72° became **1.6°**.
4. ✅ **DONE** — chirality at grab, temporal continuity through the hold.
   ⛔⛔ **THE CONVENTION CONSTANT WAS INVERTED, AND ONLY MEASUREMENT CAUGHT IT.**
   `BACK_TO_CAMERA_NZ_POSITIVE` reasoned out from the canonical model's own
   construction was **True**; the corpus says **False** — 9403 frames over 61
   sessions split **81.2% / 18.8%** the other way. Shipping the derived value would
   have inverted every rotation. This is §13.6.1's exact shape, caught this time.
   ⭐ **AND ONE PIECE OF MACHINERY TURNED OUT UNNECESSARY**: for a PLANAR model,
   mirroring the model is the same operation as flipping the pose, so `solve()`'s
   two candidates ALREADY span both hand chiralities. There is one binary, not two.
5. ✅ **DONE** — `palm_rotation.PlanarPnP`, in `estimators()`. Registering it
   immediately broke `verify_palm_rotation.py` §5b, and **the fixture was at fault,
   not the estimator**: it had an ORTHOGRAPHIC `px`, THUMB_CMC left at the ORIGIN
   (so chirality read garbage), and an invented palm shape. Every prior estimator
   ignored `px`, so none of it had ever been exercised. Fixture fixed; suite green.
6. ⛔⛔ **DONE — AND IT IS AN A10 REJECT. DO NOT PROCEED TO STEP 8.**

   | take | metric | Horn (ships) | PlanarPnP |
   |---|---|---|---|
   | yaw | mean-axis | **14.5°** | 19.6° |
   | yaw | **median/frame** | **13.0°** | **29.8°** |
   | yaw | gain | 1.13 | 1.15 |
   | pitch (2026-08-02) | mean-axis | **5.5°** | 12.7° |
   | pitch | median/frame | 20.2° | **11.0°** |
   | pitch | **gain** | 0.74 | **0.99** |

   ⭐ **THE ONE REAL WIN: pitch GAIN 0.74 → 0.99.** Pitch under-turning by 26% was
   a genuine defect and a 2D fit removes it. ⛔ **But yaw — the show-stopper — gets
   WORSE, and A10 requires all three axes.**

   ⚠⚠ **FOUR EXPLANATIONS WERE TESTED AND ALL FOUR ARE REFUTED.** Recorded so no
   one re-runs them:
   * **the planar degeneracy near edge-on** — no: PnP loses in **every** rotation
     band (40-60: 52.3 vs 27.6; 120-145: 29.5 vs 10.2), not just near 90°;
   * **twin-branch flips** — no: **12 flips in 508 frames**, and the error on a
     flip frame (27.9°) matches the error while held (29.9°);
   * **model shape mismatch** — no: this session measures **1.228** against the
     model's 1.280, and forcing the session's own shape moves 29.3° → **27.5°**;
   * **the assumed 60° FOV** — no: swept 30–120°, the best is **16.3° at 100°**
     (implausible for this webcam) and still loses to Horn's 13.0°.

   ⭐⭐ **AND THE PREMISE ITSELF NEEDS AN AMENDMENT, WHICH IS THE FINDING WORTH
   CARRYING.** T6 rested on *"the 2D landmarks are good; the predicted depth breaks
   the rotation."* The first half was an INFERENCE from roll being accurate — but
   roll was measured with **Horn over world landmarks**, so it never tested 2D
   alone. **T6 is the first direct test of a 2D-only pose, and it is worse.** The
   planar model is not the problem: reprojection RMS is **2.1–2.6 px median** on
   every take, which is the palm's own documented 2.76 mm rigidity (~3.1 px at
   0.5 m). So the model FITS — the residual is simply at the scale that, per §2.4's
   conditioning table, corrupts the out-of-plane component, and it is very likely
   **systematic** (the palm flexes with pose) rather than random.
7. ✅ **DONE — and it is the number owed to U12.** FOV sensitivity on the yaw take:
   **~2–4° of axis error per 10° of assumed-FOV error** in the 60–80° range
   (60°→29.8°, 70°→20.0°, 80°→18.2°). ⚠ That is large, and it is the **U3 port
   risk** in one figure: a phone front camera near 70–80° would read materially
   differently from this 60° assumption. Feed it into **U12**.
8. ⛔ **NOT REACHED — the call sites are UNCHANGED and production is untouched.**
   `PlanarPnP` stays in `estimators()` only, where it costs nothing and changes no
   behaviour, so a future attempt starts from working code rather than a rewrite.
<!-- VERBATIM-END -->
