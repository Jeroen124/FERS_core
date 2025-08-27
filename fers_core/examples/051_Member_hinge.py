import os
from fers_core import Node, Member, FERS, MemberSet, NodalSupport, NodalLoad
from fers_core.members.memberhinge import MemberHinge

# -------------------------
# Model
# -------------------------
calculation_1 = FERS()

# Geometry
node1 = Node(0.0, 0.0, 0.0)  # support end
node2 = Node(5.0, 0.0, 0.0)  # free end

# Support (fixed translations & rotations at node1)
node1.nodal_support = NodalSupport()

# Material & Section (needed for a NORMAL member)

# Start hinge: choose a stiff rotational spring around local z to keep rotation small
F = 1000.0  # N
L = 5.0  # m
phi_target = 0.1  # rad (approx target rotation at the start)
k_mz = (F * L) / phi_target  # ~ 50_000 N·m/rad
start_hinge = MemberHinge(hinge_type="SPRING_Z", rotational_release_mz=k_mz)

# Member with START hinge (normal beam, not rigid)
beam = Member(start_node=node1, end_node=node2, member_type="Rigid", start_hinge=start_hinge)

# Add to model
membergroup1 = MemberSet(members=[beam])
calculation_1.add_member_set(membergroup1)

# (Only if your serializer needs it) ensure hinge is collected:
# calculation_1.memberhinges.append(start_hinge)

# -------------------------
# Load case & load
# -------------------------
end_load_case = calculation_1.create_load_case(name="End Load")
# downward 1 kN at the free end
NodalLoad(node=node2, load_case=end_load_case, magnitude=-1000.0, direction=(0.0, 1.0, 0.0))

# Save & run
file_path = os.path.join("json_input_solver", "051_Member_hinge_start_semirigid.json")
calculation_1.save_to_json(file_path, indent=4)

print("Running the analysis...")
calculation_1.run_analysis()

# -------------------------
# Results
# -------------------------
results = calculation_1.results.loadcases["End Load"]

# Deflection at the free end in Y and reaction moment at the support
dy_fers = results.displacement_nodes["2"].dy
Mz_fers = results.reaction_nodes["1"].nodal_forces.mz

print(f"\nFree-end deflection dy (FERS): {dy_fers:.6f} m")
print(f"Support reaction Mz (FERS):    {Mz_fers:.6f} N·m")
print(f"Spring stiffness used k_phi_z: {k_mz:.1f} N·m/rad")
