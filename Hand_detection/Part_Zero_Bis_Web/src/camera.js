// Camera access + permission UX — Specification.md §9. This module owns the
// only getUserMedia() call in the app; it is written to be reused as-is by
// Phase 2's /web/src/camera.js later (§9's whole point for building this now).

let activeStream = null;

/**
 * Request camera access. Must be called from a user gesture (e.g. a button
 * click) — never call this automatically on page load.
 *
 * @param {HTMLVideoElement} videoEl - preview element to attach the stream to
 * @returns {Promise<{ stream: MediaStream, track: MediaStreamTrack }>}
 * @throws {Error} with a `.reason` field identifying which rejection path hit:
 *   "insecure-context" | "unsupported" | "permission-denied" | "no-camera" |
 *   "camera-in-use" | "unknown"
 */
export async function enableCamera(videoEl) {
  if (!window.isSecureContext) {
    throw Object.assign(new Error("Camera access requires HTTPS or localhost."), {
      reason: "insecure-context",
    });
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    throw Object.assign(new Error("This browser does not support camera access (getUserMedia)."), {
      reason: "unsupported",
    });
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false,
    });
  } catch (err) {
    const reason =
      err.name === "NotAllowedError" || err.name === "SecurityError"
        ? "permission-denied"
        : err.name === "NotFoundError" || err.name === "OverconstrainedError"
        ? "no-camera"
        : err.name === "NotReadableError"
        ? "camera-in-use"
        : "unknown";
    throw Object.assign(new Error(`Camera access failed: ${err.name} — ${err.message}`), { reason, cause: err });
  }

  activeStream = stream;
  videoEl.srcObject = stream;
  await videoEl.play();

  const [track] = stream.getVideoTracks();
  return { stream, track };
}

/** Stop all tracks and detach from the preview element — the explicit
 * in-UI "disable camera" control §9 requires (don't rely on tab close). */
export function disableCamera(videoEl) {
  if (activeStream) {
    for (const track of activeStream.getTracks()) track.stop();
    activeStream = null;
  }
  if (videoEl) videoEl.srcObject = null;
}

/** Real capture resolution from the active track, once known — mirrors the
 * PC pipeline's "meta" packet (see Claude/PART_ZERO.md and
 * Specification.md §5's "Camera resolution" comparison point). Don't assume
 * a fixed size; read it from the track itself. */
export function getTrackResolution(track) {
  const settings = track.getSettings();
  return { width: settings.width, height: settings.height };
}

// §9: stop all tracks on page unload — don't rely solely on the tab closing.
window.addEventListener("beforeunload", () => disableCamera(null));
