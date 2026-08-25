# `_archive/` — abandoned directions, kept so they can be consulted

⛔ **Nothing here runs in production or in the debug tool, and nothing here is
scheduled.** These are whole directions the project measured, decided against,
and stopped — kept because the evidence trail is worth more than the disk space,
and because a rejected approach that gets quietly deleted comes back.

⭐ **Still runnable.** Each moved script had its path anchor rewritten to
`_APP_ROOT` (one level up) when it was moved on 2026-08-25, and each `.bat`
`cd`s back to the app root, so anything here can be resurrected without
archaeology. Run from the app root:

```
.venv/Scripts/python.exe _archive/pinch_era/train_pinch_classifier.py
```

## `pinch_era/`

**The pinch gesture project — archived 2026-08-01.** A trained pinch classifier
built through the four-stage pipeline: labelled recording → literature benchmark
→ trained classifier → live debug tool. It reached ~77.7% cycle-detection recall
on recorded data, then **failed Stage 4 live validation** — too few real
pinches/releases detected, plus perceptible input lag. The project pivoted to
proximity snap / rotate / release.

`train_pinch_classifier.py` · `train_set_ablation.py` · `tune_event_layer.py` ·
`analyze_cycle_detection_failures.py` · `analyze_transition_window.py` ·
`sweep_window_for_cycle_detection.py` · `LiveGestureDebug.py` + `debug.bat`

⚠ The classifier weights and the corpus were **kept, not deleted** — this is
revisitable. The record is
`Claude/10_HAND_TRACKING/history/SPEC_01_12_pinch_era.md`; the reusable lessons
are its §12.7.

## `prediction_gate/`

**B7 (confirmation gate) and B8 (quadratic optimisation) — parked 2026-08-04,
park CONFIRMED under a blind test 2026-08-17.** B7 was measurable but
**invisible**; B8's every fit **lost to "hold the last value"**.

`LiveBlockPredictionDebug.py` · `debug_prediction.bat` ·
`sweep_prediction_error_window.py`

⚠ `analysis/b7_live_ab.py` still imports `LiveBlockPredictionDebug` and still
runs — the negative result stays re-runnable on purpose.

## `rotation_debug_recordings/`

Six local JSON captures from 2026-08-01, superseded by the corpus on `E:`.
⚠ **Recordings belong on `E:`, never local** — these predate that rule. Kept only
because `Claude/` cites early rotation numbers that came from them.

---

⛔ **Do not re-propose anything in here without new evidence.** The full
rejected list, with the measurement behind each verdict, is
`Hand_detection/Claude/10_HAND_TRACKING/REJECTED.md`.
