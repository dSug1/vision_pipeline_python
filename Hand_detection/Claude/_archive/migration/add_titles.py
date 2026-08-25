"""Give each split destination file its own title block. Binary mode; the header
sits above the first PROVENANCE comment, outside every VERBATIM block."""
import os

T = {}

T["00_CORE/ORIGINAL_GOAL_AND_CONSTRAINTS.md"] = (
    "ORIGINAL GOAL & CONSTRAINTS — verbatim",
    "reference · the owner's original framing, and the open decisions it listed",
    "`Specification.md` §0 and §13, the Part Zero-era build handoff",
    "⚠ **HISTORICAL FRAMING, KEPT FOR THE GOAL.** Two of its constraints have been\n"
    "overtaken by events — OpenCV *is* used server-side, and native mobile joined\n"
    "the browser as a target. What is current is [`CHARTER.md`](CHARTER.md); what is\n"
    "binding is [`CONSTRAINTS.md`](CONSTRAINTS.md).")

T["10_HAND_TRACKING/history/ORIGINAL_HANDOFF.md"] = (
    "THE ORIGINAL BUILD HANDOFF — verbatim",
    "history · prior art, repo layout, Pipeline A, the superseded build order",
    "`Specification.md` §1–§3, §7, §11",
    "⚠ Its build order is **historical** — the queue superseded it. Keep it for the\n"
    "prior-art scan and the original architecture reasoning.")

T["10_HAND_TRACKING/history/PART_ONE_ORIGINS.md"] = (
    "PART ONE — its title and banners, verbatim",
    "history · why Part One exists and how its gesture set changed twice",
    "`PART_ONE.md` lines 1–61",
    "⚠ Its pointer to *§​3.1 is the single build queue* is now\n"
    "[`../../00_CORE/QUEUE.md`](../../00_CORE/QUEUE.md).")

T["10_HAND_TRACKING/history/PART_ONE_PINCH_ERA.md"] = (
    "PART ONE — the pinch classifier's design basis, verbatim",
    "history · the 2026-07-30 state-of-the-art check and its derived result",
    "`PART_ONE.md` §6–§6.1",
    "⛔ The rule-based approach documented here was **abandoned**; pinch itself was\n"
    "archived 2026-08-01. Kept as the evidence trail for why.")

T["10_HAND_TRACKING/history/PERCEPTION_SESSION_LOG.md"] = (
    "PERCEPTION LAYER — the build log, verbatim",
    "history · §0.2–§0.18, every module built or killed and the audit of the nulls",
    "`PERCEPTION_LAYER_SPEC.md` §0.2–§0.18",
    "⭐ Where DR-1, DR-2, M2, M4, M5, M6 and Phase 1's closure actually happened,\n"
    "dated. The **forward design** is\n"
    "[`../spec/PERCEPTION_LAYER_SPEC.md`](../spec/PERCEPTION_LAYER_SPEC.md); its\n"
    "§0.1 amendment log is binding and stayed there.")

T["10_HAND_TRACKING/history/SESSION_LOG.md"] = (
    "SESSION LOG — every \"YOU ARE HERE\", newest first",
    "history · the narrative of how the project got here, 2026-08-03 → 2026-08-25",
    "`PART_ONE.md` §3.1's YOU-ARE-HERE blocks",
    "⭐ **This is where a session's story goes on the day it happens.** The current\n"
    "status lives at the top of\n"
    "[`../../00_CORE/QUEUE.md`](../../00_CORE/QUEUE.md); everything below the first\n"
    "block here is superseded and marked so.")

T["10_HAND_TRACKING/history/SPEC_01_12_pinch_era.md"] = (
    "THE PINCH ERA — the gesture pipeline spec, §1–§12, verbatim",
    "history · the trained-classifier pipeline and the whole pinch arc",
    "`GESTURE_PIPELINE_SPEC.md` §1, §3–§12.7",
    "⛔ **Archived direction** (2026-08-01) — code, corpus and weights kept, not\n"
    "deleted. ⭐ Still worth reading for §12.7's generalised lessons and for the\n"
    "four-stage method, which is unchanged and now lives in\n"
    "[`../spec/GESTURE_DEV_WORKFLOW.md`](../spec/GESTURE_DEV_WORKFLOW.md).")

