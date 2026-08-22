"""Prove the chirality drift guard still has POWER.

A guard that was changed until it passed is worthless unless it still fails on
real drift. Feed it mutated copies of each function and require every mutant to
be caught, then require the REAL production source to match the reference.

--------------------------------------------------------------------------------
⚠⚠ THIS GUARD WAS DEAD, AND SAID SO ON EVERY RUN (found 2026-08-22, with U7)
--------------------------------------------------------------------------------
It compared `HandsTriggeredActions._is_thumb_outward`'s BODY against an inlined
reference. But that function stopped containing the logic on 2026-08-03, when
queue item 1.2 moved the maths into `Resources/palm_geometry.py` and left behind
a one-line delegation. From that day (19 days, and every session in between) the
guard could never pass: it printed "GUARD IS BROKEN" on every run, and the
message was correct but about ITSELF rather than about production.

⭐ THE LESSON, which is the B4/A10 family again: **a guard that cannot pass is
worse than no guard**, because its failure carries no information and everyone
learns to ignore it. It is repointed here at the functions the logic ACTUALLY
lives in, and given a mutant for U7's new geometric chirality as well.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

PALM = os.path.join(ROOT, "Resources", "palm_geometry.py")
PROD = os.path.join(ROOT, "Resources", "HandsTriggeredActions.py")

# ---------------------------------------------------------------------------
# The references: the CURRENT shape of each function that carries chirality.
# ---------------------------------------------------------------------------

REF_IS_THUMB_OUTWARD = '''
def is_thumb_outward(landmarks, handedness):
    """doc"""
    cross = signed_palm_area(landmarks)
    if handedness == "Left":
        cross = -cross
    return cross > 0
'''

REF_SIGNED_PALM_AREA = '''
def signed_palm_area(landmarks):
    """doc"""
    v1, v2 = palm_vectors(landmarks)
    return v1[0] * v2[1] - v1[1] * v2[0]
'''

REF_PALM_VECTORS = '''
def palm_vectors(landmarks):
    """doc"""
    wx, wy = landmarks[WRIST][0], landmarks[WRIST][1]
    v1 = (landmarks[INDEX_MCP][0] - wx, landmarks[INDEX_MCP][1] - wy)
    v2 = (landmarks[PINKY_MCP][0] - wx, landmarks[PINKY_MCP][1] - wy)
    return v1, v2
'''

# ⭐ U7: the geometric chirality is now an input to everything above, so it needs
# its own mutants. Getting THIS sign backwards inverts rule 3 on every hand
# instead of on 10.8% of frames -- a bigger failure than the one U7 fixes.
REF_GEOMETRIC_CHIRALITY = '''
def geometric_chirality(world_landmarks, thumb_idx=THUMB_CMC):
    """doc"""
    v = signed_palm_volume(world_landmarks, thumb_idx)
    if v == 0.0:
        return None
    return "Left" if ((v < 0) == CHIRALITY_V_NEGATIVE_IS_LEFT) else "Right"
'''

CASES = [
    ("is_thumb_outward", PALM, REF_IS_THUMB_OUTWARD, {
        "sign inverted (the §13.6.1 bug)":
            lambda s: s.replace("return cross > 0", "return cross < 0"),
        "chirality correction dropped":
            lambda s: s.replace('    if handedness == "Left":\n        cross = -cross\n', ""),
        "chirality applied to Right instead":
            lambda s: s.replace('== "Left"', '== "Right"'),
    }),
    ("signed_palm_area", PALM, REF_SIGNED_PALM_AREA, {
        "cross product operands swapped":
            lambda s: s.replace("v1[0] * v2[1] - v1[1] * v2[0]",
                                "v2[0] * v1[1] - v2[1] * v1[0]"),
        "subtraction became addition":
            lambda s: s.replace("v1[0] * v2[1] - v1[1] * v2[0]",
                                "v1[0] * v2[1] + v1[1] * v2[0]"),
    }),
    ("palm_vectors", PALM, REF_PALM_VECTORS, {
        "wrong landmark (pinky -> ring)":
            lambda s: s.replace("PINKY_MCP", "RING_MCP"),
        "index and pinky swapped":
            lambda s: s.replace("INDEX_MCP", "_TMP").replace("PINKY_MCP", "INDEX_MCP")
                       .replace("_TMP", "PINKY_MCP"),
    }),
    ("geometric_chirality", PALM, REF_GEOMETRIC_CHIRALITY, {
        "U7 chirality convention inverted":
            lambda s: s.replace("(v < 0)", "(v > 0)"),
        "U7 Left/Right swapped":
            lambda s: s.replace('"Left" if', '"Right" if').replace('else "Right"',
                                                                   'else "Left"'),
        "U7 degenerate case guesses instead of holding":
            lambda s: s.replace("        return None\n", "        return \"Left\"\n"),
    }),
]


class _Canon(ast.NodeTransformer):
    """Rename the first parameter to a fixed name so a cosmetic rename passes."""

    def __init__(self, param):
        self.param = param

    def visit_Name(self, node):
        if node.id == self.param:
            node.id = "_LM"
        return node


def canon(src, fname):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fname:
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]
            mod = ast.Module(body=body, type_ignores=[])
            return ast.dump(_Canon(node.args.args[0].arg).visit(mod))
    return None


ok = True

for fname, path, ref, mutants in CASES:
    print("--- %s ---" % fname)
    base = canon(ref, fname)

    renamed = canon(ref.replace("landmarks", "pixel_landmarks")
                       .replace('"""doc"""', '"""other prose"""'), fname)
    same = (renamed == base)
    print("  [%s] cosmetic rename + new docstring accepted" % ("PASS" if same else "FAIL"))
    ok &= same

    for name, mutate in mutants.items():
        caught = canon(mutate(ref), fname) != base
        print("  [%s] rejects: %s" % ("PASS" if caught else "FAIL", name))
        ok &= caught

    real = canon(open(path, encoding="utf-8").read(), fname)
    if real is None:
        print("  [FAIL] %s NOT FOUND in %s" % (fname, os.path.basename(path)))
        ok = False
    else:
        match = (real == base)
        print("  [%s] the REAL source matches the reference (%s)"
              % ("PASS" if match else "FAIL", os.path.basename(path)))
        ok &= match
    print()

# The delegation itself is now the thing to guard in HandsTriggeredActions:
# if someone re-inlines the maths there, N6 is broken and the two tools can drift
# again -- which is exactly how §13.6.1 shipped.
print("--- N6: production must DELEGATE, never re-inline ---")
prod_src = open(PROD, encoding="utf-8").read()
delegates = False
for node in ast.walk(ast.parse(prod_src)):
    if isinstance(node, ast.FunctionDef) and node.name == "_is_thumb_outward":
        body = [n for n in node.body if not (isinstance(n, ast.Expr)
                                             and isinstance(n.value, ast.Constant))]
        delegates = (len(body) == 1 and isinstance(body[0], ast.Return)
                     and isinstance(body[0].value, ast.Call)
                     and getattr(body[0].value.func, "attr", None) == "is_thumb_outward")
print("  [%s] _is_thumb_outward is a one-line delegation to palm_geometry"
      % ("PASS" if delegates else "FAIL"))
ok &= delegates

print("\nGUARD HAS POWER" if ok else "\nGUARD IS BROKEN")
sys.exit(0 if ok else 1)
