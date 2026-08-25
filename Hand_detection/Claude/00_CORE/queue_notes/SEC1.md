# `SEC1` — ⭐⭐ ROBUSTNESS + SECURITY AUDIT of both tools — fixes shipped

> **Dossier.** The full, unedited history of this queue row.
> Its one-line status and its place in the order are in
> [`../QUEUE.md`](../QUEUE.md) — update **both** when it changes.
>
> **Status when this file was created (2026-08-25):** ✅ DONE 2026-08-25

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1248-1248
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
| **SEC1** | ⭐⭐ **ROBUSTNESS + SECURITY AUDIT of both tools — fixes shipped** | infra | ✅ **DONE 2026-08-25** | — | Full account: `GESTURE_PIPELINE_SPEC.md` **§18**. Suite: `analysis/verify_hardening.py` (**51 checks**). ⭐⭐ **THE CLEAN HALF IS THE POINT AND IT IS NOW CHECKED RATHER THAN BELIEVED**: **no network egress anywhere** — not one HTTP call in the pipeline, so *"nothing leaves the device"* is verifiable **by absence**, the strongest form that claim can take — plus no `eval`/`exec`/`pickle`/`shell=True`/`yaml.load` (no deserialisation or injection surface at all), both `subprocess.Popen` calls in list form, models by absolute path, socket already on loopback. **FIXED, mirrored into both tools:** off-loopback **refused** unless `--allow-remote` (S1 — the launcher forwards it so it cannot be half-applied); session tags **sanitised** in one shared `Resources/session_paths.py`, reject-and-warn rather than silent repair (S2); `meta` resolution **clamped to 8192** and every wire element **type-checked** before it reaches arithmetic — one string used to raise MID-FRAME, after part of the frame had been applied (S3); receive buffer **capped at 1 MB** and decoded per PACKET not per chunk (R1/R2); ⭐ **a single failed `cap.read()` no longer ends the session in either tool** — shared `capture_policy.py`, 30 attempts over ~0.3 s then give up, and on a `--record` take that failure used to cost the whole session (R3); a clear message when a stray holds the port (R4); and `verify_planar_pnp.py` fixed — it printed `ALL GOLDEN VECTORS PASS` then **exited 1** on a cp1252 `⚠`, so **all 26 suites now pass for the first time** (R5). ⭐ Verified additionally by an end-to-end **hostile-server** run against the real `Client.py` (oversized meta, non-numeric array, non-object packet, malformed JSON, a packet **split mid-number across two TCP writes**) — all handled, good frames still dispatched — and by `parity_replay` **NO DIVERGENCE**, which is what says the mirrored edits did not pull the tools apart |
<!-- VERBATIM-END -->
