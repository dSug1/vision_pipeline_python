# 50 — PORT · web and mobile

> **STATUS** · ⚠ **deferred** (`U3`) — Part Zero-bis is done, nothing since
> **OWNS** · everything about getting off the PC prototype
> **READ IF** · you are starting the port, or judging whether a change will
> survive one
> **LAST VERIFIED** · 2026-08-25

## Where the port actually stands

**Part Zero-bis is done**: hand detection + a cube following a fingertip, running
100% in the browser (MediaPipe Tasks Vision JS + a trivial Three.js scene). It
was deliberately done **early, on the simplest possible pipeline**, to surface
porting problems — coordinate systems, mirroring, camera permissions,
performance — while the logic being ported was still trivial. It lives in
`Web/`.

⛔ **Nothing from Part One runs there.** That is queue
[`U3`](../00_CORE/queue_notes/U3.md), deferred.

## ⭐ What has been done *for* the port, continuously

The port is deferred but it has been designed for the whole time, and three
things are already in place:

1. **The estimator layer is stdlib-only and numpy-free by contract** — so it can
   be **transliterated**, not rewritten. ⛔ Never import `cv2`/`numpy`/`scipy`
   into it ([`../00_CORE/CONSTRAINTS.md`](../00_CORE/CONSTRAINTS.md) §2).
2. **Golden vectors are written before the port exists** — 26 suites. The very
   first such fixture caught a real banker's-rounding bug.
3. **`HandState` v2 is the contract the port reimplements against**, and the
   input system ([`../40_INPUT_SYSTEM/INDEX.md`](../40_INPUT_SYSTEM/INDEX.md))
   turned it into a package with **conformance as data**, plus an
   `export_package.py` that has been run standalone.

## ⚠⚠ Three known port risks, each already measured

| risk | the number |
|---|---|
| **Camera FOV is assumed, not calibrated** (60°) | FOV error costs **~2–4° of rotation-axis error per 10° of FOV error**. A phone front camera near 70–80° would read materially differently. Owed to `U12` |
| **Camera TILT is assumed level** | a phone propped on a desk is routinely pitched **20–40°**, and 20° of tilt alone reproduces the entire yaw show-stopper. Fix is one conjugation `ΔR_world = C·ΔR_cam·C⁻¹`, `C` from `U12` — ⛔ **not** from the IMU (owner declined: *"i don't want to introduce a different behavior between desktop and mobile"*). Row [`T7`](../00_CORE/queue_notes/T7.md) |
| **Frame rate is camera-bound and environment-dependent** | proved by `L1`: the inter-frame gap is identical with and without a hand in view, and moved 48 → 64 ms with room lighting. ⭐ This is why rotation smoothing is now a **time constant**, not a per-frame factor — the old form would feel different on every device |

⭐ All three are why `U12` (start-of-game calibration) exists, and why it must
**override a working default, never be required**.

## Read

| | |
|---|---|
| what Part Zero proved on PC | [`PART_ZERO.md`](PART_ZERO.md) |
| what Part Zero-bis proved in the browser | [`PART_ZERO_BIS.md`](PART_ZERO_BIS.md), plus `Web/README.md` and `Web/NOTES.md` |
| the original port plan + the shared landmark data contract + the Snap Spectacles note | [`ORIGINAL_SPEC_PORT_SECTIONS.md`](ORIGINAL_SPEC_PORT_SECTIONS.md) (was `Specification.md` §4, §5, §6, §12) |
| what the wire carries today | [`../10_HAND_TRACKING/spec/WIRE_PROTOCOL.md`](../10_HAND_TRACKING/spec/WIRE_PROTOCOL.md) |
| `HandState` v2, the contract itself | [`../10_HAND_TRACKING/spec/PERCEPTION_LAYER_SPEC.md`](../10_HAND_TRACKING/spec/PERCEPTION_LAYER_SPEC.md) §2 |
| the package a port would target | [`../40_INPUT_SYSTEM/INDEX.md`](../40_INPUT_SYSTEM/INDEX.md) |
| camera permissions and the store position | [`../60_SECURITY_COMPLIANCE/INDEX.md`](../60_SECURITY_COMPLIANCE/INDEX.md) |

## ⚠ The platform decision blocks more than itself

[`U2`](../00_CORE/queue_notes/U2.md) (real 3D-file import) is postponed **on this
decision**, not on effort — building an importer against the pygame renderer
means building it twice. See [`../30_OBJECTS_3D/INDEX.md`](../30_OBJECTS_3D/INDEX.md).

When work starts here, add rows to
[`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md) with `Sub = PORT`.
