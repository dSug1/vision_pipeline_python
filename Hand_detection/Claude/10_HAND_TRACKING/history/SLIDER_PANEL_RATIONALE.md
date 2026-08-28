# SLIDER PANEL — the rationale, distilled out of the code 2026-08-28

> **history · why each debug slider has the range, start value and unit it has**
> **SOURCE** · `LiveSnapDebug.py`'s `SLIDERS` table, extracted VERBATIM before the
> table was reduced to one line per control

⭐ **WHY THIS FILE EXISTS.** Owner, 2026-08-28: *"for each filter, remove all the
text and simply put one line what the filter does. This will help me remember what
is the purpose of each of the filter."* The panel is a working surface and the
comments had grown to 195 lines for 9 controls, which is the opposite of a reminder.

⛔ **BUT THE TEXT WAS NOT DELETED, AND THAT IS THE BINDING RULE** (`README.md` §2:
*nothing is ever rewritten to save space — distil into a new file instead, and cite
what you distilled*). Almost every paragraph below records a MEASUREMENT or a
mistake that cost a live session:

* `GRAB radius %` is 0..300, not 0..100, because at a 100 max the owner could not
  get **back** to a working value once 33% proved unusable — a slider that cannot
  reach the previous behaviour is a trap, not a control.
* `SMOOTH ms`'s integer **is** τ in ms because an earlier version made it an INDEX
  into a ladder, so the panel read "3" while applying 20 ms — and the take was
  reported as *"3 ms is good"*.
* `FADE ms moving` can reach 0 on purpose: 0 ms **is** the teleport the acceptance
  gate rejected at 118.4 px in one frame.
* `TRIM gain %` started at 0 rather than 100 because starting it high made the
  debug tool run the trim while production did not — the exact divergence `U6`
  keeps `parity_replay` for.

⚠ **THE 4500 ms `STEADY ms` SLIDER IS NOT HERE, AND THAT IS THE ANSWER TO WHERE IT
WENT.** It was stripped in `6c3bd29` when the FREEZE replaced it: *"damping is not
stillness — even at 4500 ms of extra tau the blend factor is 0.015, so the cube
still creeps"*. Its replacement is `RELEASE deg/s` + `FREEZE frames`, where the
factor below the threshold is exactly **0.0**. See
[`../REJECTED.md`](../REJECTED.md).

---

<!-- Extracted verbatim; not a summary. -->

