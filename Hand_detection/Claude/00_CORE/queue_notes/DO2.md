# `DO2` — the three sliders

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ✅ BUILT 2026-08-29 — ⛔ LIVE LOOK OWED · **SUB** · HAND
> **KIND** · feature · **DEP** · `DO1`

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

See the spec for the full design. This dossier carries what is specific to `DO2`.

## 2026-08-29 — built

✅ **BUILT 2026-08-29.** ⭐⭐ Shipped with the four sliders: **COLLAPSING**. A slider not in use for this build gets no trackbar, keeps its constant, and still prints one dim line so it reads as parked rather than gone. Nine expanded, six collapsed. ⚠ `verify_slider_wiring` itself broke on the new 6th field — a fixed 5-tuple unpack, in a file whose own comments say *"INDEXED, NOT UNPACKED"*. Fixed, and it gained a §6 covering collapsing and `_set_slider`.

✅ 46/46 suites, `verify_delta_orbit` 10/10, `parity_replay` clean.
⛔ **A live look in BOTH tools closes it, and nothing else does** (`METHOD`).

## 2026-08-29 (later) — the `ORBIT gain %` slider was REMOVED

Owner's objection to the first wiring (see `DO1`). The mode is not a tunable: it is
what the build IS. Three sliders remain — `RATE lo %`, `RATE hi %`,
`RATE knee deg/s` — and `verify_delta_orbit` §2 now FAILS if a master gain ever
comes back.
