# `handinput` — the hand-tracking input system

⭐ **A Unity-Input-System-shaped surface over this project's hand pipeline**, built
so it can be lifted into another game, a browser build, or a lens. Actions with
phases, callbacks with a context, a polling API, and a serialisable state
contract. A consumer subscribes to events; it never sees a landmark.

Built 2026-08-25 (queue rows **IS1 / IS2 / IS3**). ⚠ Read `Claude/README.md` for
the project as a whole — this file covers the package only.

---

## 1. The one distinction that explains the whole design

Unity ships **two** packages, and this is deliberately the first of them:

| Unity | here | knows about your scene? |
|---|---|---|
| **Input System** — devices → actions → callbacks | ⭐ **this package** | ⛔ no |
| **XR Interaction Toolkit** — grab, hold, arbitration | still in `HandsTriggeredActions.py` / `LiveSnapDebug.py` | ✅ yes |

So `handinput` answers *"is this hand tracked, where is it, which way is it
facing, is it eligible to grab?"*. It never answers **"grab what"** — that needs
the scene, and answering it here would weld the module to this one game. That is
why the action is called `grab_ready` (eligibility) and not `grab`.

⭐ Extracting the second tier later changes **who consumes** this layer, not what
it produces. Nothing here has to move when that happens.

## 2. What it does today, stated plainly

⚠⚠ **It derives nothing. It adapts.** Both tools already compute every value in
the per-hand pass, so they hand those values over rather than have them
recomputed. **The input system therefore reports what RAN** — which is this
project's most expensive recurring lesson: a recomputation is a second
implementation that can silently disagree with the real one, and four harnesses
once reported CLEAN on takes the owner had just watched fail because of exactly
that.

⚠⚠ **And it drives nothing.** Every cube is still snapped, translated, rotated
and released by the existing gesture logic. `handinput` is a read-only observer.
Shipping it could not change behaviour — which is why it could ship in one
session alongside no live risk.

A future self-sufficient mode (a source that owns a MediaPipe instance and calls
the estimators itself, for a host that has only landmarks) fills the same
`HandObservation`. Everything above that struct is unchanged.

## 3. Using it

```python
from handinput import HandInput
from handinput.sources import live

hi = HandInput()
hi.actions["grab_ready"].started   += lambda ctx: print("ready", ctx.hand)
hi.actions["palm_pose"].performed  += on_pose
hi.actions["tracked"].canceled     += on_hand_lost

# once per frame, from YOUR loop
hi.update(live.frame(time_ms, [live.observe(slot="Left", ...)], frame_size))

# polling works too, exactly as Unity offers both
pose = hi.value("palm_pose", "Left")
state = hi.state("Left")            # HandState v2, JSON-serialisable
```

To rotate a held object, freeze a reference at the grab and read the delta:

```python
hi.set_rotation_reference("Left")            # at grab -> delta starts at IDENTITY
delta = hi.value("rotation_delta", "Left")   # each frame after
hi.clear_rotation_reference("Left")          # at release
```

### The actions

| action | kind | value | live when |
|---|---|---|---|
| `tracked` | button | `True` | `holds_track` — ⭐ **TRACKING *or* BRIDGING**, so a 150 ms dropout does not cancel it |
| `palm_pose` | value | `PalmPose(position_px, depth_m, depth_valid, orientation)` | TRACKING only — ⛔ a bridge has no measurement, and publishing the last pose as current is the extrapolation B8 measured losing to "hold the last value" |
| `palm_facing` | value | `PalmFacing(thumb_outward, confirmed, orientation_valid, edge_on)` | TRACKING |
| `grab_ready` | button | `True` | rule 3 (palm/back + armed exception) **and** U8 (chirality confirmed) **and** 4.2 DECISION 1 (depth measured, not frozen) |
| `rotation_delta` | value | quaternion since the consumer's reference | TRACKING, orientation present, reference set |

### Phases

Unity's five: `Disabled` / `Waiting` / `Started` / `Performed` / `Canceled`.

* **button** — rising edge → `started` then `performed`; ⭐ **nothing while held**;
  falling edge → `canceled`.
* **value** — first live frame → `started` then `performed`; every live frame
  after → `performed`; gone → `canceled` and `read_value()` returns `None`.

## 4. Files

