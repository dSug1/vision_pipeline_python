# Mobile Deployment Research — MediaPipe & OpenCV on iOS / Android

**Date:** 2026-05-29
**Method:** Deep-research harness — 5 search angles, 19 primary sources fetched, 79 claims extracted, 25 adversarially verified (3-vote, need 2/3 to refute). 22 confirmed, 3 refuted.
**Question:** Can MediaPipe and OpenCV (`cv2`) be deployed in real production iOS/Android apps, and how? What are the proven options for a single codebase targeting iOS + Android + Windows with camera-based hand/face landmark detection?

---

## TL;DR

- **The current Python stack (MediaPipe-Python + `opencv-python`/`cv2`) is desktop-only and cannot ship on mobile.** No Android wheels exist; install fails via Chaquopy. Python-on-mobile is a dead end for this use case.
- **The technology does deploy on mobile** — through **native per-platform SDKs** (Android Gradle, iOS CocoaPods), not Python.
- **The same model file** (`hand_landmarker.task` / `.tflite`) runs unchanged on Android, iOS, Windows, web, and Raspberry Pi. Cross-platform **model** reuse is real and proven by Google's own sample apps.
- **There is no turnkey single-codebase cross-platform MediaPipe-vision SDK.** The realistic architecture is **shared model files + per-platform native inference/UI glue**.
- **No named third-party shipped app** (App Store / Play Store) was verified — the evidence is Google's official *sample* apps, which prove the path works on real devices.

---

## The two-layer reality

| Layer | Portable across iOS / Android / Windows? |
|---|---|
| **Model** (`hand_landmarker.task`, `.tflite`) | ✅ Identical file on all platforms |
| **Inference runtime + camera + UI code** | ❌ Per-platform native code |

---

## Findings (all verified 3-0 unless noted; confidence: high)

