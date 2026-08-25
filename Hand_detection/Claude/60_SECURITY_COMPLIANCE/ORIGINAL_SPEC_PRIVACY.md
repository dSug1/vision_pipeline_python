# CAMERA PERMISSIONS & CYBERSECURITY — the original requirements, verbatim

> **reference · the browser permission UX, and the standing security requirement**
> **SOURCE** · `Specification.md` §9–§10 — extracted verbatim, not edited

⚠ Written before the audience decision. **COPPA/GDPR-K now apply** and the
requirements below are a floor, not the position — see [`INDEX.md`](INDEX.md).

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 553-623
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 9. Camera permission handling (browser)

Required, not optional — build this as a real UX flow, not a bare `getUserMedia()` call:

- Explicit **"Enable camera" button/gate** before any `getUserMedia()` call — don't
  auto-prompt on page load (bad UX, and looks like a dark pattern to users/browsers).
- Handle and surface all rejection paths distinctly: user denies permission, no camera
  device present, camera in use by another application, browser blocks due to non-HTTPS
  context (getUserMedia requires a secure context — HTTPS or localhost, plan hosting
  around this from day one, see §10).
- Provide a visible way to know the camera is active (a live preview thumbnail or a clear
  "camera active" indicator) — don't run hand tracking on a hidden/invisible video element
  without the user being able to see that their camera is on.
- Stop all `MediaStreamTrack`s (`track.stop()`) on page unload/navigation and expose an
  explicit in-UI "disable camera" control — don't rely solely on the tab closing.
- No frame or landmark data leaves the browser in Phase 2 (all-in-browser design already
  guarantees this) — state that explicitly in a short in-app privacy note near the camera
  permission prompt, since "does my webcam feed get sent anywhere" is the natural user
  question for this kind of app.

---

## 10. Cybersecurity requirements (apply at every phase, not just at the end)

**When researching/borrowing from state-of-the-art (web, GitHub, HuggingFace, etc.):**
- Before pulling in any third-party code sample, snippet, or library found via search:
  check repo provenance (stars/activity/maintainer are weak signals but check them),
  license compatibility, and read the actual code for anything unexpected (obfuscated
  code, unexplained network calls, eval/exec patterns) before integrating — don't
  copy-paste unread code into the project, especially anything touching camera/media
  streams or anything that will run in Phase 2's browser context with camera access.
- Treat MediaPipe's own official packages (`@mediapipe/tasks-vision` on npm,
  `mediapipe` on PyPI) and Three.js as the trusted core dependencies; treat small
  one-off utility repos (e.g. a random zmbx→glTF converter) as lower-trust — review before
  use, prefer running such conversion tools offline/locally rather than as a live
  dependency, and don't give them any credentials or network access they don't need.

**When coding:**
- Pin dependency versions (package-lock.json / requirements with hashes) — don't use
  floating `latest`/`^`/`*` version ranges for anything that ends up in the production
  bundle, to avoid unreviewed supply-chain updates landing silently.
- Run `npm audit` (or equivalent) and Python dependency vulnerability scanning
  (e.g. `pip-audit`) as a routine step before each milestone, not just once at the end.
- No secrets, API keys, or credentials committed to the repo at any point — this project
  as designed needs none (no server-side API keys in the all-browser Phase 2 design), so
  treat any future addition that *would* need one as a design decision to flag, not a
  default to reach for.
- Validate/sanitize anything loaded dynamically (glTF assets, any future user-uploaded
  content) — Three.js's GLTFLoader parses attacker-controllable file structures if asset
  upload is ever added, so keep asset sources restricted to files you've authored/vetted
  (bundled with the app) unless a user-upload feature is explicitly designed with
  validation.

**When porting to cloud (Phase 2 hosting):**
- Phase 2's all-browser design means production hosting is **static file hosting only** —
  no server-side compute, no database, no user data collected or stored server-side (the
  camera stream and landmarks never leave the browser). This is a meaningful security
  simplification — preserve it; don't casually add a backend later without re-evaluating
  the threat model.
- **Serve over HTTPS only** — required both for `getUserMedia()` (secure-context
  requirement) and generally non-negotiable for anything handling camera permissions.
- Set a reasonable Content-Security-Policy (restrict script-src to self + the specific
  CDN origin used for MediaPipe's WASM/model assets if loaded from CDN, or better: bundle
  the WASM/model files with the app build and serve from the same origin, removing the
  external CDN dependency and its associated trust/availability risk entirely — prefer
  this for production over the jsdelivr CDN pattern shown in MediaPipe's quickstart docs).
- If a static host with a public bucket/CDN (Netlify/Vercel/S3+CloudFront/etc.) is used,
  ensure no directory listing is exposed and only intended build output is public.

---

<!-- VERBATIM-END -->