| | |
|---|---|
| `contract.py` | `HandState` v2 (`PERCEPTION_LAYER_SPEC.md` §2) — ⭐ with a table of every field that is **absent and why**. Nothing is invented to fill a slot |
| `actions.py` | phases, events, contexts, the five actions, the map |
| `config.py` + `default_config.json` | action-layer policy as DATA. ⛔ No estimator constant may be copied here |
| `sources/live.py` | the push adapter both tools use |
| `sources/recording.py` | replay a session JSONL (schema 2/3) |
| `trace.py` | `HANDINPUT_TRACE=1` — write live events to a file |
| `manifest.py` | ⭐ **what the input system IS** — the estimator files, and the imports the boundary forbids |
| `export_package.py` | write a standalone copy |
| `conformance/` | golden vectors + action traces, as language-neutral JSON |

## 5. ⭐⭐ Why the estimator modules were NOT moved into this folder

They stay in `Resources/`. This was a decision, not an oversight:

* ~15 harnesses import them **bare** off `sys.path`, and dozens of paths in
  `Claude/*.md` name their current location. A move breaks working code and the
  project's own memory.
* The property that actually matters — *the input system depends on nothing from
  the game* — can be **asserted** instead of arranged:
  `analysis/verify_handinput.py` §1 parses every file's imports and fails if any
  of `CubeWindow`, `HandsTriggeredActions`, `pygame`, `cv2`, `mediapipe`, `numpy`
  … appears. A folder gives you tidiness; the test gives you a guarantee.
* And when you want the folder, it is one command:

```
.venv/Scripts/python.exe handinput/export_package.py <target-dir>
```

which writes the package plus `core/` (**9 modules, 4 416 lines, stdlib-only,
numpy-free**) plus the conformance data. ⚠ The export is **generated, not a
fork** — edit the originals and re-export.

## 6. Conformance — the thing that makes a port checkable

```
handinput/conformance/vectors/*.json      arithmetic: 7 files, 64 cases
handinput/conformance/traces/*.json       behaviour over time: 18 frames, 65 events
analysis/verify_handinput.py              runs both against this code (95 checks)
```

⭐⭐ **The 24 `verify_*.py` suites can only ever test the Python.** These files can
be run by any language, which turns *"is the TypeScript faithful?"* from an
argument into a test — rule 6 (*golden vectors before a port exists*) taken one
step further. The trace is the more valuable of the two: it pins **when** events
fire, which is what a port gets wrong and what no single-frame vector can catch.

⛔ **Regenerating to make a red suite green throws away the only thing they are
for.** A regeneration belongs in a commit that names the behaviour that changed.

⚠ Floats are compared with a tolerance (1e-9), never for equality — the first
port bug this project ever caught was Python's banker's rounding against
JavaScript's half-up.

## 7. Recording live traces

```
set HANDINPUT_TRACE=1
set HANDINPUT_TRACE_TAG=my_session
```

Either tool. Writes one JSON object per event to the capture drive (falling back
to a local folder). ⭐ This is the only way to get traces carrying **measured
orientations** — a recorded session does not store the hand's orientation
quaternion, only the cube's smoothed result, so `rotation_delta` never fires on a
replayed recording. That is stated in `sources/recording.py` rather than papered
over by re-running Horn, which would make a recomputation the reference for a
conformance file.

## 8. Ports — what would actually be involved

Nothing here is scheduled. Recorded so the next reader does not re-derive it:

| target | needs | reuses |
|---|---|---|
| this game | — | all of it, today |
| web / React Native / **Snapchat lens** | a TypeScript peer of `core/` + this package, and a source over the host's own tracker | contract, actions, conformance |
| **Unity** | a C# peer, plus a `MonoBehaviour` mapping actions to UnityEvents | ⭐ the phases already match Unity's, so the binding is thin |
| native Swift/Kotlin | a peer, or host the TS in JavaScriptCore | |

⚠ Two portability facts worth knowing before promising anything:
**(a)** a lens brings its **own** hand tracking with a different landmark set, so
what ports is the interaction semantics plus a landmark adapter — not the
MediaPipe source; **(b)** `geometric_chirality` (U7) reads **world** landmarks, so
a 2D-only host needs a signed-palm-**area** fallback. Neither is a blocker;
both are unmeasured.
