# `AS8` — an un-snap must survive more than one frame

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · BUILT 2026-08-28, both tools — ⛔ live look owed · **SUB** · 3D
> **KIND** · feature · **DEP** · `AS3`

Design of record:
[`../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md) §8ter.

---

## 2026-08-28 — the defect that took FOUR live reports

> *"the z axis movement seems broken: I can't get the cube to move on the z axis"*
> *"there is still a problem with z axis translation when a cube has been snapped and is released"*
> *"still a bug with z axis position when cubes have snapped and released"*
> *"once a cube has been un-snapped, I cannot move it on z axis. it's a bug I repeatedly asked you to correct"*

## ⛔ What it actually was

**Breaking a mate lasted exactly one frame.** `AS3`'s break measures the two
**DESIRES** diverging; it never requires the objects to **MOVE APART**. So the
instant the mate dropped, the two cubes were still touching, `can_mate` was true
again, and the 100 ms dwell re-engaged it.

The object went straight back to `role=follower` — **and a follower's depth is
owned by its parent.** That is z looking dead from the outside.

⛔⛔ **IT WAS NEVER A DEPTH DEFECT.** `4.2`'s Z-translation was correct at every
stage; what was broken was that a mate could not be undone. ⭐ The first report
even had a *different* cause (both cubes started co-located, so an ordinary drag
mated and `AS6` took the cube out of the hand) — **two distinct defects with one
appearance**, which is `METHOD`'s *"same symptom never means same cause"* again.

⚠ Doubling `MATE_RADIUS_FRACTION` on the same day made it strictly worse: the
objects had to get a full cube-width apart before re-mating would stop.

## The fix

After a break, that **connector pair** may not re-engage until the two objects are
genuinely apart — past the **BREAK** distance, for the dwell. `Assembly._cooldown`,
armed by `offer_break` and by `unlink()`, cleared by `cooling()`.

⭐ Same principle as `AS6` one level up, and the same authority: **you cannot go
from mated to mated; the transition must pass through APART** (Buxton's three-state
model). ⚠ "Apart" uses the BREAK distance, not the capture distance — a pair that
has only just left capture has not parted.

⚠ `unlink(cooldown=False)` exists for homing, which moves the objects apart itself;
a cooldown there would refuse a mate the operator may want immediately after.

## ⭐⭐⭐ The method lesson, and it is the expensive one

**Every probe broke the mate and then measured something else. None of them broke
it and simply LOOKED at whether it was still broken.** The defect was visible in a
single line of the `z` HUD: `mated=True` on the frame immediately after a call to
`unlink()`.

⚠ Three earlier probes were invalid for a second, independent reason each, and
**each was reported as a pass before the flaw was noticed**:

| probe | why it proved nothing |
|---|---|
| set `depth_m` directly | bypasses the ratio → anchor → `depth_from_ratio` chain that actually drives z |
| dragged a cube toward the other | never reached the mated state (`mated=False` in its own first line) |
| forced adjacency, then unlinked | correct setup — and its output said `mated=True` right after the unlink, which is the bug, read as noise |

⭐ It is `T6`'s rule in a new place: **a fixture whose state does not match the
product's cannot validate the product.**

## Built

`Assembly._cooldown` / `cooling()` / `unlink(cooldown=...)` in `mate_connector`;
the `_apart` test in `object_assembly.resolve`; `cooldown=False` at the debug
tool's home path.

✅ Pinned in `analysis/verify_object_assembly.py`: an un-snap survives with nothing
moved, the object reads **free** rather than **follower**, re-mating still works
once the pair has genuinely parted and returned, and a home-then-remate is not
refused. 42/42 suites; `parity_replay` clean.

⛔ **LIVE LOOK OWED.**

---

## 2026-08-28 (later) — AND THE HAND-OVER HAD TO BE MADE CONTINUOUS TOO

> **Owner:** *"when the child snap break, verify what the z position of the cube
> becomes. It looks like it does not match with the z position of the hand that
> grabbed it when it was a child."*

⭐ **Correct, and measured: an 0.180 m jump.** While an object is a mate FOLLOWER
the mate owns its depth, but its **grab baseline is stale** — captured before the
mate ever moved it. The instant the mate lets go, the hand's ratio drive resumes
from that old anchor and the object teleports to where the hand *would* have put
it, discarding everywhere the mate carried it.

**The fix**: the mate **re-seats the baseline** when it hands an object back —
`grab_depth_m`, the grip anchor, and ⛔ **the RATIO TRACKER**, because
`depth = anchor × ratio` and the ratio is measured against the hand's span at the
ORIGINAL grab. Re-anchoring without it still jumps. Same no-pop principle as the
grab frame, `D3`'s resync blend and `A1`'s walk.

⚠ **An ordering detail that cost a cycle**: the flag was first set from the ROLE
change, but `step` runs AFTER the hand loop — so it arrived one frame late and the
jump had already happened. It is set on the **break event** now.

✅ `analysis/verify_mate_handback.py`: **0.180 m → 0.000 m**, the flag is consumed
once, and the new baseline matches the object's own depth.

## ⚠⚠ THREE INSTRUMENT FAILURES IN ONE INVESTIGATION — all worth keeping

1. ⛔⛔ **The probes were DOUBLE-STEPPING.** `update_hands` already calls
   `object_assembly.step`; the probes called it again *without* `desires`, which
   makes the residual structurally zero — **so a mate could never break in any of
   them.** Several "verified" results from that session are therefore worthless.
2. **A probe printed CONTINUOUS from a run where no break occurred** (`broke at
   step None` on the line above the verdict).
3. **The first golden vector passed for the wrong reason.** Appended to
   `verify_debug_update_hands.py`, whose `main()` leaves the module-level
   `_hand_track_ids` mutated — with a stale id the hand drives nothing, so the
   CONTROL arm reported 0.000 m of jump and read as a pass of a check that had not
   run. It is a standalone suite now, and it **asserts the fixture reached the
   state it tests** before trusting either arm.

⭐⭐⭐ All three are the same rule in different clothes, and it is `T6`'s:
**a fixture whose state does not match the product's cannot validate the product.**
