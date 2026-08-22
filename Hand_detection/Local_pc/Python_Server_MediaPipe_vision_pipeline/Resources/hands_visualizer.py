import math
import time

import cv2
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
import numpy as np
# NOTE: `_normalized_to_pixel_coordinates` is deliberately NOT imported any more.
# It returns None for out-of-frame landmarks, which caused the stranded-cube
# defect and an origin-teleport on the wire -- see the long comment in the
# landmark loop below. Faces still use it, in facevisualizer.py.
from . import hand_identity

MARGIN = 10  # pixels
FONT_SIZE = 1
FONT_THICKNESS = 1
HANDEDNESS_TEXT_COLOR = (88, 205, 54) # vibrant green

# ⭐⭐ HANDEDNESS NEEDS NO CORRECTION ANY MORE (2026-08-22, spec 14.3.4.3).
# `VisionPipeline.py` now mirrors the FRAME before detection, exactly as the
# debug tool and the recorders always did. MediaPipe's Left/Right classification
# assumes an already-mirrored ("selfie") input by convention, so on a mirrored
# frame it natively reports the label that matches what the operator sees. The
# old `_mirror_handedness()` flip is therefore REMOVED -- keeping it would apply
# a SECOND flip and re-invert chirality, which is precisely the §13.6.1 bug in
# reverse.
#
# ⚠ HISTORY, kept because the trap is easy to re-enter: from 2026-08-01 to
# 2026-08-22 this file DID flip the label. That was correct THEN, because the
# pipeline detected on the RAW, un-mirrored frame and mirrored only the
# COORDINATES afterward (`remap_keypoints`/`remap_world_keypoints`,
# invert_x=True) -- so MediaPipe saw a true anatomical hand and reported the
# opposite of the mirrored display. Uncorrected, that silently inverted
# `_is_thumb_outward`'s handedness-dependent sign in production only (§13.6.1).
#
# ⭐ WHY THE WHOLE APPROACH CHANGED: mirroring the coordinates after detection is
# only equivalent to mirroring the frame before it if MediaPipe is
# mirror-equivariant. It is NOT -- measured 2026-08-22 by
# `analysis/t6_mirror_route_ab.py`: the two routes disagree by 7.7-10 mm of
# world landmark and 12-20° of fitted rotation on the SAME frames. So the
# post-hoc mirror was never a valid substitute; production and the debug tool
# were different pipelines. Mirroring the frame makes them identical BY
# CONSTRUCTION, and deletes the equivariance assumption instead of tuning it.
#
# ⚠ M5d still applies: this convention depends on THREE independent flips
# (image-y, preview mirroring, MediaPipe's selfie handedness). An EVEN number of
# mistakes still "works"; an odd number inverts. `VerifyChiralityFixture.py` is
# the permanent guard -- run it after ANY change here.


# Track-level hand identity (DR-1) now lives in `hand_identity.py`, SHARED with
# the debug tool (LiveSnapDebug.py) so the two cannot drift -- owner instruction
# 2026-08-02: "I do not want to have a debug tool which is not in tune with the
# production." Full rationale, measurements and the tunable trade-off are
# documented there and in PERCEPTION_LAYER_SPEC.md §0.4-§0.5.
_PALM_IDX = hand_identity.PALM_LANDMARKS


def _xy_list(coords):
    """hands_visualizer holds landmarks as {"x_px","y_px"} dicts; the shared
    identity module works on plain (x, y) tuples."""
    return [(c["x_px"], c["y_px"]) for c in coords]


_hand_identity_tracker = hand_identity.HandIdentityTracker()


def reset_hand_identity():
    """Drop all identity tracks (e.g. when the pipeline restarts)."""
    global _hand_identity_tracker
    _hand_identity_tracker = hand_identity.HandIdentityTracker()


