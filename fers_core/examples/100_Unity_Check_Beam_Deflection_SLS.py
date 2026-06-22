"""
Example 100 - Beam mid-span deflection (chord-relative) for an SLS check.

Demonstrates the `MemberDeflection` quantity (FERS >= 0.2.39): the beam's net sag
relative to its own supports - the quantity SLS span/limit deflection checks are
actually written against. On a real frame (beams sitting on flexible uprights)
this removes the support settlement that a global `Dy` would wrongly include; on
the rigidly pinned beam below the two coincide, which the script prints to make
the relationship explicit.

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
    SupportCondition,
)
from fers_core.unity_checks import generic_check, var, member_deflection, constant, member_sets

# Step 1: Model - a simply supported beam, span 6 m, modelled as two half-members
# meeting at the mid-span node (so the mid-span sag lands on a real node).
calculation = FERS()
calculation.settings.analysis_options.order = AnalysisOrder.LINEAR

node1 = Node(0, 0, 0)
node2 = Node(3, 0, 0)  # mid-span
node3 = Node(6, 0, 0)

steel = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)
section = Section(
    name="IPE 180", material=steel, i_y=1.01e-6, i_z=13.21e-6, j=0.027e-6, area=0.00196
)

beam1 = Member(start_node=node1, end_node=node2, section=section, classification="Beam")
beam2 = Member(start_node=node2, end_node=node3, section=section, classification="Beam")

# Pinned supports: translations fixed (default), bending rotations free.
pin = NodalSupport(
    rotation_conditions={
        "X": SupportCondition.fixed(),
        "Y": SupportCondition.free(),
        "Z": SupportCondition.free(),
    }
)
node1.nodal_support = pin
node3.nodal_support = pin

# One physical beam = its two half-members.
beam = MemberSet(members=[beam1, beam2], classification="Beam")
calculation.add_member_set(beam)

# Step 2: Load + an SLS combination (unity checks evaluate over load combinations).
sls_case = calculation.create_load_case(name="SLS")
NodalLoad(node=node2, load_case=sls_case, magnitude=-5000, direction=(0, 1, 0))  # 5 kN down
calculation.create_load_combination(
    name="SLS-combo", load_cases_factors={sls_case: 1.0}, situation="SLS", check="ALL"
)

# Step 3: SLS deflection check bound to the chord-relative quantity on the beam
# member-set. `member_deflection("Magnitude")` = the beam's own sag (settlement
# removed); demand abs(d) against the span/250 serviceability limit.
span = 6.0
calculation.add_unity_check(
    generic_check(
        "sls_beam",
        "Beam mid-span deflection (chord-relative)",
        applies_to=member_sets([beam.id]),
        variables=[
            var("d", member_deflection("Magnitude")),
            var("limit", constant(span / 250.0)),  # span/250 in metres
        ],
        demand="abs(d)",
        capacity="limit",
        report_template=(
            "<p>Beam mid-span sag delta = {{d}} against the span/250 serviceability "
            "limit. Utilisation = {{= Utilization}}.</p>"
        ),
    )
)

os.makedirs("json_input_solver", exist_ok=True)
calculation.save_to_json(
    os.path.join("json_input_solver", "100_Unity_Check_Beam_Deflection_SLS.json"), indent=4
)

# Step 4: Solve and report.
print("Running the analysis...")
calculation.run_analysis()

uc = next(u for u in calculation.unity_check_results() if u["check_id"] == "sls_beam")
governing = uc["governing"]
chord_relative = governing["demand"]  # |chord-relative sag|, metres
print(f"Chord-relative sag (engine MemberDeflection): {chord_relative:.6f} m")
print(f"Utilisation vs span/250: {uc['max_utilization']:.3f}  (status {uc['status']})")

# Cross-check against the GLOBAL mid-span Dy. With rigid pinned supports there is
# no settlement, so global == chord-relative; on a frame with flexible uprights the
# global value would be the larger by exactly that support settlement.
combo_results = calculation.resultsbundle.loadcombinations["SLS-combo"]
dy_mid_global = abs(combo_results.displacement_nodes["2"].dy)
print(f"Global mid-span |Dy|:                          {dy_mid_global:.6f} m")
print(
    "  (equal here on rigid supports; global >= chord-relative once supports settle)"
    if abs(dy_mid_global - chord_relative) < 1e-9
    else f"  (global exceeds chord-relative by {dy_mid_global - chord_relative:.6f} m of settlement)"
)