### 1. iOS native path = `MediaPipeTasksVision` via CocoaPods (not Python)
Google's official iOS guide states verbatim: *"Hand Landmarker uses the MediaPipeTasksVision library, which must be installed using CocoaPods"* — with `pod 'MediaPipeTasksVision'`, `use_frameworks!`, CocoaPods 1.12.1+. Compatible with Swift and Objective-C, no language-specific setup. Real shipped pod versions exist (e.g. `MediaPipeTasksVision 0.10.33` XCFramework). iOS Tasks support was announced in MediaPipe v0.10.1.
**Sources:** [ai.google.dev iOS guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/ios), [developers.google.com iOS guide](https://developers.google.com/mediapipe/solutions/vision/hand_landmarker/ios)

### 2. Android native path = `com.google.mediapipe:tasks-vision` via Gradle (not Python)
Official docs instruct `implementation 'com.google.mediapipe:tasks-vision:latest.release'`. Uses `HandLandmarker.createFromOptions()`, converts camera frames to `MPImage` (`BitmapImageBuilder`), and runs `detect()` / `detectForVideo()` / `detectAsync()` with `IMAGE` / `VIDEO` / `LIVE_STREAM` modes. A native AAR invoked from Java/Kotlin, corroborated by Google's `HandLandmarkerHelper.kt` sample.
**Source:** [ai.google.dev Android guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/android)

### 3. Google maintains official on-device sample apps — same model across all platforms
The `google-ai-edge/mediapipe-samples` repo's `examples/hand_landmarker/` contains exactly five subdirs: **android, ios, js, python, raspberry_pi** (confirmed via GitHub API). The Android sample (Kotlin) detects landmarks from the live camera on a physical device (SDK 24+), auto-downloading `hand_landmarker.task`. The iOS sample (Swift) loads the **same** model via `Bundle.main.path(forResource: "hand_landmarker", ofType: "task")` and runs live-camera inference. The overview describes one shared "HandLandmarker (full)" bundle served identically to Android/iOS/Python/Web. The MediaPipe README states it deploys to *"mobile (Android, iOS), web, desktop, edge devices, and IoT."*
⚠️ These are official Google **example** apps demonstrating on-device deployment — **not** verified shipped App Store / Play Store products.
**Sources:** [mediapipe-samples/android](https://github.com/google-ai-edge/mediapipe-samples/tree/main/examples/hand_landmarker/android), [mediapipe-samples/ios](https://github.com/google-ai-edge/mediapipe-samples/tree/main/examples/hand_landmarker/ios), [mediapipe repo](https://github.com/google-ai-edge/mediapipe), [hand_landmarker overview](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)

### 4. OpenCV has an official native iOS path (`opencv2.framework` / `.xcframework`)
OpenCV's official 4.x docs host the "OpenCV iOS Hello" tutorial: link `opencv2.framework` into Xcode via *Build Phases → Link Binary With Libraries*, rename `ViewController.m` → `.mm` for Objective-C++. A build script (`platforms/ios/build_framework.py`) produces `opencv2.framework` / `opencv2.xcframework` for armv7/arm64 + simulator. This is distinct from `opencv-python` (`cv2`).
⚠️ Minor caveat: the iOS install page carries an "obsolete information" banner.
**Sources:** [OpenCV iOS Hello](https://docs.opencv.org/4.x/d7/d88/tutorial_hello.html), [OpenCV iOS install](https://docs.opencv.org/4.x/d5/da3/tutorial_ios_install.html)

### 5. MediaPipe-Python & `cv2` are NOT installable on Android (no wheels; Chaquopy fails)
PyPI's MediaPipe page (v0.10.35) lists only desktop wheels (`win_arm64`, `win_amd64`, `manylinux_2_28_x86_64`, `macosx_11_0_arm64`) — no android-tagged or aarch64-linux wheel. Chaquopy can only install pure-Python (`any`) wheels or ones it built for Android; desktop ABI wheels cannot load. Chaquopy issue #1247 (2024-09-25) shows `install('mediapipe==0.10.15')` failing with *"Could not find a version that satisfies the requirement... (from versions: none)."* Maintainer: *"the MediaPipe Python build process... looks fairly complex... This package isn't currently a priority."* MediaPipe issue #4897 confirms the pybind11 C++ binding modules are missing under Chaquopy.
**Sources:** [chaquopy#1247](https://github.com/chaquo/chaquopy/issues/1247), [chaquopy#479](https://github.com/chaquo/chaquopy/issues/479), [mediapipe#4897](https://github.com/google-ai-edge/mediapipe/issues/4897), [PyPI mediapipe](https://pypi.org/project/mediapipe/)

### 6. Cross-platform binding/plugin routes are limited or off-target
- **.NET (Xamarin/MAUI):** [OpenCvSdk](https://github.com/v-hogood/OpenCvSdk) provides Android + iOS .NET bindings for the OpenCV SDK (NuGet `OpenCvSdk.Android` v4.13.0 Feb 2026, ~6,300 downloads; `OpenCvSdk.iOS` v4.13.1) — but **single-maintainer, low download volume** (low maturity). No mature MediaPipe Tasks .NET binding was found.
- **React Native:** `react-native-llm-mediapipe` is **LLM-only** — explicitly does *not* support hand/face landmark detection.
- **Flutter:** `mediapipe_genai` is **GenAI-only**, supports Android/iOS/macOS but **not Windows/Linux/Web**, v0.0.1 from an unverified uploader (~2 years stale).
⚠️ A separate vision-capable `cdiddy77/react-native-mediapipe` repo exists but was **not verified** in this research.
**Sources:** [OpenCvSdk](https://github.com/v-hogood/OpenCvSdk), [OpenCvSdk.Android NuGet](https://www.nuget.org/packages/OpenCvSdk.Android), [react-native-llm-mediapipe](https://github.com/cdiddy77/react-native-llm-mediapipe), [mediapipe_genai](https://pub.dev/documentation/mediapipe_genai/latest/)

### 7. Single codebase for iOS + Android + Windows: model reuse yes, shared binary no
The same `hand_landmarker.task` is referenced by the Android sample (`setModelAssetPath("hand_landmarker.task")`), the iOS sample (`Bundle.main.path(forResource:"hand_landmarker", ofType:"task")`), and the Python/Raspberry Pi sample (`mediapipe.tasks.python`). MediaPipe Python ships Windows wheels (`win_amd64`, `win_arm64`), so Windows desktop uses the Python API directly with the identical model. **Model reuse across all three targets is real — but the runtime/UI code differs per platform; there is no single shared application binary.**
**Sources:** [hand_landmarker overview](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker), [mediapipe-samples](https://github.com/google-ai-edge/mediapipe-samples/tree/main/examples/hand_landmarker), [PyPI mediapipe](https://pypi.org/project/mediapipe/)

---

## Refuted claims (failed verification, 0-3 — excluded)

- ❌ "`mediapipe_genai` is a Google-maintained official Flutter path for MediaPipe." (Not established as official/Google-maintained.)
- ❌ "Binary/C-extension Python packages (numpy, Pillow, OpenCV) cannot be imported in BeeWare/Briefcase apps on iOS/Android, crashing at import." (Refuted — BeeWare *does* support binary packages.)
- ❌ "pip/PyPI lack mobile support, so binary wheels are universally unavailable for iOS/Android." (Overbroad — refuted.)

---

## Caveats

- **Time-sensitivity:** MediaPipe moves fast — cited versions (`MediaPipeTasksVision 0.10.33`, mediapipe Python `0.10.35`, OpenCvSdk `4.13.x`) will drift.
- **No named production app:** every verified mobile deployment is an official Google **sample/example** app, not a named shipped App Store / Play Store product.
- **Alternatives not deeply verified:** ML Kit, Apple Vision, ONNX Runtime Mobile, LiteRT/TFLite were surfaced as context but did not have independently verified surviving claims this round.
- **Weak/stale sources flagged:** OpenCV iOS install page ("obsolete information" banner); `mediapipe_genai` v0.0.1 unverified uploader; OpenCvSdk single-maintainer/low-downloads.

---

## Open questions (candidates for a follow-up research round)

1. Are there **named, verifiable third-party production apps** (not Google samples) shipping MediaPipe Tasks or OpenCV on-device landmark detection?
2. Does the separate **`cdiddy77/react-native-mediapipe`** repo (and the Flutter `hand_landmarker` pub.dev package) provide working, maintained on-device hand/face landmark detection? *(This is the one thing that could enable a near-single-codebase path.)*
3. How do **ML Kit / Apple Vision / ONNX Runtime Mobile / LiteRT** compare as proven cross-platform landmark paths, with primary-source evidence?
4. Is there **any** framework delivering a genuinely single shared on-device codebase across iOS + Android + Windows, rather than shared model files + per-platform native code?

---

## Primary sources

- Google AI Edge — Hand Landmarker [iOS](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/ios) · [Android](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/android) · [Overview](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)
- [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe) · [mediapipe-samples](https://github.com/google-ai-edge/mediapipe-samples/tree/main/examples/hand_landmarker)
- OpenCV docs — [iOS Hello](https://docs.opencv.org/4.x/d7/d88/tutorial_hello.html) · [iOS install](https://docs.opencv.org/4.x/d5/da3/tutorial_ios_install.html) · [OpenCV Android](https://opencv.org/android/)
- [PyPI: mediapipe](https://pypi.org/project/mediapipe/)
- Chaquopy issues [#1247](https://github.com/chaquo/chaquopy/issues/1247) · [#479](https://github.com/chaquo/chaquopy/issues/479) · [#303](https://github.com/chaquo/chaquopy/issues/303) · [MediaPipe #4897](https://github.com/google-ai-edge/mediapipe/issues/4897)
- [OpenCvSdk](https://github.com/v-hogood/OpenCvSdk) · [react-native-llm-mediapipe](https://github.com/cdiddy77/react-native-llm-mediapipe) · [mediapipe_genai](https://pub.dev/documentation/mediapipe_genai/latest/)
- [ML Kit face detection (iOS)](https://developers.google.com/ml-kit/vision/face-detection/ios) · [opencv-mobile](https://github.com/nihui/opencv-mobile)

---

# Round 2 — resolving the open questions

**Date:** 2026-05-29 · 21 sources fetched, 90 claims, 25 verified (23 confirmed, 2 refuted).
**Focus:** named production apps · cross-platform vision plugins · alternatives (esp. **Windows** support) · single-codebase frameworks.

## TL;DR (Round 2)

**The decisive axis is Windows.** Of the candidate inference engines, only **ONNX Runtime** and **LiteRT (TFLite)** natively cover **all three** of iOS + Android + Windows. ML Kit and Apple Vision are mobile/Apple-only. The cross-platform *plugins* are weak: the React Native MediaPipe vision plugin has **no Windows** (and no confirmed hand-landmark module), and the Flutter Windows-capable option is low-maturity/author-asserted. **Still unverified** (ran out of token budget): Unity's `MediaPipeUnityPlugin` and a .NET MAUI inference binding — the two most likely "true single codebase" routes.

## Q1 — Named third-party production apps

- **None verified.** Even the apps in Google's own promotional posts (e.g. "Dino Jump", "Prism" hand-tracking demos) are **AI Studio web demos**, not store-listed products; Windows is never named. *(high, 3-0)* — [Google Developers Blog](https://developers.googleblog.com/jump-to-play-building-with-gemini-mediapipe/)
- A third-party engineering case study describing a hand-gesture input mobile app exists but is a vendor **blog**, not a verifiable store product. — [nomtek blog](https://www.nomtek.com/blog/hand-gesture-input-method-mobile-app)
- **Takeaway:** the absence of named shipped apps persists. This is a real signal — it's not a heavily-trodden path for production consumer apps.

## Q2 — Cross-platform vision plugins

- **`cdiddy77/react-native-mediapipe` (vision):** confirmed it IS the vision MediaPipe RN plugin; supports **iOS 12+ and Android only — NO Windows**; pre-1.0, modest maturity; has **face + pose** detection. *(high)* The claim that it implements **hand + face + pose on both platforms was REFUTED (0-3)** — i.e. **hand-landmark support is absent/unconfirmed.** — [repo](https://github.com/cdiddy77/react-native-mediapipe), [releases](https://github.com/cdiddy77/react-native-mediapipe/releases), [API docs](https://cdiddy77.github.io/react-native-mediapipe/docs/category/api/)
- **Flutter `hand_detection` (hugocornellier):** a Flutter/Dart package that *claims* true cross-platform support **including Windows** via TFLite. But this is **author-asserted**, and its maturity is **uncertain/contradictory** (the "immature" assessment failed verification 1-2 — neither confirmed mature nor immature). Treat as unproven. *(medium/low)* — [pub.dev](https://pub.dev/packages/hand_detection), [repo](https://github.com/hugocornellier/hand_detection)
- **Flutter `google_mlkit_face_detection`:** confirmed on-device **face** detection, iOS + Android (inherits ML Kit's no-Windows limit). *(high)* — [pub.dev](https://pub.dev/packages/google_mlkit_face_detection)
- *(The Flutter `hand_landmarker` pub.dev package was fetched but not among the verified-claim set this round.)*

## Q3 — Alternatives, with the Windows verdict

| Engine | iOS | Android | Windows | On-device | Notes |
|---|---|---|---|---|---|
| **Google ML Kit** | ✅ | ✅ | ❌ | ✅ | Mobile-only; face/pose. *(3-0)* — [ml-kit](https://developers.google.com/ml-kit) |
| **Apple Vision** | ✅ | ❌ | ❌ | ✅ | Apple platforms only; has hand-pose + face. *(3-0)* — [Apple docs](https://developer.apple.com/documentation/Vision/detecting-hand-poses-with-vision) |
| **ONNX Runtime** | ✅ | ✅ | ✅ | ✅ | **All three.** *(3-0)* — [compatibility](https://onnxruntime.ai/docs/reference/compatibility.html), [Windows](https://onnxruntime.ai/docs/get-started/with-windows.html), [Mobile](https://opensource.microsoft.com/blog/2020/10/12/introducing-onnx-runtime-mobile-reduced-size-high-performance-package-edge-devices/) |
| **LiteRT (TFLite)** | ✅ | ✅ | ✅ (Desktop: Linux, Windows) | ✅ | **All three**; successor to TF Lite; runs `.tflite` directly. *(3-0)* — [LiteRT](https://ai.google.dev/edge/litert) |

**Key implication:** the only engines that natively span iOS + Android + Windows are **LiteRT** and **ONNX Runtime** — both run model files directly. Since MediaPipe ships `.tflite`/`.task` bundles, **LiteRT is the natural candidate to run the same models on all three OSes** — but you'd reimplement MediaPipe's image pre-processing and landmark post-processing (the `.task` bundle wraps that pipeline, which the bare runtimes don't replicate).

## Q4 — Single shared codebase

- **Confirmed off the table for all-3-OS vision:** ML Kit (no Windows), Apple Vision (Apple-only), `cdiddy77/react-native-mediapipe` (no Windows).
- **Still UNVERIFIED this round (token budget exhausted) — the two most promising:**
  - **Unity `MediaPipeUnityPlugin` (homuler)** — [repo](https://github.com/homuler/MediaPipeUnityPlugin), [Getting Started](https://github.com/homuler/MediaPipeUnityPlugin/wiki/Getting-Started). Unity targets Windows + iOS + Android from one codebase; this is a genuine candidate but unconfirmed for maturity/on-device landmark support.
  - **.NET MAUI** with a camera (Community Toolkit `CameraView`) + a native inference binding — camera support confirmed ([MAUI CameraView](https://learn.microsoft.com/en-us/dotnet/communitytoolkit/maui/views/camera-view)), but no verified MediaPipe/LiteRT MAUI inference binding.

## Refuted in Round 2

- ❌ "`cdiddy77/react-native-mediapipe` implements hand + face + pose on both iOS and Android" (0-3) — hand support not substantiated.
- ⚠️ "Flutter `hand_detection` is immature (single maintainer, 4★, no releases)" (1-2, not upheld) — maturity left genuinely uncertain.

## Remaining open questions after Round 2

1. **Unity `MediaPipeUnityPlugin`** — does it deliver maintained, on-device hand/face landmarks across Windows + iOS + Android from one Unity project? (Most likely true single-codebase route.)
2. **.NET MAUI** — is there any viable LiteRT/MediaPipe inference binding, or would it require custom per-platform native code?
3. **`.tflite` → ONNX** conversion fidelity for MediaPipe hand/face models (if going the ONNX Runtime route).
