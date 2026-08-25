"""Check every relative markdown link in Claude/, ignoring VERBATIM blocks."""
import os
import re
import sys

CLAUDE = os.path.abspath(sys.argv[1])
BEGIN = re.compile(r"<!-- VERBATIM-BEGIN -->\r?\n")
END = re.compile(r"<!-- VERBATIM-END -->\r?\n")
LINK = re.compile(r"\]\(([^)]+)\)")

bad, checked = [], 0
for root, dirs, files in os.walk(CLAUDE):
    for f in sorted(files):
        if not f.endswith(".md"):
            continue
        path = os.path.join(root, f)
        text = open(path, encoding="utf-8", errors="replace").read()
        # strip every verbatim block
        out, pos = [], 0
        while True:
            b = BEGIN.search(text, pos)
            if not b:
                out.append(text[pos:])
                break
            out.append(text[pos:b.start()])
            e = END.search(text, b.end())
            pos = e.end() if e else len(text)
        live = "".join(out)
        for target in LINK.findall(live):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = target.split("#")[0]
            if not target:
                continue
            checked += 1
            dest = os.path.normpath(os.path.join(root, target))
            if not os.path.exists(dest):
                bad.append((os.path.relpath(path, CLAUDE).replace("\\", "/"), target))

print("checked %d relative links in Claude/" % checked)
if bad:
    print("BROKEN: %d" % len(bad))
    for src, t in bad:
        print("   %-58s -> %s" % (src, t))
    sys.exit(1)
print("all resolve")