def draw_landmarks_on_image(frame_image_shape, rgb_image, detection_result):
  hand_landmarks_list = detection_result.hand_landmarks
  # world_landmarks: metric, hand-relative 3D coordinates (meters), parallel
  # array to hand_landmarks -- needed for rotation-while-snapped
  # (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md §13.7), not previously
  # extracted here since only 2D pixel landmarks were needed before.
  hand_world_landmarks_list = detection_result.hand_world_landmarks
  handedness_list = detection_result.handedness
  annotated_image = np.copy(rgb_image)
  height, width = frame_image_shape[:2]
  all_hands_coords = []
  landmarkscoordinatesArray = []




  # Loop through the detected hands to visualize.
  for idx in range(len(hand_landmarks_list)):
    hand_landmarks = hand_landmarks_list[idx]
    hand_world_landmarks = hand_world_landmarks_list[idx]
    handedness = handedness_list[idx]
    # The frame was mirrored before detection, so MediaPipe's own label is
    # already the mirror-consistent one -- do NOT flip it again (see above).
    mirrored_handedness = handedness[0].category_name

    hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()     # Prepare protobuf for drawing
    handslandmarks_coords = []  # This will store the extracted coordinates
    # Metric hand-relative 3D coords (meters), no pixel remapping -- raw
    # x/y/z as MediaPipe returns them (mirroring/remap_keypoints only
    # applies to the pixel-space landmarks above).
    handsworldlandmarks_coords = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in hand_world_landmarks]

    for landmark in hand_landmarks:
        # Add to protobuf for drawing
        hand_landmarks_proto.landmark.append(
            landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z)
        )

        # ⭐⭐ PLAIN MULTIPLICATION, matching LiveSnapDebug.py exactly (2026-08-22).
        # This replaced `_normalized_to_px_coords`, which returns None for ANY
        # landmark outside [0,1] -- i.e. a hand PARTIALLY OUT OF FRAME -- and that
        # None caused TWO defects, both measured on the first recorded production
        # run (`2026-08-22_154426_production_4_1`):
        #
        # 1. ⛔ THE STRANDED CUBE. One None makes `palm_centroid` None, which fails
        #    the `all(o[0] is not None ...)` guard below, which SKIPS DR-1 ENTIRELY
        #    for that frame -- so NEITHER hand gets a trackId and the wire carries
        #    -1 for both slots while landmarks keep flowing. A cube held by a track
        #    id then matched no live key, while its slot still held a DETECTED
        #    hand, so release never fired: "indicated as grabbed but did not move,
        #    and the free hand could not grab it again". Measured at 40-frame
        #    (~1.6 s) runs. Moving a hand near the frame EDGE was enough.
        #
        # 2. ⛔ A LANDMARK TELEPORTING TO THE ORIGIN. `remap_keypoints` turns a
        #    None into (0, 0) via its TypeError fallback, so an out-of-frame
        #    landmark arrived at the client at the TOP-LEFT CORNER -- corrupting
        #    `_weighted_position`'s translation average, not merely identity.
        #
        # ⚠ Out-of-frame coordinates are now NEGATIVE or beyond width/height
        # instead of absent. That is deliberate and correct: MediaPipe still
        # estimates those landmarks, and a continuous extrapolated position is
        # strictly better than None-then-zero for every consumer here (centroid,
        # palm width, distance weighting). Nothing downstream requires in-bounds
        # pixels -- `remap_point` only offsets/negates, and drawing uses the
        # separate normalized proto above.
        #
        # ⭐ It also removes a production/debug DIVERGENCE of exactly the class
        # that produced §13.6.1 and the mirror bug: the debug tool has always used
        # plain multiplication and never had either defect.
        handslandmarks_coords.append({
            "x_px": landmark.x * width,
            "y_px": landmark.y * height,
        })

    solutions.drawing_utils.draw_landmarks(
      annotated_image,
      hand_landmarks_proto,
      solutions.hands.HAND_CONNECTIONS,
      solutions.drawing_styles.get_default_hand_landmarks_style(),
      solutions.drawing_styles.get_default_hand_connections_style())

    # Get the top left corner of the detected hand's bounding box.
    height, width, _ = annotated_image.shape
    x_coordinates = [landmark.x for landmark in hand_landmarks]
    y_coordinates = [landmark.y for landmark in hand_landmarks]
    text_x = int(min(x_coordinates) * width)
    text_y = int(min(y_coordinates) * height) - MARGIN

    # Draw the ANATOMICAL hand -- the one the operator is physically holding up
    # (owner report 2026-08-22: the on-screen label read inverted). This is a
    # DISPLAY-ONLY correction: `mirrored_handedness` itself is untouched and
    # keeps flowing to every consumer in the pipeline's own convention. See
    # `hand_identity.anatomical_name`'s comment block for why the internal label
    # must not be flipped instead (§13.6.1).
    cv2.putText(annotated_image, f"{hand_identity.anatomical_name(mirrored_handedness)}",
                (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX,
                FONT_SIZE, HANDEDNESS_TEXT_COLOR, FONT_THICKNESS, cv2.LINE_AA)

    # Append to full list. `score` is MediaPipe's own handedness confidence --
    # carried through (2026-08-02) because the duplicate-label resolver below
    # needs it, and because it is a measured early-warning signal: recorded label
    # flips occur at ~0.66 against a 0.95-0.99 baseline (spec §0.4).
    all_hands_coords.append({
            "handedness": mirrored_handedness,
            "score": float(handedness[0].score),
            "landmarks": handslandmarks_coords,
            "world_landmarks": handsworldlandmarks_coords
        })

  # DR-1: assign each detection a TRACK-LEVEL identity by position, overriding
  # MediaPipe's per-frame handedness. This runs after the loop so it sees all
  # detections at once, and before anything downstream resolves hands by label.
  observations = []
  for hand in all_hands_coords:
      observations.append((
          hand_identity.palm_centroid(_xy_list(hand["landmarks"])),
          hand["handedness"],
          hand["score"],
          hand_identity.palm_width(_xy_list(hand["landmarks"])),
      ))
  if all(o[0] is not None for o in observations):
      # N7: supply a real monotonic capture time so DR-1's dwells are derived
      # from the MEASURED frame rate. Without this the dwells assume 24 fps, and
      # in dim light the pipeline runs at 15-16 (queue N10), which stretched
      # SWITCH_MS to ~761 ms against an intended 500.
      resolved = _hand_identity_tracker.update(
          observations, now_ms=time.perf_counter() * 1000.0)
      ids = _hand_identity_tracker.last_track_ids
      for i, (hand, label) in enumerate(zip(all_hands_coords, resolved)):
          hand["raw_handedness"] = hand["handedness"]   # kept for diagnostics
          hand["handedness"] = label
          # ⭐ 4.1 / T3: the STABLE track id, carried to the client so cube
          # ownership can key on identity instead of on the label. The label
          # flips; 113 of 205 spurious releases were exactly that flip
          # orphaning a held cube. -1 means "no track backs this detection".
          hand["trackId"] = ids[i] if i < len(ids) else -1

  return annotated_image, all_hands_coords
