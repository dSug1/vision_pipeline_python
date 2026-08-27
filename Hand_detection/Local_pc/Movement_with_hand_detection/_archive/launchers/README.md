# Retired launchers

> **STATUS** · archived 2026-08-27 · **OWNS** · `.bat` files whose campaign is over
> **READ IF** · you are looking for a launcher that used to be in the tool root or
> in `tools/`, or you want to re-run one of the sessions below

⛔ **Nothing here is broken.** Every one of these still points at a script that
exists and passes flags the tool still accepts — they were archived because the
work they served is **finished**, not because they stopped working. To use one
again, copy it back; no edit is needed.

⭐ **Each one is also a single command**, listed below, so you never actually need
to restore the file — running the command directly is equivalent.

---

## `slant_rig.bat` · `pose_rig.bat` — `T6`'s two live rigs

```
.venv\Scripts\python.exe LiveSnapDebug.py --slant-rig --record --tag slant_rig
.venv\Scripts\python.exe LiveSnapDebug.py --pose-rig  --record --tag pose_rig
```

⛔⛔ **Both estimators were OWNER-REJECTED on 2026-08-27, the day they were built.**

* `--slant-rig` — Horn with its rotation axis steered by the palm's foreshortening.
  *"the feel is very bad. there is no consistency in the rotation axis,
  discontinuities everywhere"*
* `--pose-rig` — the owner's own strategy whole: the six-take regression on a
  canonical frozen at grab. *"panels 2 and 3 are much worse than panel 1 … lot of
  jumps, lot of jitter"*

⚠ **The scores were good**, which is the point of keeping the record: halves 1+2
produced the best yaw this project has measured (lean 27.2° → **8.6°**) and were
rejected anyway, because the per-frame orientation jump p95 went 12.6° → 30.3°.
⭐ **The tail decides the feel, every time.**

⛔ Before re-running either, read
[`REJECTED.md`](../../../../Claude/10_HAND_TRACKING/REJECTED.md): it carries a hard
gate — *demonstrate a per-frame orientation jump at or under shipped Horn's, on a
GRABBING take, before quoting a lean number.* Nothing in that family has come
within 1.8×.

⭐ The rig flags themselves are **still live in `LiveSnapDebug.py`**. Only the
convenience launchers moved.

---

## `record_anchor_takes.bat` — `B4`'s six-arm anchor session

Recorded the six-arm anchor comparison. ✅ **Closed and committed 2026-08-17**
(`9b1c2d4`): `horn-palm` shipped and was live-confirmed, arm B was rejected, and
`SINK` was found to be self-measuring. Two binding method rules came out of it —
*an anchor metric must not share an expression with the anchor* (`B4`), and *blind
tests must use the balanced `--blind-series`*.

⚠ Its `--sequence/--prompt/--note` triplets are a **recording protocol**, not just
a command line. If a comparable session is ever needed, read this file for the
prompts rather than inventing new ones — the wording is what made the arms
comparable.

---

## `record_trim_resolution.bat` — `F1` §10.1

```
.venv\Scripts\python.exe tools\RecordTrimResolution.py --hand right --tag f1_10_1
```

Recorded the take that answered *"does the fingertip trim resolve anything?"* —
and the answer was **no**: §10.1 measured it non-monotonic in the declared finger
angle at every gain and clamp. ⛔ **The trim was REMOVED on this evidence**
(`TRIM_GAIN = 0.0`), so the campaign is closed by its own result.

⭐ Kept rather than deleted because the trim's code is also kept: if the fingertip
fit is ever made non-rigid (spec §3.1's open door), this is how it gets re-tested.

---

## What was deliberately NOT archived, and why

| kept | reason |
|---|---|
| `launch.bat` · `stop.bat` | environment setup and teardown — used constantly |
| `debug_snap.bat` | the general debug launcher, referenced by 9 docs |
| `f1_rig.bat` | `F1` **shipped**; this is how the fingertip grip gets re-tested |
| `tools/record.bat` | the generic session recorder |
| `tools/record_perception_sequence.bat` | ⭐ **this is what produced the sweep and ratio-calib takes** the whole `T6` analysis runs on |
| `tools/record_rotation_debug.bat` · `record_translation_pivot_debug.bat` | their campaigns look closed, but each is a **generic** recorder that a future rotation or translation question could reuse. ⚠ Judged too useful to retire on a name-match alone |
