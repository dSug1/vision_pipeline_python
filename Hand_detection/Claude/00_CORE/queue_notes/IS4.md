<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1253-1253
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
| **IS4** | **INPUT SYSTEM — extract the INTERACTION tier (grab/hold/arbitration)** | platform | **OPEN, owner-deferred 2026-08-25** — *"Not sure if I need this for the moment... If it can be implemented in the future with little change, let's keep it for the future"* | IS3 | Move snap proximity, arbitration, sticky grab, owner-follows-track, the grab-relative transforms and the play volume out of `HandsTriggeredActions.py` (1 500 lines) and `LiveSnapDebug.py` (2 200) into one engine-agnostic tier that operates on an abstract manipulable (id, position, bounding radius, depth) the host registers. ⭐ **IS3 was built so this stays cheap: it changes WHO CONSUMES the action layer, not what the layer produces.** Nothing in `handinput` presumes it. ⚠⚠ **AND IT IS THE RISKIEST REFACTOR IN THE PROJECT, so it needs its own session and its own live take**: that code is where T3, U7, U8, U9 and the stranded cube were all paid for, and every branch in it is a lesson. Guard with `parity_replay` + the golden suites + a live look, and expect it to change no measured number. ⚠ It also re-opens **U6** (two pipelines KEPT, owner 2026-08-22): a shared interaction tier dissolves most of that duplication as a side effect, which is an owner decision, not a consequence to slip in |
<!-- VERBATIM-END -->
