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

---

## ⭐⭐ LICENCE & FEASIBILITY CHECK (2026-08-25) — done before the platform decision

Run because the platform decision must be evidenced, not preferred, and because
`N13` binds the **runtime's** MediaPipe binding as much as the pipeline's.

### Licences — one genuine gap

| what | licence | verified |
|---|---|---|
| **MediaPipe framework / code** | **Apache 2.0**, no commercial or field-of-use restriction | ✅ at source (`google-ai-edge/mediapipe/LICENSE`) |
| `@mediapipe/tasks-vision` (declared `1.0.0`) | Apache 2.0, same project | ✅ |
| `three` (declared `0.185.1`) | MIT | ✅ |
| `mediapipe==0.10.14` (Python, in use) | Apache 2.0 | ✅ |
| ✅ **the `.task` MODEL BUNDLE** | **Apache License, Version 2.0** | ✅ **the Model Card says so verbatim** |

⛔⛔ **THE ONE REAL FINDING.** Google's own hand-landmarker page licenses its
**code samples** Apache 2.0 and its **page content** CC-BY-4.0, and says
**nothing about the model bundle**. Third-party write-ups assert Apache 2.0
confidently, and the official Model Card **could not be read automatically here**
(7 pages, 18 fonts, CID-encoded text layer -- a naive extractor returns mojibake;
it needs a real PDF text extractor). ⭐ Archived for the inventory at
[`../60_SECURITY_COMPLIANCE/evidence/`](../60_SECURITY_COMPLIANCE/evidence/). ⭐ The practical read is that it is almost certainly fine —
but *"almost certainly"* is not the standard `N13` sets, and `SEC2` already
records that the licence inventory is owed. **Get this in writing before a store
submission, not before the platform decision** — it does not block the decision,
because it is the same model on every candidate platform.

### Feasibility — browser

* ⛔⛔ **iOS standalone PWA + camera is the hard blocker.** `getUserMedia` is
  long-broken/unreliable when an iOS web app runs in **standalone (home-screen)**
  mode, and the permission is **not persisted**, so the user is re-prompted.
  The documented workaround is to *stop being a PWA* — drop
  `apple-mobile-web-app-capable` and run in a Safari tab — which costs the
  app-like feel entirely.
* ⚠ In the EU, since iOS 17.4 (DMA) PWAs open in Safari tabs regardless.
* ⭐ The web runtime is **WebGL + Web Workers + OffscreenCanvas**, with a GPU
  delegate; **WebGPU for vision tasks is still an open request**, not shipped.
* ⭐ Part Zero-bis already proved the whole loop in-browser on desktop.

### Feasibility — native

* ⭐⭐ **MediaPipe Tasks ships FIRST-PARTY SDKs for Android, iOS, Python and Web.**
  So native Swift/Kotlin uses **Google's own SDK** — no third-party binding, no
  extra licence to clear.
* ⛔ **Cross-platform native is the risky middle.** There is **no official or
  widely adopted React Native / Flutter plugin** for live MediaPipe hand
  tracking; community plugins exist, are largely **Android-only**, and each is a
  separate third-party dependency that must clear `N13` on its own.
* ⭐ **Stores only exist for native.** Apple's Kids Category and Play's Families
  programme — both live because the audience is youth-inclusive — apply to
  **apps**, not to a URL.

### What this does NOT settle

⚠ **Mobile frame rate is unmeasured.** `L1` proved the rate here is
**camera-bound, not compute-bound** (the inter-frame gap is identical with and
without a hand in view), so runtime speed may well not be the binding constraint
— but that was a desktop webcam, and no mobile measurement exists.
⚠ **A native wrapper around the web build** (Capacitor / WKWebView) is the
obvious hybrid and is **not** evaluated here: `WKWebView` has its own
`getUserMedia` history and needs its own check before it is treated as a way out
of the iOS PWA problem.

---

## ⭐⭐ TARGET ARCHITECTURE — one core, N hosts (decided 2026-08-25)

**Owner: ship BOTH browser and native.** The architecture below is what keeps
that from costing double.

### ⛔ The framing that was rejected, and why

