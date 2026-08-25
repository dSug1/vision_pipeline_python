# CONSTRAINTS — the things a build may not violate

> **STATUS** · live · **OWNS** · the binding limits on any change, in any subsystem
> **READ IF** · you are about to add a dependency, a file format, a network call,
> a constant, or anything the port will have to carry
> **LAST VERIFIED** · 2026-08-25
> **SOURCED FROM** · queue rows `N13`, `N14`, `U3`, `U10`, `U11`, `SEC1`–`SEC5`;
> the old `README.md` §5–§6; `Specification.md` §10

Each of these was paid for. Violating one is not a style disagreement — it
breaks something already decided or already measured.

---

## 1. ⛔ No non-commercially-licensed dependency — `N13`, binding

The game will be commercialised. **Check the licence before proposing any model
or library, and state it in the proposal.** This is what permanently kills
**MANO, HaMeR and WiLoR**, and with them queue `0.5` (the offline oracle).

⚠ It also bites on *algorithms*, not just weights: `T6`'s planar solver was
deliberately built from 1971/1997/2000 prior art rather than IPPE/OpenCV so that
the licence question could not arise, and **Google holds two active hand-tracking
patents to 2038/2039** that touch this area (recorded in the T6 investigation log).

## 2. ⛔ The port contract — stdlib-only, numpy-free estimator layer

Every module in the client's `Resources/` estimator layer (`palm_geometry`,
`palm_rotation`, `palm_depth`, `hand_blocks`, `hand_state`, `palm_anchor`,
`hand_skeleton`, `frame_gate`, `block_predictor`, `confirmation_gate`,
`planar_pnp`, `owner_remap`) is **stdlib-only and numpy-free by contract**, so it
can be transliterated to JS / Swift / Kotlin instead of rewritten.

⛔ **Do not import `cv2`, `numpy` or `scipy` into that layer**, however
convenient. The whole of `U3` rests on this.

## 3. ⛔ Golden vectors before the port exists — not after

Rule 6 of the house rules, and it has already paid: the very first run of the
first such fixture caught a real banker's-rounding bug. New estimator code lands
with an `analysis/verify_*.py` suite in the same change. There are **26 suites,
all passing** as of 2026-08-25.

## 4. ⭐ Shared modules are imported, never copied — `N6`

If both production and the debug tool need a module, **both import the one
copy**. A second copy is how the two silently drift, and the project has paid
for that drift more than once. Corollary, from `L1`: a **tuning constant** lives
in exactly one module too (τ lives in `hand_state.py`, not in both tools).

## 5. ⛔ Nothing leaves the device

There is **no network egress anywhere in the pipeline** — audited 2026-08-25,
verifiable *by absence* (not one HTTP call). The landmark socket is
**loopback-only** and refuses anything else unless `--allow-remote` is passed
deliberately.

⛔ **This is now load-bearing for COPPA/GDPR-K compliance, not just a nicety.**
Anything that transmits is a compliance event and must be raised **before** it is
built. **No third-party analytics or ads SDKs**, ever.

⚠ `VISION_RECORD=1` must be **compile-time-disabled** in shipping builds, not
merely default-off (`U11`).

## 6. ⚠ Recordings live on `E:` — never `--local`

`E:\Python\Recordings for vision_pipeline\…`. Wake the drive first
(`wake_e_drive.py`); its first access after an idle gap fails.

⛔ **The corpus contains NO image data** (`N14`) — landmarks only, established by
exhaustive scan. So **no image-based model can ever be run over it
retroactively**, and questions that need pixels (`SEC5`'s clock, for instance)
cannot be settled from the corpus at all.

⚠ And the **camera was moved between recordings** (owner, 2026-08-24): an A/B on
the *same* take is sound, cross-take *absolute* axis numbers are not. Record the
camera tilt in `meta.json` from now on.

## 7. ⭐ On-screen size comes from `projected_size_px`, never `object.size`

Since Z-translation shipped (`4.2`), `size` means only *"how big it is at the
resting depth"*; the real extent depends on where the object currently is. This
binds the centre, the play-area clamp, the grab radius and both renderers.

⛔ `_top_left_for_center` was **deleted from both tools** for exactly this reason
— it converted with the nominal size, so a surviving copy makes an object drift
sideways as it moves in depth. **Do not reintroduce it.**

## 8. ⚠ No calibration step, anywhere, for now

Owner, 2026-08-23: *"make sure I do not need to recalibrate each time I run the
debug or the production for the moment, nor on local pc nor on future web
build."* `CAMERA_HFOV_DEG = 60.0` stays a **compile-time constant** read only
through `palm_geometry.focal_px()`. Nothing may prompt, persist, gate or block on
a calibration in either tool or in the port.

`U12` will later *override* the default with a stored per-player number — camera
FOV and camera tilt both. **It must never become required.**

## 9. ⚠ Two pipelines are KEPT — so divergence is prevented mechanically

Owner decision, `U6`: production and the debug tool both stay. Therefore run
`analysis/parity_replay.py` whenever either tool's gesture logic changes, or
whenever *"it does not happen in production"* comes up.

⚠ One webcam, and DSHOW is exclusive across processes — **the two can never run
at once**, so any such claim compares separate sessions of a possibly
intermittent defect. Compare them **back to back**.
