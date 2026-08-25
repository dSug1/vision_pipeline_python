"""Golden vectors for `Resources/capture_drive.py` -- the drive wake/retry.

⚠⚠ WHY THIS SUITE EXISTS. On 2026-08-25 the owner ran a full live acceptance take
for `F1`'s rule-3 removal and it recorded NOTHING: production's recorder tried the
capture root ONCE, got WinError 21 "The device is not ready" from a sleeping E:,
printed a one-line note and disabled itself. The take's only evidence was what the
owner saw on screen.

⭐ The retry that fixes it existed the whole time -- in `tools/wake_e_drive.py`,
where only a human running it by hand could benefit. The fix was to MOVE it
somewhere both recorders import (N6). This suite pins the behaviour that move
depends on, because the real failure cannot be reproduced on demand: you cannot
ask a USB enclosure to fall asleep.

    .venv/Scripts/python.exe analysis/verify_capture_drive.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import capture_drive                      # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

_fails = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<62} got {got!r}")
    if not ok:
        _fails.append((name, got, want))


def main():
    print("=" * 82)
    print("CAPTURE DRIVE -- wake and retry")
    print("=" * 82)

    root = tempfile.mkdtemp(prefix="capdrive_")
    quiet = lambda *_a, **_k: None                        # noqa: E731
    try:
        # 1. A writable root succeeds on the first attempt and sleeps not at all.
        check("writable root -> True", capture_drive.ensure_awake(root, log=quiet), True)
        check("the probe is cleaned up",
              os.path.exists(os.path.join(root, ".wake")), False)

        # 2. ⭐ THE REAL CASE: fails once, then succeeds -- exactly what E: does.
        real = os.makedirs
        state = {"n": 0}

        def flaky(path, exist_ok=False):
            state["n"] += 1
            if state["n"] <= 1:
                raise PermissionError(21, "The device is not ready")
            return real(path, exist_ok=exist_ok)

        os.makedirs = flaky
        try:
            got = capture_drive.ensure_awake(root, delay_s=0.0, log=quiet)
        finally:
            os.makedirs = real
        check("fails once then succeeds -> True", got, True)
        check("...and it took exactly 2 attempts", state["n"], 2)

        # 3. A permanently dead drive gives up and says so, rather than hanging or
        #    raising -- a failure to record must never stop the game.
        def dead(path, exist_ok=False):
            raise OSError(21, "The device is not ready")

        os.makedirs = dead
        try:
            got = capture_drive.ensure_awake(root, attempts=3, delay_s=0.0, log=quiet)
        finally:
            os.makedirs = real
        check("permanently dead -> False, no exception", got, False)

        # 4. ⛔ PRESENCE IS NOT WRITABILITY. A sleeping drive can report the path as
        #    existing and still refuse to open a file in it, so the probe WRITES.
        import builtins

        def no_write(*a, **k):
            raise OSError(21, "The device is not ready")

        saved = builtins.open
        builtins.open = no_write
        try:
            got = capture_drive.ensure_awake(root, attempts=2, delay_s=0.0, log=quiet)
        finally:
            builtins.open = saved
        check("path exists but cannot be written -> False", got, False)

        # 5. The tool and the recorders share ONE definition (N6).
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        import wake_e_drive                                # noqa: E402
        check("tools/wake_e_drive delegates to this module",
              wake_e_drive.ATTEMPTS == capture_drive.ATTEMPTS, True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("=" * 82)
    if _fails:
        print(f"{len(_fails)} CHECK(S) FAILED")
        return 1
    print("ALL CHECKS PASSED -- a sleeping drive is retried, a dead one is refused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
