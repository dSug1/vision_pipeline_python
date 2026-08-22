"""Golden vectors for `Resources/hand_tracks.py` (finishing 4.1's migration).

The property that matters, stated once: **per-hand state must follow the physical
HAND, not the handedness slot.** The measured failure it prevents is 4 snaps by a
thumb-outward hand that GAME_RULES rule 3 forbids, caused by a hand inheriting
the other hand's armed snap permission when the labels swapped.

Dependency-free -- no camera, no recordings, no pygame. This is the artifact a
port reproduces (U3 discipline).

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_hand_tracks.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import hand_tracks as HT  # noqa: E402

FAILURES = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:64s} got {got!r}")
    if not ok:
        FAILURES.append(name)


class Box:
    """Stand-in for a tool's per-hand bundle; only identity matters here."""
    _n = 0

    def __init__(self):
        Box._n += 1
        self.id = Box._n
        self.armed = False


def main():
    print("=" * 80)
    print("hand_tracks.TrackRegistry -- state follows the HAND, not the slot")
    print("=" * 80)

    print("\n--- 1. a published id resolves to itself ---")
    r = HT.TrackRegistry(Box)
    check("Left->3, Right->8", r.resolve({"Left": 3, "Right": 8}, 0.0), {"Left": 3, "Right": 8})

    print("\n--- 2. !! THE DEFECT: state must survive a RELABEL ---")
    print("      hand 3 arms its snap permission while in the Left slot,")
    print("      then the labels swap. It must keep its OWN permission,")
    print("      and the other hand must NOT inherit it.")
    r = HT.TrackRegistry(Box)
    r.resolve({"Left": 3, "Right": 8}, 0.0)
    r.state(3).armed = True
    a_before = r.state(3).id
    r.resolve({"Left": 8, "Right": 3}, 40.0)          # labels swapped
    check("track 3 keeps the SAME state object", r.state(3).id, a_before)
    check("track 3 is still armed", r.state(3).armed, True)
    check("!! track 8 did NOT inherit the permission", r.state(8).armed, False)

    print("\n--- 3. a slot with no id remembers its track, briefly ---")
    r = HT.TrackRegistry(Box, slot_memory_ms=250.0)
    r.resolve({"Left": 5, "Right": -1}, 0.0)
    check("inside the window the slot still points at 5",
          r.resolve({"Left": -1, "Right": -1}, 200.0)["Left"], 5)
    check("past the window it gives up (NO_TRACK)",
          r.resolve({"Left": -1, "Right": -1}, 600.0)["Left"], HT.NO_TRACK)
    check("the remembered frames were counted", r.remembered_frames >= 1, True)

    print("\n--- 4. !! it must NOT fall back to the slot ---")
    print("      falling back to 'Left' is exactly the bug being fixed")
    check("no state for NO_TRACK", r.state(HT.NO_TRACK), None)
    check("no state for None", r.state(None), None)

    print("\n--- 5. asking about an owner must not resurrect it ---")
    r = HT.TrackRegistry(Box)
    r.resolve({"Left": 1}, 0.0)
    r.state(1)
    check("known() is True for a live track", r.known(1), True)
    check("known() is False for one never seen", r.known(99), False)
    check("...and asking did not create it", r.known(99), False)

    print("\n--- 6. eviction after the TTL ---")
    r = HT.TrackRegistry(Box, track_ttl_ms=1000.0)
    r.resolve({"Left": 4}, 0.0)
    r.state(4)
    check("not evicted before the TTL", r.evict(500.0), [])
    check("evicted after it", r.evict(1500.0), [4])
    check("state is gone", r.known(4), False)

    print("\n--- 7. a returning hand finds its own state, not a cold start ---")
    r = HT.TrackRegistry(Box, track_ttl_ms=1500.0)
    r.resolve({"Left": 7}, 0.0)
    r.state(7).armed = True
    same = r.state(7).id
    r.resolve({"Left": -1}, 800.0)      # gone for a beat
    r.evict(800.0)
    r.resolve({"Left": 7}, 900.0)       # back
    check("same state object", r.state(7).id, same)
    check("its own flag survived", r.state(7).armed, True)

    print("\n--- 8. determinism / no clock is read ---")
    check("resolve takes an injected now_ms", HT.TrackRegistry.resolve.__code__.co_argcount, 3)
    check("evict takes an injected now_ms", HT.TrackRegistry.evict.__code__.co_argcount, 2)

    print("\n" + "=" * 80)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): " + ", ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED -- state follows the hand.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
