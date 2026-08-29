# `DO3` — the window — a HARD edge-on gate

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

See the spec for the full design. This dossier carries what is specific to `DO3`.

## 2026-08-29 — built

✅ **BUILT 2026-08-29 in both tools** — `edge_on_measure < EDGE_ON_THRESHOLD` drops the increment entirely. ⛔ Hard, never a fade: past edge-on the chirality sign flips, and in rate mode that is a ~180° increment integrated permanently.

✅ 46/46 suites, `verify_delta_orbit` 10/10, `parity_replay` clean.
⛔ **A live look in BOTH tools closes it, and nothing else does** (`METHOD`).

## 2026-08-29 (later) — ⛔⛔ v1 WAS WRONG. The owner found it on the first live run.

> *"I can still rotate the cube around yaw when hand is edge-on and even further
> palm facing the camera."*

⛔⛔ **`edge_on_measure` IS SYMMETRIC** — ~1.0 palm-on, ~0.15 edge-on, **~1.0 again
back-on**. The v1 gate killed a thin band and **re-opened past it**. It could never
have done the job asked of it, and no automated check noticed because every one of
them tested the band and not the far side.

✅ **v2: the PALM NORMAL, split per axis** — `yaw_pose = atan2(nx,|nz|)`,
`pitch_pose = atan2(ny,|nz|)`, and **`sign(nz)` for palm-vs-back**, which is the
piece v1 lacked. Measured monotone on both gripping takes (yaw −12→−60°, pitch
−14→+60°, with a clean split between them). Past edge-on is a HARD ZERO on every
axis, roll included.
⚠ Its limit, measured: the normal's yaw reading wanders 27° on a pure ROLL, which
it should not at all. World-`z` error. Fine for a soft gate, not for a measurement.
⭐ Sliders `YAW window deg` / `PITCH window deg`, because the thresholds read in
compressed normal-swing degrees and the felt edge is what matters.

✅ 46/46 suites; `verify_delta_orbit` §6b added (10 checks, every one of which fails
against the v1 gate); `parity_replay` clean.
