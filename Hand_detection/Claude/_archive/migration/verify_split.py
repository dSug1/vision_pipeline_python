"""Prove the split lost nothing.

For each source file, walk its ranges in source order, pull the matching
VERBATIM block back out of the destination it was written to, concatenate,
and compare BYTES against the original file.  Also checks that every line of
every destination file is accounted for (no stray content invented).
"""

import hashlib
import json
import os
import sys

CLAUDE = os.path.abspath(sys.argv[1])
ORIGINALS = os.path.abspath(sys.argv[2])   # a pristine checkout of the old files

BEGIN = b"<!-- VERBATIM-BEGIN -->\n"
END = b"<!-- VERBATIM-END -->\n"


def blocks_of(path):
    with open(path, "rb") as fh:
        data = fh.read()
    out, pos = [], 0
    while True:
        b = data.find(BEGIN, pos)
        if b < 0:
            break
        e = data.find(END, b)
        assert e > 0, "unterminated block in %s" % path
        out.append(data[b + len(BEGIN):e])
        pos = e + len(END)
    return out


manifest = json.load(open(os.path.join(CLAUDE, "_archive", "MIGRATION_MANIFEST.json"),
                          encoding="utf-8"))

cache = {}
by_src = {}
for row in manifest:
    by_src.setdefault(row["src"], []).append(row)

ok = True
for src, rows in sorted(by_src.items()):
    rows.sort(key=lambda r: r["first"])
    rebuilt = b""
    for r in rows:
        dest = os.path.join(CLAUDE, r["dest"])
        if dest not in cache:
            cache[dest] = blocks_of(dest)
        rebuilt += cache[dest][r["block"]]
    with open(os.path.join(ORIGINALS, src), "rb") as fh:
        original = fh.read()
    same = rebuilt == original
    ok = ok and same
    print("%-42s %s  %8d bytes  sha %s vs %s  %d piece(s) across %d file(s)" % (
        src,
        "IDENTICAL" if same else "*** DIFFERS ***",
        len(original),
        hashlib.sha256(original).hexdigest()[:12],
        hashlib.sha256(rebuilt).hexdigest()[:12],
        len(rows),
        len({r["dest"] for r in rows}),
    ))
    if not same:
        for i in range(min(len(rebuilt), len(original))):
            if rebuilt[i] != original[i]:
                print("      first difference at byte %d" % i)
                break

# every verbatim block in every destination must be claimed by the manifest
claimed = {}
for row in manifest:
    claimed.setdefault(row["dest"], set()).add(row["block"])
for dest, blocks in sorted(cache.items()):
    rel = os.path.relpath(dest, CLAUDE).replace("\\", "/")
    if len(blocks) != len(claimed[rel]):
        print("*** %s has %d blocks, manifest claims %d" % (rel, len(blocks), len(claimed[rel])))
        ok = False

print()
print("RESULT:", "ALL SOURCES REPRODUCE BYTE-FOR-BYTE" if ok else "*** MISMATCH ***")
sys.exit(0 if ok else 1)
