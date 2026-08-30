# `RB4` — hand identity across frames

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · queued · **SUB** · HAND · **KIND** · perception

Design of record:
[`../../10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`](../../10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md).

---

## 2026-08-29 — opened by the rebuild

> **Owner:** *"I think we have patched too much this script … I want to build the
> control by hand detection delta increment from scratch. Strip all the filters and
> multiplicators, etc.: we will rebuild them as we need them."*

⛔⛔ **What justified a rebuild rather than another fix**: the composite mapping had
become a **REFLECTION**. `camera_mount` reversed pitch+yaw, `delta_orbit.AXIS_SIGN`
reversed pitch back — net, yaw reversed alone, det −1. A rigid hand→object
correspondence cannot do that. Every layer was locally reasonable and the stack was
not: `METHOD`'s *no heuristic pile-up*, arriving in the one place nobody measured —
the composition.

See the spec for the full design. This dossier carries what is specific to `RB4`.

---

## 2026-08-30 — review: identity was held on an index the detector does not guarantee

⛔⛔ **THE DEFECT.** `_held` was read for ANY hand count, keyed on the detection's
**INDEX**, and reset only when the *count* changed — while the comment two lines
below it said MediaPipe's ordering is not stable. Two simultaneously-degenerate hands
returned in swapped order each inherited the **other's** identity: the `T3`/`U8`
state-inheritance class exactly, and invisible to the same-chirality check because the
two keys stay distinct. ✅ Found by review **before this module was ever wired**.

**Measured A/B against the committed version**, two hands going degenerate together:

| | result |
|---|---|
| committed | `['right', 'left']` — it **names two hands nobody can see** |
| fixed | `[None, None]` |

⭐⭐ **AND THE REPLACEMENT IS STRONGER THAN THE THING IT REMOVES.** Holding by index is
gone for `n >= 2`; in its place is **ELIMINATION** — with two hands in view and one
confidently named, the other *is* the remaining chirality. That is a **counting**
argument, so it needs no history, no clock and no index, and it cannot go stale.
Measured: one confident + one degenerate used to give `['right', None]` and now gives
`['right', 'left']`, **independent of the detector's ordering**. Holding survives only
for `n == 1`, where there is one slot and the index cannot mean a different hand.

⚠ It rests on the module's stated assumption — one player, two hands of opposite
chirality. Two same-chirality hands are still refused, and per the header remain the
case that requires **replacing** this module rather than patching it.

✅ **And `RB4`'s headline is now an ASSERTION, not a spec sentence: 0 swaps over 1239
two-hand frames, 2478/2478 hands named** (`verify_frame_signs` §10bis). It had never
been tested — see the `METHOD` rule on silent skips.
⚠ The first swap metric I wrote was **wrong and I nearly reported a defect on it**: it
used the **world** wrist x as a screen position, and MediaPipe's world landmarks are
hand-RELATIVE, so it "found" 62 swaps that were the wrist's offset *within* the hand
changing sign. Screen position lives in the **pixel** landmarks. The witness is now
relative screen ORDER, which needs no centre line and no calibration.
