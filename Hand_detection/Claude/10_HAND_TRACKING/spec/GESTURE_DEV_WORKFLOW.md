# HOW A NEW GESTURE GETS BUILT

> **live · the core discipline, and the four-stage workflow for any new gesture**
> **SOURCE** · `GESTURE_PIPELINE_SPEC.md` §2 + `PART_ONE.md` §8 — extracted verbatim, not edited

⭐ **Still current and still binding**, even though the pinch gesture it was
written for is archived. §2's *no heuristic pile-up* is restated in
[`../../00_CORE/METHOD.md`](../../00_CORE/METHOD.md).

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/GESTURE_PIPELINE_SPEC.md lines 64-80
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 2. Core discipline (governs everything below — read this even if skimming the rest)

- **No heuristic pile-up, ever.** If a trained classifier misclassifies
  something, the fix is (a) more/better labeled data covering that failure
  case as its own explicit class, or (b) reconsidering the feature set or
  model with literature backing — **never** a special-case rule bolted onto
  the classifier's output to patch one observed failure.
- **Every gesture goes through the same four stages below**, in order, no
  skipping. A gesture "seeming simple" is not a reason to shortcut this —
  pinch looked simple too.
- **Every design decision — which features, which model, which
  hyperparameters — must be justified by measured data from our own
  recordings, a cited state-of-the-art source, or both.** Never guessed.
  "Compare with state-of-the-art literature" is a required step, not an
  optional nicety — it's what previously surfaced the curl-angle feature,
  Otsu's method, and the AtaTouch closing-velocity precedent.

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1649-1707
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 8. General gesture classifier development workflow (apply to every future gesture)

Established while building pinch (§6–§7 are the worked example) — this is
now the standard procedure for adding **any** new gesture to §3's matrix,
not pinch-specific process notes. Four steps, always in this order:

1. **Record several automatic sessions**: the target gesture itself (cyclic
   gestures as repeated cycles per session, e.g. ×3, static poses as one
   held session — §7's convention), **plus several baseline/negative
   sessions** covering poses that could plausibly be confused with the
   target gesture. Which baselines to record is decided by step 2, not
   guessed — `fist` was recorded for pinch because the literature flagged
   it as the specific confusable pose, not because it seemed like a
   reasonable default. Use `RecordSession.py` (§7): timed/auto-stop, no
   keypress needed since both hands are busy performing the gesture.
   **Camera-in-front for now.** The same recording set gets repeated later
   with a forward/outward-facing camera once the project moves toward the
   glasses use case (Specification.md §12) — camera orientation is a
   variable to eventually test empirically, not assumed to transfer
   unchanged from the front-facing data. **Also record a baseline of the
   hand moving/rotating through varied orientations without performing the
   gesture** (§7.2's `rotating_hand` finding) — a static single-frame
   classifier is ambiguous under rotation almost by construction, and this
   is the cheapest single session to catch it early rather than live.
   **Cadence matters if the classifier will use velocity/timing at all**
   (§7.2): recording a cyclic gesture too fast (e.g. 3 reps in 4 seconds)
   makes genuine holds barely longer than incidental micro-movements,
   destroying exactly the timing signal a velocity feature needs — record
   deliberate, sustained reps unless the real target gesture is
   itself meant to be that fast.
2. **Benchmark the classifier strategy against state-of-the-art literature
   *before* computing anything.** As done for pinch (§6): what
   features/thresholds/algorithms do existing implementations and papers
   use for this gesture or a close analog? This is what surfaces the right
   feature set (e.g. §6's curl-angle vs. distance-ratio finding) and the
   specific confusable poses step 1 needs baselines for — the fist
   false-positive risk was *found* this way, not guessed after the fact.
   Don't skip straight to recording without it.
3. **Compute the classifier from the recorded data.** Derive thresholds
   empirically — Otsu's method for unlabeled bimodal cyclic-gesture data
   (§6.1), percentile-based margins where a clean min/max split doesn't
   exist, cross-validated against the negative baselines with *actually
   measured* false-positive counts, not assumed ones. `AnalyzeRecordings.py`
   (§7) is the reference implementation for pinch; extend it (or add a
   parallel analysis script) for each new gesture using the same method,
   not a different ad-hoc one each time.
4. **Live debug tool.** Run the camera live and display "gesture X
   detected" in real time (`LiveGestureDebug.py`) before wiring the
   classifier into the actual grab/release pipeline (matrix row #3+). This
   is the step that catches what a small recorded dataset can't — e.g. the
   `open_hand` false-positive gap (§6.1) was only found by running the
   finalized classifier back over the recordings as a sanity check; a live
   tool makes that kind of check immediate and visual instead of a
   one-off script run.

Don't skip a step because a gesture "seems simple" — pinch looked simple
too. Step 4 in particular is what catches what steps 1–3 miss on a small
dataset; treat thresholds from steps 1–3 as a starting point for step 4's
live tuning, not a final answer.
<!-- VERBATIM-END -->
