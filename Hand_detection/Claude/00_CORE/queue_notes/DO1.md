# `DO1` — the integrator + the rate curve

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ✅ BUILT 2026-08-29 — ⛔ LIVE LOOK OWED · **SUB** · HAND
> **KIND** · feature · **DEP** · `F1`, `V2`

Design of record:
[`../../10_HAND_TRACKING/spec/SPEC_DELTA_ORBIT.md`](../../10_HAND_TRACKING/spec/SPEC_DELTA_ORBIT.md).

---

## 2026-08-29 — opened

Branch `1.7.41-Hand-delta-orbit`. Owner: *"the cube's position still follows the
hand as in 1.7.40 … but the cube's rotation is incremented based on hand rotation
delta … with a smooth and rapid decay to zero when the hand is outside these
ranges."* The Unity `OrbitMovement` (pointer-delta orbit) was supplied as the
pattern.

⭐ The evidence this row rests on was measured the same day, on **three stepped,
GRIPPING takes** recorded for it (`window_yaw_grip`, `window_pitch_grip`,
`window_roll_grip`) — the first takes in this project whose holds are DECLARED
rather than inferred, and whose hand is gripping rather than open.
Harnesses: `analysis/delta_orbit_window.py`, `analysis/rotation_accuracy_bands.py`.

See the spec for the full design. This dossier carries what is specific to `DO1`.

## 2026-08-29 — built

✅ **BUILT 2026-08-29 in both tools.** ⭐⭐ The wiring's one real decision: delta-orbit produces a `target_quat` and goes through the EXISTING slerp rather than composing onto `cube.orientation` — because the drift control is the shipped FREEZE, and the freeze lives in the slerp factor. Composing directly would bypass it and reinstate the measured 43/35/48°-per-minute drift. ⚠ The cost is a constant (`rate_gain × slerp_factor`, ~0.86) that the sliders absorb.

✅ 46/46 suites, `verify_delta_orbit` 10/10, `parity_replay` clean.
⛔ **A live look in BOTH tools closes it, and nothing else does** (`METHOD`).

## 2026-08-29 (later) — ⛔ REWORKED ON THE OWNER'S OBJECTION: no master gain, no legacy default

> *"ORBIT gain % at 0 is today's build: I do not understand: I do not want to have
> a mix of hand follow and integral of hand motion. I want pure integral of hand
> motion since the beginning with no interference of what we previously built."*

⚠ **The first wiring was not a blend** — `ORBIT_GAIN` was a hard switch and no frame
had both paths contributing. Two things about it were still wrong:

1. ⛔ **It DEFAULTED to the legacy path**, so the build only became itself once a
   slider moved. That is an option on top of the old build, not a build.
2. ⛔ **It carried a THIRD gain** multiplying `RATE lo/hi`. Two controls, one job —
   and a half-open master reads as a partial mix. **A third gain is a blend by
   another name**, whatever the code does underneath.

✅ `delta_orbit.MODE` is `"orbit"` by default; `step()` takes no gain; the
`ORBIT gain %` slider is deleted. `DELTA_ORBIT=legacy` survives as a DIAGNOSTIC so
`A10`'s baseline stays reachable — `V1`'s shape, which the owner already accepted.

✅ **Evidence**: 46/46 suites, `verify_delta_orbit` 10/10 (§2 now asserts the
default mode AND that no `gain` argument exists), `parity_replay` **NO DIVERGENCE in
BOTH modes**.

⭐ What is NOT the old path leaking in, stated because it is the obvious next
question: the **slerp/FREEZE** is the damper and the only drift control that works;
`grab_hand_orientation` is read ONCE to seed the previous-frame reference so the
first increment is the identity; and `lean_trim` still corrects the HAND before the
increment is taken (§11 measures why it matters more here). ⚠ `LEAN pitch/roll %`
at 0 removes that last one live, if the owner wants it out too.
