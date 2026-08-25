# POST-MORTEM — the 4.1 identity migration, built, patched five times, REVERTED

> **Status: REVERTED 2026-08-22** by owner instruction (*"it is still full of bugs.
> Revert."*). Nothing was deleted. One flag turns it all back on:
> `HandsTriggeredActions.TRACK_OWNERSHIP` (and its mirror in `LiveSnapDebug.py`).
>
> ⭐ **Read this before attempting it again.** Every defect below is real, was
> measured, and will recur if the same approach is repeated.

---

## 1. What was being fixed, and why it was worth trying

Cube ownership keyed on MediaPipe's **handedness label**, which is not an
identity — it flips. A flip orphaned a held cube. Measured: **113 of 205 spurious
releases** (`analysis/d2_bridge_ab.py`), larger than true dropouts (83).

The fix was to key ownership on DR-1's **stable track id** instead. That premise
is still believed correct. ⚠ **The premise is not what failed.**

---

## 2. What was built (all of it still present, behind the flag)

| piece | where |
|---|---|
| stable `track_id` on DR-1 tracks | `hand_identity.py` (`HandTrack.track_id`, `last_track_ids`) |
| `hand_tracks` wire packet | `Server.py`, `VisionPipeline.py`, `PythonApp_Main.py` |
| ownership keyed on the id | `HandsTriggeredActions._owner_key` + `CubeWindow` |
| degraded drive + release window | `_cube_for_hand`, `OWNER_DEGRADE_MS = 250` |
| per-hand state following the track | `Resources/hand_tracks.py` + `_bind_track_state` |

⭐ **KEEP REGARDLESS — these are independent and good, and are NOT reverted:**
`palm_depth.py` (4.1's depth estimator, drives nothing), the **DR-1 frame-edge
fix**, **production recording** (`VISION_RECORD=1`), the `hand_tracks` packet
itself (sent, simply unused), and every harness in `analysis/`.

---

## 3. ⛔ THE FIVE DEFECTS, in the order the owner hit them

Each was found **live, in seconds**, after the automated suite was green.

### 3.1 The stranded cube
*"the cube was indicated as grabbed but did not move at all and the free hand
could not grab it again."*

Release read `cube_owned_by(_owner_key(hand))`. When a track ENDS the key degrades
to the LABEL, so an int-keyed cube was never found; ids are never reused, so it
stayed owned by a dead id forever — drawn as grabbed, driven by nothing, excluded
from `unowned_cube_names()`.
⚠ **The fallback fired exactly when the id was missing — which is exactly when
release needed to find the cube owned by that absent id.** It was described as a
safety net; it was the defect.

### 3.2 A second cause of the same strand
DR-1 was **skipped entirely** whenever any palm landmark left the frame
(`_normalized_to_pixel_coordinates` → `None` → `palm_centroid` → `None`), so the
wire sent `trackId = -1` for BOTH slots while landmarks kept flowing.
⭐ **Root-fixed and KEPT** (plain multiplication, matching the debug tool). It also
fixed landmarks teleporting to `(0,0)`.

### 3.3 The strand again at 300 ms and 450 ms
Production had the `OWNER_ABSENT_RELEASE_MS` net; **the debug tool did not**. A
divergence created *while fixing a divergence*.
⚠ Deeper cause: the governing map tracks a **slot**, and a slot can be refilled by
a **different** hand — so `holds_track` was True and release never fired. **A
longer coast makes this worse, not better.**

### 3.4 The forbidden back-of-hand grab
*"the back occludes the palm: the cube drops but ... the back hand can grab the
dropped cube (which should be prohibited)."* **Measured: 4 snaps that
`GAME_RULES` rule 3 forbids.**

Cause: 4.1 moved **ownership** to the track and left **eight** other per-hand
things keyed by slot — `_last_known_thumb_outward`, `_thumb_outward_snap_allowed`,
`_palm_facing_trackers`, `_hand_state_trackers`, `_hand_orientation_filters`,
`_hand_rotation_states`, `_resync_blend_left`, `_last_hand_reliability_alpha`.
On a relabel a hand **inherited the other hand's history**.

### 3.5 ⛔⛔ The worst one — introduced BY the fix for 3.4
*"the hand exited as palm and came back as back and still could grab the cube.
Then all the cubes frozed."*

To make `verify_d1_wiring` pass, new tracks were **seeded from the slot's current
state**. That
1. handed a **returning hand** (a new track) the previous hand's snap permission —
   re-creating 3.4 exactly; and
2. copied the `HandStateTracker` **by reference**, so two tracks mutated **one**
   tracker → `holds_track` answered for the wrong hand → **every cube froze**.

⚠⚠ **I fixed a test failure by re-introducing the bug the work exists to remove.
The suite went green and the real property broke.**

---

## 4. ⭐⭐ WHY IT FAILED — the part that matters for the next attempt

**Not the premise. Not any single bug. The method.**

1. **Every guard was written after the fact, and each was narrower than the bug.**
   Sixteen suites passed while the tool crashed on the first real frame sequence,
   because none drove `update_hands` with ids published *and* a hand vanishing.
2. **Instrumentation reported success while behaviour regressed — twice.** A
   recorder key collision silently kept only one arm; another silently skipped the
   session recorded to test the fix.
3. **Green numbers from empty sessions were read as evidence.** Three sessions
   produced clean results with ~0 cubes held or 0 two-hand frames.
4. ⭐ **The final session measured CLEAN — 0 rule-3 violations across 21 relabels,
   no frozen cube, 43 snaps, 1255 two-hand frames — and the owner still saw bugs.**
   **That is the decisive fact.** The instruments were not capturing what actually
   breaks, so no amount of further patching could be trusted.
5. **Half a migration is worse than none.** Ownership on the track + everything
   else on the slot produced a seam, and `_owner_hand_of_cube`,
   `_owner_absent_since` and the degrade window were all bridges over that seam —
   compensating machinery that was itself the symptom.

---

## 5. ⭐ IF IT IS ATTEMPTED AGAIN — do these differently

1. **Migrate ALL per-hand state in one step, or none.** The eight fields in §3.4
   plus ownership. A partial migration re-creates the seam.
2. ⛔ **Never seed a new track from a slot.** A returning hand is a NEW hand.
   Carry CONFIG (a bridge window) if you must; never STATE, and never an object
   by reference.
3. **Write the SYSTEM-level property test FIRST**, before any live session:
   *no cube may be owned and undriveable; no state may cross a relabel; a
   returning hand inherits nothing.* `analysis/verify_state_follows_hand.py` and
   `verify_no_frozen_cube.py` are that test — they exist now, use them from the
   start.
4. **Check session COVERAGE before reading any result** (cubes held, two-hand
   frames, relabel events). A green number from an empty session is worse than a
   red one.
5. ⚠ **Fix U6 first, or accept doing everything twice.** Production and the debug
   tool each re-implement the input path and each carry a COPY of
   `HandOrientationFilter`/`_predictive_filter_step`. Three of the five defects
   above were divergences. **This migration is a bad idea until there is one
   pipeline.**
6. **Ship it behind the flag and A/B it live**, rather than replacing the working
   path outright.

---

## 6. What the revert costs

**T3 comes back**: a held cube is orphaned when the handedness label flips,
measured at 113 of 205 spurious releases.

⭐ **That is a DROP — the operator re-grabs and continues.** The migration traded
it for **freezes** (un-grabbable cubes) and **rule violations**. Reverting is the
better failure, and it is reversible: one flag.
