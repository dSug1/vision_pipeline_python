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
import time

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
ATTEMPTS = 8


def wake(root=ROOT, attempts=ATTEMPTS):
    probe = os.path.join(root, ".wake")
    for i in range(1, attempts + 1):
        try:
            os.makedirs(probe, exist_ok=True)
            f = os.path.join(probe, "w")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(f)
            os.rmdir(probe)
            print(f"[wake] drive awake and writable (attempt {i})")
            return True
        except OSError as e:
            print(f"[wake] attempt {i}/{attempts} failed: {e.__class__.__name__} {e}")
            time.sleep(1.5)
    print("[wake] FAILED -- the drive did not come back. Do NOT fall back to --local;")
    print("[wake] recordings belong on E:. Check the cable/enclosure and retry.")
    return False


if __name__ == "__main__":
    sys.exit(0 if wake() else 1)
