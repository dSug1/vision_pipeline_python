# RECORDING & ANALYSIS WORKFLOW

> **live · how a take is made, annotated and replayed**
> **SOURCE** · `PART_ONE.md` §7–§7.2 — extracted verbatim, not edited

⚠ Recordings go to `E:`, never `--local`, and the drive must be woken first
(`wake_e_drive.py`). ⛔ The corpus holds **no image data** — landmarks only.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1469-1648
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 7. Recording & analysis workflow

**Tool**: `Local_pc/Python_Server_MediaPipe_vision_pipeline/RecordSession.py`,
run via `Local_pc/Movement_with_hand_detection/record.bat <label>
[duration_seconds]` (reuses that folder's `.venv` — run `launch.bat` at
least once first if it doesn't exist yet). Standalone: opens the webcam
directly, runs MediaPipe `HandLandmarker` in `VIDEO` mode. **Recording is
timed, not keypress-stopped** — a 3s on-screen countdown gives time to get
hands in frame, then capture runs for `duration_seconds` (default 4s) and
stops automatically. No keypress needed once it starts, since both hands
are busy performing the gesture, not at the keyboard — closing the preview
window is still available as an early abort if needed. Every captured frame
— both hands' `handedness`, normalized `landmarks`, and `world_landmarks`
(Specification.md §6 schema) — is saved to
`Local_pc/Python_Server_MediaPipe_vision_pipeline/recordings/<label>_<timestamp>.json`.
No cube window, no socket — independent of the live pipeline (§4).
`recordings/` is gitignored (raw capture data, not source).

**Session convention**: one label per whole session (§1's revision from an
earlier held-pose-only plan) — cyclic gestures like pinch are recorded as
the gesture repeated ~3 times within one session (neutral → pinch → release,
×3), so the transition dynamics show up multiple times per file, not just a
single static hold. Static baselines (open hand, fist) are a single held
session, no repetition needed.

**Sessions recorded so far**: 2× `pinch_x3` (60 frames each), 1× `fist`
(60 frames), 1× `open_hand` (60 frames) — all with both hands detected
throughout. `near_pinch` (fingers close but not touching, a deliberate
boundary stress test per the original recording-set plan) not recorded yet.

**Analysis**: built — `Local_pc/Movement_with_hand_detection/AnalyzeRecordings.py`.
Loads every session from `recordings/`, computes `pinch_ratio`,
`pinch_angle_deg`, per-finger curl angles, and per-finger extension ratios
per hand-frame (via `Resources/GestureRules.py`), prints full distributions
per label, runs the Otsu split described in §6.1, cross-checks against
`fist`/`open_hand`, and prints recommended thresholds with the actual
measured false-positive counts (not estimates). Re-run it
(`.venv\Scripts\python.exe AnalyzeRecordings.py`) any time more sessions are
added — thresholds should be re-derived, not hand-adjusted.

**Open items surfaced by this pass** (not yet resolved):
- **`open_hand` false-positive root cause found (2026-07-30 debug pass)**:
  all 11 false positives are on the **left hand only**, in three brief
  ~66–99ms bursts (frames 17-20, 31-33, 45-48 — roughly evenly spaced,
  not random scatter). Curl values throughout stay comfortably in the
  extended range (72–82°, nowhere near the 112.965° threshold) — the curl
  gate is working correctly; it's specifically the thumb-index ratio that
  periodically narrows (down to 0.212) on an otherwise genuinely open,
  relaxed left hand. Likely natural resting-hand thumb drift, not a
  tracking artifact (the rhythmic spacing argues against random jitter)
  and not a fist-confusion case.
  - **Debounce alone won't cleanly fix this**: checked contiguous
    `is_pinching()`-true run lengths in the `pinch_x3` recordings —
    genuine pinch holds run only 3–5 frames (~100–165ms), i.e. *the same
    order of duration* as the false-positive blips. A simple "require N
    consecutive frames" filter would either still catch the blips (if N is
    small enough to keep genuine fast pinches) or reject real pinches (if
    N is large enough to exclude the blips) — the current data doesn't
    support a clean duration cutoff either.
  - **Practical mitigation that already exists**: grab acquisition (matrix
    row #3) is proximity-gated, not pinch-alone-gated — a relaxed hand
    that isn't near any cube can't spuriously grab one no matter how the
    raw pinch signal flickers. This softens the real-world impact
    considerably; don't over-fit the threshold chasing this artifact from
    one small recording before row #3 exists to actually test against.
  - **If still a problem once row #3 is live-tested**: record pinch
    sessions with slower, more deliberate holds (longer `--duration`,
    fewer cycles) so genuine pinches are unambiguously longer than
    incidental drift, making a duration debounce viable; and/or record a
    second `open_hand` baseline with fingers explicitly fanned apart to
    see if that removes the drift (would confirm it's a relaxed-hand
    posture effect, not inherent to this classifier).
- `near_pinch` session still not recorded — would sharpen exactly where the
  0.371 ratio boundary should sit, rather than relying on `pinch_x3`'s own
  release-phase frames as the only "not pinching" reference for that
  threshold.
- Only one person's hand in this data (2 sessions worth of `pinch_x3`) —
  thresholds are a starting point for live tuning against `is_pinching()`,
  not a final calibration.

### 7.1 Live debug tool (§8 step 4)

**Tool**: `Local_pc/Movement_with_hand_detection/LiveGestureDebug.py`, run
via `debug_gestures.bat` in the same folder (or `--duration <seconds>` for
a bounded, non-interactive run). Standalone — no socket, no cube window —
opens the webcam directly and overlays each detected hand's gesture status
on a preview window (`PINCH *` when active), logging to the console on
each detection's rising edge rather than every frame. `GESTURES` is a
`{display_name: classifier_function}` dict — adding a future gesture here
is a one-line addition, the loop itself doesn't change.

**Integration bug found and fixed while building this (2026-07-30)**:
`GestureRules.py`'s functions were only ever exercised against
JSON-loaded landmark dicts (`{"x", "y", "z"}`, the shape
`RecordSession.py` writes) via `AnalyzeRecordings.py` — never against
MediaPipe's native live result objects, which expose `.x`/`.y`/`.z` as
attributes, not dict keys. First live run crashed on this
(`TypeError: 'Landmark' object is not subscriptable`). Fixed at the call
site (`_to_dict_landmarks()` converts before calling any classifier) rather
than making `GestureRules.py` polymorphic over two landmark shapes — keeps
the classifier functions' data contract single and simple. **Lesson for
future gestures**: a classifier that's only been tested against recorded
JSON hasn't been tested against the live data path at all — step 4 isn't
optional polish, it catches integration bugs step 3 structurally cannot.

**First live smoke test (bounded 12s run)**: 8 `PINCH` detections logged on
the right hand, no crash, clean shutdown. Not yet a full interactive
session — that's next, checking both hands and specifically trying to
reproduce the `open_hand` left-hand flicker (§7's open items) live.

### 7.2 Interactive live testing found a bigger gap: rotation (2026-07-30)

Live testing (§7.1) surfaced what the recorded-data analysis couldn't:
static single-frame geometry is fundamentally ambiguous under hand
rotation, and doesn't generalize across hand orientation at all.

**Observed live**: (1) pinch detection works well with hands in
roughly the same position/orientation as the recordings; (2) rotating the
hand triggers pinch detection randomly; (3) palm-up (not represented in any
recording) doesn't detect pinches at all.

**Quantified**: ran `is_pinching()` (the static classifier) against a new
`rotating_hand` baseline (hand moving/rotating, no pinching, recorded via
`RecordSession.py --label rotating_hand --duration 6`) — **38.5% false
positives overall, 62.2% on one hand**. Confirms this isn't a minor edge
case.

**Why, per a literature check**: a pinch is inherently a *transition*, not
a fixed pose — a static geometric snapshot can't distinguish "thumb and
index happen to be close right now" (which many rotated, non-pinching hand
configurations produce incidentally) from "thumb and index are closing
together" (the actual pinch action). A robust VR-controller pinch-detection
paper (AtaTouch) uses closing *velocity* — not just distance — as a core
signal, plus a ~100ms temporal-persistence check to reject transient noise.

**Redesign — `PinchTracker` / `is_pinching_from_window` in
`GestureRules.py`**: a windowed detector requiring both the static gates
(ratio + curl, unchanged) **and** a recent closing motion (`pinch_ratio`
decreased by at least `DEFAULT_VELOCITY_THRESHOLD` = -0.05 over a
`PINCH_WINDOW_FRAMES` = 5-frame / ~165ms window). This is the one place
state enters the module — `PinchTracker` is a thin rolling-buffer wrapper
around the pure `is_pinching_from_window` function (Specification.md §7.1
already anticipated dynamic gestures needing a sliding window; pinch just
needed it sooner than planned). `is_pinching()` (the static-only version)
is kept as a building block and for static-geometry analysis, with its
limitation documented in its own docstring — **not used for live
detection anymore**.

**Validated against all 5 recorded sessions, in temporal per-hand order**
(`ValidateWindowedClassifier.py` — unlike `AnalyzeRecordings.py`'s pooled
analysis, this preserves frame adjacency, which a velocity feature needs):

| Session | Hand | Static | Windowed |
|---|---|---|---|
| `rotating_hand` | Right | 62.2% | **22.2%** |
| `rotating_hand` | Left | 14.6% | 10.1% |
| `open_hand` | Left | 18.3% | **18.3% (unchanged)** |
| `pinch_x3` (×2, true positives) | both | 16.7–25.0% | 13.3–20.0% (some loss) |

**Real progress, not a full fix — and the reason why matters more than the
numbers.** Inspected the `open_hand` left-hand blip directly: `pinch_ratio`
drops from 0.546 → 0.212 → back to 0.543 within ~6 frames (~200ms) — a
genuine, complete closing-and-reopening motion, not static noise. It has
the velocity signature of a real pinch **because it structurally is one** —
an unintentional but real fast hand motion. Velocity alone can't
distinguish it from a genuine pinch because the reference `pinch_x3`
recordings are themselves very fast: 3 cycles in 4 seconds means real pinch
holds only last 3–5 frames (§6.1's contiguous-run-length finding) — right
in the same range as this incidental blip. **The two classes overlap in
timing because the training data doesn't have a clean timing signature to
key off of, not because the velocity approach is wrong.**

**Next step (not yet done)**: re-record `pinch_x3` (or a new, explicitly
slower variant) with deliberate, sustained holds — e.g. ~300–500ms per
hold, not a rapid ×3-in-4-seconds cadence — so genuine pinches have an
unambiguous duration to detect against. Re-deriving `DEFAULT_VELOCITY_THRESHOLD`
and `PINCH_WINDOW_FRAMES` against fast-cadence data would be overfitting
to a dataset that structurally can't support the separation; the recording
protocol needs to change, not just the threshold.

<!-- VERBATIM-END -->
