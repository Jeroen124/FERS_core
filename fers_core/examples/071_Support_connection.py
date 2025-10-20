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
node3 = Node(0.0, 2.5, 0.0)  # free end

# Support at node1 and node 3, for stability fix displacement at node 2 (fixed translations and rotations)
node1.nodal_support = NodalSupport(
    rotation_conditions={
        "X": SupportCondition.fixed(),
        "Y": SupportCondition.fixed(),
        "Z": SupportCondition.free(),
    }
)
node2.nodal_support = NodalSupport(
    rotation_conditions={
        "X": SupportCondition.fixed(),
        "Y": SupportCondition.fixed(),
        "Z": SupportCondition.free(),
    }
)

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)

# Add a force in the top node
end_force_newton = 100  # N

# Members
beam_1 = Member(start_node=node1, end_node=node2, section=section)
beam_2 = Member(start_node=node1, end_node=node3, section=section)

# Add members to the model
member_set = MemberSet(members=[beam_1, beam_2])
calculation_1.add_member_set(member_set)


# If your serializer requires explicit collection of hinges, uncomment:
# calculation_1.memberhinges.append(start_hinge)

# Step 2: Apply the load
# ----------------------
load_case = calculation_1.create_load_case(name="Top Load")

# 1 kN in the middle of the two beams
NodalLoad(
    node=node3,
    load_case=load_case,
    magnitude=end_force_newton,
    direction=(1.0, 0.0, 0.0),
)

# Save the model (useful for reproducibility or external solver runs)
file_path = os.path.join("json_input_solver", "071_Support_connection.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
print("Running the analysis...")
calculation_1.run_analysis()
results = calculation_1.resultsbundle.loadcases["Top Load"]

# Extract FERS results
reaction_node2_fy_fers = results.reaction_nodes["2"].nodal_forces.fy


# Analytical expectations:
reaction_node2_fy_expected = 100

print("\nComparison of reaction force:")
print(f"Reaction at node 2 (FERS): {reaction_node2_fy_fers:.6f} N")
print(f"Reaction at node 2 (Analytical): {reaction_node2_fy_expected:.6f} N")
if abs(reaction_node2_fy_fers - reaction_node2_fy_expected) < 1e-6:
    print("Reaction force matches the analytical solution ✅")
else:
    print("Reaction force does NOT match the analytical solution ❌")

print()
