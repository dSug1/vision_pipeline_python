# `IS2` — ⭐⭐ INPUT SYSTEM — conformance as DATA

> **Dossier.** The full, unedited history of this queue row.
> Its one-line status and its place in the order are in
> [`../QUEUE.md`](../QUEUE.md) — update **both** when it changes.
>
> **Status when this file was created (2026-08-25):** ✅ BUILT 2026-08-25

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1246-1246
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
| **IS2** | ⭐⭐ **INPUT SYSTEM — conformance as DATA** | platform | ✅ **BUILT 2026-08-25** | IS1 | `handinput/conformance/`: **vectors** (7 files, 64 cases — signs, chirality, projection round-trips, and the STATEFUL depth/rotation/coast sequences) and a **trace** (18 frames, 65 events walking enter → provisional chirality → ready → rule 3 refusal → armed exception → frozen depth → rotation reference → coast → sustained loss → re-entry). ⭐⭐ **WHY NOT A 26th `verify_*.py`**: those assert in Python, so they can only ever test the Python — **a port cannot run them**. As JSON they turn *"is the port faithful?"* into a test. Rule 6 taken one step further. ⭐ **The TRACE is worth more than the vectors**: it pins WHEN events fire (a held button does not re-fire; a coast cancels the pose but not the track; a dead track drops a rotation reference) — none of which any single-frame vector can catch. ⛔ **Regenerating to turn a red suite green destroys the only thing they are for**; a regeneration belongs in a commit that names the behaviour that changed. ⚠ Floats compare with a 1e-9 TOLERANCE, never equality — the first port bug this project caught was banker's rounding vs half-up |
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

