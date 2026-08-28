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
| ⭐⭐ **The input system is described as "action-based input, in the style of OpenXR and Unity's Input System"** | 2026-08-26 | ⛔ **Not cosmetic — it is the IP posture, and it was adopted BEFORE anyone asserted anything.** Describing `handinput/` as *Unity-Input-System-shaped* invited two avoidable readings: that Unity's marks are being traded on, and that the architecture is Unity's to license. Neither survives contact with the prior art — **semantic actions bound to physical controls is DirectInput action mapping (DirectX 8, 2000)**; the **`Started`/`Performed`/`Canceled` phase machine is `UIGestureRecognizer` (iOS 3.2, 2010)**; the callback-carrying-a-context is `EventArgs` (2002) and DOM `Event` (1998); and the closest living relative is **OpenXR's action system (Khronos, 2019), an open standard that is royalty-free by Khronos IP policy**. Unity's own Input System shipped ~2019, *after* most of it. ⭐ Naming OpenXR first states the lineage accurately and puts the royalty-free standard in front. ⚠ Unity's package ships under the **Unity Companion License** (use only with Unity products), so its **code** was never copyable — but architecture is not copyrightable anyway (17 USC §102(b); EU Software Directive Art. 1(2); **CJEU C-406/10 SAS v. WPL**, 2012 — functionality, language and file formats are not protected). `handinput/` was written from scratch and never had Unity source in the loop. ⭐ Same posture as `F1`'s: reach for **Horn 1987 / Kabsch 1976** and record the lineage, rather than build on something a holding entity can point a patent at |
| ✅✅ **SHIP THE YAW-LEAN TRIM AT 0.66/0.66** (`V2`) | 2026-08-28 | Settled live over 19 homed trials: *"now it's working, and 66/66 seem right"*. ⭐ The gain is a BRACKET, not a derivation — `ROLL` never touches world z so its 6.7° error is the accuracy floor, and `1-6.7/26.8 = 0.750` is where correction starts fighting noise; 0.66 sits just under it. ⛔ The floor is not one number: it rises with turn size, so a scalar tracks the large-turn end where the defect shows. ⚠ Shipped knowing the gate is cleared on only 3 of 4 takes (`stripped` 1.072x) |
| ⭐⭐ **THE CAMERA MOUNTING IS A SETTING, BECAUSE THE GAME MUST RUN ON BOTH** (`V1`) | 2026-08-28 | *"I need to be able to port my game to vision glasses, and in such case the camera view is aligned with the user view. Therefore I need to be able to toggle the flip: camera worn by user = current setup, camera facing user = this new setup"*. ⭐ So it is not a flip switch, it is a statement about the HARDWARE, and every camera-dependent sign derives from it in one module. ⛔ It also revealed that the shipped build is a **hybrid of the two mountings** — mirror from one, depth from the other — which is the defect the owner had been seeing as backwards yaw, pitch and z. ✅✅ **SHIPPED 2026-08-28** after the owner ran both tools in both mounts: default is `facing_user`, orientation `pitch_yaw`, landmarks hidden by default in both tools. `legacy` is kept as the bit-for-bit diagnostic baseline |
| ⭐⭐ **THE PROJECT MOVES OFF THE HANDS AND ONTO THE OBJECTS — assembly by MATE CONNECTORS** (`AS1`–`AS5`) | 2026-08-28 | *"we will stop working on the hands and start working on the cube objects. I want the objects to be able to assemble into an assembly."* ⭐ The owner's word was *sticker*; **`mate connector` is adopted from Onshape** — not cosmetic, because the name brings a taxonomy that already answers questions this design reaches (Fastened / Revolute / Slider / Ball), and it states a lineage rather than inventing one, the same posture `handinput` took towards OpenXR and `V2` towards the MEKF. ⭐⭐ **Four sub-decisions taken the same day on the literature review's findings:** **(1) the roll is closed on the connector** — a `tangent` + `roll_order`, because position + normal alone removes only 5 of 6 DOF and leaves two assembled objects free to spin (that is Onshape's **Revolute**, not **Fastened**); the rejected alternative is LEGO's, requiring two simultaneous mates, and it is harder to hit by hand. **(2) A mate that would close a CYCLE is REFUSED** — a loop is not a tree, and reopening a closed chain is a solver's job. **(3) The play-volume clamp is EXEMPT from the residual** — it is a second driver, and a wall silently breaking a joint is invisible to the player, which is the confident-but-wrong class this project keeps paying for. **(4) The break radius is `k ×` the engage radius, not equal to it** — engage and release must not share a threshold at 25° of jitter. ⛔⛔ **And the finding that reshaped the build: the owner's rules 2 and 3 CONFLICT as written** — enforcing coincidence every frame makes the separation identically zero, so the break condition can never fire; the fix is to **measure the residual on the unconstrained desires and apply the constraint after**, which is how every physics engine does breakable joints. ⭐⭐ It buys a rule for free: **one hand can never break a mate**, because a residual needs two independent drivers. Design of record: [`../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md) |
| ⭐⭐ **UN-SNAPPING NEEDS TWO HANDS — the fork is CLOSED** | 2026-08-28 | *"unsnapping needs two hands"*. ⭐ So `AS3`'s consequence is kept as the RULE, not merely tolerated: a residual needs two independent drivers, therefore **one hand can never break a mate** and a mated pair is permanent to a single hand. ⛔ The two alternatives are DECLINED, not deferred: a **tug** (a fast pull breaking it one-handed, which I had recommended) and **unheld-means-anchored**. Do not re-propose either without new evidence. ⭐ It is Guiard's asymmetry made a rule: the non-dominant hand holds the frame, the dominant one acts, and separation is the one moment both act. ⚠ Consequence to live with: an assembly cannot be taken apart while only one hand is tracked |
| **Third-party attribution must travel with the BINARY, not only the source** (`SEC6`) | 2026-08-26 | `THIRD_PARTY_NOTICES.md` + `licenses/` at the repo root. `N13` clears *may we use this*; this clears *what must ship beside it*. ⛔ A docstring notice is erased by the minifier in the same pass that creates the obligation |

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

⚠ **OWED as of 2026-08-28: `V2`'s PRODUCTION live look.** The yaw-lean trim was
settled in the debug tool over 19 homed trials; production applies the same
constants (0.66 / 0.66) and has **not** been run with them. ⛔ Leaving the hand
subsystem for `AS` does not close it — `METHOD` is explicit that a live look in
**both** tools is what closes a change, and nothing else does.

⭐ **Nothing else was outstanding as of 2026-08-25.** Both items below were closed
the same evening; they are kept struck rather than deleted so the record of what
was owed survives.

* ~~**The owner's live look at the input system, in both tools**~~ — ✅ **DONE
  2026-08-25**: the owner ran the debug tool and production back to back, both
  clean, and instructed *"ship current build"*. `IS1`–`IS3` moved **BUILT →
  SHIPPED** ([`queue_notes/IS3.md`](queue_notes/IS3.md), and the ✅✅ rows in
  [`QUEUE.md`](QUEUE.md)).
* ~~**`U7`'s declared-ground-truth acceptance take**~~ — ✅ **DONE 2026-08-25**
  (`2026-08-25_171814_known_right_reentry_acceptance`, right hand only, 1127
  single-hand frames): geometry **98.0%** against the declaration, the label
  **93.2%**. U7 is closed.
