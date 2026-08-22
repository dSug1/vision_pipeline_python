# ⛔⛔ THE HANDEDNESS LABEL IS WRONG 10.8% OF THE TIME — and rule 3 inverts on it

> **Measured 2026-08-22 against DECLARED ground truth.** Recording:
> `2026-08-22_173948_known_right_reentry` (`meta.json` → `known_hand: "right"`).
> This is the root cause behind an owner report that survived **seven** patches.

---

## 1. The report

> *"the hand exited as palm and came back with back and can still grab the cube,
> but it is not systematic"* — and *"I don't face the same issue in the
> production."*

Rule 3 (`GAME_RULES.md`) forbids a hand snapping while thumb-outward (back of
hand to camera) unless it was already thumb-outward when that object was last
un-snapped.

---

## 2. The measurement

The operator used **only the physical RIGHT hand** for the whole take. By this
project's mirrored convention — confirmed 751/751 by `VerifyChiralityFixture.py`
— a physical right hand must be labelled **`Left`**.

| | |
|---|---|
| hand-frames | 295 |
| labelled `Left` (correct) | 263 |
| **labelled `Right` (WRONG)** | **32 → 10.8%** |

At the snap on frame 122:

| | |
|---|---|
| label assigned | `Right` — **wrong** |
| pipeline believed | `thumb_outward = False` → "palm" → **snap allowed** |
| under the CORRECT label | `thumb_outward = True` → "back" → **snap forbidden** |
| MediaPipe handedness score | **0.94** — high confidence, and wrong |
| `edge_on_measure` | 0.56 — well-conditioned, not an edge-on coin flip |

⭐ **`palm_geometry.is_thumb_outward(points, handedness)` applies a
handedness-dependent chirality correction, so its answer INVERTS under a wrong
label.** A back-of-hand hand therefore computes as "palm" and passes rule 3's
gate. Verified across the take: every snap's answer flips if the label flips.

---

## 3. ⚠⚠ WHY THIS SURVIVED SEVEN PATCHES — the methodological error

Every earlier check compared the pipeline's belief against
`is_thumb_outward(px, label)` **using the same label that was wrong**. That is
self-consistent by construction, so it reported **zero violations every time**,
across several sessions, while the defect was live in front of the owner.

⭐ **This is the B4 rule, already on this project's books, re-broken in a new
place: _an anchor metric must not share an expression with the anchor._** Only a
DECLARED physical hand breaks the circularity — which is exactly why the corpus
has `known_left_*` / `known_right_*` sequences. **Reach for ground truth the
first time a chirality-sensitive claim is questioned, not the seventh.**

It also explains both halves of the report:
- **"not systematic"** → 10.8% of frames.
- **"not in production"** → the production session made 18 snaps and none landed
  on a mislabelled frame. ⚠ One camera means the two tools can never run at
  once, so "not in production" always compares SEPARATE sessions of an
  intermittent defect. It was sampling, not a divergence.

---

## 4. What is NOT the cause (each eliminated by measurement)

| candidate | verdict |
|---|---|
| Rule 3's logic | **correct** — it behaved properly given its input |
| The two tools' gesture logic | **identical** — `analysis/parity_replay.py`, 5909 frames, **zero** divergence |
| Detector configuration | identical (`num_hands=2`, VIDEO, same model, `timestamp_ms += 33`) |
| DR-2's edge-on freeze | not involved — `edge_on` was 0.56 at the failing snap |
| A low-confidence label | **no** — the wrong label scored **0.94**, so score-gating would not catch it |
| The 4.1 identity migration | **no** — this reproduces on the reverted, label-keyed baseline |

---

## 5. ⭐ THE TWO WAYS OUT — a design decision, not a patch

**(1) Make the palm/back cue label-INDEPENDENT.** Derive it from the 3D palm
normal in `world_landmarks` rather than from a 2D cross product that needs
chirality. A wrong label then cannot invert it.
⭐ *Recommended*: it removes the dependency instead of trying to improve an input
MediaPipe gets **confidently** wrong.
⚠ Touches DR-2 and the chirality convention that §13.6.1 lives in. Re-run
`VerifyChiralityFixture.py` **and** a known-hand take before and after.

**(2) Make the label more reliable on re-entry.** Have DR-1 carry identity across
a short absence instead of re-deciding from a low-quality back-of-hand view.
⚠ Weaker: it reduces the rate but leaves the inversion mechanism in place, and
DR-1 cannot use positional continuity across a gap — which is why it re-decides.

⚠ **Whichever is chosen, the acceptance test is a KNOWN-HAND take**, not a replay
that trusts the recorded label. `LiveSnapDebug.py --known-hand left|right` stores
the declaration in `meta.json`; the recorder also now stores MediaPipe's `score`
and the pre-DR-1 `raw_handedness`.

---

## 6. Scope — how much else rests on this label

⚠ Anything chirality-sensitive inherits the 10.8% error, not just rule 3:
`is_thumb_outward`, DR-2's frozen palm/back sign, and the `thumb_outward`-gated
snap restriction. ⭐ **Rotation does NOT** — `palm_rotation.Horn` fits the palm
constellation and never reads handedness, which is why a wrong label produces no
visible 180° cube flip. *(That was the owner's own observation, and it correctly
ruled out a hypothesis of mine.)*