T["10_HAND_TRACKING/history/T6_INVESTIGATION_LOG.md"] = (
    "T6 — the orientation investigation, verbatim",
    "history · §2.0–§2.0.19, twenty sections of measurement on the yaw lean",
    "`HANDOFF_T6_ORIENTATION_FROM_2D.md` §2.0–§2.0.19",
    "⭐⭐ **Read §2.0.4 before proposing any rotation fix** — *where three rejects\n"
    "leave it*. The short version: **Horn's flaw is BIAS, every per-frame\n"
    "replacement's flaw is VARIANCE.** ⚠ Also here: the Google patents, the\n"
    "distortion measured at source, and the anisotropic fit's derivation.")

T["10_HAND_TRACKING/history/T6_REJECTED_REMEDY.md"] = (
    "T6 — the proposed fix and what happened to it, verbatim",
    "history · the planar-PnP remedy, its costs, and the execution record of all 8 steps",
    "`HANDOFF_T6_ORIENTATION_FROM_2D.md` §3, §4, §9",
    "⛔⛔ **A10-REJECTED 2026-08-24.** Kept for §9's execution record, which holds\n"
    "several findings that outlived the remedy: the FOV sensitivity owed to `U12`,\n"
    "the inverted convention constant caught only by measurement, and the LCG\n"
    "noise-source trap. The **diagnosis** is\n"
    "[`../spec/ORIENTATION_DIAGNOSIS.md`](../spec/ORIENTATION_DIAGNOSIS.md).")

T["10_HAND_TRACKING/spec/GESTURE_DEV_WORKFLOW.md"] = (
    "HOW A NEW GESTURE GETS BUILT",
    "live · the core discipline, and the four-stage workflow for any new gesture",
    "`GESTURE_PIPELINE_SPEC.md` §2 + `PART_ONE.md` §8",
    "⭐ **Still current and still binding**, even though the pinch gesture it was\n"
    "written for is archived. §2's *no heuristic pile-up* is restated in\n"
    "[`../../00_CORE/METHOD.md`](../../00_CORE/METHOD.md).")

T["10_HAND_TRACKING/spec/OPEN_QUESTIONS.md"] = (
    "OPEN QUESTIONS — to resolve empirically, not now",
    "live · questions deliberately parked until evidence exists",
    "`PART_ONE.md` §5",
    "⚠ These are **not** queue items. A question here becomes a row in\n"
    "[`../../00_CORE/QUEUE.md`](../../00_CORE/QUEUE.md) only when it is worth\n"
    "measuring.")

T["10_HAND_TRACKING/spec/ORIENTATION_DIAGNOSIS.md"] = (
    "THE YAW LEAN — the defect and its cause",
    "live · the open show-stopper, and what is proven about it",
    "`HANDOFF_T6_ORIENTATION_FROM_2D.md` §1–§2",
    "⭐⭐ **THE DIAGNOSIS BELOW STILL STANDS. THE REMEDY IT WAS WRITTEN FOR DOES\n"
    "NOT** — T6 was built and A10-rejected on 2026-08-24, and the file's own banner\n"
    "says so. ⚠⚠ One amendment the banner records: the premise *\"the 2D landmarks\n"
    "are good\"* was an **inference from roll**, and roll was measured with Horn over\n"
    "**world** landmarks — T6 was the first direct test of 2D-only pose and it was\n"
    "worse. ⛔ Before proposing anything here, read\n"
    "[`../REJECTED.md`](../REJECTED.md) and\n"
    "[`../history/T6_INVESTIGATION_LOG.md`](../history/T6_INVESTIGATION_LOG.md)\n"
    "§2.0.4.")

T["10_HAND_TRACKING/spec/PART_ONE_SCOPE_AND_MATRIX.md"] = (
    "SCOPE, ARCHITECTURE DECISIONS, AND THE GESTURE/SIGNAL MATRIX",
    "live · what Part One covers, its core architecture calls, and the gesture matrix",
    "`PART_ONE.md` §1–§3 and the S1–S12 literature index",
    "⭐ §2's architecture decisions — sticky grab, shared-registry arbitration,\n"
    "image-space translation, depth-proxy over raw z, quaternion rotation — are\n"
    "**unchanged and still apply**. The matrix in §3 is meant to be enriched as\n"
    "gestures are added.")