*"De-double `Web/` into `Browser/` and `Native/`"* organises by **host**, and
leaves the logic duplicated inside each one. That is the shape this project has
already paid for twice: `Local_pc` alone carries the gesture logic in **two**
places (production + the debug tool), which is why `U6` exists, why
`parity_replay` exists, and why the debug tool silently lost its snap-highlight
for two days. Three host folders is that problem cubed — and it is really six,
because each host grows a debug variant.

### The shape

```
Hand_detection/
  Claude/                    docs
  core/
    conformance/             ⭐ LANGUAGE-NEUTRAL: vectors + action traces + manifest.
                                No language owns it; it is the contract between them.
    python/                  the REFERENCE implementation (estimators + handinput
                                + the interaction tier, after IS4)
    typescript/              the PORT
  hosts/
    pc_python/               ← Local_pc/ (server + client + debug tool)
    browser/                 ← Web/, grown up
    native/                  (new)
  analysis/                  evidence harnesses — stay Python, read recordings, never port
  tools/                     recording / troubleshooting — stay Python
```

### ⭐⭐ The insight that halves the cost

**The platform-specific part is the landmark SOURCE, not the core.** You do not
need a Swift core and a Kotlin core. `handinput/sources/` is already the seam —
the package's own doc says a future source *"that owns a MediaPipe instance and
calls the estimators itself"* fills the same `HandObservation`, and everything
above that struct is unchanged.

| | browser | native |
|---|---|---|
| core (estimators + input + interaction) | **shared TypeScript** | **the same shared TypeScript** |
| landmark source | `@mediapipe/tasks-vision` (first-party, Apache 2.0) | thin Swift/Kotlin module over MediaPipe's **first-party** iOS/Android SDK |
| renderer | Three.js | Three.js via GL bindings, or native |

So the real cost is **one core port + two thin sources + two renderers**, not two
full ports. ⚠ The known risk: there is **no off-the-shelf React Native MediaPipe
hand-tracking plugin** — those thin modules get written. A landmarks-only bridge
is small, and it is the only third-party-free path.

### ⛔ The prerequisite: `IS4`

The **interaction tier** (grab-what, arbitration, ownership) is not in the
portable core today. With two shipping hosts, leaving it out means every host
reimplements the most defect-dense logic in the project. **`IS4` moves ahead of
the port** — extract it in Python first, prove it with `parity_replay` where that
guard already exists.

### The sequence, agreed 2026-08-25

| # | step | note |
|---|---|---|
| 1 | **`F1`** — fingertip transform | unchanged; perception-only, so it accrues no throwaway work |
| 2 | **Platform decision** | right after `F1` |
| 3 | ⭐ **`IS4`** — interaction tier into the core, **in Python** | before any port; prove with `parity_replay` on the two PC tools |
| 4 | **Restructure to `core/` + `hosts/`** | same moment — a move is cheapest when the core is freshly defined |
| 5 | **TypeScript core port**, validated against `core/conformance/` | |
| 6 | **browser host**, then **native host**, sharing that core | |

⚠ **Nothing moves before step 3.** Restructuring now buys nothing and disturbs a
working pipeline right before `F1`.

### The two rules, restated for three hosts

⭐ **`N6` scales up.** Shared code is imported, never copied — and across
languages "imported" becomes **"generated from one core and checked against one
conformance suite."** `core/conformance/` is already *data*, not Python asserts,
which is what makes that enforceable.

⭐ **`U6` scales up.** `parity_replay` compares two Python implementations; across
languages the equivalent is **conformance vectors + the recorded action trace** —
replay one take through every implementation and require identical events.

⚠ And the gap that bit us on 2026-08-25 stays open and gets worse: **renderer
parity is unguarded**, and three renderers make it three ways to diverge
invisibly. Decide at step 4 whether a one-frame render comparison earns its
weight.

## ⚠ The platform decision blocks more than itself

[`U2`](../00_CORE/queue_notes/U2.md) (real 3D-file import) is postponed **on this
decision**, not on effort — building an importer against the pygame renderer
means building it twice. See [`../30_OBJECTS_3D/INDEX.md`](../30_OBJECTS_3D/INDEX.md).

When work starts here, add rows to
[`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md) with `Sub = PORT`.
