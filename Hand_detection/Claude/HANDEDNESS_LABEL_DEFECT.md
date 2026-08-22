# ⛔⛔ THE HANDEDNESS LABEL IS WRONG 10.8% OF THE TIME — and rule 3 inverts on it

> ## ✅✅ SHIPPED AND OWNER-ACCEPTED LIVE, 2026-08-22
> Owner, after the production run: ***"fix is working. I believe this is good to ship."***
>
> ⚠⚠ **BUT U7 ALONE WAS NOT ENOUGH, and that is the most useful thing on this page.**
> Fixing chirality TRUTH left two further defects with the *same appearance* — a
> back-of-hand hand ending up with the cube. All three were only separable by
> recording them:
>
> | # | mechanism | evidence | fix |
> |---|---|---|---|
> | 1 | **Steal by RELABEL** — DR-1 swaps two tracks between slots; ownership is a slot NAME, so the cube changes PHYSICAL HAND with **no release, no snap, rule 3 never consulted** | `n8_back_steal_b` f478 | `Resources/owner_remap.py` (T3 narrow remap) |
> | 2 | **Back-grab by INHERITED STATE** — a track moving into a slot inherited the previous occupant's `PalmFacingTracker`, so its back-of-hand read as PALM for 2 frames (post-mortem §3.4, still live) | `t3_remap_debug_test` f1050 | reset the tracker when the track in a slot changes |
> | 3 | **Back-grab by PROVISIONAL CHIRALITY** — a newly ENTERED hand measured wrong for 5 frames; the resolver adopted the first sighting and the debounce defended it | `t3_remap_production_test` f664 | **U8** confirmation gate (queue row U8) |
>
> ⭐ **Why 1 slipped past rule 3 while ordinary back-grabs were blocked:** it never
> reaches the gate. There is no snap event at all.
>
> ⭐ **Why 3 needed a new idea:** three cheaper remedies were measured and all
> failed — conditioning-gating (the bad frames were ABOVE median thickness),
> falling back to the label (the label is WORSE at entry, 76.8% vs 89.7%), and
> temporal voting (the wrong value was stable for 5 consecutive frames).
>
> | | |
> |---|---|
> | where | `Resources/palm_geometry.py` — `signed_palm_volume`, `geometric_chirality`, `ChiralityResolver`, wired into `PalmFacingTracker.update()` |
> | ⭐ why there | `update()` is the **one** place the handedness label enters the palm/back cue in **either** tool, so the fix lands once and both get it (N6). Patching the two call sites instead is exactly how §13.6.1's production-only inversion happened |
> | A/B switch | `palm_geometry.GEOMETRIC_CHIRALITY = False` restores pre-U7 behaviour exactly |
> | degrades safely | no `world_landmarks` → falls back to the label, i.e. today's behaviour. Never worse |
> | measured effect | at the 5 recorded snaps, rule 3's input changes on **exactly 1 — frame 122, §2's failing snap** — and the four sound snaps are untouched (STEP 9, through the real tracker) |
> | green | 19 verify suites, `VerifyChiralityFixture.py`, `analysis/verify_geometric_chirality.py` (new golden vectors), `guard_sensitivity.py`, and `parity_replay.py` on 5534 frames across two sessions |
>
> ⚠ **Two things this build found that were not part of the plan** — both recorded
> in `analysis/README.md`:
> 1. **The thickness gate earns nothing and was NOT shipped.** Sweeping it 0→7 mm
>    changed nothing between 0 and 5 mm and made things *worse* at 3–5 mm. Under
>    A10 a null result is recorded, not shipped hopefully. `palm_plane_thickness()`
>    stays exposed as a diagnostic. **The debounce does all the work.**
> 2. ⛔ **`analysis/guard_sensitivity.py` had been DEAD since 2026-08-03** — it
>    AST-compared a function that stopped holding the logic when 1.2 moved it into
>    `palm_geometry`, so it printed "GUARD IS BROKEN" on every run for 19 days,
>    about itself. Repointed at the real functions and given U7 mutants of its own.
>    **A guard that cannot pass is worse than no guard.**

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

> ⭐⭐ **UPDATE 2026-08-22 — (1) IS MEASURED AND VIABLE, but its stated mechanism
> was WRONG and is corrected below.** Harness: `analysis/u7_geometric_chirality.py`.
> Full numbers in `analysis/README.md` → "U7 — is chirality recoverable WITHOUT
> the handedness label?". Verdict: **GO.**

**(1) Make the palm/back cue label-INDEPENDENT.** ~~Derive it from the 3D palm
normal in `world_landmarks` rather than from a 2D cross product that needs
chirality.~~

⛔ **That mechanism does not work, and the strikethrough is the point.** The
shipped 2D signed area **already is** the z-component of
`cross(wrist→index_MCP, wrist→pinky_MCP)`. That normal points out of the BACK for
one chirality and out of the PALM for the other — in 2D and in 3D alike. A left
hand showing its palm and a right hand showing its back are **mirror images**, and
no function of the palm quad alone can separate them. Going to 3D adds precision,
not chirality.

⭐ **What DOES break the dependency is the THUMB, because it leaves the palm
plane.** The signed volume

```
V = det[ index_MCP − wrist , pinky_MCP − wrist , thumb_CMC − wrist ]   (world_landmarks)
```

is invariant under rotation and translation and changes sign **only under
reflection**. So `sign(V)` is chirality computed from geometry, with no MediaPipe
label anywhere in it. **Measured against the operator's declaration** (7 sessions,
2555 single-hand frames):

| | MediaPipe label | `sign(V)` |
|---|---|---|
| corpus | 98.8% | **99.8%** |
| ⭐ this take (`known_right_reentry`) — the only one that exercises the defect | 89.4% — **31 errors, reproducing §2's 10.8%** | **98.3% — 5 errors, 84% fewer** |

⚠ **The corpus row is near-meaningless alone**: six of seven takes are steady
holds where MediaPipe is already 100%, so the average is dominated by frames that
were never in doubt. Quote the re-entry row.

⭐ **The two signals are genuinely independent** — they disagree on 30 frames and
geometry is right on **28**; both are wrong on only 3. (Checked deliberately: had
MediaPipe internally chirality-normalised its world landmarks by its own label,
`sign(V)` would merely restate the label and prove nothing.)

⭐ **And it fixes THE SNAP.** At every snap recorded in this take, rule 3's input
changes on exactly **1 of 5** — frame 122, §2's failing snap, from `thumb_outward
= False` (allowed, the defect) to `True` (forbidden, correct). The four sound
snaps are unchanged.

⚠ **The new cue needs its own conditioning gate**, exactly as the 2D sign has
`edge_on_measure`: the thumb's perpendicular distance from the palm plane (median
8.8 mm, p10 7.9 mm, min 0.9 mm). Residual errors cluster where it collapses, and
they form 4 runs of lengths [2,1,1,1] — **3 of 4 are isolated single frames**, so
a 2-frame debounce (DR-1 already uses that pattern) should absorb them.

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
