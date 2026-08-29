# READ THIS FIRST — the router

⭐ **This file is a ROUTER, not a status page.** It tells you which folder to
load and nothing else. It must stay about one screen long. If you find yourself
adding a finding here, it belongs in a folder's `INDEX.md`.

⛔ **THE BUILD QUEUE IS [`00_CORE/QUEUE.md`](00_CORE/QUEUE.md) AND NOWHERE ELSE.**
One list, every subsystem, tagged by `Sub`. Do not start a second one in a
subsystem folder.

---

## Load recipes — tell a new conversation exactly this

| you are… | load |
|---|---|
| **building anything** | `Claude/00_CORE/` — always. It is small |
| working on **hand tracking / gestures / rotation** | `+ Claude/10_HAND_TRACKING/INDEX.md` (and `REJECTED.md` before proposing a fix) |
| changing **how the game behaves** | `+ Claude/20_GAME_RULES/` |
| ⭐ **object ASSEMBLY / mate connectors**, 3D import, meshes, rendering | `+ Claude/30_OBJECTS_3D/` |
| plugging the hand system into **another game, a lens, a port** | `+ Claude/40_INPUT_SYSTEM/` |
| doing the **web / mobile port** | `+ Claude/50_PORT_WEB_MOBILE/` |
| touching **privacy, dependencies, packaging, stores** | `+ Claude/60_SECURITY_COMPLIANCE/` |

⚠ Load a `spec/` or `history/` file **only when an INDEX points you at it by
name.** They are the record, not the briefing.

---

## The folders

| | |
|---|---|
| [`00_CORE/`](00_CORE/) | cross-cutting and always relevant: [`CHARTER`](00_CORE/CHARTER.md) (what/for whom) · [`CONSTRAINTS`](00_CORE/CONSTRAINTS.md) (what a build may not violate) · [`METHOD`](00_CORE/METHOD.md) (how anything gets decided) · [`QUEUE`](00_CORE/QUEUE.md) (**the** build list) · [`DECISIONS`](00_CORE/DECISIONS.md) · [`GLOSSARY`](00_CORE/GLOSSARY.md) · `queue_notes/` (each row's full history) |
| [`10_HAND_TRACKING/`](10_HAND_TRACKING/) | webcam → the object's transform. Perception, identity, chirality, snap / translate / rotate / release, depth |
| [`20_GAME_RULES/`](20_GAME_RULES/) | how the game behaves, in plain language — the behavioural record |
| [`30_OBJECTS_3D/`](30_OBJECTS_3D/) | ⭐ **active since 2026-08-28** — object assembly by mate connectors; also 3D import, meshes, rendering |
| [`40_INPUT_SYSTEM/`](40_INPUT_SYSTEM/) | `handinput` — the pipeline as a shippable input package |
| [`50_PORT_WEB_MOBILE/`](50_PORT_WEB_MOBILE/) | ⚠ deferred — Part Zero-bis is done, `U3` is not |
| [`60_SECURITY_COMPLIANCE/`](60_SECURITY_COMPLIANCE/) | privacy, minors, the audit, store submission |
| [`_archive/`](_archive/) | never loaded. Dead documents, and the migration's own proof |

---

## Where it stands, in five lines

⭐⭐⭐ **BRANCH `1.7.42-` IS A REBUILD FROM THE LANDMARKS UP** (2026-08-29). The
rotation stack had accumulated into a **REFLECTION** (det −1), which no rigid
hand→object mapping can be, so it is being rebuilt one measured step at a time:
[`10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`](10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md).
`RB0`–`RB2` built. ⚠ Archive of the old build: commit `4dd0fc5`.


✅✅ **`AS1`–`AS9`, OBJECT ASSEMBLY BY MATE CONNECTORS, IS SHIPPED** (2026-08-28) —
one production run closed it and `V2`'s long-owed production look together.
⛔⛔ **BUT `V2` RE-OPENED ON 2026-08-29 AND IS THE ONE THING OWED**: a **double-cover**
defect in the shipped trim (a 15° turn read as −345°, so `authority` reached **1.0 on
pure PITCH gestures that must receive none**), found while measuring *where* rotation
is accurate. ✅✅ The fix is **bit-identical on yaw and roll**, so it cannot regress
what was accepted live — but only a live look closes a change.
⭐⭐ **WHERE EACH AXIS IS ACCURATE, measured 2026-08-29**: **ROLL is the precision
axis** (usable from ~5°, gain ~1.00 throughout) · **YAW is 10–40° for direction and
60–90° for amount, and no band gives both** · ⛔ **PITCH has no reliable range below
~50–60°** (±29° p95 wobble while the hand is still).
✅ **The YAW LEAN is corrected** — the owner's show-stopper from 2026-08-22 (~27° at a
60–90° turn); `V2` is the fifth attempt and the first to survive live. ⚠ Corrected,
not eliminated: its gate is cleared on 3 of 4 takes.
✅ Also shipped and live: **`F1`** (the object carried by the fingertip barycentre),
**`R1`** (depth-ordered occlusion in both tools), **`V1`** (the camera mount — the
default is `facing_user`).
⚠ **What shipping did NOT close**: `AS2`'s acceptance metric is unmeasured and
**cannot be measured until the recorders carry mate state**; the preview radius has
no measured floor; the object tree has only ever held two objects; renderer parity
is unguarded.
⭐⭐⭐ **TWO METHOD RULES WERE ADDED 2026-08-29 and they bind every future suite**: a
**golden vector must feed the representations the product actually produces, not only
the canonical one**; and **`parity_replay` is blind to any defect in a SHARED module**
— it proves the two tools match, never that either is right.
⭐⭐ **THE PLATFORM DECISION IS DUE AND IT IS THE OWNER'S** — sequenced right after
`F1`, which shipped three sessions ago. `U2`, `U12`, `T7` and the game layer are all
waiting behind it, and no amount of building advances it.
Full status: [`00_CORE/QUEUE.md`](00_CORE/QUEUE.md)'s YOU-ARE-HERE block.
Full narrative: [`10_HAND_TRACKING/history/SESSION_LOG.md`](10_HAND_TRACKING/history/SESSION_LOG.md).

