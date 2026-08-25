# THE INPUT SYSTEM — §17, the record

> **live · what was built, what was deliberately not, and why**
> **SOURCE** · `GESTURE_PIPELINE_SPEC.md` §17–§17.7 — extracted verbatim, not edited

⭐ **§17.2** is the decision that made it shippable in one session (it observes,
it does not drive); **§17.5** is why the estimator modules were *not* moved into
the package; **§17.7** is what is explicitly not done. Usage doc:
`Local_pc/Movement_with_hand_detection/handinput/README.md`.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/GESTURE_PIPELINE_SPEC.md lines 6825-6957
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 17. ⭐⭐ THE INPUT SYSTEM (`handinput`) — BUILT 2026-08-25, queue IS1/IS2/IS3

> **Owner, 2026-08-24:** *"I want to be able to later ship independently this hand
> detection system as an input system (for my game, or for any other purpose such as
> a filter on Snapchat for example) ... mimicking the input system of Unity: the hand
> detection system would trigger callbacks with context, etc."* And on scope:
> *"I have no preference for the language. The current setup seems to work so if we
> can continue as current, with minimum modifications later on, this is fine."*

### 17.1 What was built, and what was deliberately NOT

`Local_pc/Movement_with_hand_detection/handinput/` — a Unity-Input-System-shaped
surface: five **actions**, Unity's five **phases**, `+=` **callbacks** carrying a
context, a **polling** API beside them, and `HandState` v2 as the serialisable
contract. Package README: `handinput/README.md`. Suite:
`analysis/verify_handinput.py` (**95 checks**).

⛔⛔ **THE SCOPE LINE, AND IT IS THE WHOLE ARCHITECTURE.** Unity ships **two**
packages — the **Input System** (devices → actions → callbacks, no scene
knowledge) and the **XR Interaction Toolkit** (grab, hold, arbitration, which has
it). This is the FIRST only. Snap proximity, arbitration, sticky grab,
owner-follows-track, the grab-relative transforms and the play volume all stay in
`HandsTriggeredActions.py` / `LiveSnapDebug.py`. ⭐ That is why the action is
`grab_ready` (**eligibility**) and never `grab`: "grab WHAT" needs a scene, and
answering it inside the module would weld it to this one game.

### 17.2 ⭐⭐ THE DECISION THAT MADE IT SHIPPABLE IN ONE SESSION: it OBSERVES, it does not DRIVE

Every value it publishes was computed by the gesture logic that already ran that
frame. It recomputes nothing and it drives nothing — **no cube is snapped, moved
or released by it.** So the change could not alter behaviour, and the evidence
says it did not: `parity_replay` **NO DIVERGENCE** on 454 frames, and 24 of 25
existing suites pass (the 25th, `verify_planar_pnp.py`, fails on a **console
encoding error printing a `⚠` character** and fails identically with the change
reverted — pre-existing, unrelated, worth fixing separately).

⚠⚠ **AND THE REASON IS THE PROJECT'S OWN SCAR TISSUE, NOT TASTE.** A layer that
re-derived the palm centre, the depth or the cue from landmarks would be a THIRD
implementation of the pipeline. Four harnesses in one session reported CLEAN on
takes the owner had just watched fail, every time because they recomputed what
production had already decided — which is why `_record_flush` records the cue
instead of re-deriving it. **The input system reports what RAN**, for the same
reason and by the same mechanism.

### 17.3 The five actions, and where each one's rule already lived

