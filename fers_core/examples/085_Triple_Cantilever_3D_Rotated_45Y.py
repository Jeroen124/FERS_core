import math
import os
from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad, AnalysisOrder


# =============================================================================
# Triple cantilever: same structure as 923, rotated -45° around the global Y axis
#
# Rotation matrix Ry(-45°):
#   x' =  cos45 * x - sin45 * z
#   y' =  y
#   z' =  sin45 * x + cos45 * z
#
# Original → Rotated:
#   Node 0 (0, 0, 0)    → (0,      0, 0)
#   Node 1 (1, 0, 0)    → (√0.5,   0, √0.5)
#   Node 2 (1, 1, 0)    → (√0.5,   1, √0.5)
#   Node 3 (1, 1, 1)    → (0,       1, √2)
#
# The same global load (-1000 N in Y at the free end) is applied to allow
# direct comparison of global displacements with the base case.
# =============================================================================

S = math.sqrt(0.5)  # ≈ 0.7071  (cos45 = sin45)
S2 = math.sqrt(2.0)  # ≈ 1.4142

calculation = FERS()

# Nodes
node0 = Node(0, 0, 0)  # Fixed end  (unchanged)
node1 = Node(S, 0, S)  # (√0.5, 0, √0.5)
node2 = Node(S, 1, S)  # (√0.5, 1, √0.5)
node3 = Node(0, 1, S2)  # (0, 1, √2)  – free end

# Material
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Section (IPE 180)
section = Section(
    name="IPE 180 Beam Section",
    material=Steel_S235,
    i_z=10.63e-6,
    i_y=0.819e-6,
    j=0.027e-6,
    area=0.00196,
)

# Members
beam1 = Member(start_node=node0, end_node=node1, section=section)
beam2 = Member(start_node=node1, end_node=node2, section=section)
beam3 = Member(start_node=node2, end_node=node3, section=section)

# Fixed support at node 0 (all 6 DOF constrained)
node0.nodal_support = NodalSupport()

# Member sets
mg1 = MemberSet(members=[beam1])
mg2 = MemberSet(members=[beam2])
mg3 = MemberSet(members=[beam3])

calculation.add_member_set(mg1, mg2, mg3)

# Load case: -1000 N in global Y at free end (node 3) — same global load as base case
lc = calculation.create_load_case(name="End Load")
NodalLoad(node=node3, load_case=lc, magnitude=-1000, direction=(0, 1, 0))

# Save JSON
file_path = os.path.join("json_input_solver", "085_triple_cantilever_3D_rotated_45Y.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation.save_to_json(file_path, indent=4)

# Run analysis (linear — matches base case 084)
print("Running analysis: 085 Triple Cantilever 3D (rotated -45° around Y)")
calculation.settings.analysis_options.order = AnalysisOrder.LINEAR
calculation.run_analysis()

result_lc = calculation.resultsbundle.loadcases["End Load"]

print("\n--- Node Displacements and Rotations (FERS IDs 1-4 = user nodes 0-3) ---")
for fers_id, label in [
    ("1", "node0 (0, 0, 0)"),
    ("2", f"node1 ({S:.4f}, 0, {S:.4f})"),
    ("3", f"node2 ({S:.4f}, 1, {S:.4f})"),
    ("4", f"node3 (0, 1, {S2:.4f})"),
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
