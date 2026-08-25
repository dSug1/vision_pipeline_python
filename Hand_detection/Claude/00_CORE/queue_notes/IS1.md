# `IS1` — ⭐⭐ INPUT SYSTEM — the package boundary

> **Dossier.** The full, unedited history of this queue row.
> Its one-line status and its place in the order are in
> [`../QUEUE.md`](../QUEUE.md) — update **both** when it changes.
>
> **Status when this file was created (2026-08-25):** ✅ BUILT 2026-08-25. ⛔ NOT "shipped" until the owner's live look

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1245-1245
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
| **IS1** | ⭐⭐ **INPUT SYSTEM — the package boundary** | platform | ✅ **BUILT 2026-08-25. ⛔ NOT "shipped" until the owner's live look** | — | `handinput/` — a Unity-Input-System-shaped module so the hand pipeline can be lifted into another game, a browser build or a lens. Full record: `GESTURE_PIPELINE_SPEC.md` **§17**; usage: `handinput/README.md`. ⭐⭐ **THE ESTIMATOR MODULES WERE DELIBERATELY NOT MOVED into it**, and that is the row's one real decision: ~15 harnesses import them BARE off `sys.path` and dozens of documented paths in `Claude/*.md` name their location, so a move breaks working code and the project's own memory. Instead the property that matters — *the input system depends on nothing from the game* — is **asserted**: `analysis/verify_handinput.py` §1 parses every file's imports with the **AST** (not a grep: this codebase is mostly comments and a text search for `pygame` hits one) and fails on `CubeWindow`, `HandsTriggeredActions`, `pygame`, `cv2`, `mediapipe`, `numpy`… ⭐ **A folder gives tidiness; the test gives a guarantee.** The closure was checked, not assumed: the only non-local import in all nine modules is `math`. ⭐ `export_package.py <dir>` writes the standalone folder when it is actually wanted (**verified by running the export with no repo on the path**). ⭐ One shared-code fix rode along: `palm_geometry.palm_center_px` now has ONE definition — both tools' `_hand_position` delegate to it, as `_is_thumb_outward` already did, and §5 of the suite asserts the arithmetic is unchanged |
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

