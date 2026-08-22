"""U8 -- how many frames before a NEWLY ENTERED hand's chirality can be trusted?

THE OWNER'S REASONING, which is what this measures (2026-08-22):

    *"you need enough frames for the thumb and the palm to be both present since
    this will define definitely the hand: if the back of the right hand enters
    from the right, you do not see the thumb before the last moment: this should
    define the order of magnitude of the number of frames, based on velocity and
    usual palm width."*

That is exactly right, and it is why no amount of temporal voting fixed the
recorded failure: chirality is `det[index_MCP-wrist, pinky_MCP-wrist, thumb-wrist]`,
so it IS the thumb's offset from the palm plane. Until the thumb is genuinely in
view the quantity is not noisy -- it is UNDEFINED, and MediaPipe hallucinates a
plausible thumb, which is why the wrong value was stable for 5 consecutive frames
at good conditioning (11-16 mm, above the 8.8 mm corpus median).

So the window is not a tuning constant. It is a TRANSIT TIME:

    N  ~=  (how far the hand must travel for the thumb to clear the frame edge)
           ---------------------------------------------------------------
                        (how fast hands actually enter)

with the numerator on the order of one palm width, since the thumb sits roughly a
palm width behind the leading edge when a hand enters side-on.

MEASURED HERE, all from the corpus rather than assumed:
  1. palm width in pixels, so the numerator is real;
  2. entry speed in px/frame for tracks that START at the frame edge;
  3. the implied transit time, per entering track;
  4. the EMPIRICAL settling age -- the first frame age after which a track's
     chirality matches its settled value and stays there.

(3) and (4) are independent estimates of the same thing. If they agree, the
window is justified twice over and is not fitted to the one failure that
prompted it.
"""

import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Resources import palm_geometry as PG  # noqa: E402

SESSIONS = (r"E:\Python\Recordings for vision_pipeline"
            r"\Recordings_perception_layer\sessions")

WRIST, INDEX_MCP, PINKY_MCP = 0, 5, 17
# Recording resolution. A track whose first centroid is within this margin of a
# vertical edge is treated as ENTERING from the side -- the case the owner
# describes, and the one where the thumb is hidden longest.
FRAME_W, FRAME_H = 640, 480
EDGE_MARGIN_PX = 120


def palm_width_px(lm):
    return math.hypot(lm[INDEX_MCP][0] - lm[PINKY_MCP][0],
                      lm[INDEX_MCP][1] - lm[PINKY_MCP][1])


def centroid(lm):
    xs = [lm[i][0] for i in (WRIST, INDEX_MCP, PINKY_MCP)]
    ys = [lm[i][1] for i in (WRIST, INDEX_MCP, PINKY_MCP)]
    return sum(xs) / 3.0, sum(ys) / 3.0


def pct(vals, q):
    if not vals:
        return 0.0
    v = sorted(vals)
    return v[min(len(v) - 1, int(q * len(v)))]


