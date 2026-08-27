# ⛔ TRIED AND REJECTED — do not re-propose without new evidence

> **STATUS** · live · **OWNS** · everything that was built or tested and lost
> **READ IF** · you are about to propose a fix to rotation, chirality, ownership,
> identity, smoothing or the play area — i.e. almost always
> **LAST VERIFIED** · 2026-08-25
> **SOURCED FROM** · the old `README.md` §4, plus `T6`/`T6d`/`L1`/`B4`/`B7`/`B8`
> dossiers in [`../00_CORE/queue_notes/`](../00_CORE/queue_notes/)

⭐ **This is the highest-value page in the folder per token.** Every entry was
**measured**, not guessed. Several were overturned twice, which is why the
retractions are kept rather than deleted.

---

## Rotation and orientation

| what | verdict |
|---|---|
| **T6 — orientation from 2D (planar PnP)** | ⛔⛔ **BUILT AND A10-REJECTED 2026-08-24.** Yaw — the defect it existed to fix — gets **worse** (median/frame 13.0° → 29.8°); pitch **gain is fixed** (0.74 → 0.99). Four explanations tested and all refuted: the edge-on planar degeneracy, twin-branch flips, model shape, and the assumed FOV. ⭐ **It amends the project's own premise**: *"the 2D landmarks are good"* was an inference from roll, and roll was measured with Horn over **world** landmarks — T6 is the first direct test of 2D-only pose and it is worse. Code stays in `estimators()`; call sites unchanged |
| **T6d — the anisotropic 2×2 fit** `g(ψ) = a + b·cos2ψ + c·sin2ψ` | ⛔⛔ **BUILT, LIVE-TESTED OVER FOUR SESSIONS, OWNER-REJECTED 2026-08-24** — *"very minor improvement and I don't want to ship it"*. ⭐ **Nothing to revert: production never ran it**, every arm sat behind a toggle measured byte-identical to shipped Horn (975/975 frames). The measured reason it was invisible: the two A/B panels' cube orientations differ by a median of **4.83°** (p90 17.4), **flat across every palm-tilt band** — below what an eye resolves on a 40–80 px cube. ⚠ The ψ finding survives as a fact about MediaPipe, not as a fix |
| **`palm_slant_axis` — steer Horn's AXIS by the palm's foreshortening** | ⛔⛔ **BUILT, LIVE-TESTED, OWNER-REJECTED 2026-08-27** — *"the feel is very bad. there is no consistency in the rotation axis, discontinuities everywhere"*. ⭐ It SCORED well: yaw lean 22.0° → 13.6°, pitch 14.8° → 10.0°. ⛔ The metric was wrong — per-frame axis WANDER measured on smooth instructed SWEEPS, which is the one motion that cannot make a gate chatter. On the owner's own grabbing take: **114 gate toggles**, jolt p95 29.7°, and per-frame axis jump p95 **1.90x** shipped Horn while the MEDIAN improved. ⚠ Replacing both hard gates with one geometric fade cut the jolt in half and moved the felt defect barely at all (1.90x → 1.84x); a time-constant sweep found **no tau** that keeps the lean fix without adding jitter. Nothing to revert — gain defaults 0 and production never constructed it |
| **`palm_slant_pose` — the owner's own strategy: the six-take regression + a canonical frozen at grab** | ⛔⛔ **BUILT WHOLE, LIVE-TESTED, OWNER-REJECTED 2026-08-27** — *"panels 2 and 3 are much worse than panel 1: the rotation does not follow a coherent axis, lot of jumps, lot of jitter"*, on BOTH the palm and the finger feature set. ⭐⭐ It produced **the best yaw number this row has ever measured — lean 27.2° → 8.6°** — and was still rejected, because per-frame orientation jump p95 went 12.6° → 30.3° (**2.4x**). ⚠ Median jump IMPROVED (2.98 → 2.41): smoother most of the time, occasionally much worse. **The tail decides the feel, every time.** ⛔ Partial blend is measured HARMFUL (yaw 53.7° at 50% vs 27.2° at 0 and 8.6° at 100): slerping two orientations that disagree lands worse than either end |
| **Down-weighting MediaPipe's world z (`k`)** | ⛔ **REJECTED 2026-08-23** — the `k` that makes yaw good **doubles** the pitch error. Yaw and pitch need **opposite** things from the same coordinate, which closes the whole *"weight z less"* family (cf. `2.3`'s five nulls). ⭐ It DID establish the diagnosis: the tilt is caused by world-z error |
| **The 9-point palm+tips constellation** | ⛔ **A10 REJECT 2026-08-23** — +1.4° of axis fidelity for **+4.9° of p95 jitter** in real handling. Its *"wins in every take"* reputation rested on the axis-**contaminated** 2026-08-04 yaw take |
| **"Fix the Horn fit"** | ⛔ Horn is **exact** — 0.000° on synthetic input. Do not touch it |
| **Quaternion UKF / anisotropic covariance** (`2.3`) | ⛔ **5 attempts, all null**; audited and confirmed genuine on corrected streams |
| **B8 — optimising the quadratic** | ⛔ every fit **loses to "hold the last value"** |
| **B7 — the confirmation gate** | ⛔ park **confirmed under a blind test** — measurable but invisible |
| **The predictive / reliability-weighted orientation filter** | ⛔ **REMOVED 2026-08-24 as DEAD CODE, not as a failure** — a real fix for the Gram-Schmidt estimator it was built against (max 144° single-frame excursions), but Horn has replaced its output since 2026-08-17 on **9091/9091** measured hand-frames. Archived whole in `Resources/_archived_predictive_orientation_filter.py`. ⚠ `_reliability_alpha` was **kept** — different thing, still drives the conditioning readout |
| **Damping the cube's jitter with a longer or ADAPTIVE tau** | ⛔⛔ **BUILT, LIVE-TESTED, OWNER-REJECTED 2026-08-27.** ⭐ The lesson in one line: **DAMPING IS NOT STILLNESS** — even at 4500 ms of extra tau the blend factor is 0.015, so the cube still creeps 1.5% of the gap every frame and wanders over a long hold. An adaptive tau with a fast-attack speed ENVELOPE was built to protect the onset and was rejected too (*"did not dampen as much as previously"*): the envelope was **triggered by noise** — the raw target exceeds 160 deg/s on **5.4% of frames with the hand still** — and each spike released the damping for ~350 ms, cutting full damping from 88.6% to 80.3% of frames. ⚠ Fixing the decay rate recovered it, but the whole approach lost to a hard FREEZE and was stripped. What ships: factor exactly **0.0** below the threshold |
| **A 2-frame freeze trigger** | ⛔ owner: *"makes the rotation jerky"*, and measured on their own take — slow-turn following **77.6% → 58.9%** for 1.3 points of stillness. ⭐ 1 frame ships; the slider is capped at 2 so the rejected setting cannot be reached by accident |
| **A directional-COHERENCE gate on the freeze trigger** (per-landmark sign vote, then the owner's whole-hand matrix form) | ⛔⛔ **BUILT TWICE, REMOVED TWICE 2026-08-27.** ⭐ The Frobenius correlation `<D1,D2>/(||D1|| ||D2||)` over frames N,N+1,N+2 is a genuinely good MEASURE — still **-0.26** vs slow turn **+0.54**, and a still hand reads NEGATIVE because consecutive noise steps anti-correlate, giving it a principled ZERO threshold where the per-landmark vote needed a tuned 0.6. ⛔ It is a bad **TRIGGER**, and that is a property of the question: **coherence says the hand is moving SOMEHOW; the freeze needs to know HOW MUCH.** A drifting still hand is coherent; a hand pausing mid-turn is not. On 6038 frames of natural use it cost **7-11 points of slow-turn following for ~1 point of stillness**, in BOTH the AND form (which can only reduce releases, so it cannot help the slow case by construction) and an OR form. ⚠ Two weaker relatives measured at the same time: the rank/subspace energy (Tomasi & Kanade 1992) at **0.33** separation and the rigid residual (Kabsch 1976) at **0.12** — both far worse than either coherence form, and they are the obvious things to try next. All four stay comparable in `analysis/global_coherence.py` |
| **Per-landmark `z` as a whole-hand DEPTH REVERSAL** | ⛔ hypothesis tested and **REFUTED 2026-08-27** (`analysis/z_depth_flip.py`). Geometric chirality is **100% consistent across palm and back frames** of the same hand in both single-hand takes, and a depth reversal would flip it. ⭐ The harness needs no ground truth — a hand cannot change chirality. ⚠ The claim it was testing ("MediaPipe puts palm-forward fingertips on the wrong side of z") was ALSO retracted: it came from a TWO-HAND take split by `signed_palm_area`, whose sign is chirality-dependent, so the split was really side XOR handedness — `U7`'s error class committed again |
| **A fixed PER-FRAME rotation smoothing factor** | ⛔ **REPLACED 2026-08-24 by a time constant.** 0.35/frame = 2.32 frames of settling, so the feel moved with the camera: **111 ms in good light, 149 ms in poor**. ⭐ The frame rate was proved **camera-bound, not compute-bound** — the inter-frame gap is identical with and without a hand in view |
| **A physical card held in the hand to steady a yaw take** | ⚠ controls the **sweep** well (best contamination score ever measured) but reads the **tilt higher** (17–19° vs the card-free 12.6–13.0°). Keep it for cleanliness, never for axis magnitude |
| **The mirror, the frame convention, hand anatomy, constellation degeneracy** | ⛔ all eliminated **by control** as causes of the yaw lean |

⭐⭐ **WHERE SIX REJECTS NOW LEAVE THE YAW LEAN, and the pattern is the whole
lesson: Horn's flaw is BIAS** (it consumes a fabricated z) **and every per-frame
replacement's flaw is VARIANCE.** Three separate 2-D-shape estimators have now
scored BETTER on the lean and WORSE on the tail, and the tail has won the verdict
every time. ⛔ **A fourth attempt of this shape should not be proposed** unless it
first demonstrates a per-frame orientation jump at or under shipped Horn's on a
GRABBING take — the lean number is not the gate and never was. Full
argument: [`history/T6_INVESTIGATION_LOG.md`](history/T6_INVESTIGATION_LOG.md) §2.0.4.

## Identity, chirality and ownership

| what | verdict |
|---|---|
| **Ownership keyed on the handedness label** | ⛔ **replaced 2026-08-22** by the stable track id. Live A/B over 3 sessions: the label orphaned a held cube 794 / 377 / 15 frames; the track, 0 every time |
| **T3 client-side ownership transfer** | ⛔ built, live-tested, **REVERTED** — it inferred "same hand" from **position**, and two hands in the same place are indistinguishable by position, which is exactly what occlusion is. Re-pointed at the track id, then fixed narrowly instead |
| **`4.1`'s full trackId ownership migration** | ⛔ built, patched **five times**, **reverted** by the owner. `TRACK_OWNERSHIP = False`; nothing deleted. See [`history/POSTMORTEM_4_1_IDENTITY_MIGRATION.md`](history/POSTMORTEM_4_1_IDENTITY_MIGRATION.md) before any wider attempt |
| **Post-hoc `invert_x` mirroring** | ⛔ **falsified 2026-08-22** — MediaPipe is **not mirror-equivariant** (7.7–10 mm, 12–20°). Replaced by flipping the frame **before** detection |
| **A thumb-plane-thickness gate on chirality** | ⛔ **measured null, not shipped** — sweeping 0→7 mm changed nothing to 5 mm and was *worse* at 3–5 mm; at the production failure the bad frames sat at 11–16 mm, **above** the 8.8 mm median |
| **Falling back to the handedness label while chirality is unconfirmed** | ⛔ **measured backwards** — at track age 0, geometry is **89.7%** and the label **76.8%**. The label is worst exactly at hand entry |
| **Temporal voting to fix a new hand's chirality** | ⛔ **cannot work** — the wrong value was stable for **5 consecutive** frames, so any majority picks it |
| **Resolving a two-hand chirality contradiction by trusting one hand** | ⛔ **near chance** — the contradiction is real (191 of 14460 two-hand frames) but trust-the-older is 46.6%, squarer 53.4%, thicker 63.9%. **Detection yes, resolution no — suppress, do not guess** |
| **N11 left/right asymmetry** | ⛔ **not reproduced**; direction reversed on clean takes |

## Manipulation and gameplay

| what | verdict |
|---|---|
| **A hand-side TRIGGER to keep an object off the display edge** | ⛔ **built twice, reverted twice** — translation is grab-relative, so the object keeps its own offset and creeps outward on every grab-push-drop cycle. **A trigger cannot enforce an invariant**; `U9` ships a positional clamp instead |
| **An ADAPTIVE edge margin (half the CURRENT palm width)** | ⛔ **failed live** — the measured width collapsed 45% in **one frame**, the margin collapsed with it, and the object was carried out of frame. **A threshold must not be computed from a quantity that is noisy where the threshold acts** |
| **A depth calibration screen (min/max reach)** | ⛔ **not needed** — absolute scale is unobservable **and cancels** in the ratio form; `d0` is captured per grab; the envelope is already 3.59× |
| **D4 grace period before release** | ⛔ **DECLINED** by the owner after seeing D2/D3 live. Not deferred — answered |

## Whole directions

| what | verdict |
|---|---|
| **Pinch classification** | archived 2026-08-01 after Stage 4 live testing; the project pivoted to snap / rotate / release. Corpus, code and weights kept |
| **Rule-based (hand-tuned threshold) gesture rules** | abandoned 2026-07-30 — false positives 38.5% of the time under rotation, at >97% MediaPipe confidence. A structural limit, not a tuning problem |
| **MediaPipe's built-in `Open_Palm` / `Closed_Fist`** | live-tested unreliable across hand positions, **reverted** |
| **M2 bone-length calibration** (`1.4`) | ⛔ **DEAD**, audited and upheld — `worldLandmarks` do not encode a pose-consistent skeleton (0/21 bones inside target) |
| **`1.7` imposed skeleton** | built, then **parked** — cannot affect orientation *by construction* |
| **MANO / HaMeR / WiLoR** (`0.5`) | ⛔ **licence** — non-commercial, and the game will be commercialised (`N13`, binding) |
| **§16.14's "SINK" metric** | ⛔ **RETRACTED** — the metric was self-measuring |
| **Collapsing production and the debug tool into one pipeline** (`U6`) | ⛔ **closed by owner decision 2026-08-22** — two are kept; divergence is prevented by `parity_replay.py` instead |

---

⚠ **Retractions stay.** When a spec section contradicts a later one, **the later
one wins** — check for a `14.3.x`-style follow-up before acting on anything old.
