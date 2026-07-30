import { defineConfig } from "vite";

// Default config is enough here: index.html at the project root, MediaPipe's
// wasm + model files served same-origin straight out of public/ (see
// scripts/copy-mediapipe-assets.mjs) — no CDN, no extra rewrite rules needed.
export default defineConfig({});
