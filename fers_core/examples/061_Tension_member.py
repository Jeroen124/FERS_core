import os
from fers_core import (
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

# =============================================================================
# Example and Validation: Cantilever With Root Rotational Spring (via MemberHinge)
# =============================================================================
# Model: node1 --[RIGID]--> node2 --[NORMAL + spring at start]--> node3
# Support: full fixity at node1 (translations and rotations)
# Load: 1 kN downward at the free end (node3)
#
# This is mechanically equivalent to a cantilever of length L with a rotational
# spring at its fixed/root end. The rigid member transmits the support DOFs to
# node2; the MemberHinge provides a rotational spring around local z at the
# start of the flexible member.
# =============================================================================

# Step 1: Set up the model
# ------------------------
calculation_1 = FERS()

# Geometry
node1 = Node(0.0, 0.0, 0.0)  # support end
node2 = Node(2.5, 0.0, 0.0)  # node for applying load
node3 = Node(5.0, 0.0, 0.0)  # free end

# Support at node1 and node 3, for stability fix displacement at node 2 (fixed translations and rotations)
node1.nodal_support = NodalSupport()
node2.nodal_support = NodalSupport(
    displacement_conditions={
        "X": SupportCondition.free(),
        "Y": SupportCondition.fixed(),
        "Z": SupportCondition.fixed(),
    }
)
node3.nodal_support = NodalSupport()

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)

# Add a force in the middle node
mid_force_newton = 1  # N

# Members
rope_1 = Member(start_node=node1, end_node=node2, section=section, member_type="TENSION")
rope_2 = Member(start_node=node2, end_node=node3, section=section, member_type="TENSION")

# Add members to the model
member_set = MemberSet(members=[rope_1, rope_2])
calculation_1.add_member_set(member_set)


# If your serializer requires explicit collection of hinges, uncomment:
# calculation_1.memberhinges.append(start_hinge)

# Step 2: Apply the load
# ----------------------
load_case = calculation_1.create_load_case(name="Mid Load")

# 1 kN in the middle of the two ropes
NodalLoad(
    node=node2,
    load_case=load_case,
    magnitude=mid_force_newton,
    direction=(1.0, 0.0, 0.0),
)

# Save the model (useful for reproducibility or external solver runs)
file_path = os.path.join("json_input_solver", "061_Tension_member.json")
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
print("Running the analysis...")
calculation_1.run_analysis()
results = calculation_1.results.loadcases["Mid Load"]

# Extract FERS results
movement_node2_fers = results.displacement_nodes["2"].dx
reaction_force_x_1 = results.reaction_nodes["1"].nodal_forces.fx
reaction_force_x_3 = results.reaction_nodes["3"].nodal_forces.fx

# Step 4: Validate against analytical solution
# --------------------------------------------
E = Steel_S235.e_mod
A = section.area
L = 2.5  # length of each rope
F = mid_force_newton

# Analytical solution for horizontal displacement at mid-span of two tension members
movement_node2_expected = (F * L) / (A * E)  # only one rope is loaded in tension
reaction_force_x_1_expected = -F  # reaction at the fixed end
reaction_force_x_3_expected = 0.0  # rope can not push, so no reaction is expected

print(movement_node2_expected)
print(movement_node2_fers)