```python
SLIDERS = (
    # ⛔ 0 = NO smoothing: the cube goes exactly where Horn says, every frame.
    ("SMOOTH ms", SLERP_TAU_MAX_MS, 20, lambda n: float(n)),
    # ⛔ 0 = the fingertip filter OFF, and off is BIT-EXACT (the input value is
    # returned unchanged), so this position is genuinely today-without-F1's-filter
    # rather than an approximation of it.
    # ⛔⛔ PARKED 2026-08-26, owner: "jitter and speed ... removed at their
    # minimums ... don't delete the code, just park those three". Both are now
    # fixed at ZERO -- the 1-euro filter's own off state, which is BIT-EXACT
    # passthrough rather than an approximation. Reason: the census puts the tip
    # noise floor at 1.5 mm median, so there was little for the filter to remove,
    # and the owner found its lag "unbearable" at any useful setting.
    # ⭐ To revisit, put these two lines back in the tuple and restore the
    # 5-value unpack in `_read_sliders`; nothing else was removed.
    #   ("JITTER tau ms", JITTER_TAU_MAX_MS, 133, lambda n: float(n)),
    #   ("SPEED b x1000", 200, 20, lambda n: n / 1000.0),
    # ⚠ DRIVES ONLY THE ARM THAT HAS THE TRIM ON. In the three-window rig panels
    # 1 and 2 pin their gain to 0.0 explicitly, so sweeping this moves panel 3 and
    # leaves the controls alone -- which is what keeps the rig one-variable.
    #
    # ⛔⛔ IT STARTS AT 0, MATCHING PRODUCTION, AND `--f1-rig` RAISES IT.
    # Starting it at 100 made the ordinary single-arm debug tool run the trim
    # while production ran without it -- i.e. the two tools would differ in normal
    # use, which is the exact divergence `U6` keeps `parity_replay` around to
    # prevent. The rig is where the trim is meant to be ON, so the rig turns it on.
    #   ("TRIM gain %", TRIM_GAIN_MAX_PCT, 0, lambda n: n / 100.0),   RETIRED 2026-08-28
    # ⭐⭐ THE GRAB RADIUS, owner 2026-08-26: "slider x the narrower axis of the
    # cube's projected footprint, slider between 0 and 1". Shown as a PERCENT
    # because the panel's rule is that the displayed integer IS the applied value
    # in its stated unit, and a trackbar cannot show 0.50.
    # ⚠ 0% means NOTHING CAN BE GRABBED -- deliberately reachable, because a
    # slider whose useful range is hidden behind a floor teaches the wrong thing
    # about where the limit is.
    # ⭐ Starts at the shipped 50%. Measured on 50 real grabs: 50% -> 42% of them
    # still occur, 60% -> 54%, 75% -> 72%, 100% -> 80%.
    # ⚠ The start value here is a PLACEHOLDER, exactly as "SMOOTH ms"'s is: this
    # table is built before `hand_state` is imported, so the real value is pushed
    # onto the trackbar in `_create_sliders`. A literal that drifts from the
    # constant would show the operator a number the pipeline is not using.
    # ⚠ RANGE IS 0..300, not 0..100. At 100 max the owner could not get BACK to a
    # working value once 33% turned out to be unusable -- a slider that cannot
    # reach the previous behaviour is a trap, not a control.
    ("GRAB radius %", 300, 100, lambda n: n / 100.0),
    # ⭐⭐ A1's fade budget, owner 2026-08-26: "make a slider for these xx ms,
    # between 0 and 1000 ms". Milliseconds OF HAND MOVEMENT, not of wall clock —
    # a hand held still does not spend it.
    # ⚠ 0 ms is the TELEPORT, and it is reachable on purpose: it is the design the
    # acceptance gate rejected at 118.4 px in one frame, so the slider's own left
    # end shows what that felt like.
    ("FADE ms moving", 1000, 300, lambda n: float(n)),
    # ⭐⭐ How much of the HAND's own step the cube may spend closing the gap, per
    # frame. Owner 2026-08-26: "a multiple of the hand movement cap, with a slider
    # between 0.05 and 1". Shown as a percent so the displayed integer IS the
    # applied value, the rule every slider on this panel follows.
    # ⚠ 0 is reachable and means the cube NEVER re-centres — informative rather
    # than hidden. The owner's stated floor, 0.05, is position 5.
    ("WALK % of hand", 100, 25, lambda n: n / 100.0),
    # ⭐⭐ T6's AXIS CORRECTION -- how much of the way to steer Horn's rotation
    # axis toward the one the palm's own foreshortening implies. This is the LEAN
    # control: the owner called the lean a show-stopper, and this is the first
    # thing measured to reduce it.
    # ⛔ 0% IS BIT-EXACT SHIPPED HORN, not an approximation of it -- the golden
    # vectors assert the quaternion is returned as the SAME OBJECT. So the left end
    # of this slider is today's production behaviour, exactly.
    # ⚠ DRIVES ONLY THE ARM THAT FOLLOWS THE GLOBAL. In `--slant-rig` panel 1 is
    # pinned to 0.0 and ignores this, so sweeping it moves panel 2 alone -- the same
    # one-variable discipline the TRIM slider follows.
    # ⭐ Measured on the clean sweeps, lean med: yaw 22.0 -> 16.2 (50%) -> 13.6
    # (75%) -> 13.5 (100%); pitch 14.8 -> 10.0 (100%). ⚠ Wander p95 is flat on yaw
    # (19.8 -> 19.6) and IMPROVES on pitch (45.0 -> 22.1), so there is no measured
    # jitter cost -- but T6d was rejected for FEELING wrong while scoring fine, so
    # the slider exists to let the hand decide, not the table.
    # ⭐⭐ THE STEADY DAMPER, owner 2026-08-27: *"there is a bit of jitter of the
    # cube"*. EXTRA milliseconds of smoothing given to a cube that is barely
    # turning, and taken back as it turns.
    # ⛔ 0 ms IS TODAY'S BEHAVIOUR, BIT-EXACT -- the left end is production.
    # ⚠ It is NOT "raise SMOOTH ms". A fixed time constant lags real motion exactly
    # as much as it damps jitter, which is the trade `L1` already rejected
    # (*"the cube is lagging the hand and this feels very uncomfortable"*). This one
    # is spent only while the cube is nearly still.
    # ⭐ Measured target: orientation moves 4.30 deg/frame median while held, which
    # at 15 fps is the shimmer. Position needs nothing -- the cube tracks the grip
    # point to within 0.1 px, so damping it would only lag translation.
    # ⚠ RANGE RAISED 400 -> 1000 (owner, 2026-08-27). 400 was the STOP, not a
    # choice: the take exited at exactly 400.0, so the useful range had not been
    # bracketed. A slider whose maximum is the answer has not been explored yet --
    # the same reason GRAB radius runs to 300%.
    # ⭐⭐ WHERE THE DAMPING LETS GO, in deg/s of hand rotation. Owner, 2026-08-27:
    # *"I don't want any quaternion slerp as soon as I start a hand rotation"*.
    # ⛔ ABOVE this the extra damping is EXACTLY ZERO -- the cube is on today's tau
    # and nothing else. Below 45% of it the damping is at full strength; the gap is
    # the whole ramp, and it is narrow on purpose.
    # ⚠ IT CANNOT GO VERY LOW. A held-STILL hand's raw target already moves
    # 2.53 deg/frame -- about 38 deg/s at 15 fps -- so a threshold under that would
    # be tripped by the very jitter the damper removes, and the damping would
    # flicker on and off.
    ("RELEASE deg/s", 400, 60, lambda n: float(n)),
    # ⭐⭐ FREEZE: consecutive fast frames needed to let the object move at all.
    # ⛔ 0 = OFF, i.e. the smooth ramp above. Any value > 0 makes the blend factor
    # EXACTLY ZERO while held -- absolutely no movement, by construction rather than
    # by being slow. Owner, 2026-08-27: *"I want absolutely no movement when the cube
    # should be steady, and immediate release when the hands move (maybe with a
    # couple of frames trigger)"*.
    # ⭐ 2 is that couple. It rejects single-frame NOISE SPIKES outright -- which the
    # instant-attack envelope could not -- at a cost of exactly N-1 frames of onset.
    # ⚠ While frozen the object ignores slow drift, so a hand creeping below the
    # threshold accumulates a gap that is paid back as a JUMP on release. That is
    # what "absolutely no movement" costs.
    # ⚠ KEEP THIS AT 1. Owner, 2026-08-27: *"if I increase the freeze frame, it
    # makes the rotation jerky. I want to keep it to 0 or 1 or max 2"*. The COHERENCE
    # gate below is what makes 1 sufficient -- it does the noise rejection the second
    # frame used to do, without costing a frame of onset.
    ("FREEZE frames", 2, 1, lambda n: int(n)),
    #   ("SLANT axis %", 100, 0, lambda n: n / 100.0),   RETIRED 2026-08-28
    # ⭐⭐ THE OWNER'S OWN STRATEGY, as a whole estimator: the regression fitted
    # from the six takes (HALF 1) on a canonical frozen at the grab (HALF 2).
    # ⛔ 0% is bit-exact shipped Horn. 100% is the strategy running alone.
    # ⛔⛔ THE MIDDLE IS A TRAP AND THE MEASUREMENT SAYS SO: yaw lean reads 27.2 at
    # 0%, **53.7 at 50%**, and 8.6 at 100%. Slerping between two orientations that
    # disagree lands on an axis worse than EITHER, so this control is all-or-nothing.
    # ⚠ Left reachable anyway -- a slider whose bad region is hidden teaches the
    # wrong thing about where the limit is, which is the GRAB radius rule.
    # ⚠ Measured cost: per-frame orientation jump p95 12.6 -> 30.3, i.e. 2.4x
    # shipped Horn, while the MEDIAN improves (2.98 -> 2.41). Smoother most of the
    # time, worse in the tail. That is a feel question, which is why it has a slider.
    #   ("POSE blend %", 100, 0, lambda n: n / 100.0),   RETIRED 2026-08-28
    # ⭐⭐ THE AXIAL HALF OF THE GRAB GATE, owner 2026-08-26: "currently, the margin
    # is too wide". In CENTIMETRES so the displayed integer is the applied value.
    # ⚠ It is deliberately SEPARATE from the in-plane radius and always has been:
    # x,y are MEASURED in pixels while depth is ESTIMATED, and `T6` measured the
    # four palm spans disagreeing about that estimate by 13-22% at a single square
    # pose. `GRAB_Z_TOLERANCE_M`'s own comment says it is sized to swallow that so
    # the gate stays REACHABLE.
    # ⛔ MEASURED BEFORE TIGHTENING: on the two takes recorded before the depth
    # ratchet was fixed, |hand depth - cube depth| at grab ran a MEDIAN 12.3 cm
    # (p95 14.6), i.e. pressed against today's 15. Most of that was the ratchet --
    # cubes pinned at the 0.30 m floor while the hand sat at 0.42 -- so it should
    # be far smaller now. This slider is how we find out, live.
    ("GRAB z margin cm", 30, 15, lambda n: n / 100.0),
    # -- V2: the yaw-lean trim (swing/twist). Two gains because the two
    # contaminants were MEASURED 1.3x apart, not because two felt safer:
    #   nx toward PITCH  mean|.| 0.431      nz toward ROLL  mean|.| 0.323
    # (`analysis/lean_decomposition.py`, 7511 yaw-like frames, four takes).
    # Both are one-directional BIASES relative to the turn, which is what makes a
    # deterministic correction able to remove them at all.
    #
    # ⛔ BOTH START AT 0, WHICH IS BIT-EXACT SHIPPED HORN -- `lean_trim.trim`
    # returns its input object unchanged at gain 0, so this position is genuinely
    # today rather than an approximation of it. Same reason `TRIM gain %` starts
    # at 0: a debug tool that silently differs from production in ordinary use is
    # the divergence `U6` keeps `parity_replay` around to prevent.
    #
    # ⚠ THE GATE, MEASURED BEFORE THESE EXISTED (`analysis/lean_trim_ab.py`):
    # per-frame orientation jump p95 vs shipped Horn, PER TAKE, four grabbing
    # takes. gains <= 0.30 sit at 1.001-1.007x on the worst take and IMPROVE the
    # other three (down to 0.83x). Above ~0.4 the worst take reaches 1.08-1.13x.
    # ⭐ For scale: the three rejected predecessors never came within 1.8x.
    # ⛔ But 1.001x is still ABOVE the 1.000x bar `REJECTED.md` sets, so the
    # useful range is the LOW end and the bar is the owner's to relax, not mine.
    ("LEAN pitch %", 100, 0, lambda n: n / 100.0),
    ("LEAN roll %", 100, 0, lambda n: n / 100.0),
    # ⭐⭐ THE Z-JUMP KNOB. `palm_depth`'s ratio may change by at most this fraction
    # of itself per SECOND, so the constant means the same thing whatever the
    # camera's frame rate (the `L1` lesson, applied on 2026-08-27).
    # Shown as PERCENT PER SECOND -- the displayed integer is the applied value.
    #
    # ⚠ WHAT THE NUMBERS MEAN, measured on the owner's own take: at ~20 fps,
    #     240 %/s = 12%/frame  <- today's shipped value
    #     100 %/s =  5%/frame  <- the module's own figure for a GENUINE hand push
    # and the per-frame depth step while held was p50 0.9%, p90 5.2%, p95 8.3%,
    # max 13.7%. So the visible jumps are the tail ABOVE the genuine rate, and the
    # useful range to explore is roughly 100-240.
    # ⚠ 0 freezes depth outright -- reachable on purpose, like every other slider
    # here, because a hidden floor teaches the wrong thing about where the limit is.
    # ⛔⛔ PARKED 2026-08-27 (owner: *"there is no need for z rate %/s slider"*).
    # The value was SETTLED at the shipped 2.00 and the work since has all been
    # rotation, which this does not touch.
    #
    # ⚠ IT WAS ALSO A PARITY LEAK, and that is the stronger reason. This slider
    # writes `_PDepth.RATE_LIMIT_PER_S`, a module BOTH tools import (N6), so while it
    # sat off 2.00 the debug tool ran a depth rate production does not. Measured
    # across the last four takes: **4.0 / 0.51 / 0.42 / 2.0** -- three of them
    # off-spec, and nothing in the session was about depth. Parking pins it at the
    # module's own constant, which is production's, so `U6` has nothing to catch.
    # ⭐ The rotation verdicts are unaffected: depth rate drives Z TRANSLATION and
    # cannot reach an orientation estimator. Recorded rather than assumed.
    #
    # ⭐ To revive: restore the line below, add `DEPTH_RATE_PER_S` back to the
    # `_read_sliders` unpack, and restore the two lines flagged "Z rate parked".
    # Nothing else was removed -- same treatment as JITTER/SPEED above.
    #   ("Z rate %/s", 400, 200, lambda n: n / 100.0),
    # ⛔ PARKED 2026-08-26 alongside the two above -- the owner retired it after
    # revisiting an earlier preference for a raised clamp.
    #   ("TRIM max deg", TRIM_MAX_DEG_MAX, 10, lambda n: float(n)),
)
```
