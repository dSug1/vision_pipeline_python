"""Golden vectors for the AUDIT FIXES of 2026-08-25.

    .venv/Scripts/python.exe analysis/verify_hardening.py

⭐ WHY A SUITE FOR DEFENSIVE CODE, WHICH BY DEFINITION NEVER RUNS IN A GOOD
SESSION. That is exactly the reason: a guard nothing exercises is a guard nobody
notices has stopped working. Every check below is a path the pipeline is supposed
to *never* take -- a tag that escapes the capture root, a camera that stalls, a
socket asked to listen off-loopback, a wire value that would size an allocation.
The only way any of them is known to still work on the day it matters is if
something exercises them on the days it does not.

⚠ These are BEHAVIOUR checks, not style checks. Each one names the defect it
closes, so a future reader can tell whether deleting it is safe.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(os.path.dirname(BASE),
                                "Python_Server_MediaPipe_vision_pipeline", "Resources"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import session_paths                      # noqa: E402
import capture_policy                                    # noqa: E402

FAILURES = []
CHECKS = [0]


def check(name, ok, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append("%s  %s" % (name, detail))
        print("  FAIL  %s  %s" % (name, detail))
    return ok


# ── §1 session tags cannot become paths ─────────────────────────────────────
def section_tags():
    print("\n§1  TAGS -- a session name cannot escape the capture root")
    cases = [
        ("prod_tau20", "prod_tau20"),
        ("lag-tau-ab", "lag-tau-ab"),
        (r"..\..\Windows\Temp", "Windows_Temp"),
        ("../../etc/passwd", "etc_passwd"),
        ("../..", "session"),
        ("", "session"),
        (None, "session"),
        ("a:b*c?d", "a_b_c_d"),
        ("with spaces", "with_spaces"),
        ("   ", "session"),
        ("/", "session"),
        ("x" * 200, "x" * session_paths.MAX_TAG_LEN),
    ]
    for raw, want in cases:
        got = session_paths.safe_tag(raw)
        check("safe_tag(%r)" % (raw if not isinstance(raw, str) or len(raw) < 40
                                else raw[:20] + "..."),
              got == want, "got %r want %r" % (got, want))

    # ⭐ The property that actually matters, stated as a property rather than as a
    # list of cases: whatever the tag, joining it under a root stays under it.
    root = os.path.join("C:" + os.sep, "capture", "sessions")
    for raw, _ in cases:
        joined = os.path.abspath(os.path.join(root, "2026-01-01_000000_" +
                                              session_paths.safe_tag(raw)))
        check("stays under root: %r" % (raw if not isinstance(raw, str) or len(raw) < 40
                                        else raw[:20] + "..."),
              joined.startswith(os.path.abspath(root) + os.sep), joined)

    safe, changed = session_paths.check_tag("clean_name")
    check("check_tag reports unchanged", safe == "clean_name" and changed is False)
    safe, changed = session_paths.check_tag("../evil")
    check("check_tag reports changed", changed is True and safe == "evil")


# ── §2 the camera may stall without ending the session ──────────────────────
class _FakeCap:
    """Fails `fail_first` times, then yields frames. ⚠ Counts calls, because the
    defect being guarded is 'gives up too early', and only the call count can
    tell 'recovered' from 'never retried'."""

    def __init__(self, fail_first, then_forever=False):
        self.fail_first = fail_first
        self.then_forever = then_forever
        self.calls = 0

    def read(self):
        self.calls += 1
        if self.then_forever or self.calls <= self.fail_first:
            return False, None
        return True, "FRAME"


def section_capture():
    print("\n§2  CAPTURE -- a transient stall must not end the run")
    noop = lambda _s: None                                   # noqa: E731

    cap = _FakeCap(fail_first=0)
    ok, frame, retries = capture_policy.read_frame(cap, sleep=noop)
    check("clean read", ok and frame == "FRAME" and retries == 0,
          "ok=%s retries=%s" % (ok, retries))
    check("clean read costs exactly one call", cap.calls == 1, str(cap.calls))

    cap = _FakeCap(fail_first=5)
    ok, frame, retries = capture_policy.read_frame(cap, sleep=noop)
    check("recovers after 5 failures", ok and frame == "FRAME" and retries == 5,
          "ok=%s retries=%s" % (ok, retries))

    # The boundary: one short of the cap must still recover.
    cap = _FakeCap(fail_first=capture_policy.MAX_CONSECUTIVE_READ_FAILURES - 1)
    ok, _, retries = capture_policy.read_frame(cap, sleep=noop)
    check("recovers at the last allowed attempt", ok, "retries=%s" % retries)

    # ⛔ And it must still GIVE UP: a tool that hangs on a dead camera is worse
    # than one that exits.
    cap = _FakeCap(fail_first=0, then_forever=True)
    ok, frame, retries = capture_policy.read_frame(cap, sleep=noop)
    check("gives up on a dead camera", (not ok) and frame is None, "ok=%s" % ok)
    check("gives up after exactly the cap",
          cap.calls == capture_policy.MAX_CONSECUTIVE_READ_FAILURES, str(cap.calls))
    check("give-up message names the cause",
          "Camera" in capture_policy.give_up_message("X"))


# ── §3 the socket refuses to leave the machine ──────────────────────────────
def section_loopback():
    print("\n§3  SOCKET -- off-loopback is refused, not merely discouraged")
    import Server                                            # noqa: E402

    for host in ("127.0.0.1", "::1", "localhost"):
        try:
            Server._refuse_non_loopback(host, False, "test")
            check("allows loopback %s" % host, True)
        except SystemExit as e:
            check("allows loopback %s" % host, False, str(e))

    for host in ("0.0.0.0", "192.168.1.20", "example.com"):
        try:
            Server._refuse_non_loopback(host, False, "test")
            check("refuses %s" % host, False, "it did NOT refuse")
        except SystemExit as e:
            check("refuses %s" % host, True)
            check("refusal explains why (%s)" % host,
                  "landmarks" in str(e) and "--allow-remote" in str(e))

    # ⚠ The override must still work, or a future two-machine rig has no route
    # that is not "edit the guard out", which is how guards die.
    try:
        Server._refuse_non_loopback("192.168.1.20", True, "test")
        check("--allow-remote overrides", True)
    except SystemExit as e:
        check("--allow-remote overrides", False, str(e))


# ── §4 the wire cannot size an allocation ───────────────────────────────────
def section_meta():
    print("\n§4  META -- a wire value that sizes a window is bounded")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import PythonApp_Main as PM                              # noqa: E402
    from Resources import HandsTriggeredActions as H         # noqa: E402

    before = H.cube_window.window_size

    # Implausible values must be REFUSED, leaving the window as it was.
    for bad in ([100000, 100000], [1e9, 1e9], [9000, 480], [640, 20000]):
        PM.receive_float_array("meta", bad)
        check("refuses meta %s" % (bad,), H.cube_window.window_size == before,
              "window became %s" % (H.cube_window.window_size,))

    # Already-rejected shapes still rejected (this behaviour predates the audit).
    for bad in ([0, 480], [-1, -1], [640]):
        PM.receive_float_array("meta", bad)
        check("refuses meta %s" % (bad,), H.cube_window.window_size == before)

    # ⭐ And a REAL resolution must still be accepted -- a guard that refuses
    # everything would pass every check above and break the pipeline.
    PM.receive_float_array("meta", [800, 600])
    check("accepts a real resolution", H.cube_window.window_size == (800, 600),
          str(H.cube_window.window_size))
    PM.receive_float_array("meta", list(before))


def main():
    print("verify_hardening -- the audit fixes of 2026-08-25")
    print("=" * 62)
    section_tags()
    section_capture()
    section_loopback()
    section_meta()
    print("\n" + "=" * 62)
    if FAILURES:
        print("FAILED: %d of %d checks" % (len(FAILURES), CHECKS[0]))
        for f in FAILURES:
            print("   ", f)
        return 1
    print("ALL %d CHECKS PASS" % CHECKS[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
