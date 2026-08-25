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
| **Down-weighting MediaPipe's world z (`k`)** | ⛔ **REJECTED 2026-08-23** — the `k` that makes yaw good **doubles** the pitch error. Yaw and pitch need **opposite** things from the same coordinate, which closes the whole *"weight z less"* family (cf. `2.3`'s five nulls). ⭐ It DID establish the diagnosis: the tilt is caused by world-z error |
| **The 9-point palm+tips constellation** | ⛔ **A10 REJECT 2026-08-23** — +1.4° of axis fidelity for **+4.9° of p95 jitter** in real handling. Its *"wins in every take"* reputation rested on the axis-**contaminated** 2026-08-04 yaw take |
| **"Fix the Horn fit"** | ⛔ Horn is **exact** — 0.000° on synthetic input. Do not touch it |
| **Quaternion UKF / anisotropic covariance** (`2.3`) | ⛔ **5 attempts, all null**; audited and confirmed genuine on corrected streams |
| **B8 — optimising the quadratic** | ⛔ every fit **loses to "hold the last value"** |
| **B7 — the confirmation gate** | ⛔ park **confirmed under a blind test** — measurable but invisible |
| **The predictive / reliability-weighted orientation filter** | ⛔ **REMOVED 2026-08-24 as DEAD CODE, not as a failure** — a real fix for the Gram-Schmidt estimator it was built against (max 144° single-frame excursions), but Horn has replaced its output since 2026-08-17 on **9091/9091** measured hand-frames. Archived whole in `Resources/_archived_predictive_orientation_filter.py`. ⚠ `_reliability_alpha` was **kept** — different thing, still drives the conditioning readout |
| **A fixed PER-FRAME rotation smoothing factor** | ⛔ **REPLACED 2026-08-24 by a time constant.** 0.35/frame = 2.32 frames of settling, so the feel moved with the camera: **111 ms in good light, 149 ms in poor**. ⭐ The frame rate was proved **camera-bound, not compute-bound** — the inter-frame gap is identical with and without a hand in view |
| **A physical card held in the hand to steady a yaw take** | ⚠ controls the **sweep** well (best contamination score ever measured) but reads the **tilt higher** (17–19° vs the card-free 12.6–13.0°). Keep it for cleanliness, never for axis magnitude |
| **The mirror, the frame convention, hand anatomy, constellation degeneracy** | ⛔ all eliminated **by control** as causes of the yaw lean |

⭐ Where four rejects leave the yaw lean: **Horn's flaw is BIAS** (it consumes a
fabricated z) **and every per-frame replacement's flaw is VARIANCE.** Full
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
