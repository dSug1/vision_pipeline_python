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
| doing **3D import / meshes / rendering** | `+ Claude/30_OBJECTS_3D/` |
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
| [`30_OBJECTS_3D/`](30_OBJECTS_3D/) | ⚠ seeded, not started — 3D import, meshes, rendering |
| [`40_INPUT_SYSTEM/`](40_INPUT_SYSTEM/) | `handinput` — the pipeline as a shippable input package |
| [`50_PORT_WEB_MOBILE/`](50_PORT_WEB_MOBILE/) | ⚠ deferred — Part Zero-bis is done, `U3` is not |
| [`60_SECURITY_COMPLIANCE/`](60_SECURITY_COMPLIANCE/) | privacy, minors, the audit, store submission |
| [`_archive/`](_archive/) | never loaded. Dead documents, and the migration's own proof |

---

## Where it stands, in five lines

✅✅ **`F1` and the rendering rebuild `R1` are SHIPPED (2026-08-27)** — the object is
carried by the fingertip barycentre, grabbed inside its projected footprint, and
occludes the hand by one depth rule in both tools. ⛔ The rotation **trim was
removed**, and `T6`'s two orientation builds were **live-rejected**: better on the
lean, worse on the tail — which has decided every verdict.
**Open show-stopper**: the **yaw lean** (~27° at a 60–90° hand turn), still unfixed.
⭐⭐ **`V1` — the CAMERA MOUNT — is BUILT (2026-08-28), default OFF, live look owed**:
yaw, pitch and z-translation read backwards because the build is a hybrid of two
camera mountings. Run `CAMERA_MOUNT=facing_user` to try it.
**No other build is chosen.** ⭐ By [`00_CORE/DECISIONS.md`](00_CORE/DECISIONS.md)
the **platform decision** is now due — it was sequenced right after `F1`, and `F1` shipped.
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
