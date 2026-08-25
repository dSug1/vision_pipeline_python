<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1251-1251
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
| **SEC4** | **The DEBUG recorder buffers the whole session in RAM; production streams** | infra | **OPEN 2026-08-25 — deliberately deferred** | — | `LiveSnapDebug.py` accumulates every frame into a list and writes at exit; `HandsTriggeredActions` appends as it goes, and its own comment says why (*"production has no clean shutdown path... a buffered take would be lost whenever the window is closed with the X button"*). The debug tool's `finally` covers a normal close and an exception but **not** `stop.bat`, a crash or a power loss, and a 30-minute take is ~70 MB of live list. ⛔ **Not restructured on 2026-08-25 because that is the tool the owner was about to judge the input system in** — changing the recorder the same evening as an unvalidated live take is how an unrelated bug gets attributed to the thing under test. ⭐ The fix is production's own shape: open the file at the first frame, append per frame, flush every N |
<!-- VERBATIM-END -->
