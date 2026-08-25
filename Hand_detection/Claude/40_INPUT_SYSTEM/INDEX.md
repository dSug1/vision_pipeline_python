# 40 — INPUT SYSTEM · `handinput`, shippable on its own

> **STATUS** · ✅✅ **SHIPPED 2026-08-25** — owner ran both tools back to back
> **OWNS** · the package boundary between the hand pipeline and any consumer
> **READ IF** · you are plugging the hand tracking into another game, a port or a
> lens; or changing what the pipeline publishes
> **LAST VERIFIED** · 2026-08-25

> **Owner, 2026-08-24:** *"I want to be able to later ship independently this hand
> detection system as an input system (for my game, or for any other purpose such
> as a filter on Snapchat for example) … mimicking the input system of Unity."*
> And: *"No need for TypeScript for the moment, no need for C# for the moment."*

## What it is

`Local_pc/Movement_with_hand_detection/handinput/` — five **actions**, Unity's
five **phases**, `+=` **callbacks with a context**, a **polling** API, and
`HandState` v2 as the serialisable contract. A consumer subscribes to events; it
**never sees a landmark**.

⭐ **The distinction that explains the whole design.** Unity ships *two* packages
and this is deliberately the first:

| Unity | here | knows the scene? |
|---|---|---|
| **Input System** — devices → actions → callbacks | ⭐ **this package** | ⛔ no |
| **XR Interaction Toolkit** — grab, hold, arbitration | still in `HandsTriggeredActions.py` / `LiveSnapDebug.py` | ✅ yes |

So it answers *"is this hand tracked, where is it, which way is it facing, is it
**eligible** to grab?"* — never *"grab what"*, which needs a scene. That is why
the action is `grab_ready` (eligibility), not `grab`. Extracting the second tier
is queue [`IS4`](../00_CORE/queue_notes/IS4.md), open and owner-deferred.

## ⚠⚠ Two properties that are the point, not caveats

1. **It derives nothing — it adapts.** Both tools already compute every value in
   their per-hand pass and hand those values over. **So it reports what RAN.**
   That is this project's most expensive recurring lesson made structural: a
   recomputation is a second implementation that can silently disagree with the
   real one.
2. **It drives nothing.** Every object is still snapped, translated, rotated and
   released by the existing gesture logic. `handinput` is a **read-only
   observer**, so shipping it *could not* change behaviour — which is why it
   landed in one session with no live risk.

## Evidence it landed clean

| | |
|---|---|
| `analysis/verify_handinput.py` | **96 checks pass** |
| the 24 pre-existing `verify_*` suites | pass |
| `parity_replay` on a real production take | **NO DIVERGENCE**, 454 frames |
| a recording replayed through it | 454 frames → **785 events** |
| `export_package.py` → run standalone, no repo on the path | **works** — 9 modules, 4 416 lines |

✅✅ **CLOSED 2026-08-25 — the owner ran the debug tool and production back to
back and instructed "ship current build".** Both sessions ran clean: MediaPipe
loaded, identity locked on both hands, tracks ended and re-decided normally, the
socket opened and closed cleanly at both ends, no errors in either log.
`IS1`–`IS3` are **SHIPPED**.

⚠ **What that claim rests on, stated plainly**: the automated evidence below,
plus two clean live sessions and the owner's instruction. If anything looked
wrong on screen, this status is the thing to revert first — the HUD line to check
is the green `handinput …` (per hand: the `tracked` phase, `RDY` when
`grab_ready` is performing, `ROT` when a rotation reference is frozen).

## Read

| | |
|---|---|
| **how to use it** (actions, phases, files, ports) | `Local_pc/Movement_with_hand_detection/handinput/README.md` — ⭐ kept beside the code by `N6`, linked not copied |
| **the record**: what was built, and what was deliberately not | [`SPEC_17_input_system.md`](SPEC_17_input_system.md) (was `GESTURE_PIPELINE_SPEC.md` §17) |
| the rows | [`IS1`](../00_CORE/queue_notes/IS1.md) · [`IS2`](../00_CORE/queue_notes/IS2.md) · [`IS3`](../00_CORE/queue_notes/IS3.md) · [`IS4`](../00_CORE/queue_notes/IS4.md) |
| what the wire carries underneath | [`../10_HAND_TRACKING/spec/WIRE_PROTOCOL.md`](../10_HAND_TRACKING/spec/WIRE_PROTOCOL.md) |

⭐ **The estimator modules were deliberately NOT moved into the package** —
§17.5 records why. Do not "tidy" them in.

## ⚠ For a port

The package is the thing `U3` reimplements against, and **conformance is data**
(`IS2`), not prose — so a port can be *checked*, not argued about. The estimator
layer it sits on is stdlib-only and numpy-free by contract; see
[`../50_PORT_WEB_MOBILE/INDEX.md`](../50_PORT_WEB_MOBILE/INDEX.md).