| action | kind | live when | the rule it publishes |
|---|---|---|---|
| `tracked` | button | `holds_track` — TRACKING **or** BRIDGING | ⭐ D2's 150 ms coast: a dropout does NOT cancel it, matching `GAME_RULES.md` rule 2 |
| `palm_pose` | value | TRACKING only | ⛔ a bridge has no measurement; publishing the last pose as current is the extrapolation **B8** measured losing to "hold the last value" |
| `palm_facing` | value | TRACKING | the palm/back cue + U8's `confirmed` + DR-2's `orientation_valid` |
| `grab_ready` | button | rule 3 **and** U8 **and** 4.2 DECISION 1 | the hand-side half of snapping, in one place |
| `rotation_delta` | value | reference set | the grab-referenced delta, starting at **identity** (§14.1's no-pop, expressed without an object) |

⭐ **The split between `tracked` and `palm_pose` is the most useful thing the layer
produces, and it fell out of a real recording rather than being designed**: a
replay of `2026-08-24_220415_prod_tau20` gives `tracked` **8** start/cancel pairs
against `palm_pose`'s **9** — the extra one is a bridge, where the hand is still
held but the pose has stopped updating. Two facts a consumer had no way to tell
apart before.

### 17.4 ⭐ CONFORMANCE — the authority moved out of Python

`handinput/conformance/` holds **vectors** (7 files, 64 cases: signs, chirality,
projection round-trips, the stateful depth/rotation/coast sequences) and a
**trace** (18 frames, 65 events: enter → provisional chirality → ready → rule 3
refusal → armed exception → frozen depth → rotation reference → coast → sustained
loss → re-entry).

⭐⭐ **WHY THIS AND NOT A 26th `verify_*.py`.** Those suites assert in Python, so
they can only ever test the Python; **a port cannot run them.** The same inputs
and outputs as JSON can be run by any language, which turns *"is the port
faithful?"* from an argument into a test. It is rule 6 (*golden vectors before a
port exists*) taken one step further. ⭐ And the **trace** is worth more than the
vectors: it pins **when** events fire — that a held button does not re-fire, that
a coast cancels the pose but not the track, that a dead track drops a rotation
reference — none of which is visible in any single-frame vector.

⛔ **Regenerating to turn a red suite green destroys the only thing they are for.**
A regeneration belongs in a commit that names the behaviour that changed.

### 17.5 ⭐⭐ THE ESTIMATOR MODULES WERE NOT MOVED — a decision, with its reasoning

The obvious shape would be `handinput/core/palm_geometry.py` and friends. **They
stay in `Resources/`,** because moving them costs real things and buys none:

* **~15 harnesses import them BARE** off `sys.path` (`sys.path.insert(0, ROOT +
  "/Resources")` then `import palm_geometry`), and **dozens of paths in
  `Claude/*.md` name their current location.** A move breaks working code and the
  project's own memory.
* The property that actually matters — *the input system depends on nothing from
  the game* — can be **asserted instead of arranged**. `verify_handinput.py` §1
  parses every file's imports with the **AST** (not a text search — this codebase
  is mostly comments, and a grep for `pygame` would hit one) and fails if any of
  `CubeWindow`, `HandsTriggeredActions`, `pygame`, `cv2`, `mediapipe`, `numpy` …
  appears. **A folder gives tidiness; the test gives a guarantee.**
* ⭐ **The closure was checked, not assumed**: the only non-local import anywhere
  in the nine manifest modules is `math`. `hand_state`, `hand_tracks` and
  `owner_remap` import nothing at all.
* And when the folder IS wanted, it is one command:
  `handinput/export_package.py <dir>` writes the package plus `core/` — **9
  modules, 4 416 lines, stdlib-only, numpy-free** — plus the conformance data.
  ⚠ Verified by running the exported copy standalone, with no repo on the path.

### 17.6 One shared-code fix that came with it

`palm_geometry.palm_center_px` — the §13.3 palm centre (wrist + four MCPs) — now
has **one** definition. It was written out identically in
`HandsTriggeredActions._hand_position` and `LiveSnapDebug._hand_position`; both
now delegate, exactly as `_is_thumb_outward` already did, and
`verify_handinput.py` §5 asserts the arithmetic is unchanged. ⚠ A duplicated
geometric convention is precisely how the palm/back sign drifted into the
production-only inversion of §13.6.1.

### 17.7 What is NOT done, so nobody assumes it is

* ⛔ **No live take yet.** The owner's own look in both tools is what closes a
  change here (§13.6.1's rule), and it had not happened when this was written.
  Automated evidence only: 95 new checks, 24 existing suites, `parity_replay` no
  divergence, a 454-frame real-recording replay, and a standalone export.
* ⛔ **No port.** TypeScript and C# were explicitly deferred by the owner. The
  conformance data exists so that when one happens it is checkable.
* ⛔ **The interaction tier is not extracted** and was left for later by the owner
  (*"if it can be implemented in the future with little change, let's keep it for
  the future"*). ⭐ It can: it changes **who consumes** this layer, not what the
  layer produces. Nothing in `handinput` presumes it.
* ⚠ `sources/recording.py` cannot produce `rotation_delta` events — a recording
  stores the cube's smoothed orientation, never the hand's reading. ⛔ Re-running
  Horn there to fill the gap would make a recomputation the reference for a
  conformance file. Use `HANDINPUT_TRACE=1` on a live session instead.

---

<!-- VERBATIM-END -->
