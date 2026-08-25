# PIPELINE B — Three.js scene + Blender asset pipeline, verbatim

> **reference · the original 3D asset plan**
> **SOURCE** · `Specification.md` §8 — extracted verbatim, not edited

⚠ Written in the Part Zero era and **never built**. It is the starting point
for `U2`, which is postponed on the platform decision — see
[`INDEX.md`](INDEX.md).

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 504-552
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 8. Pipeline B — Three.js scene + Blender asset pipeline

**Reference before building from scratch**: `stereoDrift/3d-model-playground` (see §1) is
the closest public match to this whole pipeline — same stack, same "pinch to grab, no
physics" model, same static-hosting target, and it already handles runtime GLTFLoader
usage for user-supplied models. Read its `game.js` for the gesture-detection-to-transform
logic and its camera-permission handling before implementing §8.3 and §9 from scratch —
subject to the review-before-reuse practice in §10.

### 8.1 Stack

- **Three.js** (WebGL). Use a bundler (Vite recommended — fast dev server, easy to later
  containerize the static build for hosting).
- No physics library for v1 (explicitly out of scope) — object manipulation is direct:
  recognized gesture + hand world-position → object transform (position/quaternion) each
  frame, with simple smoothing/lerp for stability, no collision/rigid-body simulation.

### 8.2 Blender → WebGL asset path

- **Export format: glTF 2.0 (`.glb`, binary/single-file preferred over `.gltf` + separate
  textures for simpler asset management).** This is the native, first-class format for
  Three.js — Blender has a built-in glTF exporter (File → Export → glTF 2.0), no plugins
  needed, and Three.js consumes it via `GLTFLoader` with no conversion step.
- Workflow: author/rig objects in Blender → `File → Export → glTF 2.0 (.glb)` → drop into
  `/web/assets/models/` → load via `GLTFLoader` in `assetLoader.js`.
- Keep exported models low-poly / optimized for real-time web rendering (this is a live
  webcam-driven interaction loop, not an offline render — frame budget matters). Consider
  `gltf-transform` or Blender's built-in export compression (Draco) if models get heavy.
- **If any assets originate as Mecabricks `.zmbx` files**: `.zmbx` is not natively
  WebGL-loadable. Path: export from Mecabricks (File → Export → "Blender Add-on") into
  Blender, then re-export from Blender as glTF following the same path above. (A
  third-party zmbx→glTF converter tool also exists if bypassing the Blender round-trip is
  preferred — vet it per §10 before using, since it's an unofficial small utility.)

### 8.3 Gesture → object manipulation mapping

- `objectController.js` subscribes to Pipeline A's recognized-gesture stream (in-process
  JS calls in Phase 2, not network messages) and updates Three.js object
  `position`/`quaternion` directly.
- Design for **one hand actively "holding" at most one object at a time** initially
  (simplest state machine: idle → hover → grabbed → released), extend to two-hand/
  two-object later if needed.
- `3d-model-playground`'s pinch-to-drag/rotate/scale mapping (see §1) is a working
  reference for this exact state machine — its "mode switch" concept (drag vs. rotate vs.
  scale, there triggered by voice command) also maps onto this project's `gestureConfig.js`
  single-source-of-truth idea if multiple manipulation modes are wanted later.

---

<!-- VERBATIM-END -->
