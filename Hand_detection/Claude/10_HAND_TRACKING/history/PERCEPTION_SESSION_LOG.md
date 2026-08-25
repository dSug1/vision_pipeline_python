# PERCEPTION LAYER — the build log, verbatim

> **history · §0.2–§0.18, every module built or killed and the audit of the nulls**
> **SOURCE** · `PERCEPTION_LAYER_SPEC.md` §0.2–§0.18 — extracted verbatim, not edited

⭐ Where DR-1, DR-2, M2, M4, M5, M6 and Phase 1's closure actually happened,
dated. The **forward design** is
[`../spec/PERCEPTION_LAYER_SPEC.md`](../spec/PERCEPTION_LAYER_SPEC.md); its
§0.1 amendment log is binding and stayed there.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PERCEPTION_LAYER_SPEC.md lines 301-2189
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 0.2 Baseline results (2026-08-02) — measured, before any module was built

Merged-queue item 0.2, run via
`Local_pc/Movement_with_hand_detection/AnalyzePerceptionBaseline.py` on the **7
existing recordings** in `Position_during_rotation` — no new capture. Raw output:
`Recordings_perception_layer/metrics/baseline_current_pipeline.jsonl`.

These are the numbers every subsequent module is judged against under A10.

| Metric | Target | **Measured** | Verdict |
|---|---|---|---|
| Bone-length CV | < 3% | **10.0%** mean (6.0–13.4 per session/hand) | **3.3× over target** |
| Palm rigidity residual | < 3 mm | **2.76 mm** mean | **already at target** |
| Palm-normal change, low-motion frames | < 1.5° | ~2.2° mean | indicative only — see caveat |
| Object jumps > 100 px | 0 | **2**, both in `jump_test4`/Right (max 513.9 px) | the known §14.1.4 bug, nothing else |

> **⚠ Finding 1 below was CORRECTED by the scripted-sequence results — read §0.3.**
> The "3.3× over target" reading treated 10% bone CV as a static sensor floor. It
> is not: held still, the same pipeline measures **0.9–1.1%**, comfortably inside
> target. The 10% is motion- and rotation-induced. The *conclusion* (M2 is worth
> building, and fingertips are the weak point) survives; the *reason* does not.

**Finding 1 — M2 is strongly justified, but its value is in the fingers, not the
palm.** Bone-length CV is 3.3× over target, and **the worst bones are consistently
the distal phalanges** (`3-4` thumb tip, `7-8` index tip, `11-12`, `19-20`) at
13–32%. That is exactly what the spec predicts: depth error dominates and is worst
distally. But the **palm is already rigid to 2.76 mm, inside the < 3 mm target** —
so M2's error-signal value, and M4's downweighting, apply mainly to fingertips. The
palm frame that M6b builds on is already well-conditioned.
*(Caveat: short bones inflate CV mechanically — `9-13`, adjacent MCPs, appears as a
worst-bone in 3 sessions largely because its mean length is small. Do not read
short-bone CV as equivalent to long-bone CV.)*

**Finding 2 — the object-jump metric works and is clean.** Exactly 2 jumps across
3801 frames, both in the one recording with a confirmed reproduction of Object Jump
Correction, max 513.9 px (matching the 509 px figure in §14.1.4). Every other
session: zero. This is now a usable regression metric — if M4's χ² gate works,
these 2 go to 0 and nothing else changes.

**Finding 3 — palm-normal jitter cannot be properly measured yet.** The ~2.2°
low-motion figure is a stand-in computed from frames where the anchor moved < 2 px;
it is **not** the spec's held-still metric and must not be quoted as one. It needs
the §7.2 *static hold* sequence. Reported only to show the order of magnitude.

### The hypothesis test: DR-2 validated

M5/DR-2 assumes the palm/back sign is reliable everywhere **except** near edge-on.
Tested by computing the edge-on measure retroactively per frame and bucketing the
recorded sign flips:

| edge-on band | frames | flips | flips / 1k frames |
|---|---|---|---|
| [0.00, 0.05) | 17 | 13 | **764.7** |
| [0.05, 0.10) | 27 | 6 | **222.2** |
| [0.10, 0.15) | 24 | 7 | **291.7** |
| [0.15, 0.25) | 57 | 1 | 17.5 |
| [0.25, 0.40) | 205 | 3 | 14.6 |
| [0.40, 0.60) | 341 | 5 | 14.7 |
| [0.60, 1.01) | **3130** | **0** | **0.00** |

3801 frames, 35 flips. **74.3% of flips fall inside the proposed DR-2 band
(< 0.15), which is only 1.8% of frames — a 41.5× over-representation**, with a
cleanly monotonic gradient.

**Two conclusions, at different confidence levels — the distinction matters:**

1. **Solid: the sign is rock-stable when well-conditioned.** *Zero* flips across
   3130 frames above edge-on 0.60 — 82% of all frames. The cue is trustworthy in
   the bulk of normal operation, and every instability is confined to a narrow
   band. This is what makes DR-2 both viable and cheap.
2. **Solid: the lowest buckets are demonstrably chatter, not real rotation.** A
   concentration of flips near edge-on is *expected even with a perfect sensor* —
   a genuine palm↔back rotation must pass through edge-on, so a correct flip
   happens there. Concentration alone therefore proves nothing. **But the rate
   does**: 13 flips across 17 frames (≈0.57 s) is physically impossible as
   genuine rotation; likewise 6 flips in 27 frames. Those are noise chatter,
   confirmed by rate rather than assumed from position.
3. **Not yet established: whether the mid-band flips (0.15–0.60) are spurious.**
   1, 3 and 5 flips over 57–341 frames are entirely consistent with genuine
   rotations. Separating them requires the §7.2 *scripted non-crossing motion*
   sequence, which is what M0's chirality-flip-rate metric actually specifies.

**Parameter amendment flagged, not applied.** `EDGE_ON_THRESHOLD = 0.15` was a
starting guess. The data shows flips continuing at a flat ~15/1k rate up to 0.60
and then stopping dead. That *may* argue for a higher threshold — but per
conclusion 3, those mid-band flips may be legitimate rotations, and raising the
threshold would suppress valid gestures over a much wider range (0.60 covers ~18%
of frames vs. 1.8%). **Do not raise it on this evidence.** Re-derive it once the
scripted non-crossing sequence exists.

---

## 0.3 Scripted-sequence results (2026-08-02) — item 0.2b, and one correction to §0.2

Four §7.2 sequences recorded with `RecordPerceptionSequence.py` (pure raw capture,
no gesture logic) and analysed with `AnalyzePerceptionSequences.py`. Sessions in
`Recordings_perception_layer/sessions/`.

| sequence | bone CV | resting jitter (mean / fingertips) | palm-normal | edge-on min | sign flips |
|---|---|---|---|---|---|
| **static_hold** | **0.89 / 1.14 %** ✅ | **0.45 mm** / 0.83 mm ✅ | **0.88 / 0.92°** ✅ | 0.714 | **0** |
| **non_crossing** | 9.47 / 9.86 % | 5.73 / 10.45 mm | 3.49 / 3.88° | **0.353** | **0** |
| pitch_sweep_slow | 24.96 % | 14.75 / 26.31 mm | 11.05° | 0.010 | 10 |
| pitch_sweep_fast | 21.39 % | 12.22 / 21.80 mm | 13.17° | 0.088 | 11 |

### Correction to §0.2: the 10% bone CV is not a sensor floor

**Held still, this pipeline meets every M0 target it can be measured against** —
bone CV 0.89–1.14% (target < 3%), resting jitter 0.45 mm (target < 1.5 mm),
palm-normal jitter 0.88–0.92° (target < 1.5°). MediaPipe at rest is *excellent*.

The error is **motion- and pose-driven**, and the gradient is steep and monotonic:

```
still 1%   ->   free translation 9.5%   ->   pitch rotation through edge-on 25%
```

§0.2 read the 10% figure (measured on grab-and-rotate recordings) as a static
floor and concluded M2 was needed to fix a noisy sensor. **That reasoning was
wrong.** The corrected picture:

- **M2's calibration is much easier than assumed.** Clean 1%-CV samples are
  readily available — just gate collection on low motion. The spec's §2f freeze
  criterion (IQR < 2%) is comfortably achievable.
- **But M2's bone-length *residual* is a weaker error signal than the spec
  assumes.** M4 treats it as a per-landmark quality cue; this data says it will
  mostly be reporting *"the hand is rotating"*, not *"landmark 8 is bad"*. It
  conflates pose with per-landmark reliability. **Amendment: M4 must not use the
  raw bone residual directly — it needs normalising against the current
  pose/motion, or it will down-weight every landmark uniformly whenever the hand
  moves**, which is both useless and actively harmful during fast gestures.
- §2f's recorded pitfall is about pose diversity removing *bias*. This is a
  different and additional effect: pose drives *variance*. Both matter.

### The `EDGE_ON_THRESHOLD` question is settled: keep 0.15, do not raise it

§0.2 flagged a temptation to raise the threshold toward 0.60, because flips in the
old recordings continued up to that value. **The `non_crossing` sequence answers
this decisively:**

- **Zero sign flips across 723 frames on both hands**, during 30 s of deliberately
  varied motion — translation, tilting, near the frame edges — with the palms
  never turning over.
- **Edge-on never dropped below 0.353** (Left) / **0.437** (Right). Normal
  non-crossing motion *does not enter the danger band at all*: 0.0% of frames
  below 0.15.
- But **4.6–8.0% of those normal frames sit below 0.60.** A 0.60 threshold would
  therefore suppress `palmFacing`-dependent gestures during ordinary use, for no
  benefit — there were no flips to prevent.

**Conclusion: `EDGE_ON_THRESHOLD = 0.15` is correct and safe.** It is never
reached in normal motion, so DR-2 will only ever fire during a deliberate
crossing — exactly its intent. Raising it toward 0.60 is now positively
contraindicated, not merely unsupported.

### Pitch sweeps: honest limits of what this shows

Flips occur across the whole edge-on range (0.010–0.807). During a pitch sweep the
hand *genuinely* crosses palm↔back, so most of these flips are **correct**, not
errors — the slow sweep's 10 flips in 30 s is about right for ~3 s per sweep.

What cannot be concluded without a ground-truth crossing count: whether the
high-edge-on flips (0.584, 0.599, 0.729 in the *slow* sweep) are genuine fast
crossings or glitches. At 24 fps (41.5 ms/frame) a fast rotation can legitimately
jump the whole band between two frames, which explains the fast sweep's
high-edge-on flips — but a *slow* sweep should linger near zero and flip there.
**Flagged as suspicious, not diagnosed.** Resolving it needs a sequence with a
counted number of deliberate crossings.

### Two incidental findings worth carrying forward

1. **The pipeline runs at ~24 fps, not 30.** All four sequences measured
   24.09–24.14 fps from real `tCapture` timestamps. The older recorders
   *synthesised* a 33 ms cadence, so this was invisible until now. Real interval is
   ~41.5 ms. **Every "N frames at 30 fps" parameter in this spec is therefore
   ~38% longer in wall-clock than intended** — M5e's 3-frame dwell, M10's 3/4-frame
   dwells, M4's 8-frame coast limit. Re-express them in milliseconds.
2. **14 of 480 frames lost detection entirely during the fast sweep** (2.9%), vs.
   0 lost in every other sequence. Motion blur costs whole frames, not just
   precision — which is what M4's coast limit and M7's prediction horizon exist to
   ride out.

---

## 0.4 Object Jump Correction — root cause REFINED and confirmed (2026-08-02)

Three more sequences recorded (`two_hand_overlap`, `two_hand_near_miss` as a
matched control, and re-using `pitch_sweep_*`), analysed with
`AnalyzeHandIdentity.py`. **The result overturned the working hypothesis and
produced a complete, concrete mechanism.**

### The hypothesis that was wrong

§14.1.4 and A9 assumed the mixup came from **two hands being confused with each
other** when close together, and the fix was framed as DR-1 + M4's χ² gate. The
controlled comparison does not support the proximity story:

| sequence | one-hand frames | teleports > 100 px | identity swaps |
|---|---|---|---|
| two_hand_overlap (hands genuinely occlude) | 205 / 717 | 2 | **0** |
| two_hand_near_miss (visible gap, CONTROL) | 0 / 723 | **0** | **0** |

