# PART ONE — the pinch classifier's design basis, verbatim

> **history · the 2026-07-30 state-of-the-art check and its derived result**
> **SOURCE** · `PART_ONE.md` §6–§6.1 — extracted verbatim, not edited

⛔ The rule-based approach documented here was **abandoned**; pinch itself was
archived 2026-08-01. Kept as the evidence trail for why.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1378-1468
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 6. Pinch classifier design basis (state-of-the-art check, 2026-07-30)

*(§6–§8: historical record of the abandoned rule-based approach — see the
banner at the top of this file. Kept for the evidence trail, not as a
description of current code.)*

Researched before building, since a naive single-distance threshold is not
what production implementations actually use. Findings, and how they shape
the design:

- **Distance alone false-positives on a fist.** Common practice (e.g.
  MediaPipe-based tutorials, GRLib) checks `distance(thumb_tip, index_tip)`
  **and** confirms the other three fingertips are *not* also curled in
  (middle/ring/pinky tips below their MCP joints) — otherwise a closed fist
  reads as a pinch too, since thumb and index end up close together there
  as well. Folded into row #2's detection logic above as a required
  conjunct, not an optional refinement.
- **Ratio-normalize by a hand-size reference**, not a raw distance — this
  is the single biggest accuracy lever per Specification.md §6, and it's
  also what makes the classifier resolution/distance-independent, which is
  the whole point of moving off pixels (§1).
- **A learned classifier (small MLP / SVM / XGBoost on landmark-derived
  features, or MediaPipe's own embedding+classification-head architecture)
  is the state-of-the-art direction for larger gesture vocabularies**, and
  several papers report strong results this way. Not adopted now —
  Specification.md §7.1 already recommends starting rule-based and only
  reaching for a learned model if rules prove insufficient, and nothing
  here contradicts that. But recording full labeled landmark data (§7),
  not just derived ratios, means today's sessions could train a small
  classifier later with **no recapture needed** if rules turn out
  insufficient — free optionality, not a plan change.
- **DTW/HMM/sliding-window+LSTM are for genuinely dynamic gestures**
  (swipe, twist trajectories), not a static pose like pinch. Confirms
  rather than changes the matrix's existing plan (row #7's dynamic
  gestures already deferred, sliding-window only if static rules prove
  insufficient — Specification.md §7.1).
- **4–6 landmarks is enough** per several papers — matches row #2 above
  (thumb tip, index tip, wrist, middle MCP, plus the three other
  fingers' MCP/PIP/tip for the uncurl check — nowhere near all 21 points).
- **Curl is a joint angle, not a wrist-relative distance ratio** — refined
  after an XR-SDK literature check (Meta Horizon OS, Unity XR Hands):
  production hand-tracking curl features use the angle at the PIP joint
  (`angle(MCP→PIP, PIP→tip)`, small = straight, large = curled), not a
  `distance(wrist, tip) / distance(wrist, MCP)` ratio. `GestureRules.py`
  implements both (`finger_curl_angle_deg`, `finger_extension_ratio`) so
  the analysis script could compare them empirically rather than assuming
  which is better — see §7's result.
- **Otsu's method (Otsu, 1979)** — a standard automatic-thresholding
  algorithm from image binarization, generalized here to any 1D bimodal
  distribution — is the principled way to split `pinch_x3`'s frames into a
  pinching/released cluster without per-frame labels, rather than an
  ad-hoc "biggest gap" heuristic. Used in `AnalyzeRecordings.py` (§7).

### 6.1 Derived result (2026-07-30, `AnalyzeRecordings.py` against 2× `pinch_x3` + `fist` + `open_hand`)

- **`pinch_ratio` threshold = 0.371`** (Otsu split of `pinch_x3`'s own
  distribution — the value is the boundary between a 56-frame low/pinching
  cluster and a 184-frame high/released cluster).
- **`pinch_angle_deg` was tested but not adopted** as a required condition:
  its own Otsu split produced a much larger, misaligned cluster (143 of 240
  frames — implausibly high for a signal meant to isolate brief pinch
  moments) versus `pinch_ratio`'s 56, indicating it responds to more than
  just the pinch action (likely overall hand orientation during the
  cycle). `pinch_angle_deg()` is still computed and available in
  `GestureRules.py` for future re-evaluation, just not required by
  `is_pinching()`.
- **Other-fingers-uncurled gate: curl angle, percentile-based, not a clean
  min/max split.** Even restricted to the 56 frames `pinch_ratio` confirms
  as genuinely mid-pinch, the *worst* (most-curled) of middle/ring/pinky
  sometimes reached fist-like curl values — a per-finger breakdown showed
  this wasn't one specific finger misbehaving, all three showed some tail
  overlap with `fist`. Read as either brief transition frames near the
  ratio decision boundary, or genuine finger coupling (thumb+index closing
  measurably drags the other fingers somewhat — documented in hand
  biomechanics literature, not unique to this data). Chasing a zero-overlap
  split on 2 recordings would be overfitting, not rigor — so the threshold
  is the **90th percentile of confirmed-pinch `curl_worst_deg`, = 112.965°**
  (accepts the top 10% of true-pinch frames failing the gate, in exchange
  for a threshold that generalizes past this one session).
- **Measured result**: `pinch_ratio < 0.371 AND curl_worst_deg < 112.965°`
  together produce **0/117 false positives on the recorded `fist`
  session** (actually measured, not assumed from the two gates
  separately).
- **Gap found, not yet closed: 9.2% (11/120) false positives on
  `open_hand`.** `open_hand` wasn't part of the threshold derivation (only
  `fist` was used as the adversarial stress test, per §6's original
  reasoning) — running the finalized `is_pinching()` back over all four
  recordings as a sanity check surfaced this. Likely a *relaxed* open hand
  occasionally lets thumb and index drift closer than a deliberately
  splayed one. Not fixed yet — see §7's open items.

<!-- VERBATIM-END -->
