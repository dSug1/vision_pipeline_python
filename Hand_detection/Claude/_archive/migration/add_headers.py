"""Prepend a short navigable header to each queue dossier.

BINARY MODE ON PURPOSE: the file's own line endings must not be touched. The
header goes ABOVE the first PROVENANCE comment, entirely outside the VERBATIM
markers, so verify_split.py still reproduces the source byte-for-byte.
"""
import glob
import os
import re

QN = "00_CORE/queue_notes"
SPLIT = re.compile(r'(?<!\\)\|')
BEGIN = re.compile(rb"<!-- VERBATIM-BEGIN -->\r?\n")
END = re.compile(rb"<!-- VERBATIM-END -->\r?\n")


def plain(s):
    return re.sub(r'\s+', ' ', re.sub(r'\*\*|\*|`|~~', '', s)).strip()


n = 0
for path in sorted(glob.glob(os.path.join(QN, "*.md"))):
    name = os.path.basename(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"# "):
        continue
    nl = b"\r\n" if raw.count(b"\r\n") else b"\n"

    if name == "_QUEUE_PREAMBLE.md":
        lines = ["# The queue's preamble — verbatim", "",
                 "> The governing rules of the build queue, exactly as they stood in",
                 "> `PART_ONE.md` §3.1 before the 2026-08-25 reorganisation.",
                 "> The queue itself is now [`../QUEUE.md`](../QUEUE.md).", "", "---", ""]
    elif name == "_TABLE_SCAFFOLD.md":
        lines = ["# The queue table's scaffolding — verbatim", "",
                 "> The header row and phase dividers of the original `PART_ONE.md` §3.1",
                 "> table, kept so the table reassembles exactly. The live queue is",
                 "> [`../QUEUE.md`](../QUEUE.md); each data row is its own file here.", "",
                 "---", ""]
    else:
        b = BEGIN.search(raw)
        e = END.search(raw, b.end())
        body = raw[b.end():e.start()].decode("utf-8").strip("\r\n")
        cells = [p.strip() for p in SPLIT.split(body)[1:-1]]
        rid = plain(cells[0]) if cells else name[:-3]
        item = plain(cells[1])[:120] if len(cells) > 1 else ""
        status = plain(cells[3])[:200] if len(cells) > 3 else ""
        lines = ["# `%s` — %s" % (rid, item), "",
                 "> **Dossier.** The full, unedited history of this queue row.",
                 "> Its one-line status and its place in the order are in",
                 "> [`../QUEUE.md`](../QUEUE.md) — update **both** when it changes.",
                 ">",
                 "> **Status when this file was created (2026-08-25):** %s" % status,
                 "", "---", ""]

    head = nl.join(s.encode("utf-8") for s in lines) + nl
    with open(path, "wb") as fh:
        fh.write(head + raw)
    n += 1

print("headers added to %d files (line endings untouched)" % n)