Occlusion clearly *happened* (28.6% single-hand frames vs. 0% in the control),
but produced no identity swap at all. **Proximity and occlusion are not the
mechanism.**

### The actual mechanism: MediaPipe's handedness label is unstable

The mixups appeared in **`pitch_sweep_fast` — a ONE-HANDED sequence**, where
confusing two hands is impossible by construction:

| sequence | frames | duplicate-label frames | label flips | mean score at flip |
|---|---|---|---|---|
| static_hold | 288 | 0 | 0 | — |
| non_crossing | 723 | 0 | 0 | — |
| pitch_sweep_slow | 722 | 0 | 0 | — |
| **pitch_sweep_fast** | 480 | **4** | **18** | **0.663** |
| two_hand_crossing | 723 | **9** | 5 | 0.970 |
| **two_hand_overlap** | 717 | **12** | 5 | 0.986 |
| two_hand_near_miss | 723 | 0 | 0 | — |

Two distinct failures, both real, both absent from every control:

1. **Label flips on a single physical hand.** In `pitch_sweep_fast` one physical
   hand was labelled `Left` on 448 frames and **`Right` on 14** — with continuous
   position across the flip (e.g. frame 254 `Left` x=268.9 → 255 `Right` x=258.0
   → 256 `Left` x=272.7). Obviously the same hand; only the label moved.
2. **Duplicate labels — both detections carrying the SAME label** (`('Left','Left')`).
   4 frames in fast rotation, 9 and 12 in the two-hand sequences. Zero in all
   controls.

Handedness confidence degrades monotonically with rotation, and flips cluster at
the bottom of it:

```
static 0.981  ->  non_crossing 0.976  ->  pitch_slow 0.960  ->  pitch_fast 0.941
                                          (11.5% of frames < 0.90, min 0.501)
flips occur at mean score 0.663, against a ~0.95-0.99 baseline
```

**This is exactly what §5b predicts** — handedness is decided from *appearance*
(knuckles, creases, shading), not landmark geometry, so it degrades under blur and
when the back of the hand is shown. Handedness and palm-facing are the same bit,
and rotation is what breaks it. The two-hand sequences did **not** reproduce it
because the palms stayed toward the camera throughout, keeping those cues intact.

### Why this produces the observed cube jump — confirmed in production code

Cube ownership is keyed by handedness (`cube_owned_by(handedness)`,
`_thumb_outward_snap_allowed[handedness]`), and the wire protocol resolves hands
by label:

```python
def extract_hand_by_type(hands_array, handedness):
    hand = next((h for h in hands_array if h.get("handedness") == handedness), None)
    return hand.get("landmarks", []) if hand else []      # <- first match, or NOTHING
```

With duplicate labels `('Left','Left')`:

- the `"Left"` lookup returns **whichever came first** — possibly the physically
  *right* hand → that cube snaps across the screen to the other hand's position;
- the `"Right"` lookup returns `[]` → `remap_keypoints` emits 21 zero points →
  `_is_detected()` is False → **tracking-loss release fires and the cube is
  dropped.**

A transient label flip does the same thing one frame at a time. This accounts for
both halves of the recorded §14.1.4 event — the 509 px teleport *and* its
self-correction a few frames later.

### Why this was invisible until now

The older recorder stored hands in a **dict keyed by handedness**
(`hand_data_by_hand[handedness] = {...}`). A duplicate label silently
**overwrote** the first entry, so the failure mode was destroyed at record time
and could never appear in analysis. The new recorder keeps the raw MediaPipe
**list**, which is why the same bug that had resisted diagnosis for two sessions
showed up within minutes.

*This vindicates the pure-raw-capture design (§M0's integration note): derived or
re-keyed data at record time can erase the very defect you are hunting.*

### Consequences for the plan

- **DR-1 (chirality lock) is confirmed as the correct fix, and is now the
  primary one** — not DR-1 *plus* M4 as A9 assumed. Making handedness a
  track-level property removes both failure modes at their source.
- **A ready-made gate exists**: the handedness `score`. Flips occur at ~0.66
  against a 0.95–0.99 baseline, so DR-1's acquisition rule ("accumulate over
  frames where quality is high") has a directly usable signal.
- **A stateless duplicate-label resolver was built and then REMOVED the same day
  (2026-08-02) — see §0.5.** It chose between two same-labelled detections by
  handedness score. Measurement killed it: the score gap was < 0.05 (a coin
  flip) on 36% of affected frames, it disagreed with position continuity on 16%,
  and it was structurally blind to the larger half of the problem — 28 recorded
  single-hand label flips. It addressed ~47% of identity events. **DR-1 was built
  in its place** (§0.5).
- **M4's χ² gate is demoted** for this TODO from "necessary" to "useful
  belt-and-braces": it would catch the *symptom* (an implausible jump) but not
  the cause, and per A5 it should not be relied on where the real fix is upstream.

---

## 0.5 DR-1 built (2026-08-02) — and a design correction the data forced

Owner decision: remove the stateless resolver ("it does not address the issue")
and implement a **hysteresis-based track identity** instead. Built in
`hands_visualizer.py` as `_HandTrack` / `_HandIdentityTracker`, at the same
single source as `_mirror_handedness`.

### The design

1. **Associate detections to tracks by POSITION**, never by MediaPipe's label
   (greedy nearest-neighbour, gated at `MAX_ASSOC_PALM_RATIO = 3.0` palm widths —
   normal frame-to-frame motion measured 0.6–1.4 palm widths, the Object Jump
   excursion was 513 px).
2. **Lock the label** after a short weighted vote (`LOCK_VOTE_FRAMES`), or
   immediately as the complement when a second track appears (DR-1's
   two-simultaneous-hands rule).
3. **A raw-label mismatch flags the track**: brief → hold (transient glitch);
   long *and confident* → switch.
4. **Re-decide freely when a track genuinely ends** (absent > `TRACK_END_MS`).

All dwell constants are expressed in **milliseconds and converted at the measured
~24 fps**, per finding N1 — not the 30 fps the spec's frame counts assumed.

### The correction: "never switch mid-track" was wrong

The first implementation followed a refinement suggested during design — *never*
switch a locked label, on the reasoning that handedness cannot change within a
track (your left hand does not become your right hand). **Replay disproved it.**

That reasoning holds only if the track genuinely follows one physical hand — and
**position-based association cannot guarantee that.** When two hands cross,
nearest-neighbour association swaps them, the track identity itself becomes
wrong, and a never-switch rule then locks that error in permanently.

Measured on `two_hand_crossing` with the never-switch rule: **528 overrides,
96.6% at score > 0.90**, in runs of **62 and 225 consecutive frames** — the
tracker confidently holding a *wrong* label for ~9 seconds after a crossing.

The owner's original "switch after YYY frames" was correct. What made it safe to
implement was that the two cases separate cleanly in the data:

| case | run length | score | correct action |
|---|---|---|---|
| transient sensor glitch | 1–2 frames | **0.52** | hold the lock |
| association swap at a crossing | 62–225 frames | **0.97–0.98** | switch |

So only mismatches at `score >= 0.90` accumulate toward a switch, and the dwell is
longer than any observed glitch. Switches are applied **at tracker level,
exchanging both labels together**, so two tracks can never transiently hold the
same label.

### ⚠ `SWITCH_MS` is a TUNABLE latency-vs-false-glitch trade-off

Currently **12 frames (~500 ms)**. This is the one parameter here most worth
revisiting, and the trade-off is genuinely two-sided. Measured populations:

| | run length |
|---|---|
| longest glitch run correctly **held** | **7 frames (~292 ms)** |
| genuine association swaps (raw disagreement) | **62–225 frames** |

- **Lower** → faster correction after a real crossing, but the margin above the
  7-frame glitch shrinks. At 7 or below, a glitch that actually occurred in these
  recordings **would have caused a false switch** — a cube visibly jumping to the
  wrong hand for no reason.
- **Higher** → more margin, and real swaps still cannot be missed (they run
  62–225 frames), at the cost of the wrong label persisting longer after a
  genuine crossing.

12 was chosen as the balance: 5 frames of margin above the worst observed glitch,
half a second of worst-case correction latency. **Re-derive from fresh recordings
if the camera, frame rate or lighting change** — the glitch population sets the
floor and is blur/lighting dependent, so the safe minimum will move with them.

*A cheaper structural discriminator was proposed and **refuted by measurement**:
"both tracks mismatched simultaneously" does not separate the populations. Real
swaps frequently have no second visible track at all (5 of 8 occurred with one
hand detected — `pitch_sweep_fast` is one-handed throughout, and hands occlude
during crossings), while two correctly-held glitches DID show both tracks
mismatched for 5 frames each. Using it as a fast-track would have caused false
switches on exactly the runs the current rule correctly rejects. Do not retry it
without new evidence.*

### Verified by replaying all seven recorded sessions

| sequence | duplicates out | overrides (before → after) | longest wrong-hold run | switches |
|---|---|---|---|---|
| static_hold | 0 | 0 → **0** | 0 | 0 |
| non_crossing | 0 | 0 → **0** | 0 | 0 |
| pitch_sweep_slow | 0 | 0 → **0** | 0 | 0 |
| pitch_sweep_fast | 0 | 116 → **41** | 26 | 1 |
| two_hand_crossing | 0 | 528 → **71** | **225 → 10** | 4 |
| two_hand_overlap | 0 | 322 → **24** | 10 | 1 |
| two_hand_near_miss | 0 | 0 → **0** | 0 | 0 |

- **Duplicate labels eliminated entirely** (25 → 0) — structurally, since two
  detections associate to two different tracks each emitting its own label.
- **Longest wrong-hold collapsed from 225 frames (~9 s) to 10 (~420 ms)** — the
  intended dwell before a switch confirms, not a stuck error.
- **Zero overrides and zero switches in all three control sequences.** The
  tracker is inert when nothing is wrong, so it cannot introduce regressions in
  normal use.

`pitch_sweep_fast`'s 26-frame run exceeds the 12-frame dwell because low-score
frames legitimately do not count toward a switch — correct behaviour (never
switch on unreliable evidence), at the cost of a longer correction under heavy
blur.

### Shared by production AND the debug tool (2026-08-02)

DR-1 was initially built inside `hands_visualizer.py`, which is server-side —
making it **production-only**, since `LiveSnapDebug.py` runs MediaPipe in-process
and never imports it. Owner instruction: *"I do not want to have a debug tool
which is not in tune with the production."*

Resolved the architecturally correct way rather than by copying: the tracker was
extracted to **`Resources/hand_identity.py`** — standalone, pure stdlib, no
cv2/mediapipe and no window side effects, operating on plain `(x, y)` tuples so
each caller adapts its own landmark shape. Both consumers now **import** it.

This is the §1 boundary discipline applied to the tooling itself: perception
lives below the `HandState` line and is shared, not duplicated. Duplication is
what let the thumb-outward sign convention drift between the two paths once
already (§13.6.1).

**The same change fixed a latent bug in the debug tool**: it stored hands in a
dict keyed by handedness, so a duplicate label silently overwrote one of the
pair — the very defect that hid Object Jump Correction in the old recorder.

**Verified**: production and the debug tool produce **byte-identical identity
output across all 7 recorded sessions**, and exactly one tracker definition
exists in the codebase.

### Still open

- ~~**Not yet live-tested.**~~ **DONE 2026-08-02 — see §0.6 below.**
- **Acquisition can still lock wrong.** If the first frames are mislabelled, the
  switch branch is what recovers it — which is now another reason that branch
  must exist. **Observed live twice (§0.6), and recovered both times.**
- `_ASSUMED_FPS = 24.0` is hard-coded. It should come from measured frame timing
  once `HandState.tCapture` exists (M0/N1).

---

## 0.6 DR-1 LIVE-CONFIRMED against a camera (2026-08-02)

Run via `launch.bat`'s exact code path (production: `VisionPipeline.py` +
`Client.py`), the operator deliberately rotating hands to show the backs of
them and crossing/overlapping them while holding cubes. **Operator verdict:
"it's working"** — no cube teleported to the other hand and none was
spuriously dropped.

This closes the item the handoff called out as the one thing standing between
replay verification and trust, and it matters because this project has shipped
a production-only bug that survived a "confirmed working end-to-end" claim
once already (`GESTURE_PIPELINE_SPEC.md` §13.6.1; summarised in the handoff §3.2).

