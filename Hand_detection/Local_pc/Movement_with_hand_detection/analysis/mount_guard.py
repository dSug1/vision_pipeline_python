# -*- coding: utf-8 -*-
"""⛔ "THIS SUITE CANNOT SPEAK ABOUT THAT CAMERA MOUNT" — said out loud, once.

⭐ Some suites here are not testing a mechanism, they are testing a CONVENTION or
replaying a RECORDED BASELINE. Both are properties of the camera mounting the
corpus was captured with, so running them under a different mount produces a
`FAIL` that is not a defect — the fixture is simply mute on that configuration.

⛔ THAT MATTERS MORE HERE THAN IT WOULD ELSEWHERE. `METHOD.md`'s most expensive
lesson is that **the instrument is a suspect, always** — four harnesses once
reported CLEAN on takes the owner had just watched fail. A harness that reports
FAIL on a build that is CORRECT is the same defect wearing the opposite sign, and
it is worse in one way: it trains the reader to discount red.

⚠ So this SKIPS LOUDLY and exits 0. Exiting 1 would cry wolf; skipping silently
would let a real regression hide behind a mount setting. The banner names the
mount, the mounts the suite is valid for, and why.

⭐ It is the same shape as `T6`'s method rule — *a corpus whose motion does not
match the product's cannot validate an estimator for the product* — applied to
the camera's PLACEMENT instead of the hand's motion. There is no head-worn corpus
and no head-worn baseline; when there is one, these fixtures get a second
expectation set rather than a loosened one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import camera_mount as CM                      # noqa: E402


def require_mount(suite, allowed, reason):
    """Skip `suite` (exit 0, loudly) unless the live mount is in `allowed`."""
    if CM.MOUNT in allowed:
        return
    bar = "=" * 78
    print(bar)
    print("SKIPPED -- %s cannot validate CAMERA_MOUNT=%s" % (suite, CM.MOUNT))
    print(bar)
    print("  valid for : %s" % ", ".join(allowed))
    print("  because   : %s" % reason)
    print("")
    print("  This is NOT a pass and NOT a failure -- the fixture is mute on this")
    print("  configuration. Re-run with CAMERA_MOUNT unset (or =legacy) to get a")
    print("  real verdict. See Resources/camera_mount.py.")
    print(bar)
    sys.exit(0)


# ⛔⛔ `CONVENTION_BOUND` WAS REMOVED THE DAY IT WAS WRITTEN, AND THE REASON IS THE
# POINT OF THIS FILE. It guarded `verify_geometric_chirality` and `verify_handinput`
# on the theory that their fixtures were bound to the mirrored chirality convention.
# They were not. Those suites were reporting a REAL DEFECT -- a chirality bit that
# had been made mount-dependent when it is not -- and guarding them SILENCED it. The
# owner then found it by eye in one live run.
#
# ⭐ So the bar for adding an entry here is now explicit: a suite may be guarded
# only once its claim has been re-derived INDEPENDENTLY and shown to be about a
# convention rather than a defect. Suspecting the instrument is not the same as
# dismissing it, and this file makes dismissing it cheap.

BASELINE_BOUND = (
    (CM.LEGACY, CM.HEAD_WORN),
    "it replays cube positions RECORDED under the shipped `grab / ratio` depth "
    "mapping; `facing_user` reverses that mapping by design, so divergence here is "
    "the change working, not the pipeline breaking",
)
