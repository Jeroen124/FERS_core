import json
import os
import shutil
import subprocess
import sys

from fers_core import FERS, ResultBlock, ResultRequest
from fers_core.builders import create_beam


# =============================================================================
# Example: the command-line loop (author -> validate -> solve -> read a selection)
# =============================================================================
# `pip install FERS` installs the `fers` command. This script does what a shell
# session or a coding agent does: build the model with the objects, save it,
# let `fers` validate and solve it, and read only the results it needs.

# Step 1: author the model and ask for only the results we will read
# ------------------------------------------------------------------
model = create_beam(5.0, "IPE180", udl=5000.0)  # 5 m simply supported span, 5 kN/m downward
model.settings.analysis_options.result_requests = [
    ResultRequest(ResultBlock.REACTIONS),
    ResultRequest(ResultBlock.NODE_DISPLACEMENTS, components=["dy"]),
]

os.makedirs("json_input_solver", exist_ok=True)
model_path = os.path.join("json_input_solver", "811_Command_Line_Workflow.json")
results_path = os.path.join("json_input_solver", "811_Command_Line_Workflow_results.json")
model.save_to_json(model_path, indent=2)


# Step 2: the `fers` command (or `python -m fers_core.cli` where it is not on the path)
# -------------------------------------------------------------------------------------
fers = [shutil.which("fers")] if shutil.which("fers") else [sys.executable, "-m", "fers_core.cli"]


def run(*args: str) -> subprocess.CompletedProcess:
    completed = subprocess.run([*fers, *args], capture_output=True, text=True, encoding="utf-8")
    print(f"$ fers {' '.join(args)}")
    print(completed.stdout.rstrip() or completed.stderr.rstrip())
    return completed


validated = run("validate", model_path)
assert validated.returncode == 0, validated.stderr

solved = run("solve", model_path, "--out", results_path, "--json")
assert solved.returncode == 0, solved.stderr
summary = json.loads(solved.stdout)
print(f"recorded failures: {summary['solve_failures'] + summary['load_case_failures']}")


# Step 3: read the selection, not the file
# ----------------------------------------
solved_model = FERS.from_json(results_path)
case = next(iter(solved_model.resultsbundle.loadcases.values()))
reaction = case.reaction_nodes["1"].nodal_forces.fy
midspan_dy = min(node.dy for node in case.displacement_nodes.values())

w, L, E = 5000.0, 5.0, 210e9
I = model.get_all_members()[0].section.i_z  # IPE180 about its strong axis, from the catalogue
hand_dy = -5 * w * L**4 / (384 * E * I)
print()
print(f"Reaction at the left support (FERS):     {reaction:.1f} N   (hand: {w * L / 2:.1f} N)")
print(f"Midspan deflection (FERS):               {midspan_dy * 1000:.3f} mm")
print(f"Midspan deflection (5wL^4/384EI, hand):  {hand_dy * 1000:.3f} mm  (bending only; FERS adds shear)")
if abs(reaction - w * L / 2) < 1.0 and abs(midspan_dy - hand_dy) < 0.03 * abs(hand_dy):
    print("Reaction and deflection match the hand calculation")
else:
    print("Results do NOT match the hand calculation")
