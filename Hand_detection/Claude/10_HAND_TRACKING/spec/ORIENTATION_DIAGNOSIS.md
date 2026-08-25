# THE YAW LEAN — the defect and its cause

> **live · the open show-stopper, and what is proven about it**
> **SOURCE** · `HANDOFF_T6_ORIENTATION_FROM_2D.md` §1–§2 — extracted verbatim, not edited

⭐⭐ **THE DIAGNOSIS BELOW STILL STANDS. THE REMEDY IT WAS WRITTEN FOR DOES
NOT** — T6 was built and A10-rejected on 2026-08-24, and the file's own banner
says so. ⚠⚠ One amendment the banner records: the premise *"the 2D landmarks
are good"* was an **inference from roll**, and roll was measured with Horn over
**world** landmarks — T6 was the first direct test of 2D-only pose and it was
worse. ⛔ Before proposing anything here, read
[`../REJECTED.md`](../REJECTED.md) and
[`../history/T6_INVESTIGATION_LOG.md`](../history/T6_INVESTIGATION_LOG.md)
§2.0.4.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/HANDOFF_T6_ORIENTATION_FROM_2D.md lines 1-104
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
# HANDOFF — T6: orientation from 2D, not from predicted depth

> **Owner, 2026-08-23:** *"I want to implement the fix before anything else is
> built."* — and, on the defect itself: *"this is a show-stopper for me as I can't
> tolerate a cube which rotates differently than what it should to reflect the
> physical world."*

⭐ **This file is a COMPLETE brief. A new conversation should be able to read this
one file plus the four sections it names and start implementing.** It is a
handoff, not a source of record: the record is `GESTURE_PIPELINE_SPEC.md`
§14.3.4.7 → §14.3.4.11 and the queue's **T6** row.

---

# ⛔⛔⛔ CLOSED (2026-08-24) — T6 IS REJECTED. KEEP THIS FILE FOR ITS **DIAGNOSIS**, NOT ITS REMEDY.

> **Owner, after four live T6d sessions:** *"the anisotropic fit bring very minor
> improvement and I don't want to ship it."*

**FIVE ARMS WERE BUILT AND ALL FIVE FAILED**: planar PnP, the 6-point thumb model,
the world-z gate, the trustworthy-halves rebuild, and T6d's anisotropic 2×2 (the
first four on A10, the fifth on the owner's feel test).

⭐⭐ **NOTHING HAD TO BE REVERTED, AND THAT IS THE PROCESS RESULT WORTH CARRYING.**
Every arm lived in `palm_rotation.estimators()` and in the debug tool behind a toggle
that was **measured byte-identical to shipped Horn** (975/975 and 1084/1084 replayed
frames). Production never ran a line of it. **A rejected experiment cost one flag
flip, not a revert** — compare `POSTMORTEM_4_1_IDENTITY_MIGRATION.md`, where the same
volume of work had to be unpicked from live code.

⭐ **WHAT SURVIVES AND IS STILL THE BEST ACCOUNT OF THE DEFECT** — §2.0 through
§2.0.16. MediaPipe reports a physically face-on palm as **24.9° tilted** (61 sessions,
3131 pixel-verified frames); its world **x,y are faithful** (1.1° against the pixels'
1.2°) and only **z is fabricated**; it gets the tilt **BEARING** right (median 10.6°
vs 45° for chance) and only the **MAGNITUDE** wrong. That is a fact about the
detector, not about any of the five remedies.

⭐ **AND ONE MEASUREMENT WORTH REUSING**: ψ, the compression direction read in the
canonical palm's own frame, cleanly separates the two motions from pixels alone — a
yaw take piles up at ψ≈0/180 (61% of frames) and a pitch take at ψ≈90 (85%). ⛔ Two
port traps recorded with it: the textbook eigenvector row collapses to noise at
exactly pure yaw and pure pitch (use `½·atan2(2b, a−c)`), and `sin2ψ` is
chirality-ODD while `cos2ψ` is not.

⛔ **WHY IT WAS INVISIBLE, MEASURED**: across 3553 frames of a two-panel A/B the
shipped and rebuilt cubes differ by a median of **4.83°** (p90 17.4°), and that is
**flat across every palm-tilt band**. ~5° on a 40–80 px cube is below what an eye
resolves. ⭐⭐ **The instrument lesson is the transferable part: "I can't see a
difference" and "there is no difference" are different claims, and only a number
separates them.**

⚠⚠ **THE DIRECTION IS SUPERSEDED, NOT MERELY REJECTED.** The owner's next build
(`F1`) drives the cube's whole transform from the **fingertips**, with the palm
demoted to a support role — so the question T6 was answering ("how do we make the
palm-only estimator's tilt correct?") is no longer the question being asked.

⚠ **T6d IS REMOVED FROM `LiveSnapDebug.py`** — sliders, HUD, presets, A/B rig,
recorder fields and the wireframe ghost. The estimator survives in
`palm_rotation.py` only because `analysis/t5i_zscale_sweep.py` and `t5j_roll_axis.py`
drive it. **Nothing live reads it.**

⭐ **The four live sessions are on E:** `2026-08-24_202454_t6d_psi_sweep`,
`_203927_t6d_ab_before_after`, `_204928_..._b`, `_205729_t6d_ab_ghost`. Their
per-frame ψ/ratio data is still the only intermediate-ψ coverage the corpus has, if
that question is ever reopened.

---

## 1. The defect, in the owner's terms

When the hand turns like a page (yaw about the vertical), the object **does not
turn purely about the vertical — it LEANS as it turns**:

| hand turned | object tipped out of upright |
|---|---|
| 20° | 6.8° |
| 40° | 12.3° |
| 60° | 21.9° |
| **60–90°** | **26.8°** (p90 32.2°) |

⚠⚠ **ALWAYS STATE IT THIS WAY, NEVER AS "13° of axis deviation".** They are the
same fact. The degrees-of-axis framing is why an earlier pass recommended
*accepting* it — the number sounds minor and the visible effect is not.
⭐ The rotation **amount** is fine (gain 1.13). It is the **uprightness** that fails.

---

## 2. The cause is PROVEN, not suspected — two independent routes

| axis | mean-axis error | gain | uses MediaPipe's world z? |
|---|---|---|---|
| **ROLL** | **6.7°** | **1.02** | ⭐ **NO** — pure image plane |
| YAW | 14.5° | 1.13 (over-turns) | yes |
| PITCH | 5.5° | 0.74 (under-turns) | yes |

1. **The axis that never touches depth is the accurate one**, and the two that do
   are wrong in **opposite** directions (§14.3.4.10).
2. **Scaling world z by `k` slides the yaw tilt smoothly 14.5° → 0.6°** (§14.3.4.9).

⭐ **Everything code-side is therefore EXONERATED**: the Horn fit (exact to 0.000°
on synthetic input), the quaternion maths, the frame conventions, the mirror, the
renderer. Roll exercises all of them and comes out right. **MediaPipe's 2D
landmarks are good; its predicted depth breaks the rotation.**

<!-- VERBATIM-END -->
