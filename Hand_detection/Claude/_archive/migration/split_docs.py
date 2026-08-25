"""Mechanical, verifiable split of Claude/*.md into the new folder structure.

Every source file is TILED into line ranges that cover 1..N exactly once.
Each range is written VERBATIM (bytes untouched) into its destination between
markers.  The verifier then walks the ranges in source order, pulls the matching
verbatim block back out of each destination, concatenates, and compares BYTES
against the original.  Any edit, reorder or dropped line fails the run.
"""

import io
import json
import os
import re
import sys

CLAUDE = os.path.abspath(sys.argv[1])
COMMIT = sys.argv[2]

BEGIN = b"<!-- VERBATIM-BEGIN -->\n"
END = b"<!-- VERBATIM-END -->\n"


def read_lines(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return data, data.splitlines(keepends=True)


# --------------------------------------------------------------------------
# the tiling plan:  source -> [(first_line, last_line, destination), ...]
# --------------------------------------------------------------------------
PLAN = {}

PLAN["GESTURE_PIPELINE_SPEC.md"] = [
    (1, 63, "10_HAND_TRACKING/history/SPEC_01_12_pinch_era.md"),
    (64, 80, "10_HAND_TRACKING/spec/GESTURE_DEV_WORKFLOW.md"),
    (81, 2674, "10_HAND_TRACKING/history/SPEC_01_12_pinch_era.md"),
    (2675, 3463, "10_HAND_TRACKING/spec/SPEC_13_snap_rotate_release.md"),
    (3464, 5331, "10_HAND_TRACKING/spec/SPEC_14_manipulation.md"),
    (5332, 6824, "10_HAND_TRACKING/spec/SPEC_16_blocks.md"),
    (6825, 6957, "40_INPUT_SYSTEM/SPEC_17_input_system.md"),
    (6958, None, "60_SECURITY_COMPLIANCE/SPEC_18_security_audit.md"),
]

PLAN["PERCEPTION_LAYER_SPEC.md"] = [
    (1, 300, "10_HAND_TRACKING/spec/PERCEPTION_LAYER_SPEC.md"),
    (301, 2189, "10_HAND_TRACKING/history/PERCEPTION_SESSION_LOG.md"),
    (2190, None, "10_HAND_TRACKING/spec/PERCEPTION_LAYER_SPEC.md"),
]

PLAN["HANDOFF_T6_ORIENTATION_FROM_2D.md"] = [
    (1, 104, "10_HAND_TRACKING/spec/ORIENTATION_DIAGNOSIS.md"),
    (105, 1139, "10_HAND_TRACKING/history/T6_INVESTIGATION_LOG.md"),
    (1140, 1246, "10_HAND_TRACKING/history/T6_REJECTED_REMEDY.md"),
    (1247, 1373, "10_HAND_TRACKING/spec/ROTATION_ACCEPTANCE_AND_TRAPS.md"),
    (1374, None, "10_HAND_TRACKING/history/T6_REJECTED_REMEDY.md"),
]

PLAN["Specification.md"] = [
    (1, 9, "10_HAND_TRACKING/history/ORIGINAL_HANDOFF.md"),
    (10, 62, "00_CORE/ORIGINAL_GOAL_AND_CONSTRAINTS.md"),
    (63, 238, "10_HAND_TRACKING/history/ORIGINAL_HANDOFF.md"),
    (239, 362, "50_PORT_WEB_MOBILE/ORIGINAL_SPEC_PORT_SECTIONS.md"),
    (363, 503, "10_HAND_TRACKING/history/ORIGINAL_HANDOFF.md"),
    (504, 552, "30_OBJECTS_3D/ORIGINAL_SPEC_PIPELINE_B.md"),
    (553, 623, "60_SECURITY_COMPLIANCE/ORIGINAL_SPEC_PRIVACY.md"),
    (624, 666, "10_HAND_TRACKING/history/ORIGINAL_HANDOFF.md"),
    (667, 719, "50_PORT_WEB_MOBILE/ORIGINAL_SPEC_PORT_SECTIONS.md"),
    (720, None, "00_CORE/ORIGINAL_GOAL_AND_CONSTRAINTS.md"),
]

PLAN["README.md"] = [
    (1, None, "_archive/README_2026-08-25_pre_reorg.md"),
]

# PART_ONE needs the queue table exploded row by row, so its plan is built below.
QUEUE_FIRST, QUEUE_LAST = 1158, 1262


def queue_row_id(line_bytes):
    text = line_bytes.decode("utf-8", "replace")
    if not text.startswith("|"):
        return None
    cell = text.split("|")[1]
    cell = cell.replace("*", "").replace("`", "").replace("~", "").strip()
    if not cell or cell.endswith("—") or " " in cell.strip(" "):
        # phase dividers look like "| **PHASE 0 - instrumentation** ||||||"
        return None
    if not re.fullmatch(r"[A-Za-z0-9._]+", cell):
        return None
    return cell


def build_part_one_plan(lines):
    plan = [
        (1, 61, "10_HAND_TRACKING/history/PART_ONE_ORIGINS.md"),
        (62, 222, "10_HAND_TRACKING/spec/PART_ONE_SCOPE_AND_MATRIX.md"),
        (223, 276, "00_CORE/queue_notes/_QUEUE_PREAMBLE.md"),
        (277, 1140, "10_HAND_TRACKING/history/SESSION_LOG.md"),
        (1141, 1157, "10_HAND_TRACKING/spec/PART_ONE_SCOPE_AND_MATRIX.md"),
    ]
    for n in range(QUEUE_FIRST, QUEUE_LAST + 1):
        rid = queue_row_id(lines[n - 1])
        if rid is None:
            dest = "00_CORE/queue_notes/_TABLE_SCAFFOLD.md"
        else:
            dest = "00_CORE/queue_notes/%s.md" % rid
        plan.append((n, n, dest))
    plan += [
        (1263, 1302, "10_HAND_TRACKING/spec/WIRE_PROTOCOL.md"),
        (1303, 1377, "10_HAND_TRACKING/spec/OPEN_QUESTIONS.md"),
        (1378, 1468, "10_HAND_TRACKING/history/PART_ONE_PINCH_ERA.md"),
        (1469, 1648, "10_HAND_TRACKING/spec/RECORDING_WORKFLOW.md"),
        (1649, None, "10_HAND_TRACKING/spec/GESTURE_DEV_WORKFLOW.md"),
    ]
    # merge consecutive ranges that share a destination
    merged = []
    for first, last, dest in plan:
        if merged and merged[-1][2] == dest and merged[-1][1] == first - 1:
            merged[-1] = (merged[-1][0], last, dest)
        else:
            merged.append((first, last, dest))
    return merged


def provenance(src, first, last):
    return (
        "<!-- PROVENANCE — machine-extracted, NOT edited.\n"
        "     source : Claude/%s lines %d-%d\n"
        "     commit : %s\n"
        "     when   : 2026-08-25 documentation reorganisation\n"
        "     Every byte between the VERBATIM markers below is exactly as it was.\n"
        "     The map of the new folder layout is Claude/README.md.\n"
        "-->\n" % (src, first, last, COMMIT)
    ).encode("utf-8")


def main():
    manifest = []
    written = {}           # dest -> list of byte chunks
    block_count = {}       # dest -> how many verbatim blocks so far

    for src in list(PLAN) + ["PART_ONE.md"]:
        path = os.path.join(CLAUDE, src)
        data, lines = read_lines(path)
        n = len(lines)
        plan = build_part_one_plan(lines) if src == "PART_ONE.md" else PLAN[src]
        plan = [(a, (n if b is None else b), d) for a, b, d in plan]

        # -- the tiling must cover 1..n exactly once, in order
        cursor = 1
        for first, last, _ in plan:
            assert first == cursor, "%s: gap/overlap at line %d (expected %d)" % (src, first, cursor)
            assert last >= first, "%s: empty range %d-%d" % (src, first, last)
            cursor = last + 1
        assert cursor == n + 1, "%s: plan stops at %d, file has %d lines" % (src, cursor - 1, n)

        for first, last, dest in plan:
            chunk = b"".join(lines[first - 1:last])
            assert END not in chunk and BEGIN not in chunk, "%s: marker collision" % src
            idx = block_count.get(dest, 0)
            block_count[dest] = idx + 1
            written.setdefault(dest, []).append(
                provenance(src, first, last) + BEGIN + chunk + END
            )
            manifest.append({"src": src, "first": first, "last": last,
                             "dest": dest, "block": idx})

    for dest, chunks in written.items():
        out = os.path.join(CLAUDE, dest)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as fh:
            fh.write(b"".join(chunks))

    with open(os.path.join(CLAUDE, "_archive", "MIGRATION_MANIFEST.json"), "w",
              encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)

    print("wrote %d destination files from %d ranges" % (len(written), len(manifest)))
    for dest in sorted(written):
        size = os.path.getsize(os.path.join(CLAUDE, dest))
        print("   %-62s %8d bytes  (%d block(s))" % (dest, size, block_count[dest]))


main()
