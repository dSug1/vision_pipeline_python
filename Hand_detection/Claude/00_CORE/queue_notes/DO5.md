# `DO5` — the pitch sign, and why it cannot live in `camera_mount`

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ✅ BUILT 2026-08-29 — ⛔ LIVE LOOK OWED · **SUB** · HAND
> **KIND** · feature · **DEP** · `DO1`

Design of record:
[`../../10_HAND_TRACKING/spec/SPEC_DELTA_ORBIT.md`](../../10_HAND_TRACKING/spec/SPEC_DELTA_ORBIT.md).

---

## 2026-08-29 — opened by a live A/B, after two wrong diagnoses of mine

> **Owner:** *"yaw and roll are right: the cube follows the hand's rotation
> direction. pitch is mirrored. I think we just need to introduce a quaternion
> multiplication to revert the pitch if camera is facing the user."*

⚠ **THE ROUTE TO IT IS WORTH KEEPING, because I proposed two wrong homes first.**

1. I first hypothesised the mirroring was the out-of-range region past edge-on, and
   ⭐ **gated it instead of fixing it** — which the owner correctly rejected: *"you
   did not fix this bug."*
2. I then replayed the same frames through BOTH paths and found delta-orbit
   reproduces the 1.7.40 absolute path **to every decimal** (14.13° / 23.78° /
   73.27° identical). ⭐⭐ **So the mirroring was never a `DO` defect**, and no
   amount of work in this row could have fixed it. The successive deltas telescope
   to exactly the grab-referenced delta, which is why.
3. A second test of mine compared the cube's pitch against the RAW camera-frame
   hand pitch and showed a clean negation — ⚠ **and that proved nothing**, because
   those two differ by the mount conjugation *by design*. Recorded because it looked
   like a finding and was not.

## ⛔⛔ THE CONSTRAINT THAT DECIDES WHERE THE FIX GOES

A viewpoint change is a **conjugation**, and a conjugation reverses **exactly two**
axes — `camera_mount`'s own finding, the one that made its search finite:

    diag( 1, 1,-1)  reverses PITCH + YAW      <- shipped (`pitch_yaw`)
    diag(-1, 1, 1)  reverses YAW   + ROLL
    diag( 1,-1, 1)  reverses PITCH + ROLL

**None gives "pitch reversed, yaw and roll as-is."** Reversing one alone would need
`det(Q)` to be `+1` and `−1` at once. So the owner's reading is **unreachable by any
mount setting**, and the fix cannot go there.

## ⭐ WHY RATE CONTROL MAKES IT LEGAL

`step` already scales the increment's per-axis components — that is the pose window
(`DO3`). A sign is the same multiplication with a gain of `−1` instead of one in
`[0,1]`. It is a **control mapping**, not a change of coordinates, so the
determinant argument does not bind it. One line, in the place that already decides
how much of each axis reaches the object.

## ⚠⚠ What it costs, and it was stated before it was built

**The object no longer RIGIDLY follows the hand.** Pure pitch is exactly right; a
COMPOUND motion (yaw and pitch together, about a diagonal axis) turns the object
about the **mirrored** diagonal. Increments are small, so nothing is discontinuous
and the integral stays a valid rotation — but it is a reflection of the
correspondence, not a rotation of it, and diagonal turns are where it would be felt.
⚠ **Judge that specifically in the live look.**

⚠ It exists ONLY in rate mode. The trick is not well defined on `legacy`'s
accumulated absolute rotation, so `DELTA_ORBIT=legacy` keeps the old behaviour.

## ⛔ Deliberately NOT wired to `CAMERA_MOUNT`

The owner said *"if camera is facing the user"*, and that is the mount this game
runs. But the mount is already a setting, and **one setting silently rewriting
another is exactly how the 2026-08-28 hybrid happened** — mirror from one mounting,
depth from the other, which was the defect `V1` existed to fix. `AXIS_SIGN` is its
own switch; a port that measures a different sign changes it there.

## Built

`delta_orbit.AXIS_SIGN = (-1.0, 1.0, 1.0)` · live toggle `PITCH invert 0/1`
(default INVERTED, the owner's reading) · `verify_delta_orbit` §6c, which asserts
each axis's direction independently and that inverting pitch leaves a pure yaw
untouched on every axis.
✅ 46/46 suites, `parity_replay` clean.
⛔ **A live look in BOTH tools closes it, and nothing else does** (`METHOD`).
