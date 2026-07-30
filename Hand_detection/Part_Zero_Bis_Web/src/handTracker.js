// Thin wrapper around @mediapipe/tasks-vision's HandLandmarker, VIDEO mode —
// the JS analog of the Python side's Resources/inference.py load_models() +
// run_inference_on_frame(). Assets are loaded same-origin (see
// scripts/copy-mediapipe-assets.mjs), not from a CDN — Specification.md §10.
import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";

/**
 * @returns {Promise<HandLandmarker>}
 */
export async function createHandLandmarker() {
  const vision = await FilesetResolver.forVisionTasks("/mediapipe/wasm");

  return HandLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: "/models/hand_landmarker.task",
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numHands: 2,
  });
}

/**
 * Run detection for the current video frame.
 * @param {HandLandmarker} handLandmarker
 * @param {HTMLVideoElement} videoEl
 * @param {number} timestampMs - must be monotonically increasing, per MediaPipe's VIDEO-mode contract
 * @returns {import("@mediapipe/tasks-vision").HandLandmarkerResult}
 */
export function detectHands(handLandmarker, videoEl, timestampMs) {
  return handLandmarker.detectForVideo(videoEl, timestampMs);
}

/**
 * Pull out one hand's result by MediaPipe's own handedness label ("Left" /
 * "Right") — the JS mirror of the Python side's extract_hand_by_type. Per
 * MediaPipe's documented convention, handedness is reported from the
 * subject's own perspective assuming a mirrored/selfie view, i.e. "Left"
 * here already corresponds to the user's real left hand — the same
 * assumption the Python pipeline relies on. Confirm this empirically once
 * running (see NOTES.md) rather than trusting this comment alone.
 */
export function extractHandByType(result, handedness) {
  if (!result?.handednesses) return null;
  const index = result.handednesses.findIndex((h) => h[0]?.categoryName === handedness);
  if (index === -1) return null;
  return {
    landmarks: result.landmarks[index],
    worldLandmarks: result.worldLandmarks[index],
    score: result.handednesses[index][0].score,
  };
}
