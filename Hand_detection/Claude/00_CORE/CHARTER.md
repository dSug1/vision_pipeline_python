# CHARTER — what is being built, and for whom

> **STATUS** · live · **OWNS** · the goal, the audience, the target platforms
> **READ IF** · you are new to the project, or a decision turns on "who is this for"
> **LAST VERIFIED** · 2026-08-25
> **SOURCED FROM** · `Specification.md` §0 and §13 (verbatim in
> [`ORIGINAL_GOAL_AND_CONSTRAINTS.md`](ORIGINAL_GOAL_AND_CONSTRAINTS.md)), plus the
> owner decisions recorded in [`DECISIONS.md`](DECISIONS.md)

## The product

A **3D game in which hand movements captured by an ordinary webcam manipulate 3D
objects.** Hand landmarks come from MediaPipe; objects are grabbed, moved,
rotated and released by hand, with no controller and no marker.

The manipulation model is **direct and kinematic** — an object's transform is
driven straight from the hand's, not through a physics engine. That was an
original constraint and it still holds.

Today's demonstrator is a cube in a pygame window. **The cube is a placeholder**
for imported 3D assets (queue `U2`); everything downstream of the estimator layer
was deliberately built mesh-generic.

## Who it is for

⛔⛔ **ALL PUBLIC, INCLUDING YOUTH** — owner decision, 2026-08-23. This is not a
preference, it is the fact that makes **COPPA and GDPR-K live**, puts the build
inside Google Play's Families policy and Apple's Kids Category, and turns three
architecture questions into compliance questions. See
[`../60_SECURITY_COMPLIANCE/INDEX.md`](../60_SECURITY_COMPLIANCE/INDEX.md).

**The game will be commercialised.** That is what makes `N13` binding: no
non-commercially-licensed dependency may enter the build, which is why MANO,
HaMeR and WiLoR are permanently out.

## Where it has to run

**Cross-platform is the target, not an aspiration**: desktop (Windows today),
and eventually iOS / Android / web. That target is what drives two rules that
otherwise look like over-engineering:

* the estimator layer is **stdlib-only and numpy-free by contract**, so it can be
  ported by transliteration rather than rewritten (`U3`);
* **golden vectors are written before the port exists**, not after.

⚠ A consequence worth stating plainly: **do not build a feature against the
pygame renderer** if it is really a renderer feature. That is why `U2` (3D file
import) is postponed on the *platform decision*, not on effort.

## The four-part path, and where the project actually is

The original plan was Part Zero (PC cube) → Part Zero-bis (browser dry run) →
Part One (gesture R&D on PC) → Phase 2 (port everything to the browser).

**Part Zero and Part Zero-bis are done** ([`../50_PORT_WEB_MOBILE/`](../50_PORT_WEB_MOBILE/)).
**Part One is where all the work has been since** — and it grew far beyond
"gesture recognition" into a perception layer, a manipulation model and an input
system. **Phase 2 (the port) has not started**; it is queue `U3`.

⚠ **Two original constraints have been overtaken by events, and both matter:**

| original | today |
|---|---|
| *"No OpenCV"* | OpenCV **is** used server-side on PC (capture + the mirror flip). The constraint survives as *"nothing that cannot cross to the browser may sit in the estimator layer"* — which is the port contract |
| *"browser-based"* | still the eventual target, but the audience decision and the mobile ambition made **native mobile** a first-class target too, which is why camera **tilt** (`T7`) and per-device FOV (`U12`) are real rows and not paranoia |

## What "done" looks like for the current phase

An object can be picked up, moved in all three axes, rotated as a real object
would rotate, and released — reliably enough that a person forgets they are
using a webcam. The open blocker on that is the **yaw lean**
([`../10_HAND_TRACKING/spec/ORIENTATION_DIAGNOSIS.md`](../10_HAND_TRACKING/spec/ORIENTATION_DIAGNOSIS.md))
and the next build against it is `F1`, the fingertip-driven transform.
