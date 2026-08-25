# The queue's preamble — verbatim

> The governing rules of the build queue, exactly as they stood in
> `PART_ONE.md` §3.1 before the 2026-08-25 reorganisation.
> The queue itself is now [`../QUEUE.md`](../QUEUE.md).

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 223-276
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 3.1 Merged build queue — THE single TODO list (2026-08-02)

**This is the only build queue. It supersedes every other ordered TODO
list in the project**, including `PERCEPTION_LAYER_SPEC.md` §5's
module→TODO mapping and the three-item queue previously carried in
`HANDOFF_SNAP_ROTATE_RELEASE.md` §3. Those now point here. Do not
maintain a second list anywhere.

Created when `PERCEPTION_LAYER_SPEC.md` was integrated into the pipeline
(2026-08-02, direct request: *"the list of TODO can be merged into one for
the pipeline"*). It merges (a) the perception-layer modules M0–M10 and
(b) the pipeline's own pre-existing TODOs, which were previously tracked
separately and in some cases duplicated each other without knowing it.

**Owner decisions on integration (2026-08-02)**: build the perception
layer in **Python** under `Local_pc/` (the spec's `gestureConfig.js`
target does not exist — see the spec's §0.1/A1), keeping the spec
language-neutral for the later web/mobile port; run **Phases 0–2, then
reassess** before committing to Phase 3+; **do not** replace §14.1's
shipped translation mechanism with the spec's M8a until an A/B measures
them (A7).

**Governing rule (spec A10, binding):** every module must show a measured
improvement on the M0 metrics via replay A/B on identical recorded input,
or be **reverted**. A null result is recorded, not shipped hopefully.

**Where the evidence lives (added 2026-08-03):** every non-obvious number in this
queue's status cells was produced by a script in
**`Local_pc/Movement_with_hand_detection/analysis/`** — see that folder's
`README.md`, which maps each claim to its script. Run them from the parent
directory (`.venv/Scripts/python.exe analysis/<name>.py`). This matters because
several statuses below are *negative* results used to kill or re-point items
(2.3 deprioritised, T1/T2 re-pointed, 1.4 declared unreachable): **a negative
result that cannot be re-run is an assertion, not a finding.** The README also
lists the four measurement bugs caught mid-session — start any audit there.

**⚠ THOSE NEGATIVE RESULTS WERE THEMSELVES AUDITED (2026-08-03) — read
`PERCEPTION_LAYER_SPEC.md` §0.15 before acting on any status cell below.**
Outcome in one line: **the five 2.3 nulls and the M2 premise-kill are GENUINE
and re-confirmed on corrected streams; two claims were artifacts** — the jump
tail was inflated ~25% by identity contamination (82% → ~77% at high
observability, conclusion unchanged), and **"the motion model is weak" is
RETRACTED** (it was a closed-loop cascade statistic; the real one-frame error is
a 4.2–4.5° median), which **unblocks item 3.1**. New harnesses:
`analysis/audit_jump_provenance.py`, `analysis/audit_m2_proportions.py`.
**Binding for all future harnesses: build streams via `build_v2()` (DR-1 replay
+ duplicate-label + frame-continuity guards); never key a stream on the raw
MediaPipe label again.** A state-of-the-art literature audit ran at the same
time; **its adopted items S1–S12 are now folded into the rows below** (rationale
and sources stay in the spec's §10 addendum). **This table remains the only list
to follow — no S-item lives outside it.**

---

<!-- VERBATIM-END -->