**Console record — 16 tracker events, 0 errors or tracebacks:**

| event | count | reading |
|---|---|---|
| `identity locked` | 5 | 3 by vote, 2 as the complement of an existing track |
| `track ended` | 4 | hands leaving frame — identity correctly re-decidable |
| **`duplicate label would have been emitted`** | **3** | the end-of-function invariant firing — **new, see below** |
| `switch confirmed after 12 confident frames` | 2 | lone track, `Right`→`Left`: acquisition locked wrong, switch branch recovered it |
| `switch confirmed` (with clash) | 1 | `Left`→`Right`, other track took `Left` — an association swap through a crossing |
| **`transient glitch rejected, lock held`** | **1** | 3 confident mismatched frames held, then agreement — **the core design behaviour, proven live** |

**The failure conditions were genuinely exercised, not merely absent.** Those
events only fire when MediaPipe actually disagreed with the track, so this was
not a run that passed by never provoking the bug — the glitch-rejection and
switch branches both fired and both did the right thing.

### One genuinely new finding: the duplicate-repair fallback is reachable in normal use

§0.5 reported duplicates eliminated **structurally** ("two detections associate
to two different tracks each emitting its own label"), and the explicit
end-of-function invariant was described as an edge case found by fuzzing —
reachable only when a detection jumps beyond the association limit with both
track slots full.

**It fired 3 times in a single short live session.** No duplicate was emitted —
the invariant did exactly its job, which is why the run passed — but the
frequency is new information that the 7 recorded sessions did not predict.

Two readings, and this is **not yet diagnosed**:

- `MAX_ASSOC_PALM_RATIO = 3.0` may be too tight for live motion. It was derived
  from recorded frame-to-frame motion of 0.6–1.4 palm widths; a live operator
  deliberately crossing hands fast may simply exceed it.
- Or the association is failing for a different reason (a dropped frame — recall
  §0.3's finding that 2.9% of frames lost detection entirely under fast motion —
  leaves a stale `avg` position for a track).

**Do not tune `MAX_ASSOC_PALM_RATIO` on this evidence.** Per A10, that is a
measurement question, not a guess: the fallback firing is currently *harmless*
(the invariant catches it), so the cost of leaving it alone is zero, and the
next scripted-sequence recordings (queue 0.2b) can quantify it properly.
**Logged as queue item N9.**

### Also observed: `SWITCH_MS = 12` frames behaved correctly at both extremes

The single transient glitch ran 3 confident frames and was **held** (correctly
rejected), while the real association swap accumulated its full 12 and
**switched**. That is the exact separation §0.5 predicted from the recorded
populations (glitches ≤7 frames, real swaps 62–225), now confirmed against a
live camera rather than replay. **No reason to re-derive `SWITCH_MS` at this
time** — but the standing instruction still holds: re-derive it if the camera,
frame rate or lighting change.

---

## 0.7 `palm_back` recorded (2026-08-02) — N3 ground truth, and a frame-rate surprise

Queue item 0.2b continued. §7.2's *palm↔back rotation at 4 speeds* recorded with
`RecordPerceptionSequence.py --sequence palm_back`, to E: per owner instruction.
Session: `2026-08-02_221948_palm_back` (630 frames, 39.95 s, 628 with a hand).

> **⚠ BOTH `palm_back` TAKES WERE DELETED (2026-08-02, owner instruction)** — the
> counted one above and an earlier aborted one — because both were recorded in
> poor light at 15–16 fps: *"I don't want the lack of light to pollute our
> analysis."* **The numeric result below is retained as INDICATIVE ONLY; the data
> behind it no longer exists and it must not be cited as a measurement.** What
> survives as durable is the *method* — the unit trap, the frame-rate finding, and
> the redesign in §0.7.1. Re-record in daylight before concluding anything.

### The counting convention — read this before using the number

**The operator counts one "crossing" as palm → back → palm, i.e. a full CYCLE.**
The analyser counts per-frame **sign inversions**. One cycle is **two** sign
changes, so the two units differ by 2×.

> **This ambiguity produced a wrong reading on the first pass** — 29 was briefly
> compared against 52 detected flips and misreported as a ~40% *spurious* rate,
> when the correct comparison (58 expected) shows the opposite. Both numbers are
> now stored explicitly in the session's `meta.json` as `counted_crossing_cycles`
> (29) and `expected_sign_changes` (58). **Always compare against
> `expected_sign_changes`.**

### Result: the sign cue UNDER-detects crossings

| | expected | detected | delta |
|---|---|---|---|
| Left | 58 | **52** | −6 |
| Right | 58 | **50** | −8 |

*(58 is a lower bound: the clip ends with the hand edge-on mid-turn and that
trailing incomplete transition was not counted, so the true figure may be 59.)*

**There is no evidence here of a large spurious-flip population** — the earlier
working suspicion. If anything the cue misses genuine crossings. Detected flips
span the whole edge-on range (0.015–0.949), and per the operator several cycles
were deliberately fast, which is consistent with genuine crossings traversing the
band between frames.

**What totals alone CANNOT settle** — and this is the honest limit of this take:
a compensating mix (some genuine crossings missed *plus* some spurious flips)
also nets to 52. Separating them needs per-flip matching against the rotation
timeline, not counts. **N3 is therefore advanced, not closed.**

### ⚠ The pipeline does NOT run at a fixed ~24 fps — it is environment-dependent

Finding N1 (§0.3) recorded ~24 fps as a property of the pipeline. **Two takes
this evening measured 15.1 and 15.77 fps** — same recorder, same camera, same
machine, same resolution. The seven earlier sequences were recorded 19:13–20:51
and measured 24.09–24.14; these at 22:18–22:19.

The likely mechanism is webcam **auto-exposure lengthening frame duration in
dimmer light** — untested, so treat it as the leading hypothesis rather than a
diagnosis. What matters is the consequence, which does not depend on the cause:

- **Frame rate varies with ambient conditions**, so `ASSUMED_FPS = 24.0` in
  `hand_identity.py` is not a constant to be measured once and hard-coded.
- **Every DR-1 dwell derives from it.** `SWITCH_FRAMES = round(500 × 24/1000) =
  12`. At 15.77 fps those 12 frames are **~761 ms, not the intended 500** — a 52%
  overshoot, in the parameter §0.5 identified as the one most worth getting right.
  The live test (§0.6) that validated the 12-frame dwell was itself run at an
  unmeasured frame rate.
- **N7 is therefore a correctness item, not tidiness.** Promoted. New queue item
  **N10** records the environment-dependence itself.
- This take is **not frame-rate-comparable** to the seven earlier sequences, and
  the wider 63.4 ms interval is precisely the confound for the high-edge-on
  question above. **Re-record `palm_back` in better light** before drawing
  conclusions about where spurious flips live.

### Housekeeping — both takes deleted

`2026-08-02_221831_palm_back` (aborted, 24.9 s of 40) and
`2026-08-02_221948_palm_back` (the counted one) were **both deleted on owner
instruction**. The seven earlier sessions are intact and verified after the fact.

*Incidental confirmation of N4: the delete itself failed part-way with `The device
is not ready` — the E: dropout, live rather than historical. It completed on
retry, and the result was re-verified rather than assumed.*

---

## 0.7.1 Redesign: four speed-decoupled `palm_back` takes (owner request, 2026-08-02)

> *"It may be worth decoupling and do 4 recordings at different speeds, so we can
> gauge what is the threshold where we lose detection."*

**Why this is better than the single blended take.** Mixing four speeds into one
clip yields one flip count that cannot answer the question that matters — *at what
speed does the cue start missing crossings?* One take says "6–8 missed"; four
takes locate the **threshold**, which is what a fix or a quality gate has to be
designed against.

Built into `RecordPerceptionSequence.py`:

| sequence | cycle time | prescribed cycles | expected sign changes | duration |
|---|---|---|---|---|
| `palm_back_s1_very_slow` | ~4 s | 10 | 20 | 40 s |
| `palm_back_s2_slow` | ~2 s | 15 | 30 | 30 s |
| `palm_back_s3_medium` | ~1 s | 20 | 40 | 20 s |
| `palm_back_s4_fast` | ~0.5 s | 30 | 60 | 15 s |

Three deliberate design choices, each fixing something that bit us:

1. **Cycle counts are PRESCRIBED, not recalled.** Ground truth comes from the
   protocol, not from the operator remembering a number afterwards. `--cycles`
   overrides when the actual count differs; whichever is used is written to
   `meta.json` along with `expected_sign_changes = 2 × cycles`. **Both units are
   always stored**, so the §0.7 unit trap cannot recur.
2. **The axis is PITCH, stated explicitly** (owner instruction). Not incidental:
   the open TODO is the *pitch*-plane crossing (T2 / §13.7), and the
   `pitch_sweep_*` takes these are compared against are pitch — a yaw take would
   not be comparable. Yaw has its own separate item (T4, §14.1.1) and must not be
   mixed in. The recorder now prints the full axis description at briefing time
   and stores `rotation_axis: "pitch"` in `meta.json`.
3. **A low-frame-rate guard.** The recorder warns loudly at save time when
   `measured_fps < 20`, telling the operator to add light and re-record. A quiet
   15 fps take is worse than a failed one: it looks valid in analysis while being
   non-comparable to the rest of the corpus.

The original `palm_back` sequence is kept runnable but marked **SUPERSEDED**.

**Not yet recorded** — deferred to daylight at the owner's request.

---

## 0.8 Speed-threshold sweep (2026-08-03, daylight) — N3 CLOSED, and totals were lying

The four `palm_back_s*` takes recorded in daylight, all at **24.1–24.5 fps** (the
N10 guard stayed silent), 100% detection on every take, both hands simultaneously.
Operator-counted actual cycles, patched into each `meta.json`.

| speed (s/cycle) | hand | expected | detected | delta | **implausible** | **implaus %** | dup-label frames |
|---|---|---|---|---|---|---|---|
| 4.44 very slow | L | 18 | 17 | −1 | 1 | **6%** | 0 |
| 4.44 | R | 18 | 17 | −1 | 4 | **24%** | 0 |
| 2.14 slow | L | 28 | 30 | +2 | 2 | **7%** | 1 |
| 2.14 | R | 28 | 31 | +3 | 7 | **23%** | 1 |
| 1.29 medium | L | 31 | 27 | −4 | 4 | **15%** | 8 |
| 1.29 | R | 31 | 37 | +6 | 15 | **41%** | 8 |
| 0.96 fast | L | 31 | 28 | −3 | 14 | **50%** | 11 |
| 0.96 | R | 31 | 40 | +9 | 23 | **58%** | 11 |

**"Implausible"** = a flip whose *both* straddling frames sit at edge-on > 0.60.
The analyser reports a flip at `min(eos[k], eos[k-1])`, so this means the hand
would have crossed s = 0 and re-emerged strongly oriented within one ~41 ms frame.
That is beyond plausible hand-rotation speed, so these cannot be genuine crossings.
*(The 0.60 cut is a judgement call, inherited from §0.2's observation that the cue
was stable above it; the monotonic trend below does not depend on the exact value.)*

### Finding 1 — the totals were lying, and this is the headline

**Delta stays small at every speed** (−4 to +9). Judged on totals alone — which is
all §0.7 could do — you would conclude the cue works fine at all four speeds.

**It does not.** The implausible fraction rises monotonically from **6%** to
**58%**. At the fast end, *half or more of every detected flip is physically
impossible*, yet the total still lands near ground truth — because genuine
crossings are being **missed** at roughly the same rate spurious ones are being
**added**. The two errors cancel in the total.

**This resolves the question §0.7 declared unresolvable.** §0.7 said a compensating
mix of missed-plus-spurious "needs per-flip matching against the rotation
timeline." It does not — the edge-on plausibility test separates them from the
recorded data alone, with no timeline needed. **N3 is closed.**

### Finding 2 — the knee is around 1.3 s/cycle

6–24% at 4.44 s/cycle and 7–23% at 2.14 are broadly flat; degradation accelerates
at 1.29 (15–41%) and is severe by 0.96 (50–58%). **Between ~2 s and ~1 s per cycle
is where the sign cue stops being trustworthy.**

**Honest limit:** the "fast" take only reached **0.96 s/cycle, not the 0.5 s
prescribed** — the operator could not sustain the target rate. So the breakdown is
bracketed, not bounded: we know it is already severe by ~1 s/cycle, but not where
it saturates. A genuinely faster take would be needed for that, and may not be
physically achievable by hand.

### Finding 3 — the Left/Right asymmetry is systematic

Right is worse than Left at **every** speed (24 vs 6, 23 vs 7, 41 vs 15, 58 vs 50).
Consistent across four independent takes, so not noise. **Not diagnosed** — a
candidate is the handedness-dependent chirality correction being the one
non-symmetric step in the pipeline (§13.6.1's bug lived exactly there), but that is
a hypothesis, not a finding. Logged as **N11**.

### Finding 4 — duplicate labels scale with rotation speed

Duplicate-label frames per take: **0 → 1 → 8 → 11**, monotonic with speed. This is
precisely DR-1's target failure mode, and it independently reproduces §0.4's
"handedness degrades under rotation" on fresh daylight data. These takes are **raw
pre-DR-1 capture**, so this is the *unmitigated* rate — a direct measure of what
DR-1 has to absorb, and further justification for it.

*Tooling note: a first pass of this analysis under-counted flips because it
appended every hand matching a label, while `AnalyzePerceptionSequences.py`'s
`per_hand_stream` takes only the first per frame. Duplicate-label frames therefore
produced same-index entries that the consecutive-frame check silently dropped. The
discrepancy (33 vs 37) was chased rather than reported, and the corrected numbers
above reconcile exactly with the analyser.*

---

## 0.9 M5d `K` fixture test — BUILT AND PASSING (2026-08-03). Item 1.1 DONE.

`Local_pc/Movement_with_hand_detection/VerifyChiralityFixture.py`. Four ground-truth
clips recorded in daylight (24–25 fps, 100% detection). **All 13 checks pass,
exit 0.**

**It exercises production's real `_is_thumb_outward`**, imported headlessly via
`SDL_VIDEODRIVER=dummy` to work around the `CubeWindow()` import side effect
(§7.3). This is the whole point: a fixture test carrying its own copy of the
formula would have passed happily on 2026-08-01 while the game was inverted, and
would have guarded nothing. When the L7 cleanup removes that side effect, two
env-var lines can simply be deleted.

Three checks per clip, plus a drift guard:

| check | result |
|---|---|
| label matches ground truth | **788/788** across four clips |
| **production sign is correct** | **788/788** — both hands, both facings |
| negative control (label un-mirrored → answer must invert) | **788/788** |
| drift guard: production vs. `LiveSnapDebug` copy | identical |

### THE LABEL CONVENTION — established from data, and it is counter-intuitive

**The label carried through this pipeline is the MIRRORED (apparent) hand, not the
physical hand. A clip of the operator's physical RIGHT hand carries the label
`"Left"`.**

The first version of this test assumed the opposite and failed **0/788** on all
four clips. That was resolved by measurement rather than by flipping the
expectation until it went green:

> In a mirrored preview the operator's physical right hand *necessarily* appears
> on the right of the image — the mirror property, not an interpretation. Across
> every recorded session, for frames holding exactly two distinctly-labelled
> hands, the `"Right"` label fell on the image-**left** hand **100%** of the time
> in every take where hands stay on their natural sides: `static_hold` (288
> frames), `non_crossing` (723), `palm_back_s1_very_slow` (980). The two-hand
> crossing takes sit near 30% precisely *because* the hands deliberately swap
> sides — corroborating, not contradicting.

**Both paths converge on this convention by different routes**, which is exactly
what §13.6.1's fix established and why `_is_thumb_outward` is correct in both:

| path | detection frame | MediaPipe returns | after | final label |
|---|---|---|---|---|
| recorder / debug tool | **mirrored** | mirrored/apparent hand | — | apparent |
| production | **un-mirrored** | true anatomical hand | `_mirror_handedness()` | apparent |

⚠ **Do not "simplify" either path to make the label the physical hand** without
re-deriving this test. The asymmetry is load-bearing.

### The drift guard was fixed, then PROVEN to still have power

`LiveSnapDebug.py` keeps its own copy of `_is_thumb_outward` by design (it must not
import production). Duplication is how the convention drifted once already, so the
guard compares the two ASTs.

Its first run was a **false positive**: it dumped identifiers, so production's
`landmarks` vs the debug copy's `pixel_landmarks` read as drift. Now the landmarks
parameter is canonicalised before comparison.

**A guard changed until it passes is worthless unless it still fails on real
drift**, so it was re-validated against mutants. It accepts a renamed parameter and
different docstring, and **rejects all five**: sign inverted (the §13.6.1 bug
itself), chirality correction dropped, chirality applied to `Right` instead,
cross-product operands swapped, and pinky→ring landmark substitution.

---

## 0.10 M5a `edgeOnMeasure` built (2026-08-03) — item 1.2 DONE, and the duplicate is gone

New shared module **`Local_pc/Movement_with_hand_detection/Resources/palm_geometry.py`**.

**Two deliverables in one change**, and the second was not in the original scope:

1. **The magnitude is recovered.** `_is_thumb_outward` computed the signed area `s`
   and used only `sign(s)`. `edge_on_measure` = `|s| / (‖v1‖·‖v2‖)` = `|sin θ|`
   between the palm vectors: 0 = edge-on (sign is a coin flip), 1 = knuckle row
   square to camera. One division, and it is the observability signal DR-2, M4 and
   M6 all need.
2. **The hand-synced duplicate is retired.** `HandsTriggeredActions.py` and
   `LiveSnapDebug.py` each carried their own copy of the sign formula. **That
   duplication is the direct cause of §13.6.1's production-only inversion.** Both
   now *delegate* to the shared module — the same fix already applied to the
   identity tracker (N6) on the owner's instruction. The module is pure stdlib with
   no cv2/pygame, so the debug tool can import it without triggering
   `CubeWindow()`'s window side effect.

### Verification

| check | result |
|---|---|
| `edge_on_measure` vs `AnalyzePerceptionSequences.edge_on()` | **max abs diff 5.55e-16 over 22,345 hand-frames / 24 sessions** |
| fixture test (item 1.1) after the refactor | **15/15, exit 0** — production sign unchanged, 788/788 |
| corpus below `EDGE_ON_THRESHOLD = 0.15` | 1.54%, matching §0.3's predicted shape |

The exact-match check is not ceremony: **every recorded threshold — above all
`EDGE_ON_THRESHOLD = 0.15`, settled by measurement in §0.3 — is expressed in the
analyser's normalisation.** A different scale in production would silently
invalidate it, with no test failing. `palm_geometry.verify_matches_analyser()`
keeps the two locked together and lives next to the code it constrains.

### The drift guard was re-pointed, not deleted

With both sides delegating, comparing their two one-line bodies is nearly vacuous.
The fixture test now *additionally* asserts that **neither file has reinlined the
maths** — that is the invariant that actually prevents drift now. Both the
body-equality check and the delegation check are kept.

### LIVE-CONFIRMED 2026-08-03

Run via `launch.bat`'s production path immediately after the refactor. **Operator
verdict: "everything working."** Checked: the thumb-outward rule in *both*
orientations on *both* hands (the one non-handedness-symmetric step, and the exact
thing §13.6.1 inverted), plus grab / translate / rotate / tracking-loss release.

Console: **18 DR-1 events, all benign** — 9 identity locks, 9 track-ends as hands
left frame — and **0 switches, 0 duplicate-label repairs, 0 glitch rejections,
0 errors or tracebacks.** The tracker sitting inert is the correct result for
normal use.

This was a **regression test by design**: item 1.2 is behaviour-preserving, so
"nothing changed" *is* the pass condition. It confirms the refactor — production
and the debug tool now sharing one chirality implementation — did not disturb the
shipped behaviour.

*Incidental: this run produced no duplicate-repair events at all, where the first
DR-1 live test (§0.6) produced three. Not enough to conclude anything about N9's
frequency, and N9 stays open.*

### Still open

- **Nothing consumes `edgeOnMeasure` yet.** DR-2 (item 2.2) is the consumer, and
  gating gesture rules on it is a real behaviour change that needs its own live
  test — unlike this one, "nothing changed" will NOT be the pass condition there.

---

## 0.11 DR-2 edge-on exclusion built (2026-08-03) — item 2.2, and a real rule-3 bug it closes

`PalmFacingTracker` in `Resources/palm_geometry.py`, per hand, **shared by
production and the debug tool** (same class, same policy — the tool cannot apply a
different edge-on rule than the game).

### The concrete defect this removes

Rule 3 disarms its snap exception on a single reading:

```python
if not thumb_outward:
    _thumb_outward_snap_allowed[handedness] = False
```

Near edge-on the raw sign chatters at up to **765 flips per 1000 frames** (§0.2) —
impossible as real rotation. So **one** spurious flip silently revokes the
exception. In play: release a cube showing the back of your hand (which arms the
exception), pass through edge-on, and your re-grab is refused with nothing on
screen explaining why. Freezing the sign through the band removes that path
entirely.

### Behaviour

- `edge_on_measure >= 0.15` → measure per frame, as before.
- `< 0.15` → **freeze** at the last confident value; `orientation_valid = False`.
- Exit → resume only after edge-on exceeds `0.15 × 1.6 = 0.24` for ~100 ms
  (`EXIT_DWELL_MS`, expressed in ms per finding N1 rather than the spec's
  30 fps-assuming "3 frames").
- Hand lost → `reset()`, so a stale sign is never carried across a reacquire.
  `_last_known_thumb_outward` deliberately survives (rule 3 needs an orientation to
  record at a tracking-loss release); only the frozen value is dropped.

### A/B under A10 — modest but real, with zero regressions

Replayed over all 24 sessions, measuring what the *gesture layer* sees:

| | result |
|---|---|
| ground-truth streams improved | **2 of 10** |
| ground-truth streams **worsened** | **0** |
| unchanged | 8 |
| chirality controls (`static_hold`, `non_crossing`) where DR-2 did anything | **0** |
| fixture test after wiring | 15/15, exit 0 |

Best case: `palm_back_s2_slow`/Right went from **4 off** ground truth to **exactly
matching**. `two_hand_near_miss` shed 14 flips (10→0, 4→0) in a take where no
crossing was ever scripted. **The effect is modest — 8 of 10 streams unchanged —
and that is stated rather than dressed up**; it passes A10 on "measured
improvement, no regression, inert on controls," not on magnitude.

> **Test-design error worth recording:** the first A/B run flagged
> `two_hand_near_miss` as a violated control. It is not a chirality control — it is
> the *identity* control from §0.4, and 9.7–12% of its frames sit below edge-on
> 0.15 because hands naturally turn edge-on as they pass each other. The true
> chirality controls are `static_hold` and `non_crossing`, and DR-2 was inert on
> both. The fault was in the test's control list, not in DR-2.

### ⚠ Partial vs. the spec, deliberately

M5e also specifies **carrying the sign through the band by integrating angular
velocity from M6** (the kinetic-depth effect), so a genuine crossing registers
instantly on exit. **M6 is item 2.3 and is not built.** Consequence: a real
crossing is still detected correctly, but only after the hand leaves the band and
the exit dwell elapses — **late by ~100 ms+, never wrong**. Revisit when 2.3 lands.

### Live test 2026-08-03 — passed, with one test-design failure of mine

Operator: **test 4 (regression) clean — "it does not seem anything regressed."**
Zero errors across two runs; 3 identity switches, 0 duplicate repairs.

**Test 3 was unobservable and that was my error.** I asked the operator to judge
whether "the game agrees you have turned over" — but production exposes **no
on-screen indicator** for the thumb-outward state; its only observable consequence
is whether a grab is permitted. The operator correctly reported they could not
tell. *Lesson: do not ask a human to verify a state the UI does not surface —
measure it instead.*

**Measured properly afterwards, over 144 freeze episodes in the corpus:**

| | freeze duration |
|---|---|
| median | **96 ms** |
| p90 | 163 ms |
| p99 | **1781 ms** |
| max | **3480 ms** |

The median matches the ~100 ms design intent and is imperceptible (the operator
felt nothing). **The tail was not anticipated**: `two_hand_near_miss` medians
1.6 s and peaks at 3.5 s, because the hand is held *sustained sideways-on* and the
cue is genuinely unreadable that whole time. Not a mechanism defect — but it means
rule 3 can act on a reading up to ~3.5 s stale in that pose. Recorded in
`GAME_RULES.md` rather than left implicit. A max-freeze cap was considered and
**not** added: the spec's answer is to suppress `palmFacing`-dependent gestures via
`orientationValid`, which is the correct fix once a consumer exists — inventing a
cap now would be exactly the heuristic pile-up the project avoids.

### A separate defect surfaced by the same test — see queue N12

The operator observed a **held cube jumping as the hand crosses the horizontal
(pitch) plane**, settling once the crossing completes. **Not DR-2** (which never
touches a held cube's position). It is the **third independent symptom** of
§14.1's fingertip-anchored translation, alongside T4's yaw/palm-sinking and Object
Jump Correction — and precisely what M8a predicted. Strengthens the case for the
M8a A/B (item 3.3). Full entry: `PART_ONE.md` §3.1 N12.

### Still open
- `orientation_valid` is computed and returned but **no rule consumes it yet** —
  it is the natural hook for `HandState.quality.orientationValid`.
- `_ASSUMED_FPS = 24.0` is hard-coded here as well as in `hand_identity.py`.
  **N7 covers both; do not fix one alone.**

---

## 0.12 M6b measured BEFORE adoption (2026-08-03) — the SVD frame is a REGRESSION; keep the shipped frame, take the observability metric

Item 2.3, stage 1. The spec warns that changing the frame construction can silently
invert yaw/roll (§13.7's recorded lesson), so M6b's SVD frame was **measured against
the shipped Gram-Schmidt frame on identical recorded input before any production
change.** That decision paid for itself immediately.

### Result: do NOT adopt M6b's frame

| | shipped Gram-Schmidt | M6b SVD |
|---|---|---|
| left-handed frames (must be 0) | 0 | 0 |
| **>30° per-frame orientation jumps** | **1533** | **3233** |

**2.1× worse overall, and worse specifically where the shipped frame is clean:**

| control sequence | shipped | SVD |
|---|---|---|
| `non_crossing` | 1 | **175** |
| `depth_sweep` | 0 | **64** |
| `two_hand_near_miss` | 0 | **57** |
| `known_right_palm` | 0 | **15** |
| `static_hold` | 0 | 0 |

**Diagnosis (likely, not proven):** singular vectors are defined only up to sign,
and when `S[1] ≈ S[2]` the 2nd and 3rd axes can **swap between consecutive
frames**. The implementation enforced right-handedness but not *temporal
continuity*. A continuity-enforcing variant may well fix it — but that is a **new
design, not M6b as specified**, and would have to be measured the same way.

**Under A10 this is a null/negative result and is recorded rather than retried
blindly.** Chirality was never violated (0 left-handed frames in either
construction), so this is a *stability* failure, not the inversion the spec warned
about.

### What IS validated: `observability` is a far better conditioning signal

| signal | range across the whole corpus |
|---|---|
| **`observability` = 1 − S₃/S₂ (M6b)** | **0.046 → 0.908** |
| `conditioning_norm` (shipped) | 0.058 → 0.092 |

`observability` collapses to **0.05–0.15 at exactly the pitch crossings**
(`pitch_sweep_slow` 0.046, `palm_back_s2_slow` 0.071–0.096) and sits at
**0.75–0.91 on every control** (`static_hold` 0.818, `non_crossing` 0.749,
`known_*` 0.834–0.890). `conditioning_norm` spans a narrow band across
*everything* and barely discriminates. Per-session correlation between the two is
only 0.27–0.81, with several near zero or negative — **they are not the same
signal.**

> ### ⚠ CORRECTION (same day): "adopt observability as the conditioning signal" was WRONG
>
> This section originally concluded that `observability` should **replace**
> `conditioning_norm`, inferring it from the wider dynamic range. **That inference
> was not tested when it was written, and when tested it failed.**
>
> A/B driving the *shipped* filter with each signal, identical input, same metric
> the 2026-08-02 filter audit used (§13.7.1):
>
> | config | >30° jumps | >60° jumps |
> |---|---|---|
> | no filter at all (α ≡ 1) | 1533 | 730 |
> | **shipped: `conditioning_norm` 0.015/0.06** | **1386** | **611** |
> | best `observability` (0.40/0.90, swept) | 1473 | 663 |
>
> Observability beats no-filter but **loses to what is already shipped**, at every
> threshold pair swept (0.10/0.40 through 0.40/0.90).
>
> **Why, and it is not mysterious:** `conditioning_norm` measures the conditioning
> of *the frame actually in use* — the orthogonalised `wrist→middle_MCP` length
> against the knuckle axis. `observability` measures the conditioning of the
> **palm-plane fit**, i.e. of the construction rejected above. The useful
> conditioning signal is the one matched to the estimator you are actually running.
>
> **Lesson: a wider dynamic range is not evidence of a better signal.** Measure the
> thing you care about, not a proxy for it.

**Revised conclusion:**

- **Keep** the shipped Gram-Schmidt frame for orientation. *(unchanged)*
- **Keep** `conditioning_norm` driving the current reliability blend. **Do not
  swap it for `observability`.**
- `palm_observability()` is built, numpy-free and verified to 1.6e-11 against
  numpy — **retained for M6c**, where it is used to shape a *per-axis* covariance
  rather than as a scalar blend weight. That is a different use, and this null
  result does not condemn it there.
- **A6's "one metric, not two" is therefore NOT yet settled.** It becomes a real
  decision only when M6c ships and something actually consumes observability. Until
  then only one metric is in the estimation path, so the constraint is not violated.

*Implementation note for whoever builds M6c: computing singular values needs numpy,
which `HandsTriggeredActions.py` does not currently import (it is pure `math`).
Decide deliberately whether to add the dependency or compute the 3×3 eigenvalues in
closed form.*

### A tooling error caught in the same pass

The first run of this comparison reported **575 of 576 frames in `static_hold` as
>30° jumps** — impossible for a hand held still. Cause: iterating `rec["hands"]`
with a single `prev`, so consecutive entries alternated Left→Right→Left and the
angle *between the two hands* was being counted as a per-frame jump. **This is the
same bug class as the §0.8 per-hand-stream error, caught the same way — by a number
that could not be true.** Fixed to track the previous frame per hand; corrected
figures are the ones above.

---

## 0.13 M6c anisotropic covariance — NOT DEMONSTRATED (2026-08-03). Nothing shipped.

Item 2.3, stage 3. Three parameterisations tried, replayed over all 24 sessions.
**None beat the shipped isotropic filter. `HandOrientationFilter` stays.**

### What was built

An **error-state** update rather than a full UKF: `q_err = q_pred⁻¹ ⊗ q_meas` →
log map → 3-vector in the body frame → per-axis gain `k_i = P/(P + R_i)` → exp map
→ compose. That is 6c's mechanism (diagonal `R` in the body frame), numpy-free so
it ports to the web target. Sigma points buy process-nonlinearity handling that a
small-angle error state largely removes.

### Why the first two attempts looked like wins and were not

**Attempt 1 (single sigma for all axes) scored spectacularly** — `>60°` jumps
589 → **0**, max 180° → 53°. It was over-damping wearing an anisotropic costume:
one parameter damped every axis uniformly.

**The metric that caught it** — and which must be used in any future attempt:

> `tracking_error = angle(fused, raw_measurement)` on frames where
> `observability > 0.6`, i.e. where the measurement is trustworthy and the filter
> has **no excuse to disagree**.

| | well-cond | fast motion |
|---|---|---|
| shipped | **1.40°** | **5.04°** |
| attempt 1, σ=4 | **37.32°** | 59.28° |

**Jump counts reward a filter that ignores the hand.** A filter with gain ≈ 0 has
zero jumps and is useless. Never judge an orientation filter on jump counts alone.

**Attempt 2** conflated the two parameters again (one σ for both the well-observed
and the blown axes), forcing a trade the spec never intended.

### Attempt 3 — the spec's actual two-parameter form, and the honest result

`R = diag(σ_long², σ_base²/obs, σ_base²/obs)`, swept σ_long ∈ {0.1, 0.2, 0.3} ×
σ_base ∈ {0.5, 1, 2, 4}:

| σ_long | σ_base | >60 | p99 | max | trk_well | trk_fast |
|---|---|---|---|---|---|---|
| *(shipped)* | | **589** | 120.2 | 180.0 | **1.40°** | **5.04°** |
| 0.30 | 1.00 | 649 | 92.5 | 177.2 | 5.79° | 11.81° |
| 0.30 | 2.00 | 562 | 85.7 | 173.7 | 13.92° | 25.12° |
| 0.30 | 4.00 | 472 | 82.4 | 166.6 | 29.05° | 45.12° |

**Every config that improves the tail costs 3–10× worse tracking.** No config wins
both. Under A10 that is a null result: **not shipped, not tuned into looking good.**

### ⚠ This does NOT disprove M6c — it disproves *this approximation of it*

The implementation holds **P fixed at 1.0**; there is no covariance propagation. A
real UKF grows `P` while coasting on an unobservable axis, which *raises* the gain
when observability returns and lets it re-converge fast. That is materially
different behaviour and is exactly where 6c's benefit is supposed to live.

**A fair next attempt must propagate the covariance** — i.e. build the actual
filter, not the fixed-gain approximation. Do not re-run the fixed-P version and
expect a different answer.

### 0.13.1 — The propagated-covariance filter WAS built, and it also loses (2026-08-03)

§0.13 said the fixed-P approximation was not a fair test and that a real filter must
propagate covariance. **That filter was then built** — `Resources/orientation_filter.py`,
a full error-state multiplicative Kalman filter on SO(3), numpy-free:

```
predict   q_pred = q ⊗ exp(ω);  ω *= OMEGA_DECAY;  P += Q      <- uncertainty GROWS while coasting
update    dz = log(q_pred⁻¹ ⊗ q_meas)                          <- innovation, body frame
          R  = diag(σ_long², σ_base²/obs, σ_base²/obs)         <- 6c anisotropy
          K_i = P_i/(P_i+R_i);  q = q_pred ⊗ exp(K·dz)
          P_i = (1-K_i)·P_i                                    <- shrinks ONLY when trusted
```

This is the growing-while-lost / snapping-back-when-found mechanism §0.13 identified
as missing. **It works exactly as intended and still loses.**

**54 configurations swept** (σ_long ∈ {0.02…0.3} × σ_base ∈ {0.6, 1, 2} × Q ∈ {0.005…0.3}):

| config | >60 | p99 | max | trk_well | trk_fast |
|---|---|---|---|---|---|
| **shipped isotropic** | 589 | 120.2 | 180.0 | **1.40°** | **5.04°** |
| UKF σ_l=0.3 σ_b=2.0 Q=0.005 | **1** | **38.0** | **62.7** | 23.65° | 42.40° |
| UKF σ_l=0.02 σ_b=0.6 Q=0.3 | 596 | 102.7 | 175.9 | 3.56° | 7.55° |

**The trade is absolute.** Push the tail down and tracking collapses; tighten
tracking and the tail benefit vanishes entirely. **No configuration wins both.**

### ⭐ Why the shipped heuristic is so hard to beat — the actual insight

The shipped filter is **not really a continuous filter — it is a switch.**
`alpha_iso` saturates at 1 when well-conditioned (so `fused == raw`, a pure
passthrough, zero lag) and drops to 0 when degenerate (hard damp, full prediction
trust). **That bimodality is matched to the failure mode**: degeneracy here is
*rare and severe*, not gradual. A Kalman filter necessarily applies **graded**
damping on every frame, so it pays lag continuously to buy protection that is only
needed occasionally.

**This reframes A6's "delete `HandOrientationFilter`" obligation.** The filter is
not a crude stand-in for a principled estimator — its crudeness *is* the fit to the
problem. Any replacement must reproduce that near-bimodal response, not smooth it
away. **Four independent attempts have now failed to beat it** (SVD frame,
observability-as-blend-weight, fixed-P anisotropic, propagated-covariance
anisotropic).

**Do not attempt a fifth without a new idea.** Candidates not yet tried, recorded so
the next attempt is not a repeat: (a) gate the Kalman update so it is a passthrough
above an observability threshold and only engages below it — i.e. keep the
bimodality and use the covariance only inside the bad band; (b) full 3×3 `P` with
the frame-rotation cross-term this diagonal version omits; (c) accept the tail and
address it at the *source* (M2/M4 landmark quality) rather than by filtering.

### 0.13.2 — ROOT CAUSE FOUND: the tail is NOT an observability problem (2026-08-03)

> **⚠ NUMBERS CORRECTED BY THE §0.15 AUDIT — read it before quoting anything below.**
> The census here was built on raw-label streams with no duplicate-label or
> frame-continuity guard, which inflated the tail. Corrected on DR-1
> identity-corrected streams: **>60° jumps 730 → 572, and the "82% at
> observability ≥ 0.60" figure → ~77%** (73% with the strictest guards).
> **The conclusion survives; the numbers do not.** Quote §0.15's.

Attempt 5 gated the KF to passthrough above an observability threshold, keeping the
shipped filter's zero-lag bimodality and using the covariance only inside the bad
band. **It tracked perfectly (0.000°) and left the tail untouched** (>60: 698–742 vs
baseline 589; max unchanged at 180°).

That result prompted the diagnostic that should have come first — **where do the
large RAW jumps actually occur?**

| observability | % of frames | >60° jumps | >60 per 1k frames |
|---|---|---|---|
| [0.00, 0.15) | 0.1% | 2 | **166.7** |
| [0.15, 0.30) | 0.3% | 22 | **318.8** |
| [0.30, 0.45) | 0.6% | 37 | **278.2** |
| [0.45, 0.60) | 1.4% | 72 | **235.3** |
| [0.60, 0.75) | 4.2% | 155 | 166.3 |
| **[0.75, 0.90)** | **82.6%** | **349** | **18.9** |
| [0.90, 1.01) | 10.9% | 93 | 38.3 |

**Both readings are true and the second is the one that matters:**

1. **Per frame, low observability IS ~17× more dangerous** (319/1k vs 19/1k). The
   premise is not nonsense.
2. **But 82% of all large jumps occur at observability ≥ 0.60** — because that is
   97.7% of frames. **Only 18% of the problem lives in the band M6c can reach.**

### This single fact explains all five failures

- **Attempts 1–4** keyed damping to observability. To catch the 82% they had to damp
  *everywhere*, which is why every tail improvement cost 3–17× worse tracking.
- **Attempt 5** acted only inside the band. It therefore addressed only 18% of the
  jumps and produced no tail benefit at all — while tracking perfectly.

Two failure modes, one cause, seen from opposite sides. **M6c's mechanism is sound
and simply does not apply to the dominant failure here.**

### Consequence for the plan — redirect, do not iterate

A sixth attempt at anisotropy is **not** warranted. The 82% of jumps occurring in
well-conditioned frames are a **landmark-quality** problem, not a pose-estimation
one: at 24 fps a >60° change in 41 ms implies >1460°/s, at or beyond the human wrist
limit, so most of these are bad landmarks rather than real motion.

That points at option (c) from §0.13.1, now with evidence behind it:

- **1.4 (M2 bone-length calibration)** and **1.6 (M4 precision weighting + χ²
  gating)** attack the tail at its source. M4's χ² innovation gate in particular is
  designed to reject exactly this: a physically implausible single-frame excursion.
- **T1/T2 were queued behind 2.3 on the assumption that better pose filtering would
  fix them. That assumption is now measured false for 82% of the failures.** They
  should be re-tested after 1.4/1.6, not after 2.3.

**2.3 is therefore DEPRIORITISED, not merely paused** — and `orientation_filter.py`
stays parked and unwired.

### 0.13.3 — Salvage assessment: what the 5 failed attempts left behind (2026-08-03)

Owner question: *do the built artifacts have value somewhere we did not think of?*
Probed rather than assumed.

**Tested and REJECTED — repurposing the machinery as M4's χ² gate.** A χ² innovation
gate needs a prediction, an innovation and an innovation covariance; the parked
filter has all three, and unlike graded anisotropy a gate is **bimodal** (the shape
that keeps winning) and targets implausible jumps *wherever* they occur — including
the 82% in well-observed frames. It looked like the right salvage. It is not:

| | >60 | max | trk_well | rejected |
|---|---|---|---|---|
| shipped | **589** | 180° | **1.40°** | — |
| χ² gate p=0.01 | **2167** | 180° | 17.16° | 14.6% |
| physical gate 25° | **14319** | 180° | 102.96° | 59.9% |

**3.7× and 24× worse.** Rejecting a measurement means coasting on the model; the
model diverges; the eventual re-acceptance produces a *larger* jump than the one
suppressed. **The gate manufactures the failure it targets.**

### ⭐ The finding underneath ALL of it: the motion model is weak

> ## ⚠⚠ RETRACTED BY THE §0.15 AUDIT (2026-08-03). This subsection is WRONG.
>
> **"60% of frames" is a closed-loop cascade statistic, not a prediction error.**
> Once the gate rejects a frame the filter coasts, the prediction drifts away
> from the raw stream, and following frames keep failing until the 8-frame coast
> limit force-accepts — so one bad frame books up to 8 "rejections". Measured
> open-loop on identity-corrected streams, the one-frame constant-angular-velocity
> model has **median error 4.2–4.5°** and exceeds 25° on only **6.4–11.4%** of
> frames. The model is *sound in the bulk*; its tail is the same bad-landmark
> population as the jump tail.
>
> **The χ² gate's own failure remains real** (a gate that coasts on any model
> cascades — see S5's anti-cascade rule), but the generalisation drawn from it
> does not. M7's ⚠⚠ STOP block is amended accordingly. Full horizon table: §0.15.

The physical gate rejects **60% of frames at a 25° threshold**, i.e. a one-frame
constant-angular-velocity prediction routinely disagrees with the measurement by
more than the typical motion (mean frame-to-frame change: 9.9°).

**This unifies every failure in §0.13–§0.13.2.** The shipped filter wins because
`alpha` saturates at 1 and it therefore *ignores the prediction almost always*.
Graded blending, coasting and gating all lean on the model to different degrees, and
all inherit its weakness.

### Verdict

**No value:** the anisotropic update; the χ² / physical gate for orientation.
Both measured, both worse, both recorded so they are not retried.

**Real value, two items:**

1. **`palm_observability()` → `HandState.quality.orientationValid` (M6e).** It is a
   *correct* observability signal — collapses at crossings, 0.046–0.908, matched to
   numpy at 1.6e-11, numpy-free and portable. It simply is not what drives the tail.
   Its home is the §2 quality contract that gestures branch on, not the filter.
2. **⚠ A WARNING FOR ITEM 3.1 (M7), worth more than the code.** M7's forward
   prediction extrapolates with *this same* constant-angular-velocity model, up to
   ~80 ms ≈ 2 frames. **The model is measurably unreliable at ONE frame.**
   **Before building M7, measure the model's prediction error and confirm it is fit
   to extrapolate with.** M7's premise — "net perceived latency can go to zero" —
   assumes a predictor this data does not yet support.

*Caveat, stated because it bounds the claim: M4's χ² gate was designed for the
Object Jump case — a whole-hand POSITION teleport, where the excursion is
unambiguous and position is far easier to coast. **This result condemns the gate for
ORIENTATION only**; item 1.6 should still evaluate it for position.*

### What this run did establish

The shipped hand-rolled filter was **re-validated a third time** on the full
24-session corpus (1533 → 1374 `>30°`, 730 → 589 `>60°` versus no filter). The
2026-08-02 audit kept it on a smaller sample; it has now survived a deliberate
attempt to replace it.

**A6's "delete `HandOrientationFilter`" obligation is therefore NOT met and the
filter stays.** The bar is a replacement that is measurably better on *both*
families of metric — which is a higher bar than "more principled".

---

## 0.14 M2 built and MEASURED (2026-08-03) — the fixed-bone-length prior does not exist in this sensor

> **✅ VERDICT UPHELD, measurement design corrected (§0.15).** The scripts below
> pooled **absolute** metre lengths, while §2f defines the target as *proportions
> plus a per-session scale constant*. Re-measured on the correct quantity
> (`audit_m2_proportions.py`): palm-normalised **proportions** give median IQR
> 6.5–8.7% and **0/21 bones inside 2%** — no better than absolute. Cross-session
> disagreement of normalised medians reaches **32–40%**, worst on the
> *back-of-hand* takes. **The premise-kill stands.** External corroboration
> (§10.2): `worldLandmarks` are a GHUM-average-hand fit with a documented
> **1.3–1.5 cm** mean 3D error, and Google has an **open issue (#5156) for palm
> world landmarks collapsing when the back of the hand faces the camera.**
> **→ The replacement is S7 (queue 1.7): impose a fixed skeleton by constrained
> IK instead of measuring one.**

Queue item 1.4. `Resources/hand_model.py` built (numpy-free, portable): 21-bone
topology, low-motion-gated collection, running **median** (never mean — occlusion
outliers are severe and one-sided), IQR freeze gate, per-user persistence, plus
`pose_normalised_residual()` for N2.

**Then measured against the spec's own acceptance criterion, and it fails.**

### The measurement

Pooled **still frames only** (motion < 3% of hand size) across all 24 sessions —
i.e. calibrated exactly as §2f prescribes, with pose diversity:

| | IQR / median, per bone |
|---|---|
| **freeze gate requires** | **< 2%** |
| Left, palm bones | median **10.49%**, worst 11.93% — **0/5 inside 2%** |
| Left, fingertip bones | median 11.37%, worst 15.46% — 0/5 |
| Right, palm bones | median **6.28%**, worst 12.59% — **0/5 inside 2%** |
| Right, fingertip bones | median 11.36%, worst **22.21%** — 0/5 |

Independent half-vs-half check (calibrate on half the sessions, verify on the
other): worst bone disagreement **4.02%** (Left) and **24.33%** (Right), against a
< 2% target.

**Not a single bone, in any group, converges.** The best subset is Right-hand palm
bones at ~6%, still 3× outside the gate.

### This does NOT contradict §0.2 — it is a different quantity

§0.2 measured the palm **rigidity residual** at 2.76 mm (inside target): a
rigid-body fit of the palm *within* a pose. This measures bone length *across*
poses. **Within a pose the palm is rigid; across poses the measured lengths shift
by 6–12%.** Both are true, and the second is what a persistent body schema needs.

### What it means

**MediaPipe's `worldLandmarks` do not encode a pose-consistent hand skeleton.**
Depth error is pose-dependent, so bone lengths derived from them inherit that
dependence. M2's premise — that ~20 fixed lengths are "the strongest prior
available, free to obtain" — **does not hold for this sensor at the stated
precision.**

Consequences, stated plainly because several queue items rest on this:

- **1.4's acceptance criterion is unreachable as written.** Do not tune the gate to
  make it pass; 2% is not available.
- **N2 is confirmed and my proposed fix FAILED.** `pose_normalised_residual()`
  (dividing out the rigid palm's common-mode scale) moved the moving/still residual
  ratio only from **2.05× to 1.99×**. The pose effect is not common-mode, so it does
  not divide out. **N2 stays open and needs a different idea.**
- **1.6 (M4) loses its intended per-landmark error signal.** M4 was to consume the
  bone residual; that residual is dominated by pose, not by landmark quality.
- **4.1 (M9 metric depth) and T4 are at risk** — both depend on 1.4 supplying a
  reliable scale reference, which it cannot at better than ~6–10%.

### Options, none yet chosen

1. **Relax the target and use bone lengths as a SOFT prior (~6–10%).** Still useful
   for gross outlier rejection (a bone 3× too long is certainly wrong), useless for
   precision depth.
2. **Calibrate per-pose rather than globally.** Within a pose, bone CV is ~1%
   (§0.3), so short-horizon consistency is achievable — but it does not persist,
   which is most of what a body schema was for.
3. **Question the input.** Bone lengths from `worldLandmarks` inherit its depth
   error. Screen landmarks are far better conditioned (§0.2); a screen-based
   foreshortening formulation may be the better route to M9 than a metric skeleton.

*Implementation note: `_try_freeze` currently fires as soon as all bones pass with
`MIN_SAMPLES`, which can freeze prematurely on an early tight window (observed:
"0/21 stable" reported alongside "frozen=YES"). Fix before any use — though given
the above, nothing should be relying on the frozen model yet.*

---

## 0.15 AUDIT of this session's negative results (2026-08-03) — two artifacts found, the rest confirmed

Owner instruction: *"Assume the nulls are artifacts of the measurement code until
proven otherwise. Find the ones that are."* Audited by re-deriving every
load-bearing number with corrected harnesses:
`analysis/audit_jump_provenance.py` and `analysis/audit_m2_proportions.py`.
Both reproduce the published numbers exactly before applying corrections, so the
deltas below are attributable to the corrections alone.

### The systematic flaw: every 2.3-era harness measured a pipeline that no longer exists

All of `where_are_jumps.py`, `m6c_ab.py` (whose stream loop every other A/B
imports), `obs_ab.py`, `m6_ukf_ab.py`, `m6_gated_ab.py` and `chi2_probe.py` build
per-hand streams keyed on the **raw MediaPipe label**, with **no duplicate-label
guard and no frame-continuity guard** — on a corpus deliberately recorded to
contain label flips, duplicate labels and association swaps (they are what DR-1
was built from, §0.4). Production runs DR-1; the A/Bs replayed pre-DR-1 streams.
Three artifact mechanisms, all real in this data:

1. **Duplicate-label frames** (25+ across the corpus): both hands enter the same
   stream; the angle *between the two hands* is counted as a per-frame jump.
   The §0.12 static-hold bug (575/576 false jumps), reduced but not eliminated.
2. **Label flips**: the stream silently switches physical hand; the cross-hand
   delta is counted as a jump — typically at HIGH observability, since both
   hands are usually well-conditioned when this happens.
3. **Detection-loss gaps** (2.9% of frames under fast motion): frames ~2–15
   intervals apart compared as if consecutive.

### Corrected raw-jump census (validated: V0 reproduces the published numbers)

| variant | >30° | >60° | >60 at obs ≥ 0.60 |
|---|---|---|---|
| V0 published method (raw label, no guards) | **1533** | **730** | 597 (**81.8%**) |
| V1 + dup-skip + continuity guard | 1194 | 482 | 352 (**73.0%**) |
| V2 DR-1 identity-corrected + guards | 1350 | 572 | 440 (**76.9%**) |

**⚠ 22–34% of the published jump tail was measurement artifact.** Corrected
headline numbers: **~480–570** large jumps, **~73–77%** at observability ≥ 0.60.

**The qualitative §0.13.2 conclusion SURVIVES**: even on clean streams, roughly
three quarters of large jumps occur in well-observed frames, so the
redirect away from observability-keyed anisotropy stands. Quote the corrected
numbers from now on, not 730/82%.

### VERDICT 1 — the five nulls are GENUINE (re-confirmed on clean streams)

The full A/B was re-run on V2 identity-corrected streams (filters reset at every
run break, as live tracking loss would):

| config | >30 | >60 | p99 | max | trk_well |
|---|---|---|---|---|---|
| no filter | 1350 | 572 | 123.3 | 179.9 | — |
| **shipped isotropic** | **1183** | **442** | **96.6** | 179.9 | **1.34°** |
| UKF best-tail (σl 0.3, σb 2.0, Q 0.005) | 690 | 11 | 39.4 | 121.7 | 22.48° |
| UKF best-track (σl 0.02, σb 0.6, Q 0.3) | 1242 | 526 | 98.4 | 175.9 | 3.20° |
| UKF gated (gate 0.6) | 1351 | 578 | 119.6 | 179.9 | 0.00° |
| iso blend driven by observability 0.40/0.90 | 1276 | 499 | 94.2 | 177.1 | 1.76° |

The trade is structurally identical to the published one: every tail improvement
still costs an order of magnitude in tracking; the gated variant still does
nothing; observability as a blend signal still loses to `conditioning_norm`.
**The Kalman-family discard, the SVD-frame discard and the shipped filter's
retention are all CONFIRMED. Do not revisit on artifact grounds.**

### VERDICT 2 — the "motion model is weak" finding is an ARTIFACT. M7's warning is retracted.

`chi2_probe.py`'s "one-frame prediction disagrees by >25° on **60%** of frames"
is a **closed-loop cascade statistic, not a prediction error**: after one
rejection the filter coasts, the prediction drifts further from the raw stream,
and subsequent frames keep failing until the 8-frame coast limit force-accepts —
one bad frame books up to 8 "rejections". Measured honestly (open loop:
ω from the last two raw frames, applied forward, on identity-corrected streams):

| horizon | median | mean | p90 | >15° | >25° |
|---|---|---|---|---|---|
| 1 frame (~42 ms) | **4.2–4.5°** | 8.6–12.6° | 18.6–28.4° | 13–18% | **6.4–11.4%** |
| 2 frames (~83 ms) | 7.3–8.0° | 15–20° | 34–51° | 27–31% | 15–20% |
| 3 frames (~125 ms) | 10.8–11.8° | 21–26° | 51–72° | 39–43% | 25–29% |

(Ranges: seeded-sane vs all triples.) **The constant-angular-velocity model is
fine in the bulk at one frame and workable at M7's capped ~80 ms horizon with
confidence scaling; the heavy tail is the same bad-landmark population as the
jump tail, which M7 step 3 (scale horizon by quality) already handles.**
This table IS item 3.1's "required first task", done. The ⚠⚠ STOP block in M7 is
amended accordingly. *(Note: this measures ORIENTATION prediction; position
prediction error is expected to be more benign and is still unmeasured.)*

The χ² gate's closed-loop failure (§0.13.3) was real — a gate that coasts on
this motion model does cascade — but its magnitude was inflated by the same
artifact streams, and the generalisation drawn from it ("the model is
measurably unreliable at ONE frame") was wrong.

### VERDICT 3 — the M2 premise-kill is GENUINE, but it was measured against the wrong quantity

§0.14's scripts pooled **absolute metre lengths across sessions and poses** and
applied the <2% gate to those — while §2f defines the calibration target as
*"proportions plus a per-session scale constant"*, and `hand_model.py`'s own
header says worldLandmark units are "self-consistent-but-unscaled". The audit
re-measured the right quantity (`audit_m2_proportions.py`, same still-frame
gate, dup-label frames excluded):

| measure | Left | Right |
|---|---|---|
| A absolute (published method) | median 7.6%, 0/21 inside 2% | median 7.5%, 0/21 |
| B per-frame palm-normalised **proportions** | median 8.7%, 0/21 | median 6.5%, 0/21 |
| C cross-session normalised worst disagreement | **39.9%** (`known_right_back`) | **32.3%** (`known_left_back`) |

**Proportions do not rescue the gate. §0.14's verdict is CONFIRMED on the
correct quantity** — and the worst cross-session offenders are the
*back-of-hand* takes, which matches the externally documented failure mode
(MediaPipe issue #5156, "hand world landmarks collapse for the back of the
hand", open). The premise-kill stands; the measurement-design error is recorded
so the next acceptance test is written against the quantity the module claims.

### Binding rule for all future harnesses (add to §7.1)

> **Stream construction in any replay harness must (a) replay
> `hand_identity.py` (DR-1) to assign identity, (b) drop or resolve
> duplicate-label frames, and (c) break runs at frame-index gaps.**
> `audit_jump_provenance.py`'s `build_v2()` is the canonical loader — import or
> copy it; do not key streams on the raw label again. The published-method (V0)
> loader exists there too, solely to reproduce historical numbers.

---

## 0.16 M3a anatomical constraints BUILT (2026-08-04) — item 1.5 DONE, and the control caught a wrong constraint

`Resources/hand_anatomy.py` (stdlib-only, numpy-free, no import side effects —
importable by production and the debug tool alike, per the N6 precedent), with
`analysis/m3a_violations.py` and `analysis/m3a_diagnose.py`.

### The headline

| condition | violation rate |
|---|---|
| **`static_hold` CONTROL (valid poses)** | **0.00%** (0 / 1446 hand-frames) |
| back-of-hand (`known_right_back`, hand under test) | 5.12% |
| finger self-occlusion (hand under test) | 5.62% |
| pitch / edge-on crossing (`pitch_sweep_*`, `palm_back_*`) | **33–59%** |

A zero false-positive rate on the control is the property that matters: 1.6 will
gate on this bit, and a validity bit that fires on good frames is worse than no
bit at all.

### ⚠ The first version was WRONG, and only the control revealed it

It reported **93.7% violations on `static_hold`** — i.e. it claimed a still,
ordinary hand is anatomically impossible 94% of the time. Diagnosed by dumping
distributions (`m3a_diagnose.py`) rather than by relaxing thresholds, which is
the trap §0.14 records against M2 ("do not tune the gate to make it pass"). Two
genuine errors:

1. **"All three joints of a finger co-flex" is anatomically false.** The MCP is a
   condyloid joint that extends — indeed hyperextends to ~45° — while the
   interphalangeal joints flex. That is an ordinary resting posture. Measured:

   | axis pair | negative on valid hands |
   |---|---|
   | dot(MCP axis, PIP axis) | **31.1%** |
   | dot(PIP axis, DIP axis) | **0.0%** (min +0.41, p05 +0.69) |

   Only the IP joints are obligate co-flexors, so the unidirectional prior — and
   with it the bas-relief disambiguation term — belongs to the **PIP↔DIP pair
   alone**. The surviving constraint has an enormous margin: worst observed
   agreement +0.41 against a threshold of 0.0.

2. **The hinge plane was ill-conditioned.** Built from metacarpal×proximal it
   reported a median 25.5° out-of-plane "violation" on a still hand, because the
   MCP bend has a median of only ~14° so the two vectors are near-parallel and
   their cross product is noise. Rebuilt from **proximal×middle**, testing the
   distal phalanx: median 11.5°, p95 16.7°, max 19.4°.

### Where the numbers come from — and the trap that was avoided

S6 cites Spurr et al. for constraints that halve depth error (FreiHAND depth
error 15% → 50% reduction, confirmed from the paper). **But that paper publishes
no table of limits — its limits are FITTED FROM DATA.** The reference
implementation, `MengHao666/Hand-BMC-pytorch`, is **MIT but ships no constraint
values at all**: it generates `bone_len_*`, `curvatures_*`, `PHI_*` and
`CONVEX_HULLS.npy` from RHD, GANerated, STB and FreiHAND. The MIT licence covers
that code, **not** those research-licensed datasets.

Two reasons that route was rejected, either sufficient on its own:
- **Licensing** — this project is intended for commercial release (queue N13).
- **Circularity** — fitting the gate to MediaPipe-derived data is precisely the
  "MediaPipe judging itself" weakness that item 0.5 existed to remove, and 0.5 is
  now dropped, so nothing would have caught it.

The constraint **form** is therefore taken from the paper (a method, freely
usable) and the **numbers** from clinical goniometry norms — anatomical facts,
unlicensed: MCP flexion 0–90° / hyperextension to 45° / abduction ±25°; PIP
flexion 0–100°; DIP flexion 0–80°; and **abduction occurs only at the MCP, never
at the interphalangeal joints**, which is the planar-articulation constraint
stated as anatomy rather than as a tuned threshold. **Do not re-derive these from
the corpus.**

### Deliberately chirality-free

No constraint here reads the handedness label. That is a design choice, not an
oversight: the label carried through this pipeline is the MIRRORED/apparent hand
(§0.9), the two code paths reach that convention by different routes, and a sign
error there has already shipped once (§13.6.1). A constraint set that never asks
cannot get it wrong. The PIP↔DIP test achieves this by comparing a finger's
bends against *each other* rather than against the palm normal — which is also
exactly why it disambiguates bas-relief: a depth-mirrored reconstruction flips
the out-of-plane component of the bends so the senses stop agreeing, while every
2D projection is unchanged.

### Still open

- **Nothing consumes the validity bit yet.** Under A10 this is characterisation,
  not a demonstrated pipeline improvement; **1.6** is what converts it.
- The thumb is **excluded** — its CMC saddle joint has two coupled axes and a far
  wider envelope, so "no abduction at the IP joint" is simply false for a thumb in
  opposition. Constraining it needs its own model.
- One expectation was **wrong and is recorded as such**: finger self-occlusion was
  predicted to be the richest source of impossible poses. It is not (5.6%);
  rotation and edge-on crossing are (33–59%). The constraints are most useful
  where **T2** lives, not where M4's occlusion story does.

### ⭐ Does the validity bit actually predict the jumps? YES — and the useful direction is inverted

`analysis/m3a_predicts_jumps.py`, run before starting 1.6. §0.16 established that
the constraints are clean and that they fire more often in poses MediaPipe fails
at. That is **not** the same claim as "they fire on the frames that actually go
wrong", and only the second makes them useful. Streams built exactly as
`build_v2()` builds them, **verified by reproducing its jump census** (>30: 1413,
>60: 586 — larger than §0.15's 1350/572 only because the corpus grew by the five
2026-08-04 sessions; same method).

Violation at **either endpoint** of the transition (a jump is a property of a
transition, validity of a frame, and the bad landmark may sit at either end):

| | >30° | >60° |
|---|---|---|
| base rate | 4.97% | 2.06% |
| P(jump \| **anatomically ok**) | 0.89% | **0.22%** |
| P(jump \| violation) | 17.0% | 7.5% |
| **lift** | **19.1×** | **33.8×** |
| **coverage** (jumps flagged) | 86.6% | **92.0%** |
| frames flagged | 25.3% | 25.3% |

**A10: item 1.5 SURVIVES.** A lift of 33.8× is not 1.0; the bit carries real
information about the failure it is meant to catch.

⚠ **BUT IT IS AN EXCULPATOR, NOT AN ACCUSER — build 1.6 accordingly.**
- **As an accuser it is poor**: only 7.5% of flagged frames actually jump, i.e.
  wrong 92.5% of the time, and it flags **a quarter of the whole corpus**. A 1.6
  that rejects every violating frame would discard 25% of the stream to catch 2%
  of it, and would run straight into S5's binding anti-cascade rule (cap
  consecutive rejections at 1–2 frames — the cascade is what manufactured the χ²
  gate's own failure, §0.13.3).
- **As an exculpator it is excellent**: anatomically valid ⇒ **99.78%** chance
  this is not a large jump.

**Design consequence for 1.6**: use M3a as a cheap FIRST-STAGE PASS that clears
~75% of frames from further scrutiny, and run the expensive consistency cues
(velocity/acceleration plausibility, palm-pixel-width collapse, comparison
against the last accepted measurement) only on the flagged quarter. That is also
what keeps rejections rare enough for the anti-cascade cap to be satisfiable.

⚠ **This is co-occurrence, not forecasting.** A badly-estimated frame both
violates anatomy and produces a jump — two symptoms of one cause. That is exactly
what a gate needs, but it is not prediction and must not be described as such
(nor reused as one in 3.1, which has its own measured motion model).

### The 2026-08-04 takes this was built on, and what to record next

Five takes, all at **24.13–24.15 fps** — a 0.02 fps spread, which is what makes
them cross-comparable under N10:

| take | hands | span | frames | detection |
|---|---|---|---|---|
| `static_hold` (**the control**) | both | 29.9 s | 723 | 100% |
| `known_right_back` | both ⚠ N16 | 29.9 s | 723 | 100% |
| `known_left_back` | left | 30.0 s | 723 | 100% |
| `occlusion_finger_over_finger` | both ⚠ N16 | 45.0 s | 1085 | 100% |
| `pitch_sweep_slow` | right | 44.9 s | 1084 | 98.9% |

**Proposed next recording session**, in priority order — the first three exist to
serve **1.6**, which needs frames that are *bad in a known way*:

1. **`known_right_back` retake, genuinely single-hand** — closes N16 and restores
   the matched pair with `known_left_back` that N11 needs. Check the frame for a
   resting hand before starting.
2. **A back-of-hand + finger-occlusion variant** — deliberately *not* recorded on
   2026-08-04, because mixing two documented failure mechanisms in one take makes
   them inseparable (the mistake the original `occlusion` prompt and the
   `two_hand_overlap`/`near_miss` split both record). Worth having now as its own
   take, precisely because §0.16 shows the two mechanisms fire at very different
   rates.
3. **`pitch_sweep_fast`** — §0.16's violation rate rises with rotation speed, and
   the existing fast take is from a different session/lighting.
4. Optional: a first **`--save-frames`** take of any sequence, to exercise that
   path on real hardware — it is compile-checked but has never run live.

⚠ Prefer **daylight**: the corpus's own record is that the two takes which had to
be discarded for low fps were recorded at 22:18 (15 fps), while the good ones ran
19:13–20:51 (N10). "Later" is not the same as "better lit".

---

## 0.17 M4 frame gate BUILT (2026-08-04) — item 1.6. Two cues shipped, two measured out.

`Resources/frame_gate.py` (stdlib-only, numpy-free, no side effects), with
`analysis/m4_cue_distributions.py` (threshold derivation) and
`analysis/m4_gate_ab.py` (the A10 A/B + ablation).

### Shipped configuration and its measured result

Two cues, both scale-free (divided by palm width), compared against the **last
accepted** frame, with rejections capped at **2 consecutive frames**:

| | raw | gated | removed |
|---|---|---|---|
| position excursions > 0.5 palm widths | 142 | 89 | 37% |
| **> 1.0** | **71** | **33** | **54%** |
| **> 2.0** | **56** | **26** | **54%** |

Rejection rate **0.40%** (118 of 29,164 hand-frames), of which 39 hit the
anti-cascade cap. **Tracking cost on trustworthy frames (raw innovation < 0.2 and
anatomically valid): mean 0.00004 palm widths, p99 exactly 0.** The gate is
effectively invisible when the measurement deserves to be believed.

**A10: PASSES on both metric families** — excursions materially down, tracking
cost ~0. Reporting only the first would have been the over-damping trap §0.12
records.

### ⭐ Two cues were built, measured, and REMOVED

Ablation against >1.0-palm-width excursions (71 in the raw stream):

| configuration | rejects | left | removed | track cost |
|---|---|---|---|---|
| **position + width (SHIPPED)** | **118** | **33** | **54%** | **0.00004** |
| + bone deviation | 507 | 35 | 51% | 0.00021 |
| + M3a tightening | 227 | 33 | 54% | 0.00013 |
| bone deviation ALONE | 323 | 72 | **−1%** | 0.00016 |
| without position innovation | 54 | 61 | 14% | 0.00004 |
| without palm-width collapse | 86 | 47 | 34% | 0.00007 |

- **Bone-length deviation REMOVED.** It changed the outcome by one excursion
  while causing 296 of 507 rejections — 58% of all rejections for a 2-point
  effect — and alone it is *worse than doing nothing*. World-landmark bone
  lengths are simply too jittery to gate on (§0.14 measured 6–22% IQR; the
  all-frames p95 of frame-to-frame change is 51%).
- **M3a tightening REMOVED — and this is the uncomfortable one.**

### ⚠ Item 1.5 is NOT consumed by item 1.6

M3a was built as the cue that would feed this gate. Measured, it does not: using
the validity bit to tighten these thresholds made the result **slightly worse**
(35 vs 33 excursions) at nearly double the rejections. The reason is measured and
coherent — **80.8% of the largest position innovations occur on anatomically
VALID frames**, exactly as §14.1.4's root cause predicts, because a teleport moves
every landmark together coherently and leaves the hand anatomically perfect while
putting it in the wrong place.

**M3a and M4 address different failure classes and do not compose.** M3a covers
the orientation-jump class (92% coverage, 33.8× lift, §0.16); M4 covers the
position-teleport class. That is consistent with **A5**, which already said M4 is
an occlusion/outlier mechanism and not a pitch-crossing fix — the converse now
also holds.

**Consequence for 1.5, stated plainly: it currently has NO demonstrated
consumer.** Its A10 justification was "1.6 will gate on it", and 1.6 measures
that it should not. It is not thereby disproven — the orientation-side signal is
real and strong — but it is **unconsumed code**, and under A10 that is a revert
candidate unless an orientation-side consumer is built. Do not treat §0.16's
lift figure as a licence to keep it indefinitely. **Owner decision.**

### The anti-cascade cap is not a formality

Loosening it to 4 frames costs **170× worse tracking** (0.00693 vs 0.00004) to
remove one additional excursion. That is the §0.13.3 cascade starting, measured
directly here on position rather than inferred from the orientation χ² failure —
independent confirmation of S5's 1–2 frame rule.

### Still open

- **Not wired into production.** `frame_gate.py` is built, measured and unused;
  nothing imports it yet. The game's behaviour is unchanged, and this has had **no
  live-camera confirmation.**
- **T3 (Object Jump Correction) is not closed by this.** 54% of large excursions
  removed is a real improvement, not a fix, and the remaining ones are largely
  multi-frame teleports that outlast the 2-frame cap by design.
- **`translation_pivot_jump_test4` has not yet been replayed through the gate** —
  the named reproduction for this item lives in `Position_during_rotation/` with a
  different schema from the perception corpus.

---

## 0.18 Phase 1 closed (2026-08-04) — 1.5, 1.6 and 1.7 all PARKED; T1/T2 are a sensor floor

Three consecutive items were built, measured and parked on the same day. They
are not three separate disappointments — **they are three independent
measurements of one fact**, and that fact is the useful output of this phase.

| item | built | measured verdict |
|---|---|---|
| **1.5** M3a anatomical constraints | ✅ works: 0.00% FP on the control, 92% coverage / 33.8× lift on orientation jumps | **no viable consumer.** 1.6 measured that wiring it in makes results worse (different failure class); using it to gate orientation would reject 33–59% of frames during rotation — legitimate input |
| **1.6** M4 consistency gate | ✅ works: 54% of position excursions removed at ~0 tracking cost | **over-filters 4:1.** 80.2% of its rejections are real fast movement, at every threshold of both cues. A teleport and a fast real movement are the same signal |
| **1.7** M2b imposed skeleton | ✅ works: phalange bone CV → exactly 0.000 | **cannot affect orientation, by construction** — the frame uses 4 palm landmarks, no finger bones. 0.0% change |

### The one fact underneath all three

The orientation frame is `wrist / index-MCP / middle-MCP / pinky-MCP`. When
MediaPipe's palm reconstruction collapses (Google issue **#5156**, back of hand),
those four points are wrong **together, coherently**. Consequently:

- **filtering** cannot fix it — §0.13.2: the jumps are in *well-observed* frames;
- **re-weighting** cannot fix it — A5/§13.7: the residual is a correlated
  whole-knuckle-row distortion, so landmark selection is statistically
  indistinguishable at the degenerate frames;
- **constraining bone lengths** cannot fix it — §0.16/here: the frame does not
  use those bones;
- **gating** cannot fix it without destroying legitimate fast input — §0.17.

**T1 and T2 are therefore reclassified from open bugs to a known limit of a
single monocular camera at back-of-hand and edge-on poses.** This matches the
literature rather than contradicting it: HandFlow (VMV 2022) shows that pose
family is genuinely ill-posed for one RGB view — the posterior is multimodal —
and Meta ships multi-camera rigs for precisely this. Do not open a fifth attempt
without either a second camera or a fundamentally different sensor.

### ⚠ The methodological lesson, which cost the most to learn

**1.6 initially PASSED its A/B and the verdict had to be reversed.** The metric
("excursions removed") could not distinguish a correct rejection from a wrong
one, so removing the owner's real fast movements scored as success. This is the
same class of error as §0.12's "jump counts REWARD an over-damped filter" — and
it was walked into by a harness whose own docstring quoted that lesson.

> **Binding, from now on: any module that REJECTS or SUPPRESSES data must
> classify what it removed, not merely count it.** A count cannot tell you
> whether you removed the failure or the feature.

The owner's acceptance bar that exposed it is worth recording verbatim, because
it is a product decision and not a technical one: *"what I captured in the
recordings are rapid movements but still acceptable expected inputs for my
game."* Rapid movement is input, not noise.

### ✅ What survives Phase 1

- **`palm_width_world()`** — the per-session scale reference **M9 (item 4.1)**
  needs, which dead item 1.4 was supposed to supply and could not. It requires no
  skeleton fit, just the observed palm width, the documented pose-invariant
  anchor (§10.1). **This unblocks 4.1 → 4.2 (Z-axis translation).**
- Five daylight recordings at a 0.02 fps spread, and the recorder's
  `--save-frames` and early-stop instrumentation.
- Four measurement harnesses that close off whole families of approach.

**Recommendation recorded for the owner: treat this as the queue's R
(reassess) gate arriving early, and spend effort on features — 4.1/4.2 Z-axis
translation, or M10.7's grace period which also closes N8 — rather than a fifth
attempt at the orientation floor.**

---

<!-- VERBATIM-END -->
