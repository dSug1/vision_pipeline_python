"""Wake the external capture drive, and RETRY -- one copy, both recorders (N6).

⚠⚠ THE DEFECT THIS CLOSES, and it cost a real take (2026-08-25). Production's
recorder tried to create its session directory ONCE, got WinError 21 "The device
is not ready", printed `cannot record, continuing WITHOUT it` and set
`VISION_RECORD=0` so it would not retry. The owner ran a full live acceptance take
for `F1`'s rule-3 removal and it recorded NOTHING; the take's only evidence was
what they saw on screen.

⛔ THE OPERATOR CANNOT PREVENT THIS BY WAKING THE DRIVE FIRST. E: goes back to
sleep on its own (USB selective suspend), so waking it before an EARLIER take is
no help -- which is exactly what happened: the drive was woken, the debug take ran
and recorded fine, and by the time production started it had slept again.

⭐ THE FIX IS THE ONE `tools/wake_e_drive.py` ALREADY KNEW: the access itself is
what wakes the drive, so retry. Attempt 1 fails, attempt 2 succeeds (measured
2026-08-22, and reproduced twice on 2026-08-25). This module is that logic, moved
somewhere both recorders and the tool can import it instead of only the tool
having it -- `N6`: shared modules are imported, never copied.

⚠ This works around SLEEP only. It does NOT address the "Full Repair Needed" flag
on the volume, which is separate and unresolved (`N4`).
"""
import os
import time

ATTEMPTS = 8
DELAY_S = 1.5


def ensure_awake(root, attempts=ATTEMPTS, delay_s=DELAY_S, log=print):
    """True once `root` is writable, retrying past a sleeping drive.

    Writes and removes a `.wake` probe rather than trusting `os.path.exists`: a
    sleeping drive can report a path as present and still refuse to open a file
    in it, and the recorders need WRITABILITY, not presence.

    ⚠ Returns False rather than raising. A failure to record must never stop the
    game from running -- but the CALLER must then say so loudly, because a take
    the operator believes is recording and is not is worse than a refused one.
    """
    probe = os.path.join(root, ".wake")
    for i in range(1, attempts + 1):
        try:
            os.makedirs(probe, exist_ok=True)
            f = os.path.join(probe, "w")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(f)
            os.rmdir(probe)
            if i > 1:
                log(f"[wake] drive awake and writable (attempt {i})")
            return True
        except OSError as e:
            log(f"[wake] attempt {i}/{attempts} failed: {e.__class__.__name__} {e}")
            if i < attempts:
                time.sleep(delay_s)
    log("[wake] FAILED -- the drive did not come back. Do NOT fall back to --local;")
    log("[wake] recordings belong on E:. Check the cable/enclosure and retry.")
    return False
