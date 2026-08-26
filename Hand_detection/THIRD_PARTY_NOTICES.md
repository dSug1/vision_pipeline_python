# THIRD-PARTY NOTICES

> **STATUS** · ✅ **complete 2026-08-26** — every component attributed, the one
> pending copyright line verified upstream
> **OWNS** · the attribution that must travel with every distributed build
> **READ IF** · you are packaging, exporting, porting, or adding a dependency
> **QUEUE ROW** · [`SEC6`](Claude/00_CORE/queue_notes/SEC6.md) · **BINDING RULE** ·
> [`N13`](Claude/00_CORE/queue_notes/N13.md)

This product includes third-party software. Each component below is listed with
its licence, and the full licence texts are bundled in [`licenses/`](licenses/).

⛔⛔ **WHY THIS FILE EXISTS, AND WHY A SOURCE COMMENT WAS NOT ENOUGH.** Every
component here is already attributed *in the source that uses it* — the BSD-3
notice sits in `Resources/one_euro.py`'s module docstring, MediaPipe's licence
ships in its wheel. That satisfies the licences **while the source is what
ships**. It does **not** survive the three things this project is committed to:

* a **minified web bundle** (`U3`, and `Web/` already builds one with Vite),
* a **compiled or packaged native build** (`U11`, "shipping-build hygiene"),
* a **store submission**, where the notices are a listed submission artifact.

⭐ BSD-3 clause 2 and Apache-2.0 §4(d) both attach to *binary* redistribution
specifically. A docstring is erased by exactly the step that makes the obligation
bite. **This file is the artifact that must be shipped alongside the binary.**

---

## Components

| component | used by | version | licence | full text |
|---|---|---|---|---|
| **1€ Filter** (One Euro Filter) — Casiez, Roussel & Vogel | `Resources/one_euro.py` — **transliterated**, not imported | reference impl. | **BSD-3-Clause** | [`licenses/BSD-3-Clause.txt`](licenses/BSD-3-Clause.txt) |
| **MediaPipe** (Python) | the desktop pipeline | `0.10.14` | **Apache-2.0** | [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt) |
| **MediaPipe `@mediapipe/tasks-vision`** | `Web/` | `1.0.0` | **Apache-2.0** | [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt) |
| **`hand_landmarker.task`** — the bundled model | both platforms | — | **Apache-2.0** | [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt) |
| **three.js** | `Web/` | `0.185.1` | **MIT** | [`licenses/MIT.txt`](licenses/MIT.txt) |

⭐ The model's licence is on **Google's own authority**, not a third-party
assertion — the Model Card states *"LICENSED UNDER Apache License, Version 2.0"*.
Evidence is archived at `Claude/60_SECURITY_COMPLIANCE/evidence/`. See `N13`.

---

## 1€ Filter — BSD-3-Clause

Casiez, G., Roussel, N. and Vogel, D. (2012). *"1€ Filter: A Simple Speed-based
Low-pass Filter for Noisy Input in Interactive Systems."* CHI '12.
Reference implementation: <https://github.com/casiez/OneEuroFilter>

`Resources/one_euro.py` is a **transliteration** of that algorithm into
dependency-free Python, so the BSD-3 obligation applies to it exactly as if the
code had been copied: the notice, the conditions and the disclaimer must travel
with every copy, source or binary.

```
Copyright 2023 Inria
```

⭐ **Verified 2026-08-26 against the upstream licence**, not guessed:
<https://github.com/casiez/OneEuroFilter/blob/main/python/LICENSE> — fetched
twice, byte-consistent both times. ⚠ **It is at `python/LICENSE`, NOT the repo
root**; the root path 404s, which is what left this line blank when the file was
first drafted. Record the path, or the next person repeats the dead end.

Licence conditions in force (full text: [`licenses/BSD-3-Clause.txt`](licenses/BSD-3-Clause.txt)):

1. Source redistribution retains the copyright notice, conditions and disclaimer.
2. **Binary redistribution reproduces them in the documentation or other
   materials** — that obligation is what this file discharges.
3. ⛔ **No endorsement.** The names of the copyright holder and contributors may
   not be used to promote this product. So marketing copy must not say or imply
   that the authors, Inria, or any affiliated institution endorse this game.

---

## MediaPipe and the hand-landmarker model — Apache-2.0

Copyright The MediaPipe Authors. Licensed under the Apache License, Version 2.0
(the "License"); you may not use these files except in compliance with the
License. You may obtain a copy of the License at
<http://www.apache.org/licenses/LICENSE-2.0>, and a copy is bundled at
[`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt).

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an **"AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND**, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

⭐ **The model and the WASM runtime are BUNDLED, not hot-linked**, on both
platforms — verified under `N13`. That is a licence-adjacent decision but not a
licence one: Google's *API terms* would apply to the hosted endpoint regardless
of the model's own licence.

⚠ Apache-2.0 §4(b) requires that modified files carry prominent notices of
change. Nothing here modifies MediaPipe; it is consumed as a dependency.

---

## three.js — MIT

Copyright © 2010-2025 three.js authors. Full text:
[`licenses/MIT.txt`](licenses/MIT.txt). MIT requires the copyright notice and
permission notice in all copies or substantial portions — including the built
bundle.

---

## ⛔ Rules for keeping this file true

1. **A new dependency lands with its notice in the same commit.** `N13` already
   requires the licence to be *checked and stated* before a package is proposed;
   this file is where the answer gets recorded.
2. ⚠ **`handinput/export_package.py` does not copy this file yet.** The exported
   standalone package carries `Resources/one_euro.py`'s docstring notice, which
   satisfies BSD-3 for a **source** export — so this is not a live breach. It
   becomes one the moment an export is built or minified. Tracked on `SEC6`.
3. ⚠ **`one_euro.py` is not in `handinput/manifest.py`'s `MODULES` yet** — `F1`
   step 2 is what will consume it. When it joins the package, this row and the
   export copy above must be revisited together.
4. **Verify at package time, not only here.** `U11` is the shipping-hygiene row;
   this file is an input to it, not a substitute for it.