---

## ⛔ Every update must PRESERVE this tiered architecture

> **Owner, 2026-08-25:** *"any update to the md files shall preserve this tiered
> architecture."* **Binding on every doc edit from here on**, not just on the
> session that built it.

1. **State lives in `INDEX.md` and topic files; narrative lives in `history/`.**
   The old docs grew to 1.3 MB because they mixed the two. A session's story goes
   to the session log the same day; the INDEX gets **one updated line**.
2. **Nothing in `spec/` or `history/` is ever rewritten to save space.** It is
   the record. Distil *into* a new file instead, and cite what you distilled.
3. **Cap the front doors.** `INDEX.md` ≤ 400 lines, a topic file ≤ 800. Hitting
   the cap is the signal to push narrative down a tier, not to keep appending.
   This file stays a router, about one screen — never a status page.
4. ⛔ **Never edit inside `<!-- VERBATIM-BEGIN/END -->` markers.** Those blocks
   are the byte-verified record; `_archive/migration/verify_split.py` fails if one
   is altered.
5. ⛔ **A queue row's status changes in TWO places or neither**: the one-line
   status in [`00_CORE/QUEUE.md`](00_CORE/QUEUE.md) **and** an append to its
   `00_CORE/queue_notes/<ID>.md` dossier. And **never a second queue.**

⭐ **The test before calling a doc change done:** could a fresh session answer
*"what is the state of X"* from `00_CORE/` plus one `INDEX.md` alone? If it needs
a `history/` file to know the **current** state, the fact is in the wrong tier.

---

## ⚠ Section numbers from before 2026-08-25

`§14.3.4.11`, `§16.17`, `PART_ONE.md §3.1` and friends still resolve — the
numbers were **not** changed, only the files they live in.
→ [`10_HAND_TRACKING/spec/SPEC_MAP.md`](10_HAND_TRACKING/spec/SPEC_MAP.md)

The reorganisation was mechanical and verified: every source file was rebuilt
from its scattered pieces and matched **byte-for-byte** before the original was
removed (`_archive/MIGRATION_MANIFEST.json`, `_archive/migration/`). The
pre-reorg `README.md` is kept whole at
[`_archive/README_2026-08-25_pre_reorg.md`](_archive/README_2026-08-25_pre_reorg.md).

**Docs that deliberately live with the code, not here** (rule `N6` — imported,
never copied): `Local_pc/Movement_with_hand_detection/analysis/README.md` (every
claim → its script) and `.../handinput/README.md` (the package's own usage doc).
