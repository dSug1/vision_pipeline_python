# `tools/` — resource tools

**Not run by production or by the debug tool** — but needed for **recording,
troubleshooting and verification**, so they are kept here, live and runnable,
rather than archived.

⭐ **Run them from the APP ROOT**, one level up, exactly as before:

```
.venv/Scripts/python.exe tools/wake_e_drive.py
.venv/Scripts/python.exe tools/VerifyChiralityFixture.py
tools\record_perception_sequence.bat <sequence>
```

The `.bat` files `cd` back to the app root themselves, so double-clicking still
works.

## What is here

| | |
|---|---|
| **`wake_e_drive.py`** | ⚠ **run this first, always.** The capture drive's first access after an idle gap fails; this retries past it |
| **`VerifyChiralityFixture.py`** | ⛔ **run after ANY mirroring or handedness change.** End-to-end chirality guard — §13.6.1 once shipped inverted while an "end-to-end confirmed" claim passed |
| `RecordPerceptionSequence.py` + `record_perception_sequence.bat` | record a **scripted take** (raw MediaPipe output, no gesture logic, no cube) |
| `RecordRotationDebug.py` + `record_rotation_debug.bat` | record a rotation take |
| `RecordTranslationPivotDebug.py` + `record_translation_pivot_debug.bat` | record a translation-pivot take. ⚠ **Queue `N17`: this one SYNTHESISES its timestamps** — do not use it for anything timing-sensitive |
| `record_anchor_takes.bat`, `record.bat` | batch capture helpers |
| `AnalyzePerceptionBaseline.py` | the **M0 regression metrics** — what closes a perception change under A10 |
| `AnalyzePerceptionSequences.py` | scripted-sequence analysis. ⚠ **Imported by `analysis/verify_edge_on.py`, `n11_compare.py` and `speed_threshold.py`** — it is the single definition of `edge_on`, so do not fork it |
| `AnalyzeTranslationPivot.py` | translation-pivot analysis |
| `AnalyzeHandIdentity.py`, `AnalyzeHandReappearance.py` | DR-1 identity and reappearance analysis |

## ⚠ Two rules that still apply here

* **Recordings go to `E:`, never `--local`.** These scripts still accept a local
  root; the corpus does not live there.
* **The corpus holds no image data.** Landmarks only, permanently — so no
  question that needs pixels can be answered by replaying a take.

⭐ The re-runnable *evidence* harnesses are in `analysis/`, not here. That folder
maps every claim in the docs to the script that produced it. **A negative result
that cannot be re-run is an assertion, not a finding**, which is why neither
folder gets pruned for tidiness.

Full context: `Hand_detection/Claude/10_HAND_TRACKING/ARCHITECTURE.md`.
