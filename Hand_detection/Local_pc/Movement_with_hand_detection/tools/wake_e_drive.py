"""Wake the external capture drive before a take.

E: (Samsung_T5) reports HealthStatus=Warning / OperationalStatus="Full Repair
Needed", and independently of that its FIRST access after an idle gap fails with
WinError 21 "The device is not ready" -- USB selective suspend. The access itself
is what wakes it, so the fix is simply to retry: attempt 1 fails, attempt 2
succeeds (measured 2026-08-22).

Recorders preflight the capture root and REFUSE to record if it is not writable
(by design -- never lose an operator's take at save time). That preflight would
otherwise fail on a merely sleeping drive, so run this first.

⚠ This works around SLEEP only. It does NOT address the "Full Repair Needed"
flag, which is a separate, unresolved condition on the volume holding the whole
recording corpus.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import capture_drive          # noqa: E402

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
ATTEMPTS = capture_drive.ATTEMPTS


def wake(root=ROOT, attempts=ATTEMPTS):
    """⚠ THE RETRY ITSELF NOW LIVES IN `Resources/capture_drive.py` (N6).

    It moved there on 2026-08-25 because only this TOOL had it: production's
    recorder tried once, gave up, and a full live acceptance take recorded
    nothing. Both recorders now call the same function, so running this by hand
    is a convenience rather than a precondition.
    """
    ok = capture_drive.ensure_awake(root, attempts=attempts)
    if ok:
        print("[wake] drive awake and writable")
    return ok


if __name__ == "__main__":
    sys.exit(0 if wake() else 1)
