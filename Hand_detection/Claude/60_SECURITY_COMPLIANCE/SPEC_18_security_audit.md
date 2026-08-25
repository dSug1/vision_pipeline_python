# ROBUSTNESS & SECURITY AUDIT — §18

> **live · what was already right, what was fixed, and what was deliberately not**
> **SOURCE** · `GESTURE_PIPELINE_SPEC.md` §18–§18.5 — extracted verbatim, not edited

⭐ **§18.1 is the compliance evidence** — no network egress anywhere, verifiable
by absence. ⚠⚠ **§18.4 is a retraction made the same day**, and it carries the
audit's own lesson: an audit is not exempt from A10 because its findings are
code-shaped.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/GESTURE_PIPELINE_SPEC.md lines 6958-7088
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 18. ⭐⭐ ROBUSTNESS & SECURITY AUDIT of the debug and production scripts (2026-08-25)

> **Owner:** *"do a full audit of the scripts of the debug and production and
> verify the robustness of the scripts, and if they are cybersecurity safe. If you
> correct any of the debug or production scripts, make sure you also correct the
> production or debug scripts so they keep mirroring each other."*

Scope: both capture loops and everything they import —
`LiveSnapDebug.py`, `HandsTriggeredActions.py`, `CubeWindow.py`, `Client.py`,
`PythonApp_Main.py`, `Launcher_for_Server_and_Client.py`, `VisionPipeline.py`,
`Server.py`, `inference.py`, `hands_visualizer.py`, the remap utilities,
`hand_identity.py`, the three `.bat` entry points, `requirements.txt`, and the
new `handinput/`. Suite: **`analysis/verify_hardening.py` (51 checks)**.

### 18.1 ⭐ WHAT THE AUDIT FOUND ALREADY RIGHT — this is the compliance evidence

Worth recording as findings, not assumed: these are the claims the store
declarations and the COPPA/GDPR-K position rest on, and they are now checked
rather than believed.

* ⭐⭐ **NO NETWORK EGRESS ANYWHERE.** Not one `urlopen`, `requests`, or HTTP call
  in the entire pipeline. *"Nothing leaves the device"* is verifiable **by
  absence**, which is the strongest form that claim can take.
* ⭐ **No `eval`, `exec`, `pickle`, `marshal`, `os.system`, `shell=True` or
  `yaml.load`** — so there is no deserialisation or command-injection surface at
  all. The wire format is `json.loads`, which cannot construct objects.
* ⭐ Both `subprocess.Popen` calls use the **list form** with paths derived from
  `__file__`, so neither argument-splitting nor PATH substitution applies.
* ⭐ Models load by **absolute path from the package directory** — bundled, never
  fetched (already verified for N13; re-confirmed here).
* ⭐ The socket **already defaulted to `127.0.0.1`**. Nothing shipped bound wider.

### 18.2 What was fixed — and both tools were corrected together

