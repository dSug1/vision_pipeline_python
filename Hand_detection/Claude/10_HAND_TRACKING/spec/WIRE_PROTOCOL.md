# THE WIRE — what the socket actually carries

> **live · the landmark packets between server and client**
> **SOURCE** · `PART_ONE.md` §4 — extracted verbatim, not edited

⭐ The gap this section originally described is **closed**: the wire *does*
carry `world_landmarks` (`hands_world`, 21×3 per hand, sent before each
`hands` packet). Relevant to the port —
[`../../50_PORT_WEB_MOBILE/INDEX.md`](../../50_PORT_WEB_MOBILE/INDEX.md).

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1263-1302
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->

## 4. Known wire-protocol gap (live pipeline, not recording)

> ⚠⚠ **CORRECTED 2026-08-22 — THE GAP DESCRIBED BELOW IS CLOSED. The wire DOES
> carry `world_landmarks`.** `VisionPipeline.py` builds a `hands_world` packet
> (`remap_world_keypoints`, 21x3 per hand) and sends it *before* each `"hands"`
> packet; `PythonApp_Main.py` decodes it as `hands_world` into
> `on_hands_world_frame`. It was extended for rotation-while-snapped (§13.7) and
> the section below was never updated. **Consequence for 4.1: the depth anchor
> needs NO protocol work** — `hand_skeleton.palm_width_world()` can run
> client-side on data already arriving today.
>
> ⭐ **What is genuinely NOT on the wire is DR-1's TRACK IDENTITY.**
> `hand_identity.py` lives only under
> `Local_pc/Python_Server_MediaPipe_vision_pipeline/Resources/` and nothing
> client-side imports it; the client receives landmarks keyed by handedness SLOT
> only. **That — not `world_landmarks` — is the real content of the `HandState`
> v2 migration, and it is what T3 needs** (see §3.1's T3 row and
> `PERCEPTION_LAYER_SPEC.md` §2.2's 2026-08-22 addendum).
>
> The original text is kept below for provenance. Read it as history, not status.

The existing socket protocol (`VisionPipeline.py` → `Client.py` →
`PythonApp_Main.py`) currently sends only 2D pixel-space landmarks (21
points × 2 hands × `(x_px, y_px)` = 84 floats per `"hands"` packet) — no `z`,
no `world_landmarks`. Translation (step 5) only needs 2D image-space data,
so that part of the protocol doesn't need to change. But since §1's revision,
**gesture classification needs `world_landmarks`**, which the live socket
protocol doesn't carry yet — originally this gap was only flagged for step 7
(rotation), it now also blocks wiring the tuned pinch classifier (step 2/3)
into the live pipeline.

This does **not** block recording or analysis, though: `RecordSession.py`
(§7) captures `world_landmarks` directly from the in-process MediaPipe
`HandLandmarker` result, bypassing the socket entirely — recording and
offline analysis can proceed with today's protocol unchanged. The wire
extension is only needed at the point where the *tuned* classifier gets
wired into `HandsTriggeredActions.py` for live use. Extend `VisionPipeline.py`
/ `Server.py` to send `world_landmarks` then, not before.

<!-- VERBATIM-END -->
