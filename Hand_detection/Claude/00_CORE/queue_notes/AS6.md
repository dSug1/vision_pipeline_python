# `AS6` — release at mate, and re-arm on exit

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · BUILT 2026-08-28, both tools — ⛔ live look owed · **SUB** · 3D
> **KIND** · feature · **DEP** · `AS3`

Design of record:
[`../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md) §7bis.

---

## 2026-08-28 — opened BY THE FIRST LIVE RUN, and closed the same evening

> **Owner, after running the debug tool:** *"the smaller object must ungrab at snap
> otherwise the snap breaks immediately."*

⭐⭐ **The owner found this by LOOKING, on the first session, and every automated
check had passed.** 42 suites and four clean parity replays said the mate engaged,
held, re-rooted and broke correctly — because none of them had a hand that keeps
moving after contact.

## ⛔ Why it broke

With a cube in each hand **both objects are driven**, so `AS3`'s residual is real.
Nobody stops dead at the instant of contact, so the placing hand carries its cube's
DESIRE onward while the mate holds its rendered pose — and within a few frames the
residual passes the break threshold.

⭐ **The owner's fix is the stronger of the two the spec had on the table.** §7
proposed **re-seating the grab baseline**; that leaves **two authorities on one
transform** and merely agrees them for one instant. Releasing the child's grab
removes one authority, and §4.1 then makes the mate unbreakable by the survivor.

## ⛔⛔ The second problem it creates, and its name

The hand is still exactly where the object is, so the next frame's proximity snap
takes it straight back: **mate → release → re-grab → break → repeat.** That is the
**Midas touch** — unintended activation because the system cannot tell "over it"
from "taking it".

⭐⭐ **Buxton's three-state model (1990) names the constraint exactly: you cannot go
from State 2 (dragging) to State 2 — the transition must pass through State 1
(tracking).** There must be a state where the hand is over the object and not
holding it, and the system must be able to reach it.

## The mechanism, and why this one

**Positional re-arm**: after an automatic release, the hand that placed the object
must LEAVE it — past `REGRAB_RELEASE_FACTOR` × the grab radius, for `REGRAB_DWELL_MS`
— before it may take it again.

* the Midas-touch literature's own answer: *"leave the zone before it can
  re-trigger"*;
* the VR grasp literature's asymmetric thresholds (grab at ≥ 0.75, release at
  ≤ 0.25) exist for exactly this — *"when threshold values are too close together,
  the hand state will continuously bounce"*;
* ⭐⭐ **the shape this project has already paid for twice**: `U9`'s two hand-side
  TRIGGERS were built and reverted before a POSITIONAL rule shipped, and `METHOD`
  keeps the lesson as *"a trigger cannot enforce an invariant"*;
* **self-clearing** — a player who stands still keeps their assembly, which a
  cooldown timer would silently undo;
* **no new gesture** — `4.4`'s hand-open release stays unbuilt.

⭐ **Per (object, HAND), not per object**: the OTHER hand may take the child
immediately, which is what a two-handed detach needs. Only the hand that let go has
to step away.

## Built

`object_assembly.RegrabLatch` + the release/latch arguments to
`object_assembly.step`; consulted in **both** tools' `_try_snap`, before the radius
test — because the far case is exactly the one that clears it.

⚠ **A stale latch must not outlive the mate**: `step` calls `latch.forget()` on a
break, or an ordinary grab would be refused later for no visible reason.

✅ 42/42 suites; `parity_replay` **NO DIVERGENCE on 4 takes**
(`stripped`, `frob`, `steadytrans`, `freeze`). The new checks in
`analysis/verify_object_assembly.py` include the live defect itself, as a
regression: the mate now survives 145 px of the placing hand moving on.

⛔ **LIVE LOOK OWED.** ⚠ And the consequence to judge live: **to detach you need two
hands**; one hand alone moves the whole assembly instead. Physically that is what
taking a brick off a model requires — but it is a choice, not a law.
