# `IS3` — ⭐⭐ INPUT SYSTEM — the action layer, wired into both tools as an OBSERVER

> **Dossier.** The full, unedited history of this queue row.
> Its one-line status and its place in the order are in
> [`../QUEUE.md`](../QUEUE.md) — update **both** when it changes.
>
> **Status when this file was created (2026-08-25):** ✅ BUILT 2026-08-25. ⛔ Owner's live take still owed

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1247-1247
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
| **IS3** | ⭐⭐ **INPUT SYSTEM — the action layer, wired into both tools as an OBSERVER** | platform | ✅ **BUILT 2026-08-25. ⛔ Owner's live take still owed** | IS1 | Five actions — `tracked`, `palm_pose`, `palm_facing`, `grab_ready`, `rotation_delta` — with Unity's five phases and `+=` events. ⚠⚠ **IT DRIVES NOTHING, AND THAT IS WHY IT COULD LAND IN ONE SESSION**: every value was already computed by the gesture logic that frame, so behaviour cannot change — `parity_replay` **NO DIVERGENCE** (454 frames), 24 existing suites pass, 95 new checks pass. ⭐ **It reports what RAN rather than recomputing it**, for the same reason `_record_flush` records the cue: four harnesses once reported CLEAN on takes the owner had just watched fail, every one of them a recomputation. ⛔⛔ **SCOPE — `grab_ready` IS ELIGIBILITY, NOT A GRAB.** Unity splits Input System from XR Interaction Toolkit; this is the first only, because "grab WHAT" needs a scene and answering it here welds the module to this game. ⭐ **THE FINDING THAT FELL OUT OF A REAL RECORDING**: replaying `2026-08-24_220415_prod_tau20` gives `tracked` **8** start/cancel pairs against `palm_pose`'s **9** — the extra one is a BRIDGE, where the hand is still held but the pose has stopped updating. Two states a consumer previously had no way to tell apart. ⚠ Live event traces: `HANDINPUT_TRACE=1` in either tool (a recording cannot produce `rotation_delta` — it stores the cube's smoothed orientation, never the hand's reading, and re-running Horn to fill that gap would make a recomputation the reference for a conformance file) |
<!-- VERBATIM-END -->

---

## Appended 2026-08-25 — ✅✅ SHIPPED

The owner ran the **debug tool and production back to back** and instructed
*"ship current build"*. Both sessions clean: MediaPipe loaded, identity locked on
both hands, tracks ended and were re-decided normally, the socket opened and
closed cleanly at both ends, no errors in either log.

Automated evidence unchanged and re-run the same day: **26/26** golden vector
suites, `verify_handinput.py` **96 checks**, `verify_hardening.py` **51 checks**,
`parity_replay` **NO DIVERGENCE** over 454 frames.

⚠ Status moved **BUILT → SHIPPED**. It rests on those two live sessions plus the
owner's instruction; if the HUD looked wrong on screen, revert this line first.

---

## ⛔ Appended 2026-08-26 — the wording above is SUPERSEDED (it could not be edited)

The block above describes the package as **"Unity-Input-System-shaped"** and as
having **"Unity's five phases"**. ⛔ **That wording is superseded.** The current
description, on owner instruction, is:

> **action-based input, in the style of OpenXR and Unity's Input System**

⚠ **The text above was NOT edited, and must not be** — it is inside a
`<!-- VERBATIM -->` block, byte-verified by
`_archive/migration/verify_split.py`. A pointer is the only correct remedy.

⭐ **Why the change, in one line:** the prior art is far older than Unity's
package (~2019) — **DirectInput action mapping (2000)**, **`UIGestureRecognizer`
(2010)**, **OpenXR's action system (2019, royalty-free by Khronos IP policy)** —
so naming OpenXR first is more accurate as well as safer. Unity's *code* is under
the Unity Companion License and was never copyable; architecture is not
copyrightable anyway (**CJEU C-406/10, SAS v. WPL**). Full reasoning:
[`../DECISIONS.md`](../DECISIONS.md) (2026-08-26) and
[`../../40_INPUT_SYSTEM/INDEX.md`](../../40_INPUT_SYSTEM/INDEX.md).
