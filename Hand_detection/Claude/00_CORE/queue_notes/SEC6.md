# `SEC6` — Third-party attribution notices at the SHIP boundary

> **Dossier.** The full, unedited history of this queue row.
> Its one-line status and its place in the order are in
> [`../QUEUE.md`](../QUEUE.md) — update **both** when it changes.
>
> **Status when this file was created (2026-08-26):** ⚠ DRAFTED — `THIRD_PARTY_NOTICES.md` + `licenses/` exist; one copyright line unverified; the export path does not carry them

---

<!-- PROVENANCE — authored 2026-08-26, NOT machine-extracted.
     This row did not exist before the 2026-08-25 reorganisation, so it has no
     VERBATIM block. It was opened by an owner licence question, recorded below.
-->

## Opened 2026-08-26 — the owner's question, and what it exposed

> **Owner, 2026-08-26:** *"is the 1euro filter license-free?"*

The answer is **yes for use** — but the question surfaced a gap that is not about
the 1€ filter at all, and would have surfaced at store submission instead.

⭐⭐ **THE FINDING: `N13` was clearing the INPUT side and nothing was clearing the
OUTPUT side.** `N13` is rigorous about *may we use this* — it killed `0.5`
(MANO/HaMeR/WiLoR), it chased the model bundle's licence to Google's own Model
Card rather than accept a third-party assertion, it caught that a permissive
licence on **code** does not cover **data** derived from research datasets. Every
one of those is an *acquisition* question.

⛔ **But permissive licences also impose a DISTRIBUTION duty, and nothing in the
project discharged it.** BSD-3 clause 2 and Apache-2.0 §4(d) attach specifically
to **binary** redistribution. The repo had:

* **no `LICENSE` file anywhere** (checked: `find -iname "*licen*"` outside
  `.venv`/`node_modules` returned two unrelated MSIX manifests from `_not_used/`),
* **no `THIRD_PARTY_NOTICES`**,
* attribution living **only** in source docstrings and in vendored wheel metadata.

⭐ **That is compliant today and stops being compliant at exactly the step this
project is committed to taking.** Source distribution is satisfied by a docstring.
A Vite bundle (`Web/` already builds one), a packaged native build (`U11`), or a
store submission is not — and the minifier erases the notice in the same pass
that creates the obligation.

## What landed 2026-08-26

| artifact | what it is |
|---|---|
| `Hand_detection/THIRD_PARTY_NOTICES.md` | the shippable notices file — 5 components, per-licence obligations spelled out |
| `Hand_detection/licenses/Apache-2.0.txt` | ⭐ **copied from the installed wheel**, not retyped — `mediapipe-0.10.14.dist-info/LICENSE` |
| `Hand_detection/licenses/BSD-3-Clause.txt` | the standard BSD-3 body |
| `Hand_detection/licenses/MIT.txt` | for `three` 0.185.1 (`Web/`) |

Components covered: **1€ filter** (BSD-3), **`mediapipe` 0.10.14** (Apache-2.0),
**`@mediapipe/tasks-vision` 1.0.0** (Apache-2.0), **`hand_landmarker.task`**
(Apache-2.0, on Google's own authority per `N13`), **`three` 0.185.1** (MIT).

## ⛔ Three things deliberately NOT done, and why

1. ⚠⚠ **The 1€ copyright line is LEFT BLANK, not guessed.** BSD-3 requires
   reproducing *the* upstream copyright notice. This session had no network
   access, so the holder line was **not** written from recollection. ⭐ **The
   project's own standard is the reason** — `N13` refused to accept third-party
   assertions about the model licence and chased the Model Card instead; `SEC5`
   was corrected the same day for letting a plausible mechanism become a recorded
   fact. A guessed copyright line in a legal notice is that failure mode with
   worse consequences, because the file *looks* authoritative. **One fetch of
   `github.com/casiez/OneEuroFilter/blob/main/LICENSE` closes it.**
2. **`handinput/export_package.py` was not changed to copy the notices.** The
   export is a **source** copy, so `one_euro.py`'s docstring notice satisfies
   BSD-3 there; adding a file-copy is real behaviour change to a shipped tool and
   is packaging work, which belongs with `U11`. Recorded, not silently patched.
3. **No project `LICENSE` was written.** That is the owner's choice — it declares
   the terms of *this* work, not a third party's, and nobody asked for one.

## ⚠ Interaction with `F1`

`one_euro.py` is **not yet in `handinput/manifest.py`'s `MODULES`** — `F1` step 2
is what will consume it. When it joins the exported package, item 2 above stops
being theoretical: an export would then carry BSD-3 code, and any minified build
of that export would carry it without a notice. **Revisit this row at `F1` step 2.**

## Acceptance

* ⛔ **Not closable by inspection.** It closes when a **built** artifact — a Vite
  bundle or a packaged native build — is shown to carry the notices, which means
  it closes with `U11`, not before.
* ✅ The drafting half is done and is what unblocks a submission from being
  started at all.

---

## Appended 2026-08-26 — ✅ THE PENDING COPYRIGHT LINE IS RESOLVED

`THIRD_PARTY_NOTICES.md` shipped with exactly one hole: the 1€ filter's upstream
copyright line, **deliberately left blank rather than guessed** because the
drafting session had no network. That was the right call — a wrong holder in a
notices file is worse than a missing one, since it reads as authoritative.

⭐ **Resolved 2026-08-26, verified rather than assumed:**

```
Copyright 2023 Inria
```

Fetched from <https://github.com/casiez/OneEuroFilter/blob/main/python/LICENSE>
**twice, byte-consistent both times**, and confirmed BSD-3-Clause.

⚠⚠ **THE PATH IS THE TRAP, AND IT IS NOW RECORDED IN BOTH PLACES.** The licence
is at **`python/LICENSE`**, not the repository root — `/LICENSE` and
`/main/LICENSE` both **404**, which is precisely the dead end that left the line
blank the first time. The notices file and `Resources/one_euro.py` now each name
the real path, so the next person does not repeat it.

✅ The line is now in **both** places the licence requires, which are different
obligations and not a duplication:

* **clause 1 (source)** — the module docstring of `Resources/one_euro.py`;
* **clause 2 (binary)** — `THIRD_PARTY_NOTICES.md`, the artifact that ships
  beside a minified or packaged build.

⚠ **Clause 3 is a live constraint on MARKETING, not on code**: no endorsement.
Copy must not say or imply that the authors or Inria endorse this game. Recorded
in both files so it is seen by whoever writes store text.

`THIRD_PARTY_NOTICES.md` moves **drafted → complete**.

⛔⛔ **BUT THE ROW DOES NOT MOVE TO DONE, AND THE DISTINCTION IS THE WHOLE POINT
OF ITS ACCEPTANCE BAR.** The *file* is complete; the *obligation* is discharged
only where the file actually travels. `SEC6` closes when a **built** artifact — a
Vite bundle or a packaged native build — is shown to carry the notices, which puts
it with `U11`. Still open, unchanged:

* **`handinput/export_package.py` does not copy the notices** — harmless for a
  source export, a breach the moment one is minified;
* **`one_euro.py` is not yet in `handinput/manifest.py`'s `MODULES`** — `F1` step 2
  is what puts BSD-3 code inside the exported package. **Revisit both together
  there.**

⭐ Status: **drafted → drafted-and-verified**, in this dossier and in
[`../QUEUE.md`](../QUEUE.md) — both, per the queue's own rule.
