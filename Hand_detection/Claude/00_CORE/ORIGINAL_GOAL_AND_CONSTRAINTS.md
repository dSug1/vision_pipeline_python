<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 10-62
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 0. Goal & constraints (read first)

Build a browser-based 3D "game" where hand movements captured by webcam manipulate
3D objects, using MediaPipe hand landmarks as input.

Hard constraints from the owner:
- **No Unity. No OpenCV.** Everything client-facing ends up in the browser (WebGL / Three.js).
- **No physics engine** for v1 — direct kinematic manipulation of objects (position/rotation
  driven straight from hand transform), not force/collision simulation.
- **3D assets authored in Blender**, exported to whatever format WebGL/Three.js consumes
  natively (glTF/GLB — see §8).
- **Camera access rights must be explicitly managed** in the browser (permissions UX,
  not just `getUserMedia()` fire-and-forget) — see §9.
- **Cybersecurity requirements apply throughout**: browsing/research, dependency selection,
  coding practices, and cloud deployment — see §10. This is a standing requirement, not a
  final checklist item — apply it at each part below, starting with Part Zero.
- **Four-part development path (important — design for this explicitly):**
  - **Part Zero (now, on PC):** take the *existing* Python MediaPipe pipeline, which
    currently moves the PC mouse cursor from detected finger position, and retarget it:
    instead of moving the OS cursor, open a simple local window (e.g. Pygame or a minimal
    OpenGL/matplotlib window — whatever's fastest to stand up) containing one cube, and
    move that cube using the same finger-position signal that used to drive the cursor.
    This is a minimal, deliberately low-effort milestone — its only purpose is to prove
    "landmark → 2D/3D object position" works end to end before any other complexity is
    added.
  - **Part Zero-bis (now, port to browser):** port *that same minimal loop* — hand
    detection + cube-follows-finger — to JavaScript/WASM, running 100% in-browser
    (MediaPipe Tasks Vision JS + a trivial Three.js scene with one cube). This is a
    deliberate early dry run of the Python→browser port, done on the *simplest possible*
    pipeline, specifically to surface porting problems (camera permissions, MediaPipe JS
    API differences, coordinate system differences, performance) while the logic being
    ported is still trivial — not after Pipeline A has grown complex. Treat Part Zero-bis
    as the risk-reduction step for the eventual Phase 2 port in §5.
  - **Part One (later, stays on PC):** develop Pipeline A proper (pattern/gesture
    recognition beyond a single cursor point) using the existing Python MediaPipe pipeline
    as the data source. This part does **not** move to the browser yet — it stays a PC-side
    R&D effort, informed by what Part Zero-bis already taught about portability.
  - **Phase 2 (later, production):** once Pipeline A's gesture logic is validated on PC,
    port it to JavaScript/WASM and run 100% in-browser — this port should now be
    low-risk, since Part Zero-bis already validated the porting mechanics on a simpler
    case.
  - **Design implication:** Pipeline A's gesture-recognition logic must be written so its
    *core algorithm* (feature extraction + classification/threshold logic) is portable
    between Python (numpy) and JS with minimal re-architecture — i.e., keep it as pure
    functions over a landmark-array data structure, not entangled with Python-only
    libraries (no pandas, no sklearn Pipeline objects if avoidable — prefer plain numpy /
    a tiny hand-rolled MLP so the trained weights can be exported as flat arrays and
    re-implemented as a forward-pass in JS, or exported to ONNX/TF.js if a real NN is used).
    Apply this same discipline even in Part Zero, small as it is — it's the first proof
    point for the pattern.

---

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 720-728
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 13. Open decisions to make during implementation (flag back to owner, don't assume)

- Exact gesture set beyond the starter list in §7.2 (game-design dependent).
- One-hand vs. two-hand interaction model.
- Whether any dynamic gesture actually needs a learned model, or whether rules suffice
  (resolve empirically in Part One before writing any training code).
- Final static hosting provider for Phase 2 deployment.
- Which local-window library to use for Part Zero's cube (Pygame vs. alternatives) —
  depends on what's already available in the existing pipeline's environment.
<!-- VERBATIM-END -->