| # | finding | severity | fix | mirrored |
|---|---|---|---|---|
| **S1** | `--host` accepted **any interface**. `0.0.0.0` would put a live stream of hand *and face* landmarks on the LAN, unauthenticated | ⚠ **medium in the COMPLIANCE frame** — local-only is load-bearing for a youth audience, so a transmission is a reportable event, not a bug | non-loopback **refused** unless `--allow-remote` is passed deliberately; the refusal names the reason | ✅ server **and** client, plus the launcher forwards the flag so it cannot be half-applied |
| **S2** | the session tag is interpolated into a **path** in three places (`VISION_RECORD_TAG`, `--tag`, `HANDINPUT_TRACE_TAG`) with no check — `..\..\x` escapes the capture root, `:` or `*` fail with an OSError that reads like a broken drive | low (local, operator-supplied) but the classic finding of any review | one shared `Resources/session_paths.py`; **reject-and-substitute with a printed warning**, never silent repair — a recording whose name lies about the take is worse than a refused one | ✅ both recorders + `handinput/trace.py` |
| **S3** | the `meta` packet's resolution goes straight to `pygame.display.set_mode()` with **no upper bound** — `[100000, 100000]` asks for a ~40 GB surface | low-medium (needs a local process to hold the port first) | clamped to 8192, plus a **type check on every array element**: the consumers do arithmetic, so one string raised *mid-frame*, after part of the frame had been applied | n/a (client-only path) |
| **R1** | `Client.py`'s receive buffer was **unbounded** — a peer that never sends `\n` grows it until the process dies, and a server wedged mid-`sendall` has that exact shape | robustness | capped at 1 MB (~400× the largest real packet) and the connection dropped with a clear message | n/a |
| **R2** | `recv(4096).decode()` **per chunk** splits any multi-byte UTF-8 sequence straddling a chunk boundary | latent — today's payload is all-ASCII | buffer **bytes**, decode each complete packet. ⚠ Left as-is it would fail ~once every few hundred frames, at random, the first time a non-ASCII field is added | n/a |
| **R3** | ⭐ **a single failed `cap.read()` ended the session — in BOTH tools.** A USB hiccup or an exposure re-negotiation closes the window mid-take, and on a `--record` take that is the whole session | robustness, and it bites hardest exactly when it costs most | shared `capture_policy.read_frame()`: 30 attempts over ~0.3 s, then give up with a message naming the cause. ⛔ Deliberately **not** retry-forever — a tool that hangs on a dead camera is worse than one that exits | ✅ **both loops and both cold-start probes**, one module, identical constants |
| **R4** | `bind()` failure surfaced as a bare traceback, and *"a stray from the previous run holds the port"* is the normal cause (the children outlive their launcher by design) | robustness | a clear message that names `stop.bat` | n/a |
| **R5** | `analysis/verify_planar_pnp.py` printed `ALL GOLDEN VECTORS PASS` and then **exited 1** on a `UnicodeEncodeError` writing `⚠` to a cp1252 console | ⚠ worse than it sounds | added the `sys.stdout.reconfigure` guard every other suite already had. ⭐ **A permanently-red suite is worse than no suite: it teaches the reader to skip the red.** All 26 now pass | n/a |

### 18.3 ⛔ Found and deliberately NOT fixed — with the reason, so it is a decision

* ⛔⛔ **THE FACE DETECTOR RUNS EVERY FRAME AND NOTHING CONSUMES IT.** Its
  keypoints are computed, serialised and sent over the socket, and the client's
  dispatch is literally `elif datatype == "face": pass`. (`CursorController.py`,
  the Part Zero consumer it was for, is likewise defined and imported by nothing.)
  ⭐ It is **also a debug/production divergence** — `LiveSnapDebug.py` has no face
  detector at all — so the two pipelines differ in what they load and compute per
  frame. ⚠ **And it is a disclosure question**: with the audience decided as all
  public including youth, *"does this app run a face detector"* has a different
  answer depending on this, and running one for no consumer is the worst version
  of that trade. ⚠ **Do not expect a frame-rate win** — the capture rate is
  measured **camera-bound, not compute-bound**.
  ⭐ **A switch was added and the default was NOT flipped**: `--face off` stops
  the model, the computation and the wire packet. Turning it off is visible (the
  preview loses the overlay), so it is the owner's call, not an audit's.
  **Queue `SEC3`.**
* ⚠ **The debug recorder buffers the ENTIRE session in RAM and writes at exit;
  production streams.** Production's own comment says why streaming matters
  (*"production has no clean shutdown path... a buffered take would be lost"*).
  The debug tool's `finally` covers normal exits and exceptions but **not**
  `stop.bat` or a crash, and a 30-minute take is ~70 MB of live list. ⛔ Not
  restructured **on the same day as an unvalidated live take** — it is the tool
  the owner is about to judge the input system in. **Queue `SEC4`.**
