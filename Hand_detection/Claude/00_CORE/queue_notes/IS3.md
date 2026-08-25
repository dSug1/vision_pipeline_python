<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1247-1247
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
| **IS3** | ⭐⭐ **INPUT SYSTEM — the action layer, wired into both tools as an OBSERVER** | platform | ✅ **BUILT 2026-08-25. ⛔ Owner's live take still owed** | IS1 | Five actions — `tracked`, `palm_pose`, `palm_facing`, `grab_ready`, `rotation_delta` — with Unity's five phases and `+=` events. ⚠⚠ **IT DRIVES NOTHING, AND THAT IS WHY IT COULD LAND IN ONE SESSION**: every value was already computed by the gesture logic that frame, so behaviour cannot change — `parity_replay` **NO DIVERGENCE** (454 frames), 24 existing suites pass, 95 new checks pass. ⭐ **It reports what RAN rather than recomputing it**, for the same reason `_record_flush` records the cue: four harnesses once reported CLEAN on takes the owner had just watched fail, every one of them a recomputation. ⛔⛔ **SCOPE — `grab_ready` IS ELIGIBILITY, NOT A GRAB.** Unity splits Input System from XR Interaction Toolkit; this is the first only, because "grab WHAT" needs a scene and answering it here welds the module to this game. ⭐ **THE FINDING THAT FELL OUT OF A REAL RECORDING**: replaying `2026-08-24_220415_prod_tau20` gives `tracked` **8** start/cancel pairs against `palm_pose`'s **9** — the extra one is a BRIDGE, where the hand is still held but the pose has stopped updating. Two states a consumer previously had no way to tell apart. ⚠ Live event traces: `HANDINPUT_TRACE=1` in either tool (a recording cannot produce `rotation_delta` — it stores the cube's smoothed orientation, never the hand's reading, and re-running Horn to fill that gap would make a recomputation the reference for a conformance file) |
<!-- VERBATIM-END -->
