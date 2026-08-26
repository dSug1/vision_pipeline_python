# 60 — SECURITY & COMPLIANCE · privacy, minors, stores, hardening

> **STATUS** · live · **OWNS** · the privacy position, the audit, and everything
> that must be true before a store submission
> **READ IF** · you are adding a dependency, a network call, a recording path, an
> SDK, or preparing to package
> **LAST VERIFIED** · 2026-08-26

⛔⛔ **The audience is ALL PUBLIC, INCLUDING YOUTH** (owner, 2026-08-23). That
single decision makes **COPPA and GDPR-K live**, puts the build inside Google
Play's Families policy and Apple's Kids Category, and turns three architecture
questions into compliance ones.

## The position, and it is now CHECKED rather than assumed

⭐⭐ The strongest claim is a negative: **there is no network egress anywhere in
the pipeline.** Not one HTTP call — so *"nothing leaves the device"* is
verifiable **by absence**. Also verified: no `eval` / `exec` / `pickle` /
`shell=True` / `yaml.load` (no deserialisation or injection surface), both
`subprocess.Popen` calls in list form, models loaded by absolute path.

| control | where |
|---|---|
| the landmark socket is **loopback-only**, refused otherwise | `Server.py` / `Client.py`; `--allow-remote` exists **only as a deliberate transmission decision** |
| a session tag can never escape the capture root | `Resources/session_paths.py`, shared by both recorders |
| the wire cannot size an allocation or inject a non-number | `PythonApp_Main.receive_float_array` |
| a camera stall does not end a take | `capture_policy.py`, shared by both capture loops |

Suite: `analysis/verify_hardening.py` — **51 checks**.

## Three things that are binding on architecture, not preferences

1. **No third-party analytics or ads SDKs.** Ever.
2. **The local-only, no-transmission design is load-bearing for compliance.**
   Anything that transmits is a **compliance event**, raised *before* it is built.
3. **`VISION_RECORD=1` must be compile-time-disabled in shipping builds**, not
   merely default-off (`U11`).

✅ Already verified, no action: the MediaPipe model **and** its WASM runtime are
bundled, not hot-linked, on both platforms (`N13`). ⚠ ~16 MB of dead model files
to strip at package time (`U11`).

⛔ **Professional advice is not optional here** — but those three are actionable
today and are what protects the position.

## ⛔ Four open items — decisions, not omissions

| row | state |
|---|---|
| [`SEC3`](../00_CORE/queue_notes/SEC3.md) | ⛔ **a face detector runs every frame and nothing consumes it** (`elif datatype == "face": pass`), and the debug tool has none at all — a divergence **and** a disclosure question for a youth audience. `--face off` exists; **the default was deliberately not flipped** because turning it off is visible in the preview. **Owner's call** |
| [`SEC2`](../00_CORE/queue_notes/SEC2.md) | ⭐ **half done.** Measuring it corrected the row's own framing: the risk is not an attack, it is **reproducibility of the rig** — 24 of 26 packages float and had already drifted past what mediapipe 0.10.14 was built against (numpy 2.4.6, OpenCV 5.0). `requirements.lock.txt` now records the environment. Hash pinning + the **licence inventory `N13` needs** are packaging work |
| [`SEC5`](../00_CORE/queue_notes/SEC5.md) | ⚠ both tools feed MediaPipe a **fake 33 ms clock**. ⛔ The first write-up **overstated its effect and was retracted the same day** (§18.4): the clock is wrong, the output effect is **unmeasured and may be nil**. ⚠ The corpus cannot settle it — **no pixels** — the test is two detectors on the same frames |
| [`SEC4`](../00_CORE/queue_notes/SEC4.md) | the debug recorder buffers a whole session in RAM where production streams — not restructured on the eve of a live take |
| [`SEC6`](../00_CORE/queue_notes/SEC6.md) | ⭐ **NEW 2026-08-26 — attribution must travel with the BINARY.** `THIRD_PARTY_NOTICES.md` + `licenses/` now exist at the repo root (1€ filter BSD-3 · MediaPipe + the model Apache-2.0 · `three` MIT). ⭐ **The BSD-3 copyright line was left blank rather than guessed, then FETCHED** — `Copyright 2023 Inria`, from `casiez/OneEuroFilter/python/LICENSE`; ⚠ **the repo-root path 404s**, which is the dead end that stalled it. ⚠ `handinput/export_package.py` does not copy the notices yet — harmless for a **source** export, a breach the moment one is minified |

⚠⚠ **`SEC5` carries the audit's own lesson, and it is worth more than the
finding: a mechanism that sounded right stood as a recorded fact for one day. An
audit is not exempt from A10 because its other findings are code-shaped.**

## Still to do before any store submission

| row | what |
|---|---|
| [`U10`](../00_CORE/queue_notes/U10.md) | **write it down**: a privacy policy saying exactly what is true, per-store camera declarations (Steam / App Store / Google Play each differ), platform permission strings. ⚠ Not a build — do not start it as one |
| [`U11`](../00_CORE/queue_notes/U11.md) | shipping-build hygiene: strip dead assets, hard-disable dev capture. At package time |
| [`N13`](../00_CORE/queue_notes/N13.md) | the licence inventory the commercial release requires. ⭐ **The model licence is now CLOSED** — the Model Card states *"LICENSED UNDER Apache License, Version 2.0"*; evidence in [`evidence/`](evidence/) |
| [`SEC6`](../00_CORE/queue_notes/SEC6.md) | ⭐⭐ **the distinction `N13` did not cover.** `N13` gates *may we take this dependency*; `SEC6` is *what must ship beside the binary*. BSD-3 clause 2 and Apache-2.0 §4(d) attach to **binary** redistribution — and the minifier erases a docstring notice in the same pass that creates the obligation. ⛔ Closes with `U11`, on a **built** artifact, not by inspection |

## Read

| | |
|---|---|
| the audit in full | [`SPEC_18_security_audit.md`](SPEC_18_security_audit.md) (was `GESTURE_PIPELINE_SPEC.md` §18) — §18.1 what was already right, §18.2 what was fixed, §18.3 what was deliberately not, **§18.4 the retraction**, §18.5 how it was verified |
| the original browser-era requirements | [`ORIGINAL_SPEC_PRIVACY.md`](ORIGINAL_SPEC_PRIVACY.md) (was `Specification.md` §9–§10) — camera-permission UX and the standing cybersecurity requirement |
| the constraints these produce | [`../00_CORE/CONSTRAINTS.md`](../00_CORE/CONSTRAINTS.md) §1, §5, §6 |
