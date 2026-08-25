"""Session-name safety -- one definition, shared by both recorders (N6).

⚠⚠ THE DEFECT THIS CLOSES (audit, 2026-08-25). Three places build a filesystem
path out of a name the operator supplies, and none of them checked it:

    HandsTriggeredActions._record_open   os.path.join(root, f"{stamp}_{tag}")   VISION_RECORD_TAG
    LiveSnapDebug.main                   os.path.join(root, f"{stamp}_{tag}")   --tag
    handinput/trace.py                   os.path.join(root, f"{stamp}_{tag}")   HANDINPUT_TRACE_TAG

A tag of `..\\..\\somewhere` writes the session OUTSIDE the capture root, and a
tag containing `:` or `*` -- both legal in a shell argument, neither legal in a
Windows filename -- fails with an OSError that reads like a broken drive rather
than a bad name. ⭐ Neither is an attack in a single-user desktop tool; both are
the kind of unchecked path construction that a store or security review flags,
and the fix is four lines.

⛔ IT IS *NOT* A SUBSTITUTE FOR THE CAPTURE-ROOT PREFLIGHT. `LiveSnapDebug`
already probes the root for writability BEFORE the first frame, because a take
discarded at save time costs the operator the whole session (learned on
2026-08-02). This only makes sure the name cannot point somewhere else.

⚠ REJECT-AND-SUBSTITUTE, NOT SILENT REPAIR. An unusable tag is replaced by a
visibly marked fallback and a printed warning, so a recording never lands under a
name the operator did not choose while believing it did. A recording whose name
lies about the take is worse than a refused one.
"""
import re

# Everything except letters, digits, dash and underscore becomes `_`. ⚠ The
# separators are the point: `/`, `\` and `:` are what make a tag a PATH instead
# of a name, and dots are collapsed so `..` cannot survive in any form.
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")

MAX_TAG_LEN = 60          # Windows' MAX_PATH is 260 for the WHOLE path, and the
                          # capture root is already ~70 characters of it.


def safe_tag(tag, fallback="session"):
    """A filename-safe session tag. Returns `fallback` if nothing usable is left.

    >>> safe_tag("prod_tau20")
    'prod_tau20'
    >>> safe_tag(r"..\\..\\etc")
    'etc'
    >>> safe_tag("../../")
    'session'
    """
    cleaned = _UNSAFE.sub("_", str(tag or "")).strip("_")
    if not cleaned:
        return fallback
    return cleaned[:MAX_TAG_LEN]


def check_tag(tag, fallback="session"):
    """`(safe, was_changed)` -- so a caller can WARN rather than silently rename."""
    safe = safe_tag(tag, fallback)
    return safe, safe != str(tag or "")
