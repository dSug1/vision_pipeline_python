# `DO4` — the OUTER EDGE — the one open number

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ⚠ OPEN — deferred by the owner 2026-08-29 · **SUB** · HAND
> **KIND** · perception · **DEP** · `DO3`

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

See the spec for the full design. This dossier carries what is specific to `DO4`.
