// Bootstrap: permission gate -> detection loop -> cube render. The direct
// browser analog of Movement_with_hand_detection's Client.py + PythonApp_Main.py
// + HandsTriggeredActions.py dispatch chain, collapsed into one page since
// there's no separate server process here (see Specification.md §2).
import { enableCamera, disableCamera, getTrackResolution } from "./camera.js";
import { createHandLandmarker, detectHands, extractHandByType } from "./handTracker.js";
import { CubeScene } from "./cubeScene.js";

const videoEl = document.getElementById("camera-preview");
const canvasEl = document.getElementById("scene-canvas");
const enableBtn = document.getElementById("enable-camera-btn");
const disableBtn = document.getElementById("disable-camera-btn");
const statusEl = document.getElementById("status");
const indicatorEl = document.getElementById("camera-indicator");
const debugEl = document.getElementById("debug-readout");

const cubeScene = new CubeScene(canvasEl);

// Model loading doesn't touch the camera, so start it immediately on page
// load (not gated behind the button) to cut wait time after the user clicks
// "Enable camera" — only getUserMedia() itself is gated, per §9.
const handLandmarkerPromise = createHandLandmarker().catch((err) => {
  setStatus(`Failed to load hand landmarker model: ${err.message}`);
  throw err;
});

let trackingActive = false;

function setStatus(text) {
  statusEl.textContent = text;
}

const REJECTION_MESSAGES = {
  "insecure-context": "Camera requires HTTPS or localhost — this page isn't in a secure context.",
  unsupported: "This browser doesn't support camera access.",
  "permission-denied": "Camera permission was denied. Allow camera access in your browser's site settings and try again.",
  "no-camera": "No camera device was found.",
  "camera-in-use": "The camera is already in use by another application.",
  unknown: "Camera access failed for an unknown reason.",
};

enableBtn.addEventListener("click", async () => {
  enableBtn.disabled = true;
  setStatus("Requesting camera access…");

  let track;
  try {
    const result = await enableCamera(videoEl);
    track = result.track;
  } catch (err) {
    setStatus(REJECTION_MESSAGES[err.reason] ?? err.message);
    enableBtn.disabled = false;
    return;
  }

  indicatorEl.classList.add("active");
  disableBtn.disabled = false;
  setStatus("Loading hand model (if not already loaded)…");

  const { width, height } = getTrackResolution(track);
  console.log(`[camera] active track resolution: ${width}x${height}`);

  await handLandmarkerPromise;

  setStatus("Tracking active — move your left hand in front of the camera.");
  trackingActive = true;
  requestAnimationFrame(detectionLoop);
});

disableBtn.addEventListener("click", () => {
  trackingActive = false;
  disableCamera(videoEl);
  indicatorEl.classList.remove("active");
  disableBtn.disabled = true;
  enableBtn.disabled = false;
  setStatus("Camera disabled.");
  debugEl.textContent = "(camera disabled)";
});

async function detectionLoop() {
  if (!trackingActive) return;

  const handLandmarker = await handLandmarkerPromise;
  const result = detectHands(handLandmarker, videoEl, performance.now());
  const hand = extractHandByType(result, "Left");

  if (hand) {
    const fingertip = hand.landmarks[8]; // index fingertip, MediaPipe's 21-point model
    // Mirror X so "hand moves right -> cube moves right" holds for the user
    // facing the camera — see NOTES.md's Mirroring section for why, and to
    // confirm this empirically against the Python window's behavior.
    const mirroredX = 1 - fingertip.x;
    cubeScene.setCubePositionFromNormalized(mirroredX, fingertip.y);

    debugEl.textContent = [
      `handedness: Left (score ${hand.score.toFixed(2)})`,
      `fingertip normalized: x=${fingertip.x.toFixed(3)} y=${fingertip.y.toFixed(3)} z=${fingertip.z.toFixed(3)}`,
      `mirrored x used for cube: ${mirroredX.toFixed(3)}`,
    ].join("\n");
  } else {
    debugEl.textContent = "no left hand detected";
  }

  cubeScene.render();
  requestAnimationFrame(detectionLoop);
}