* ⚠ **Both tools feed MediaPipe a FAKE clock**: `timestamp_ms += 33` per frame, a
  hardcoded 30 fps, while N7 measured the real rate at 15–24 fps. ⭐ They MIRROR
  each other, so this is not a divergence, and the timestamps are monotonic so
  MediaPipe's contract holds. ⛔ **Not changed here**, and see §18.4 — the first
  version of this bullet asserted a mechanism it had not measured. **Queue `SEC5`.**
* ⚠ **Only two direct dependencies are pinned** (`mediapipe==0.10.14`,
  `pygame==2.6.1`); the other **24 are transitive from mediapipe and float**.
  ⭐ Measured, not assumed: they have **already drifted past what mediapipe 0.10.14
  was built against** — numpy 2.4.6 and opencv-contrib-python 5.0.0.93. So the
  environment the corpus's numbers came from was unrecorded and not reproducible.
  `requirements.lock.txt` now records it; hash pinning and the licence inventory
  N13 needs belong to packaging. **Queue `SEC2`.**
* ⚠ `Client.py` connects **at import time**, so its packet-parsing loop cannot be
  unit-tested without a live socket. Verified this time by an ad-hoc fake server
  (below); restructuring it is more risk than value today.

### 18.4 ⚠⚠ A CORRECTION TO §18.3, MADE THE SAME DAY — and it is the audit's own lesson

The first version of §18.3's `SEC5` bullet said the fake clock means *"the tracker
is told the hand moves ~2× faster than it does, a plausible contributor to
landmark-layer jitter."*

⛔ **That is a hypothesis about MediaPipe's internals, and it was written as
though it were a finding.** In the Tasks API the VIDEO-mode timestamp is primarily
a **graph packet timestamp**; it is not established that the hand-landmarker graph
runs any velocity- or time-based filter that would consume it. The honest
statement is narrower: **the clock is wrong, and the effect on the output is
unmeasured — quite possibly nil.**

⭐ It is corrected here rather than quietly edited because it is exactly the
failure this project keeps a rejected-list for: *"a mechanism that sounds right"*
becoming a recorded fact, and then a build being sequenced around it. An audit is
not exempt from A10 just because its other findings are code-shaped.

⭐⭐ **AND THE CONSTRAINT THAT MAKES IT INTERESTING: THE CORPUS CANNOT TEST IT.**
Changing MediaPipe's *input* means re-running MediaPipe, and the corpus holds **no
image data at all** — 415 files, landmarks only, deliberately. There is nothing to
replay. ⭐ But a clean test needs no pixels and no new recording format: **two
`HandLandmarker` instances fed the SAME `mp_image` each frame**, one on `+= 33`,
one on the measured `tCapture`. Same camera, same frames, one variable, each
keeping its own tracking state — the multi-arm pattern `update_hands_all` already
implements, with the second inference free because the pipeline is camera-bound.
Both arms record through the existing recorder, so `t5h` scores it with no new
harness. A **null closes the item permanently**, which is worth as much as a hit.

### 18.5 How the fixes were verified

* **`analysis/verify_hardening.py`, 51 checks** — tag traversal (including the
  *property* that any tag joined under the root stays under it), the capture
  retry's recover **and** give-up paths with their exact call counts, the loopback
  refusal on both ends including the `--allow-remote` override, and the `meta`
  clamp — with a check that a **real** resolution is still accepted, because a
  guard that refuses everything passes every other check and breaks the pipeline.
* **An end-to-end hostile-server run** against the real `Client.py`: an oversized
  `meta`, a non-numeric array, a non-object packet, malformed JSON, and a packet
  **split mid-number across two TCP writes**. Every one was handled, the split
  packet reassembled silently, and the good frames still dispatched.
* **All 26 `verify_*` suites pass** (26/26 for the first time), `VerifyChirality
  Fixture` passes, and **`parity_replay` reports NO DIVERGENCE** — which is what
  says the mirrored edits did not pull the two tools apart.

---
<!-- VERBATIM-END -->
