"""Prove the drift guard still has POWER after being fixed.

A guard that was changed until it passed is worthless unless it still fails on
real drift. Feed it mutated copies of the function and require each to be caught.
"""
import ast
import os
import sys

sys.path.insert(0, r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
                   r"\Hand_detection\Local_pc\Movement_with_hand_detection")

PROD = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection\Resources\HandsTriggeredActions.py")

BASE = '''
def _is_thumb_outward(landmarks, handedness):
    """doc"""
    wrist = landmarks[WRIST]
    idx_mcp = landmarks[INDEX_MCP]
    pinky_mcp = landmarks[PINKY_MCP]
    v1 = (idx_mcp[0] - wrist[0], idx_mcp[1] - wrist[1])
    v2 = (pinky_mcp[0] - wrist[0], pinky_mcp[1] - wrist[1])
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    if handedness == "Left":
        cross = -cross
    return cross > 0
'''

# Same logic, different parameter name + different docstring: MUST be accepted.
RENAMED = BASE.replace("landmarks", "pixel_landmarks").replace('"""doc"""', '"""other prose"""')

MUTANTS = {
    "sign inverted (the §13.6.1 bug)": BASE.replace("return cross > 0", "return cross < 0"),
    "chirality correction dropped": BASE.replace('    if handedness == "Left":\n        cross = -cross\n', ""),
    "chirality applied to Right instead": BASE.replace('== "Left"', '== "Right"'),
    "cross product operands swapped": BASE.replace("v1[0] * v2[1] - v1[1] * v2[0]",
                                                   "v2[0] * v1[1] - v2[1] * v1[0]"),
    "wrong landmark (pinky -> ring)": BASE.replace("PINKY_MCP", "RING_MCP"),
}


class _Canon(ast.NodeTransformer):
    def __init__(self, param):
        self.param = param

    def visit_Name(self, node):
        if node.id == self.param:
            node.id = "_LM"
        return node


def canon(src):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_is_thumb_outward":
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]
            mod = ast.Module(body=body, type_ignores=[])
            return ast.dump(_Canon(node.args.args[0].arg).visit(mod))
    return None


base = canon(BASE)
ok = True

print("--- must ACCEPT (identical logic, cosmetic differences only) ---")
same = canon(RENAMED) == base
print(f"  [{'PASS' if same else 'FAIL'}] renamed parameter + different docstring accepted")
ok &= same

print("\n--- must REJECT (real drift) ---")
for name, src in MUTANTS.items():
    caught = canon(src) != base
    print(f"  [{'PASS' if caught else 'FAIL'}] {name}")
    ok &= caught

print("\n--- the guard also matches the REAL production source ---")
real = canon(open(PROD, encoding="utf-8").read())
print(f"  [{'PASS' if real == base else 'FAIL'}] production _is_thumb_outward == reference logic")
ok &= (real == base)

print("\nGUARD HAS POWER" if ok else "\nGUARD IS BROKEN")
sys.exit(0 if ok else 1)
