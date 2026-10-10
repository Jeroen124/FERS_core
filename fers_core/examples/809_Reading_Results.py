"""
809 — Reading Results
=====================
Solves a small portal frame with two load cases and a load combination, then
reads the results: node displacements, reactions and member forces. Shows the
read-only tables that hold member results and node displacements (FERS 0.1.98),
saves the solved model and reloads it, and solves straight to a file, which is
the route for large models.

Key features shown:
  • model.resultsbundle.loadcases / .loadcombinations  — results by name
  • displacement_nodes / reaction_nodes / member_results — by id, as a string
  • read-only tables, and .copy() for editable dicts
  • model.save_to_json(path) and FERS.from_json(path)
  • model.run_analysis_to_file(path)  — the solver writes the file itself
"""

import collections.abc
import os

from fers_core import (
    FERS,
    AnalysisOrder,
    Material,
    Member,
    MemberSet,
    NodalLoad,
    NodalSupport,
    Node,
    Section,
)


# =============================================================================
# Step 1: A portal frame, 6 m wide and 4 m high, fixed at both feet
# =============================================================================
model = FERS()
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)
column_section = Section.from_name("HEA200", steel)
beam_section = Section.from_name("IPE300", steel)

foot_left, eave_left = Node(0, 0, 0), Node(0, 4, 0)
eave_right, foot_right = Node(6, 4, 0), Node(6, 0, 0)
foot_left.nodal_support = NodalSupport()
foot_right.nodal_support = NodalSupport()

left_column = Member(start_node=foot_left, end_node=eave_left, section=column_section)
beam = Member(start_node=eave_left, end_node=eave_right, section=beam_section)
right_column = Member(start_node=eave_right, end_node=foot_right, section=column_section)
model.add_member_set(MemberSet(members=[left_column, beam, right_column]))

dead = model.create_load_case(name="Dead")
wind = model.create_load_case(name="Wind")
NodalLoad(node=eave_left, load_case=dead, magnitude=-20e3, direction=(0, 1, 0))
NodalLoad(node=eave_right, load_case=dead, magnitude=-20e3, direction=(0, 1, 0))
NodalLoad(node=eave_left, load_case=wind, magnitude=8e3, direction=(1, 0, 0))
model.create_load_combination("ULS 1", {dead: 1.35, wind: 1.5}, situation="ULS", check="ALL")

model.settings.analysis_options.order = AnalysisOrder.LINEAR
model.run_analysis()


# =============================================================================
# Step 2: Read the results
# =============================================================================
# Load cases and combinations are keyed by name; nodes and members by their id,
# as a string, because results round-trip through JSON.
uls = model.resultsbundle.loadcombinations["ULS 1"]

sway = uls.displacement_nodes[str(eave_right.id)].dx
print(f"Sway at the right eave: {sway * 1000:.2f} mm")

for foot in (foot_left, foot_right):
    reaction = uls.reaction_nodes[str(foot.id)].nodal_forces
    print(
        f"Reaction at node {foot.id}: Fx = {reaction.fx / 1e3:.1f} kN, "
        f"Fy = {reaction.fy / 1e3:.1f} kN, Mz = {reaction.mz / 1e3:.1f} kNm"
    )

# Member forces are in member axes; a column here bends about its local y, the
# beam about its local z.
for member_id, result in uls.member_results.items():
    envelope = (result.local_maximums, result.local_minimums)
    peak = max(abs(m) for forces in envelope for m in (forces.my, forces.mz))
    print(
        f"Member {member_id}: largest bending moment {peak / 1e3:.1f} kNm, "
        f"axial force at the start {result.local_start_forces.fx / 1e3:.1f} kN"
    )


# =============================================================================
# Step 3: The tables are read-only
# =============================================================================
# member_results and displacement_nodes read like dicts but are not dicts, and
# every lookup builds a fresh object that cannot be changed.
assert isinstance(uls.member_results, collections.abc.Mapping)
assert not isinstance(uls.member_results, dict)
try:
    uls.member_results[str(beam.id)].local_maximums.mz = 0.0
except AttributeError as error:
    print(f"Editing a result raises: {error}")

# .copy() gives a plain dict of ordinary, editable objects.
editable = uls.member_results.copy()
editable[str(beam.id)].local_maximums.mz = 0.0
print("The same edit on a copy works:", editable[str(beam.id)].local_maximums.mz)


# =============================================================================
# Step 4: Save, reload, and solve straight to a file
# =============================================================================
folder = "json_input_solver"
os.makedirs(folder, exist_ok=True)

saved = os.path.join(folder, "809_portal_frame.json")
model.save_to_json(saved)
reloaded = FERS.from_json(saved)
reloaded_sway = reloaded.resultsbundle.loadcombinations["ULS 1"].displacement_nodes[str(eave_right.id)].dx
print(f"Sway after save and reload: {reloaded_sway * 1000:.2f} mm")

# For a large model, let the solver write the file: the result then never passes
# through Python as one string, and from_json reads it one entry at a time.
solved_file = os.path.join(folder, "809_portal_frame_results.json")
model.run_analysis_to_file(solved_file)
solved = FERS.from_json(solved_file)
print("Solved to a file and loaded:", list(solved.resultsbundle.loadcombinations))
