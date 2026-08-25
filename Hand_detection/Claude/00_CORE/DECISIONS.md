# DECISIONS — taken, and still open

> **STATUS** · live · **OWNS** · owner decisions and their consequences
> **READ IF** · you are about to re-open something, or need to know whose call it is
> **LAST VERIFIED** · 2026-08-25
> **SOURCED FROM** · the old `README.md` §5; queue rows `U1`–`U12`, `D4`, `T7`,
> `IS4`, `SEC3`; the YOU-ARE-HERE blocks in
> [`../10_HAND_TRACKING/history/SESSION_LOG.md`](../10_HAND_TRACKING/history/SESSION_LOG.md)

⚠ A decision here is **not** a rejected experiment. Things that were tried and
measured out live in
[`../10_HAND_TRACKING/REJECTED.md`](../10_HAND_TRACKING/REJECTED.md).

---

## Taken and binding

| decision | date | consequence |
|---|---|---|
| **Perception layer in Python under `Local_pc/`** | 2026-08-02 | the spec stays language-neutral for the later port |
| **No non-commercially-licensed dependencies** (`N13`) | 2026-08-04 | MANO / HaMeR / WiLoR permanently out; killed queue `0.5` |
| **Recordings stay on `E:`** | — | never `--local` |
| **Rotation is permanently ungated by open-palm** | 2026-08-01 | `U1` parked; release is tracking-loss + a future hand-open trigger |
| **`GAME_RULES.md` rule 2 is the dropout behaviour of record** | 2026-08-21 | D2/D3 shipped; **`D4` declined**, not deferred |
| **Two pipelines are KEPT** (`U6`) | 2026-08-22 | divergence prevented mechanically — run `parity_replay.py` |
| ⛔ **Audience is ALL PUBLIC, INCLUDING YOUTH** | 2026-08-23 | COPPA / GDPR-K live → no analytics or ads SDKs; local-only is now load-bearing; `VISION_RECORD` compile-time-disabled in shipping builds |
| **`4.4` and `B5` are ONE project, not two rows** | 2026-08-23 | same mechanism from both ends; `N8` rides on it |
| **The whole `5.x` block is an optional MENU** | 2026-08-23 | nothing scheduled, nothing waiting on it |
| **No calibration step now, anywhere** | 2026-08-23 | `CAMERA_HFOV_DEG = 60.0` is a compile-time constant; `U12` may later override, never require |
| **`T7`'s camera tilt comes from `U12`, not the IMU** | 2026-08-24 | *"i don't want to introduce a different behavior between desktop and mobile"* — identical on every platform, identity (level) until `U12`. ⛔ `T7` ships **with `U12`**, and `T6`-class work must not anticipate it |
| ⭐⭐ **SHIP BOTH browser AND native** | 2026-08-25 | *"I would rather deploy both for browser and for native. That doubles the work but increases my reach."* ⭐ It costs far less than double **if the core is shared**: the platform-specific part is the landmark **SOURCE**, not the core — `handinput/sources/` is already that seam. One TypeScript core serves browser *and* native (React Native), with a thin native module per platform over MediaPipe's **first-party** iOS/Android SDK. ⛔ Consequence: **`IS4` becomes a prerequisite of the port**, and the repo moves to a `core/` + `hosts/` split — see `50_PORT_WEB_MOBILE/INDEX.md` |
| **The PLATFORM decision is sequenced RIGHT AFTER `F1`** | 2026-08-25 | `F1` is perception-only and touches no renderer, so it accrues no throwaway work. Everything renderer-shaped (`U2`, `U12`, `T7`, the game layer) waits for it — and must not be started before it |
| ⛔ **UNITY STAYS OUT — the original constraint is re-affirmed, not inherited** | 2026-08-25 | *"keep as it is currently. if ever we will move to Unity, we will do another project to port it to C#"*. ⭐ So Unity is **not** a candidate in the platform decision, and a future Unity build is a **separate project** that ports to C# — not a migration of this one. `U3`'s standing note that C# follows "when Unity is real" is scoped accordingly |
| ⭐⭐ **Next build is `F1`** — the cube's transform from the **fingertips** | 2026-08-24 | palm demoted to support (frame, sign, chirality); owner will specify it in its own conversation |
| **The hand system must be shippable as a standalone input system** | 2026-08-24 | `handinput/` ✅ **shipped** 2026-08-25 (`IS1`–`IS3`); *"for my game, or for any other purpose such as a filter on Snapchat"* |

## Owner-declined, so do not re-raise as a build

| | |
|---|---|
| **`D4` grace period** | **declined** after seeing D2/D3 live — answered, not deferred |
| **`T6d` anisotropic fit** | **rejected** after four live sessions — *"very minor improvement and I don't want to ship it"*. Nothing to revert; production never ran it |
| **An IMU source for camera tilt** | declined — would split desktop and mobile behaviour. Stays a recorded second-order fallback for **a camera that moves during play** |
| **`IS4` interaction tier** | deferred — *"Not sure if I need this for the moment… If it can be implemented in the future with little change, let's keep it for the future"* |

---

## ⚠ Still the owner's to make

| | what is actually blocked on it |
|---|---|
| **`U2` — real 3D-file import** | ⛔ blocked on the **platform decision**, not on effort. Do not build it against the pygame renderer |
| **`U3` — the web / mobile port** | the estimator layer is written for it; nothing else is |
| **`U1` — open-palm / fist priority** | parked; rotation is ungated regardless |
| **`SEC3` — the face detector default** | it runs every frame and **nothing consumes it**; `--face off` exists, the default was deliberately **not** flipped because turning it off is visible in the preview. A youth-audience disclosure question as much as a perf one |
| **Whether ownership should follow the *physical* hand** | today the cube the pipeline calls "left" is driven by the operator's right hand. `4.1`'s trackId migration would dissolve this — and was reverted |

---

## ⛔ Owed, and not closed by anything above

⭐ **Nothing is outstanding as of 2026-08-25.** Both items below were closed the
same evening; they are kept struck rather than deleted so the record of what was
owed survives.

* ~~**The owner's live look at the input system, in both tools**~~ — ✅ **DONE
  2026-08-25**: the owner ran the debug tool and production back to back, both
  clean, and instructed *"ship current build"*. `IS1`–`IS3` moved **BUILT →
  SHIPPED** ([`queue_notes/IS3.md`](queue_notes/IS3.md), and the ✅✅ rows in
  [`QUEUE.md`](QUEUE.md)).
* ~~**`U7`'s declared-ground-truth acceptance take**~~ — ✅ **DONE 2026-08-25**
  (`2026-08-25_171814_known_right_reentry_acceptance`, right hand only, 1127
  single-hand frames): geometry **98.0%** against the declaration, the label
  **93.2%**. U7 is closed.