T["10_HAND_TRACKING/spec/PERCEPTION_LAYER_SPEC.md"] = (
    "PERCEPTION LAYER — the forward design",
    "live · the target architecture, `HandState` v2, modules M0–M10, test protocol",
    "`PERCEPTION_LAYER_SPEC.md` header, §0.0, §0.1, and §0–§10",
    "⚠⚠ **READ §0.1's AMENDMENT LOG BEFORE ANY MODULE BODY.** Several modules were\n"
    "amended, re-pointed or killed after they were written, and the log is what says\n"
    "which. The dated build record is\n"
    "[`../history/PERCEPTION_SESSION_LOG.md`](../history/PERCEPTION_SESSION_LOG.md).")

T["10_HAND_TRACKING/spec/RECORDING_WORKFLOW.md"] = (
    "RECORDING & ANALYSIS WORKFLOW",
    "live · how a take is made, annotated and replayed",
    "`PART_ONE.md` §7–§7.2",
    "⚠ Recordings go to `E:`, never `--local`, and the drive must be woken first\n"
    "(`wake_e_drive.py`). ⛔ The corpus holds **no image data** — landmarks only.")

T["10_HAND_TRACKING/spec/ROTATION_ACCEPTANCE_AND_TRAPS.md"] = (
    "ROTATION — the acceptance bar, the traps, and the takes",
    "live · what any rotation change must beat, and how not to be fooled measuring it",
    "`HANDOFF_T6_ORIENTATION_FROM_2D.md` §5–§8",
    "⭐⭐ **Reusable, and the most useful page here for `F1`.** §5 is the baseline\n"
    "table (yaw 14.5° / lean 23.4° / pitch 5.5° / roll 6.7° / jitter p95 25.41°),\n"
    "§6 what is already rejected, **§7 the six measurement traps — every one hit for\n"
    "real**, §8 which take to use for which axis and which to distrust.\n"
    "⚠ Cross-take absolute axis numbers are not comparable: the camera moved between\n"
    "recordings. Same-take A/B is sound.")

T["10_HAND_TRACKING/spec/SPEC_13_snap_rotate_release.md"] = (
    "SNAP / TRANSLATE / ROTATE / RELEASE — §13",
    "live · the current gesture set's design, build record and the mesh-generic renderer",
    "`GESTURE_PIPELINE_SPEC.md` §13–§13.8",
    "⭐ The pivot away from pinch, and everything that shipped after it. ⚠ §13.6.1 is\n"
    "the production-only inversion that passed an \"end-to-end confirmed\" claim while\n"
    "shipped inverted — the origin of the *automated green is not sufficient* rule.")

T["10_HAND_TRACKING/spec/SPEC_14_manipulation.md"] = (
    "MANIPULATION — §14: translation, depth, the yaw investigation, the lag",
    "live · grab-relative translation, Z-axis, 4.2, and the rotation lag fix",
    "`GESTURE_PIPELINE_SPEC.md` §14–§14.3.6",
    "⭐ The most-cited spec file. **§14.1** grab-relative translation · **§14.2** the\n"
    "release trigger · **§14.3** Z-axis · **§14.3.4–§14.3.4.11** the yaw-lean\n"
    "investigation · **§14.3.5** what 4.2 shipped · **§14.3.6** the lag.\n"
    "⚠ When two sections conflict, **the later one wins**.")

T["10_HAND_TRACKING/spec/SPEC_16_blocks.md"] = (
    "THE BLOCK REPRESENTATION — §15–§16",
    "live · the palm transform + finger arcs, and the six-arm anchor decision",
    "`GESTURE_PIPELINE_SPEC.md` §15–§16.17",
    "⭐ **§16.17 is binding**: *a jump both estimators reproduce is already in the\n"
    "landmarks* — which is why T1/T2 belong to the landmark layer and no further\n"
    "estimator work will touch them. ⚠ **§16.14 is RETRACTED** — the metric was\n"
    "self-measuring.")

