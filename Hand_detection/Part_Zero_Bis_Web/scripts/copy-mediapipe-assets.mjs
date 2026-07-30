// Copies MediaPipe's WASM runtime and the shared hand_landmarker model into
// public/ so the browser loads them same-origin instead of from a CDN — see
// Claude/Specification.md §10 (prefer bundling WASM/model assets same-origin
// over the jsdelivr CDN pattern shown in MediaPipe's own quickstart docs, to
// remove the external-CDN trust/availability risk entirely).
//
// Run via `npm run copy-mediapipe-assets` (also runs automatically after
// `npm install`, see package.json's "postinstall").
import { existsSync, mkdirSync, copyFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(here, "..");

const wasmSrcDir = path.join(projectRoot, "node_modules", "@mediapipe", "tasks-vision", "wasm");
const wasmDestDir = path.join(projectRoot, "public", "mediapipe", "wasm");

const modelSrc = path.resolve(
  projectRoot,
  "..",
  "Python_Server_MediaPipe_vision_pipeline",
  "Resources",
  "hand_landmarker.task"
);
const modelDestDir = path.join(projectRoot, "public", "models");
const modelDest = path.join(modelDestDir, "hand_landmarker.task");

function copyDir(srcDir, destDir) {
  mkdirSync(destDir, { recursive: true });
  for (const entry of readdirSync(srcDir, { withFileTypes: true })) {
    if (!entry.isFile()) continue;
    copyFileSync(path.join(srcDir, entry.name), path.join(destDir, entry.name));
  }
}

if (!existsSync(wasmSrcDir)) {
  throw new Error(`MediaPipe wasm folder not found at ${wasmSrcDir} — run "npm install" first.`);
}
copyDir(wasmSrcDir, wasmDestDir);
console.log(`[copy-mediapipe-assets] Copied MediaPipe wasm runtime -> ${wasmDestDir}`);

if (!existsSync(modelSrc)) {
  throw new Error(
    `hand_landmarker.task not found at ${modelSrc} — expected the same model file already used by the Python pipeline.`
  );
}
mkdirSync(modelDestDir, { recursive: true });
copyFileSync(modelSrc, modelDest);
console.log(`[copy-mediapipe-assets] Copied hand_landmarker.task -> ${modelDest}`);
