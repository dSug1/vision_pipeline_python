"""Prove the 2026-08-25 documentation split lost nothing — re-runnable forever.

For each source file that was split, this walks its ranges in source order, pulls
the matching VERBATIM block back out of the destination it was written to,
concatenates them, and compares the sha256 against the digest recorded in
MIGRATION_MANIFEST.json when the originals still existed.

    python _archive/migration/verify_split.py            # run from Claude/

Exit 0 means every original is still fully present, byte for byte, scattered
across the new folder structure. Anything else means a verbatim block was
edited, reordered or lost — which is a bug, not a style change: the blocks are
the record. Edit the distilled files instead.
"""

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE = os.path.abspath(os.path.join(HERE, "..", ".."))
MANIFEST = os.path.join(CLAUDE, "_archive", "MIGRATION_MANIFEST.json")

# ⚠ The marker LINE's own ending is tolerated as either LF or CRLF: git runs with
# core.autocrlf=true here, so a checkout rewrites it. The bytes BETWEEN the
# markers are compared exactly and are not normalised.
BEGIN = re.compile(rb"<!-- VERBATIM-BEGIN -->\r?\n")
END = re.compile(rb"<!-- VERBATIM-END -->\r?\n")


def blocks_of(path):
    with open(path, "rb") as fh:
        data = fh.read()
    out, pos = [], 0
    while True:
        b = BEGIN.search(data, pos)
        if not b:
            break
        e = END.search(data, b.end())
        if not e:
            raise SystemExit("unterminated VERBATIM block in %s" % path)
        out.append(data[b.end():e.start()])
        pos = e.end()
    return out


def main():
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    ranges = manifest["ranges"]
    originals = manifest["originals"]

    by_src = {}
    for row in ranges:
        by_src.setdefault(row["src"], []).append(row)

    cache, ok = {}, True
    for src, rows in sorted(by_src.items()):
        rows.sort(key=lambda r: r["first"])
        rebuilt = b""
        for r in rows:
            dest = os.path.join(CLAUDE, r["dest"])
            if dest not in cache:
                cache[dest] = blocks_of(dest)
            rebuilt += cache[dest][r["block"]]
        want = originals[src]
        got = hashlib.sha256(rebuilt).hexdigest()
        same = (got == want["sha256"] and len(rebuilt) == want["bytes"])
        ok = ok and same
        print("%-42s %-16s %8d bytes  %d piece(s) across %d file(s)" % (
            src, "IDENTICAL" if same else "*** DIFFERS ***",
            len(rebuilt), len(rows), len({r["dest"] for r in rows})))
        if not same:
            print("      expected sha %s / %d bytes" % (want["sha256"][:16], want["bytes"]))
            print("      rebuilt  sha %s / %d bytes" % (got[:16], len(rebuilt)))

    claimed = {}
    for row in ranges:
        claimed.setdefault(row["dest"], set()).add(row["block"])
    for dest, blocks in sorted(cache.items()):
        rel = os.path.relpath(dest, CLAUDE).replace("\\", "/")
        if len(blocks) != len(claimed[rel]):
            print("*** %s holds %d blocks, the manifest claims %d"
                  % (rel, len(blocks), len(claimed[rel])))
            ok = False

    print()
    print("RESULT:", "ALL SOURCES REPRODUCE BYTE-FOR-BYTE"
          if ok else "*** MISMATCH — a verbatim block was altered ***")
    return 0 if ok else 1


sys.exit(main())
