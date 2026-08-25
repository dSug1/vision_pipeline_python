# `SEC3` — ⛔ The FACE DETECTOR runs every frame and nothing consumes it — switch added, default NOT flipped

> **Dossier.** The full, unedited history of this queue row.
> Its one-line status and its place in the order are in
> [`../QUEUE.md`](../QUEUE.md) — update **both** when it changes.
>
> **Status when this file was created (2026-08-25):** OPEN — OWNER'S CALL 2026-08-25

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1250-1250
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
| **SEC3** | ⛔ **The FACE DETECTOR runs every frame and nothing consumes it — switch added, default NOT flipped** | privacy / perf | **OPEN — OWNER'S CALL 2026-08-25** | — | Its keypoints are computed, serialised and sent over the socket, and the client's dispatch is literally `elif datatype == "face": pass`. (`CursorController.py`, the Part Zero consumer it was for, is likewise defined and imported by **nothing**.) ⭐ **It is also a debug/production DIVERGENCE**: `LiveSnapDebug.py` has no face detector at all, so the two pipelines differ in what they load and compute per frame. ⚠⚠ **AND IT IS A DISCLOSURE QUESTION**: with the audience decided as ALL PUBLIC INCLUDING YOUTH, *"does this app run a face detector"* has a different answer depending on this — and running one **for no consumer** is the worst version of that trade. ⚠ **Do NOT expect a frame-rate win**: the capture rate is measured **camera-bound, not compute-bound** (64.1 vs 64.0 ms with and without a hand in view). ⭐ `--face off` now stops the model, the computation and the wire packet; the default stays `on` because turning it off is **visible** (the preview loses the overlay) and that is the owner's decision, not an audit's. ⚠ If it is turned off for good, delete `CursorController.py` in the same pass |
<!-- VERBATIM-END -->