def main():
    widths, speeds, transits, settles = [], [], [], []
    transits_ms = []          # the same transit expressed in TIME (see below)
    entering = total = 0

    for s in sorted(os.listdir(SESSIONS)):
        p = os.path.join(SESSIONS, s, "raw_landmarks.jsonl")
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                frames = [json.loads(x) for x in fh if x.strip()]
        except Exception:
            continue
        # ⭐ The session's OWN measured rate. Converting a frame count with a
        # guessed rate would bake an error into the constant; each take carries
        # its real one, and they range 15-25 fps across the corpus.
        try:
            with open(os.path.join(SESSIONS, s, "meta.json")) as fh:
                fps = float(json.load(fh).get("measured_fps") or 0.0)
        except Exception:
            fps = 0.0

        seq = defaultdict(list)
        for i, fr in enumerate(frames):
            for h in (fr.get("hands") or []):
                t = h.get("trackId")
                if t is None or t < 0 or not h.get("world_landmarks"):
                    continue
                seq[t].append((i, h["landmarks"], h["world_landmarks"]))

        for t, ev in seq.items():
            if len(ev) < 12:
                continue
            total += 1
            chir = [PG.geometric_chirality(w) for _i, _lm, w in ev]
            settled = Counter(c for c in chir if c).most_common(1)[0][0]

            # (4) ENTRY settling = the length of the LEADING run of disagreement.
            #
            # ⚠ THE FIRST VERSION OF THIS MEASURED "the LAST age at which it
            # disagrees", which is a different quantity entirely: it picks up
            # mid-track occlusion glitches hundreds of frames later (p90 was 369
            # frames) and says nothing about entry. The window being sized here
            # governs only the FIRST adoption, so only the leading run counts.
            lead = 0
            for c in chir:
                if c == settled:
                    break
                lead += 1
            settles.append(lead)

            # width at the moment the track is established
            w0 = palm_width_px(ev[0][1])
            if w0 > 0:
                widths.append(w0)

            # (2)+(3) entry speed, only for tracks starting at a vertical edge
            cx, _cy = centroid(ev[0][1])
            if cx <= EDGE_MARGIN_PX or cx >= FRAME_W - EDGE_MARGIN_PX:
                entering += 1
                steps = []
                for k in range(1, min(6, len(ev))):
                    ax, ay = centroid(ev[k - 1][1])
                    bx, by = centroid(ev[k][1])
                    d = math.hypot(bx - ax, by - ay)
                    gap = ev[k][0] - ev[k - 1][0]
                    if gap > 0:
                        steps.append(d / gap)
                if steps and w0 > 0:
                    v = sum(steps) / len(steps)
                    speeds.append(v)
                    if v > 1e-6:
                        transits.append(w0 / v)
                        # ⭐⭐ THE SAME QUANTITY IN TIME, which is what it really
                        # is: entry speed in px/SECOND is v * fps, so the transit
                        # is width / (v * fps). This is the number the shipped
                        # constant should be expressed in -- a hand crossing a
                        # palm width takes the same TIME whatever the capture
                        # rate, while the FRAME count for it does not.
                        if fps > 0:
                            transits_ms.append(1000.0 * w0 / (v * fps))

    print("=" * 76)
    print("U8 -- how long before a newly entered hand's chirality is meaningful?")
    print("=" * 76)
    print()
    print("%d tracks (>=12 frames); %d of them START at a vertical frame edge."
          % (total, entering))
    print()

    print("1. PALM WIDTH in pixels (the distance the thumb trails the leading edge)")
    print("   p10 %.0f   median %.0f   p90 %.0f"
          % (pct(widths, .10), pct(widths, .50), pct(widths, .90)))
    print()
    print("2. ENTRY SPEED for edge-starting tracks, px/frame (first 5 frames)")
    print("   p10 %.1f   median %.1f   p90 %.1f"
          % (pct(speeds, .10), pct(speeds, .50), pct(speeds, .90)))
    print()
    print("3. IMPLIED TRANSIT TIME = palm width / entry speed, in FRAMES")
    print("   p10 %.1f   median %.1f   p75 %.1f   p90 %.1f"
          % (pct(transits, .10), pct(transits, .50),
             pct(transits, .75), pct(transits, .90)))
    print("   -> a FAST entry crosses a palm width in the p10 time; a slow one")
    print("      takes the p90. The window must cover the FAST case at minimum,")
    print("      because that is when the thumb is hidden for the fewest frames")
    print("      and the hand is grabbing soonest.")
    print()
    print("3b. THE SAME TRANSIT IN MILLISECONDS -- the rate-independent form")
    print("    p10 %.0f ms   median %.0f ms   p75 %.0f ms   p90 %.0f ms"
          % (pct(transits_ms, .10), pct(transits_ms, .50),
             pct(transits_ms, .75), pct(transits_ms, .90)))
    print("    -> express the shipped constant in THIS unit. A frame count is")
    print("       only correct at the rate it was measured at, and the corpus")
    print("       spans 15-25 fps depending on lighting (N7/N10).")
    print()
    print("4. ENTRY SETTLING -- length of the LEADING run of wrong chirality")
    print("   (0 = correct from the very first frame of the track)")
    print("   median %.0f   p75 %.0f   p90 %.0f   p95 %.0f   max %.0f"
          % (pct(settles, .50), pct(settles, .75), pct(settles, .90),
             pct(settles, .95), pct(settles, 1.0)))
    n = len(settles)
    for k in (0, 1, 2, 3, 5, 8, 10, 15):
        c = sum(1 for x in settles if x <= k)
        print("     settled by age %-3d : %5.1f%% of tracks" % (k, 100.0 * c / n))
    print()
    print("=" * 76)
    print("READ (3) AND (4) TOGETHER -- two independent estimates of one quantity.")
    print("(3) is physical: how long the thumb is out of view on entry.")
    print("(4) is behavioural: how long the measurement actually stays wrong.")
    print("=" * 76)


if __name__ == "__main__":
    main()
