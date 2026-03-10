import os
from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad, AnalysisOrder


# =============================================================================
# Triple cantilever: 3 beams connected in 3D space (base orientation)
#
# Node 0 at (0, 0, 0) - Fixed support
# Node 1 at (1, 0, 0) - beam 1 runs along global X
# Node 2 at (1, 1, 0) - beam 2 runs along global Y
# Node 3 at (1, 1, 1) - beam 3 runs along global Z, free end
#
# Counterpart: 924_Triple_Cantilever_3D_Rotated_45Y.py (same structure,
#              rotated -45° around the global Y axis)
# =============================================================================

calculation = FERS()

# Nodes (user indices 0-3, FERS will assign IDs 1-4)
node0 = Node(0, 0, 0)  # Fixed end
node1 = Node(1, 0, 0)
node2 = Node(1, 1, 0)
node3 = Node(1, 1, 1)  # Free end

# Material
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Section (IPE 180)
section = Section(
    name="IPE 180 Beam Section",
    material=Steel_S235,
    i_z=13.21e-6,
    i_y=1.01e-6,
    j=0.027e-6,
    area=0.00196,
)

# Members
beam1 = Member(start_node=node0, end_node=node1, section=section)  # along global X
beam2 = Member(start_node=node1, end_node=node2, section=section)  # along global Y
beam3 = Member(start_node=node2, end_node=node3, section=section)  # along global Z

# Fixed support at node 0 (all 6 DOF constrained)
node0.nodal_support = NodalSupport()

# Member sets
mg1 = MemberSet(members=[beam1])
mg2 = MemberSet(members=[beam2])
mg3 = MemberSet(members=[beam3])

calculation.add_member_set(mg1, mg2, mg3)

# Load case: -1000 N in global Y at free end (node 3)
lc = calculation.create_load_case(name="End Load")
NodalLoad(node=node3, load_case=lc, magnitude=-1000, direction=(0, 1, 0))

# Save JSON
file_path = os.path.join("json_input_solver", "084_triple_cantilever_3D.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation.save_to_json(file_path, indent=4)

# Run analysis (linear — consistent with the rotated counterpart 085)
print("Running analysis: 084 Triple Cantilever 3D (base orientation)")
calculation.settings.analysis_options.order = AnalysisOrder.LINEAR
calculation.run_analysis()

result_lc = calculation.resultsbundle.loadcases["End Load"]

print("\n--- Node Displacements and Rotations (FERS IDs 1-4 = user nodes 0-3) ---")
for fers_id, label in [
    ("1", "node0 (0,0,0)"),
    ("2", "node1 (1,0,0)"),
    ("3", "node2 (1,1,0)"),
    ("4", "node3 (1,1,1)"),
]:
    if fers_id in result_lc.displacement_nodes:
        d = result_lc.displacement_nodes[fers_id]
        print(f"  {label}:")
        print(f"    dx={d.dx:.6f}  dy={d.dy:.6f}  dz={d.dz:.6f}")
        print(f"    rx={d.rx:.6f}  ry={d.ry:.6f}  rz={d.rz:.6f}")

print("\n--- Reaction Forces at Fixed Support (node0) ---")
for k, rn in result_lc.reaction_nodes.items():
    f = rn.nodal_forces
    print(f"  Support {k}: Fx={f.fx:.3f} N  Fy={f.fy:.3f} N  Fz={f.fz:.3f} N")
    print(f"             Mx={f.mx:.3f} Nm  My={f.my:.3f} Nm  Mz={f.mz:.3f} Nm")
