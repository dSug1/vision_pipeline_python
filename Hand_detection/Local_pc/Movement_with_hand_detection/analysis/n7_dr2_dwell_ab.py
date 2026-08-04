"""N7 (DR-2 half): time-based exit dwell vs the old 24 fps frame count.

`PalmFacingTracker`'s exit dwell was always DEFINED in milliseconds
(EXIT_DWELL_MS = 100). Converting it to a frame count is what made it depend on
the frame rate, and the rate varies 15-27 fps with lighting (N10). Supplying a
timestamp removes the dependency entirely -- no estimator needed, unlike
`hand_identity`, whose dwells genuinely gate frame COUNTS in a voting scheme.

⭐ RESULT: the time-based variant was REJECTED. This script is the evidence.

    TOTAL frozen frames: old 595, new 877  (+47.4%)

I predicted a ~20% ceiling and was wrong, which is what forced the re-think.
The error was in reading the old dwell: `exit_run >= 2` exits on the SECOND
consecutive above-threshold frame, i.e. after ONE frame interval (~42 ms at
24 fps) -- not ~83 ms. A 100 ms time-based dwell therefore needs FOUR frames at
24 fps, roughly doubling the freeze rather than nudging it.

⚠ And a 47% longer freeze is a felt regression, not a refinement: it lengthens
exactly the staleness window `GAME_RULES.md` rule 3 documents (the palm/back
reading the game acts on, already median 96 ms / p90 163 ms).

THE REASON IT DOES NOT APPLY HERE, generalised: this dwell is a DEBOUNCE --
"resume only after N consecutive confirmations" -- not a physical duration.
Consecutive-confirmation counts belong in frames. N1's "re-express frame
parameters in ms" applies to dwells that represent real elapsed time, which
DR-1's voting windows are and this is not. **N7 fixed a real defect in
`hand_identity` and does not apply to `palm_geometry`.**

The rejected variant lives in this file (`TimeBasedTracker`) rather than in the
shipped module, so the null result stays reproducible without leaving dead code
in production.

Reported per session: freeze episodes, and total frozen frames, under each path.

    .venv/Scripts/python.exe analysis/n7_dr2_dwell_ab.py
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP
from Resources import palm_geometry as PG


class TimeBasedTracker(PG.PalmFacingTracker):
    """The REJECTED time-based variant, kept HERE rather than in the shipped
    module so the null result stays reproducible without leaving dead code in
    production (A10: a negative result that cannot be re-run is an assertion,
    not a finding).

    Identical to `PalmFacingTracker` except that the exit dwell is elapsed
    milliseconds since the recovery run began, instead of a frame count.
    """

    def __init__(self, threshold=PG.EDGE_ON_THRESHOLD):
        super().__init__(threshold)
        self.exit_started_ms = None

    def update(self, landmarks, handedness, now_ms=None):
        eo = PG.edge_on_measure(landmarks)
        measured = PG.is_thumb_outward(landmarks, handedness)
        if self.frozen is None:
            self.frozen = measured
        if not self.in_band:
            if eo < self.threshold:
                self.in_band = True
                self.exit_started_ms = None
                self.band_entries += 1
            else:
                self.frozen = measured
                return measured, True
        else:
            if eo > self.exit_threshold:
                if self.exit_started_ms is None:
                    self.exit_started_ms = now_ms
                if (now_ms is not None and self.exit_started_ms is not None
                        and now_ms - self.exit_started_ms >= PG.EXIT_DWELL_MS):
                    self.in_band = False
                    self.exit_started_ms = None
                    self.frozen = measured
                    return measured, True
            else:
                self.exit_started_ms = None
        self.frames_frozen += 1
        return self.frozen, False


def run(frames, use_timestamps):
    trackers = {}
    episodes = frozen_frames = 0
    was_in_band = {}
    for rec in frames:
        now = rec.get("tCapture") if use_timestamps else None
        for h in (rec.get("hands") or []):
            lab = h["handedness"]
            t = trackers.get(lab)
            if t is None:
                t = trackers[lab] = (TimeBasedTracker() if use_timestamps
                                     else PG.PalmFacingTracker())
            lm = [tuple(p) for p in h["landmarks"]]
            if use_timestamps:
                t.update(lm, lab, now_ms=now)
            else:
                t.update(lm, lab)
            if t.in_band:
                frozen_frames += 1
                if not was_in_band.get(lab):
                    episodes += 1
            was_in_band[lab] = t.in_band
    return episodes, frozen_frames


def main():
    print("=" * 78)
    print("N7 (DR-2): time-based 100 ms exit dwell vs the 24 fps frame count")
    print("=" * 78)
    print(f"\n  EXIT_DWELL_MS={PG.EXIT_DWELL_MS:.0f}, old frame count="
          f"{PG.EXIT_DWELL_FRAMES} (~{1000.0*PG.EXIT_DWELL_FRAMES/24.0:.0f} ms "
          f"at 24 fps -- SHORT of the intent)\n")
    print(f"  {'session':<40}{'fps':>7}{'ep old':>8}{'ep new':>8}"
          f"{'frz old':>9}{'frz new':>9}")

    seen = {}
    tot_o = tot_n = 0
    for raw_name, frames in AJP.SESSIONS:
        seen[raw_name] = seen.get(raw_name, 0) + 1
        name = raw_name if seen[raw_name] == 1 else f"{raw_name} #{seen[raw_name]}"
        if not frames or "tCapture" not in frames[0]:
            continue
        span = (frames[-1]["tCapture"] - frames[0]["tCapture"]) / 1000.0
        fps = len(frames) / span if span > 0 else 0.0
        eo, fo = run(frames, use_timestamps=False)
        en, fn = run(frames, use_timestamps=True)
        tot_o += fo
        tot_n += fn
        if eo or en:
            print(f"  {name[:39]:<40}{fps:>7.1f}{eo:>8}{en:>8}{fo:>9}{fn:>9}")

    print(f"\n  TOTAL frozen frames: old {tot_o}, new {tot_n} "
          f"({100.0*(tot_n-tot_o)/tot_o:+.1f}%)" if tot_o else "")
    print("\n  VERDICT: time-based dwell REJECTED, frame count RETAINED.")
    print("  The old dwell exits after ONE frame interval (~42 ms at 24 fps),")
    print("  so a 100 ms time-based dwell needs FOUR frames -- roughly doubling")
    print("  the freeze and lengthening the rule-3 staleness window for no")
    print("  correctness gain. This is a consecutive-confirmation DEBOUNCE, which")
    print("  belongs in frames; N7 applies to hand_identity, not here.")
    print("=" * 78)


if __name__ == "__main__":
    main()