T["10_HAND_TRACKING/spec/WIRE_PROTOCOL.md"] = (
    "THE WIRE — what the socket actually carries",
    "live · the landmark packets between server and client",
    "`PART_ONE.md` §4",
    "⭐ The gap this section originally described is **closed**: the wire *does*\n"
    "carry `world_landmarks` (`hands_world`, 21×3 per hand, sent before each\n"
    "`hands` packet). Relevant to the port —\n"
    "[`../../50_PORT_WEB_MOBILE/INDEX.md`](../../50_PORT_WEB_MOBILE/INDEX.md).")

T["30_OBJECTS_3D/ORIGINAL_SPEC_PIPELINE_B.md"] = (
    "PIPELINE B — Three.js scene + Blender asset pipeline, verbatim",
    "reference · the original 3D asset plan",
    "`Specification.md` §8",
    "⚠ Written in the Part Zero era and **never built**. It is the starting point\n"
    "for `U2`, which is postponed on the platform decision — see\n"
    "[`INDEX.md`](INDEX.md).")

T["40_INPUT_SYSTEM/SPEC_17_input_system.md"] = (
    "THE INPUT SYSTEM — §17, the record",
    "live · what was built, what was deliberately not, and why",
    "`GESTURE_PIPELINE_SPEC.md` §17–§17.7",
    "⭐ **§17.2** is the decision that made it shippable in one session (it observes,\n"
    "it does not drive); **§17.5** is why the estimator modules were *not* moved into\n"
    "the package; **§17.7** is what is explicitly not done. Usage doc:\n"
    "`Local_pc/Movement_with_hand_detection/handinput/README.md`.")

T["50_PORT_WEB_MOBILE/ORIGINAL_SPEC_PORT_SECTIONS.md"] = (
    "THE ORIGINAL PORT PLAN — verbatim",
    "reference · Part Zero, Part Zero-bis, the landmark data contract, Snap Spectacles",
    "`Specification.md` §4, §5, §6, §12",
    "⭐ §6's **shared landmark data contract** is the ancestor of `HandState` v2 and\n"
    "is still the right frame for the port. §12 (Snap Spectacles) is design-for-later\n"
    "only, not in scope.")

T["60_SECURITY_COMPLIANCE/ORIGINAL_SPEC_PRIVACY.md"] = (
    "CAMERA PERMISSIONS & CYBERSECURITY — the original requirements, verbatim",
    "reference · the browser permission UX, and the standing security requirement",
    "`Specification.md` §9–§10",
    "⚠ Written before the audience decision. **COPPA/GDPR-K now apply** and the\n"
    "requirements below are a floor, not the position — see [`INDEX.md`](INDEX.md).")

T["60_SECURITY_COMPLIANCE/SPEC_18_security_audit.md"] = (
    "ROBUSTNESS & SECURITY AUDIT — §18",
    "live · what was already right, what was fixed, and what was deliberately not",
    "`GESTURE_PIPELINE_SPEC.md` §18–§18.5",
    "⭐ **§18.1 is the compliance evidence** — no network egress anywhere, verifiable\n"
    "by absence. ⚠⚠ **§18.4 is a retraction made the same day**, and it carries the\n"
    "audit's own lesson: an audit is not exempt from A10 because its findings are\n"
    "code-shaped.")

T["_archive/README_2026-08-25_pre_reorg.md"] = (
    "THE PRE-REORGANISATION README — verbatim",
    "archive · the single-file map as it stood before 2026-08-25",
    "`README.md` at commit 3d44c9a",
    "⛔ **SUPERSEDED.** Kept whole as the safety net for the reorganisation: every\n"
    "fact in it was redistributed into the new `00_CORE/` and `INDEX.md` files.\n"
    "The live router is [`../README.md`](../README.md).")


def block(title, status, source, note, nl):
    lines = ["# %s" % title, "",
             "> **%s**" % status,
             "> **SOURCE** · %s — extracted verbatim, not edited" % source,
             ""]
    lines += note.split("\n") + ["", "---", ""]
    return nl.join(s.encode("utf-8") for s in lines) + nl


n = 0
for rel, (title, status, source, note) in T.items():
    path = os.path.join(*rel.split("/"))
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"# "):
        continue
    nl = b"\r\n" if raw.count(b"\r\n") else b"\n"
    with open(path, "wb") as fh:
        fh.write(block(title, status, source, note, nl) + raw)
    n += 1
print("titled %d files" % n)
