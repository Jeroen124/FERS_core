"""
Example 101 - Cross-member checks via `reference_member` (FERS >= 0.2.39).

A member can point at another member through `reference_member`, and a unity check
can then bind quantities on BOTH - the entity's own nodes/properties and the
referenced member's. This composes arbitrary relative checks (clearance, relative
drift, differential settlement) in plain formulas, reusable across a whole
classification because each member carries its own reference.

Here a lower "rail" references the "beam" above it and a single check verifies the
vertical gap between their tips, alongside the relative deflection and the
referenced member's length/shear - all read back from the calculation trace.

Requires: fers_calculations >= 0.2.39.
"""

import os

from fers_core import (
    AnalysisOrder,
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    NodalLoad,
)
from fers_core.unity_checks import (
    generic_check,
    var,
    node_position,
    node_displacement,
    geometry,
    member_force,
    constant,
    classification,
)

# Step 1: Two cantilevers - an (almost unloaded) beam at Y = 0.5 and, 0.5 m below
# it, a loaded rail whose tip deflects. The rail references the beam.
calculation = FERS()
calculation.settings.analysis_options.order = AnalysisOrder.LINEAR

steel = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)
section = Section(
    name="IPE 180", material=steel, i_y=1.01e-6, i_z=13.21e-6, j=0.027e-6, area=0.00196
)

# Beam (the reference), fixed at its base.
b1 = Node(0, 0.5, 0)
b2 = Node(4, 0.5, 0)
b1.nodal_support = NodalSupport()  # fully fixed
beam = Member(start_node=b1, end_node=b2, section=section, classification="Beam")

# Rail, fixed at its base, pointing at the beam via reference_member.
r1 = Node(0, 0, 0)
r2 = Node(4, 0, 0)
r1.nodal_support = NodalSupport()  # fully fixed
rail = Member(
    start_node=r1,
    end_node=r2,
    section=section,
    classification="Rail",
    reference_member=beam,  # <-- the member this check compares against
)

calculation.add_member_set(
    MemberSet(members=[beam], classification="Beam"),
    MemberSet(members=[rail], classification="Rail"),
)

# Step 2: Load the rail tip down, plus an SLS combination to evaluate over.
case = calculation.create_load_case(name="SLS")
NodalLoad(node=r2, load_case=case, magnitude=-3000, direction=(0, 1, 0))  # 3 kN down at rail tip
calculation.create_load_combination(
    name="SLS-combo", load_cases_factors={case: 1.0}, situation="SLS", check="ALL"
)

# Step 3: A single check on every "Rail" member. It binds the rail's own tip and
# - via reference_member - the beam's tip, and composes the vertical clearance.
# demand = required gap, capacity = actual deflected gap (util > 1 => too close).
min_gap = 0.40  # metres
calculation.add_unity_check(
    generic_check(
        "rail_clearance",
        "Rail-to-beam vertical clearance",
        applies_to=classification("Rail"),
        variables=[
            var("y_self", node_position("End", "Y")),  # rail tip, deflected Y
            var("y_ref", node_position("ReferenceMemberEnd", "Y")),  # beam tip, deflected Y
            var("d_self", node_displacement("End", "Dy")),  # rail tip deflection
            var("d_ref", node_displacement("ReferenceMemberEnd", "Dy")),  # beam tip deflection
            var("Lb", geometry("Length", of="ReferenceMember")),  # beam length
            var("Vb", member_force("Vy", of="ReferenceMember")),  # beam shear
            var("gap_min", constant(min_gap)),
        ],
        demand="gap_min",
        capacity="y_ref - y_self",  # deflected vertical gap between the two members
        report_template=(
            "<p>Rail-to-beam clearance = {{= y_ref - y_self}} (>= {{gap_min}} required). "
            "Utilisation = {{= Utilization}}.</p>"
        ),
    )
)

os.makedirs("json_input_solver", exist_ok=True)
calculation.save_to_json(
    os.path.join("json_input_solver", "101_Unity_Check_Reference_Member_Clearance.json"), indent=4
)

# Step 4: Solve and read the resolved quantities straight from the trace.
print("Running the analysis...")
calculation.run_analysis()

uc = next(u for u in calculation.unity_check_results() if u["check_id"] == "rail_clearance")
governing = uc["governing"]
trace = {step["label"]: step["value"] for step in governing["trace"]}

print(f"Rail tip deflected Y (y_self):     {trace['y_self']:.6f} m")
print(f"Beam tip deflected Y (y_ref):      {trace['y_ref']:.6f} m")
print(f"Vertical clearance (y_ref-y_self): {trace['y_ref'] - trace['y_self']:.6f} m")
print(f"Rail tip deflection (d_self):      {trace['d_self']:.6f} m")
print(f"Beam tip deflection (d_ref):       {trace['d_ref']:.6f} m  (reference member)")
print(f"Beam length via of=ReferenceMember (Lb): {trace['Lb']:.3f} m")
print(f"Beam shear via of=ReferenceMember (Vb):  {trace['Vb']:.3f} N")
print(f"Clearance utilisation (gap_min / gap): {uc['max_utilization']:.3f}  (status {uc['status']})")
