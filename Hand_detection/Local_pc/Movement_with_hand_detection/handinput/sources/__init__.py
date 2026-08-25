"""Sources -- the only platform-specific code in the package.

A SOURCE produces `HandFrame`s. Everything above it (contract, actions, events,
conformance) is platform-free, which is the property that makes the module
portable: a new platform writes a source and reuses the rest.

| source | what it is |
|---|---|
| `live.py` | the PUSH adapter both of this project's tools use -- they have already computed every value, so they hand them over rather than have them re-derived |
| `recording.py` | replays a session `raw_landmarks.jsonl` (recorder schema 2/3), for harnesses and conformance |
| *(a future)* | a PULL source that owns a MediaPipe instance and calls the estimator modules itself -- for a host that has only landmarks. It fills the same struct; nothing above it changes |

⚠ A source's ONLY job is to fill `HandObservation` honestly, including leaving
fields absent. A source that invents a value it does not have would put a
plausible number where a measured one belongs -- see `contract.py`.
"""
