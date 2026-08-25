# METHOD — how anything gets decided here

> **STATUS** · live · **OWNS** · the evidence discipline, and the instrument traps
> **READ IF** · you are about to claim something works, or to accept a harness's word
> **LAST VERIFIED** · 2026-08-25
> **SOURCED FROM** · spec A10 and B4's method rules; the old `README.md` §6;
> the YOU-ARE-HERE blocks in
> [`../10_HAND_TRACKING/history/SESSION_LOG.md`](../10_HAND_TRACKING/history/SESSION_LOG.md);
> `GESTURE_PIPELINE_SPEC.md` §2 and §18.4 (verbatim in
> [`../10_HAND_TRACKING/spec/GESTURE_DEV_WORKFLOW.md`](../10_HAND_TRACKING/spec/GESTURE_DEV_WORKFLOW.md)
> and [`../60_SECURITY_COMPLIANCE/SPEC_18_security_audit.md`](../60_SECURITY_COMPLIANCE/SPEC_18_security_audit.md))

---

## The eight rules

1. ⭐⭐ **A10 — measure or revert.** Every module must show a **measured**
   improvement on the M0 metrics via replay A/B **on identical recorded input**,
   or be reverted. A null result is *recorded*, not shipped hopefully. Four
   estimator replacements have died under this rule and the project is better
   for each one.
2. **An anchor metric must not share an expression with the anchor** (`B4`). A
   metric built from the thing it is judging measures nothing — §16.14's "SINK"
   was retracted for exactly this.
3. **Blind tests use the balanced `--blind-series`** (`B4`).
4. **Never key a stream on the raw MediaPipe handedness label** — build via
   `build_v2()`. The label is measured **10.8% wrong** and was doing two jobs it
   was never fit for.
5. **`N6` — shared modules are imported, never copied.**
6. **Golden vectors before a port exists**, not after.
7. **Check the licence before proposing any model**, and state it (`N13`).
8. ⭐ **On-screen size comes from `palm_geometry.projected_size_px`**, never
   `object.size` (see [`CONSTRAINTS.md`](CONSTRAINTS.md) §7).

## No heuristic pile-up

If something misclassifies, the fix is **more/better labelled data covering that
failure as its own class**, or **a reconsidered feature set / model with
literature backing** — *never* a special-case rule bolted onto the output to
patch one observed failure. Every design choice must be justified by measured
data from our own recordings, a cited source, or both. Never guessed.

⭐ The corollary the project keeps re-learning: **a trigger cannot enforce an
invariant.** Two hand-side triggers were built and reverted before `U9` shipped a
positional clamp.

---

## ⛔⛔ The instrument is a suspect, always

**This is the most expensive lesson in the project.** In one session, **four
harnesses reported CLEAN on takes the owner had just watched fail.** Every time,
the instrument was wrong and the owner was right.

What came out of it, and is now standing practice:

* **Production RECORDS the cue it actually used** (`thumb_outward`,
  `chirality_confirmed`, `orientation_valid`, `snap_allowed`) instead of a
  harness recomputing it. **A recomputation is a second implementation that can
  silently disagree with the real one** — and twice in one night, it did.
* **The two recorders have their own parity guard** (`verify_recorder_parity.py`),
  because production once sampled cubes a frame earlier than debug and silently
  skewed every harness that paired hands with cubes.
* **Print the aggregation, not just the value.** Two harnesses aggregating
  differently under the same name reported pitch as *"45–55°, broken"* when the
  mean axis was 5.5°.
* ⚠⚠ **An audit is not exempt from A10 because its findings are code-shaped.**
  `SEC5` asserted a mechanism it had not measured and stood as fact for one day
  before being retracted. Deliberately kept as the audit's own lesson.

⚠ **Automated green is necessary, not sufficient.** §13.6.1 shipped **inverted**
while passing an "end-to-end confirmed" claim. **A live look in both tools is
what closes a change** — nothing else does.

⛔ If a baseline does not reproduce before you change anything, **stop**. The
instrument is the suspect, and that has been true five times in one session.

---

## Rules for reading the record

* **Retractions are kept on purpose.** A claim that was overturned is more useful
  than one silently deleted — several were overturned *twice*.
* **When two sections conflict, the later one wins.** Check for a `14.3.x`-style
  follow-up before acting on any older section.
* **A negative result that cannot be re-run is an assertion, not a finding.**
  Every non-obvious number traces to a script — see
  `Local_pc/Movement_with_hand_detection/analysis/README.md`.
* ⭐ **A constant borrowed from another row's derivation inherits that row's
  QUESTION, not just its number.** An object's resting depth was nearly set to
  0.40 m from a sentence that was about the *closest approach*, not the working
  distance; the measured median is 0.497 m, and 0.40 m would have made a quarter
  of all frames unable to pick anything up — reading as a broken build, not a
  mis-sized constant.
* ⚠ **"Same symptom" never means "same cause."** Three distinct defects
  (`U7`/`T3`/`U8`) presented as *one* appearance and were only separable by
  recording them.

---

## Where the evidence lives

| | |
|---|---|
| every number → the script that produced it | `Local_pc/Movement_with_hand_detection/analysis/README.md` |
| how a *new gesture* gets built, end to end | [`../10_HAND_TRACKING/spec/GESTURE_DEV_WORKFLOW.md`](../10_HAND_TRACKING/spec/GESTURE_DEV_WORKFLOW.md) |
| how a *recording* gets made and replayed | [`../10_HAND_TRACKING/spec/RECORDING_WORKFLOW.md`](../10_HAND_TRACKING/spec/RECORDING_WORKFLOW.md) |
| the rotation-measurement traps, all six hit for real | [`../10_HAND_TRACKING/spec/ROTATION_ACCEPTANCE_AND_TRAPS.md`](../10_HAND_TRACKING/spec/ROTATION_ACCEPTANCE_AND_TRAPS.md) |
| what to run, and to verify | [`../10_HAND_TRACKING/ARCHITECTURE.md`](../10_HAND_TRACKING/ARCHITECTURE.md) §Running |
