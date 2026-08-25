"""What to do when the webcam misses a frame -- ONE policy, both capture loops.

⚠⚠ THE DEFECT THIS CLOSES (audit, 2026-08-25). Both loops read:

    ret, frame = cap.read()
    if not ret:
        break

so **a single failed read ends the session.** `cap.read()` returns False for
reasons that are not "the camera is gone": a USB hiccup, a mode change while the
webcam re-negotiates exposure, another process briefly touching the device. The
operator sees the tool close mid-take with no message, and on a RECORDED take the
whole session ends there.

⭐ It also matters more here than it looks, because of something already measured:
the frame rate is **camera-bound, not compute-bound** (the inter-frame gap is
identical with and without a hand in view, 64.1 vs 64.0 ms). The capture device
IS the pipeline's clock, so its transients are the pipeline's transients.

⛔ THE POLICY IS DELIBERATELY NOT "RETRY FOREVER". A camera that has genuinely
gone away must still end the run, and promptly -- a tool that hangs on a dead
device is worse than one that exits. **30 attempts at 10 ms is ~0.3 s**: long
enough to ride out any transient anyone has observed here, short enough that a
real disconnection still closes the window while the operator is still looking at
it.

⚠ N6 -- this lives in ONE module because both loops need it. It carries no cv2
import (the capture object is passed in), so importing it costs the debug tool
nothing; that tool already puts this directory on `sys.path` for `hand_identity`.
"""
import time

MAX_CONSECUTIVE_READ_FAILURES = 30
RETRY_SLEEP_S = 0.01


def read_frame(cap, sleep=time.sleep):
    """`(ok, frame, retries)` -- one frame, tolerating a transient stall.

    `retries` is 0 on the normal path, so a caller can report a recovery without
    reporting silence. ⚠ `sleep` is injectable so a test does not have to wait
    0.3 s to prove the give-up path works.
    """
    for attempt in range(MAX_CONSECUTIVE_READ_FAILURES):
        ok, frame = cap.read()
        if ok:
            return True, frame, attempt
        sleep(RETRY_SLEEP_S)
    return False, None, MAX_CONSECUTIVE_READ_FAILURES


def give_up_message(where):
    return (f"[{where}] Camera stopped delivering frames "
            f"({MAX_CONSECUTIVE_READ_FAILURES} consecutive failed reads over "
            f"~{MAX_CONSECUTIVE_READ_FAILURES * RETRY_SLEEP_S:.1f}s). "
            f"Is the device still connected, or has another program taken it?")
