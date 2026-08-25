<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1-61
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
# Part One — gesture/pattern recognition design & matrix

> ⭐ **§3.1 IS THE SINGLE BUILD QUEUE FOR THE WHOLE PROJECT.** If you are here to
> find out what to build next, go to §3.1's "YOU ARE HERE" block. For the map of
> everything else — architecture, what was rejected, which file answers what —
> read `README.md` first.

> **⚠ Gesture set changed again (2026-08-01): read `GESTURE_PIPELINE_SPEC.md`
> §13 first.** After §6-§8's rule-based pinch attempt was abandoned
> (2026-07-30, see the original banner text preserved below) and a
> subsequently *trained* pinch classifier was built, fixed repeatedly, and
> finally live-validated (`GESTURE_PIPELINE_SPEC.md` §12, through §12.7),
> **Stage 4 live testing found pinch still missed too many real
> grabs/releases (worse off `front`) and had a perceptible input lag** —
> a real, live-observed UX problem, not just an offline metric. **Pinch is
> now archived** (code/corpus/weights kept, not deleted — reusable if
> revisited later). **New primary gesture set (§13 of the pipeline spec
> has the full design + state-of-the-art check): proximity-based object
> snapping (replaces pinch-triggered grab), open-palm rotation, closed-fist
> release.** The matrix in §3 below has been updated accordingly — rows
> 2-4 (trigger/grab/release) now describe the new gestures; rows 1, 5, 7
> (scaffolding, translation, rotation) mostly reuse their prior design,
> just with the new trigger signal swapped in; row 6 (depth-proxy
> scale/color) is dropped for now, not carried forward automatically.
> §2's core architecture decisions (sticky grab, shared-registry
> arbitration, image-space translation, depth-proxy-not-raw-`z`,
> quaternion rotation) are **unchanged and still apply** — only the
> *trigger* gestures changed, not the manipulation architecture around
> them.
>
> **Update (2026-08-01, later conversation): open-palm/closed-fist
> detection (row 2) is now PARKED**, not being pursued for the moment —
> so "open-palm rotation, closed-fist release" above is historical intent,
> not the current plan. Rotation is permanently ungated; release now
> relies on tracking-loss plus a new hand-open-quick-release gesture
> (§3 row 4, `GESTURE_PIPELINE_SPEC.md` §14.2) instead of `Closed_Fist`.
>
> **Original 2026-07-30 banner, preserved for context**: §6–§8 below
> document a **rule-based (hand-tuned threshold) pinch classifier that was
> built, tested, and then abandoned** — it worked for the hand orientation
> it was calibrated on, but a state-of-the-art literature check plus
> reproducible live/recorded evidence showed it could not be fixed without
> either endless heuristic patching (rejected — not backed by literature,
> doesn't generalize) or a fundamentally different approach. That
> different approach — labeled recording, a *trained* classifier instead
> of hand-picked thresholds, and a live debug tool, run identically for
> every future gesture — is specified in `GESTURE_PIPELINE_SPEC.md`
> (still the active methodology spec for any gesture that ends up needing
> custom training). Every file the rule-based attempt produced
> (`GestureRules.py`, `AnalyzeRecordings.py`,
> `ValidateWindowedClassifier.py`, `LiveGestureDebug.py`,
> `debug_gestures.bat`) and every old recording have been deleted — §6–§8
> are kept below **only** as the evidence trail for why, not as a
> description of current code.

Implements §7 of `Specification.md`: Pipeline A gesture recognition, developed
on PC against the existing Python MediaPipe pipeline. This file is the living
design reference for Part One's gesture vocabulary — **the matrix in §3 below
is meant to be enriched** as new gestures/objects are added; keep it in sync
with the classifier code as it's built (see `GESTURE_PIPELINE_SPEC.md` for how).

<!-- VERBATIM-END -->
