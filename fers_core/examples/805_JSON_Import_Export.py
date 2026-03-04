"""
805 — JSON Import / Export
==========================
Demonstrates how to save a FERS model to JSON, reload it, and verify
that the round-trip preserves the model exactly.

Key features shown:
  • model.save_to_json(path)     — write the model to a JSON file
  • FERS.from_json(path)         — reconstruct the model from a JSON file
  • model.to_dict() / FERS.from_dict()  — dict-based serialisation
  • Running an analysis on a reloaded model
"""

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
)


# =============================================================================
# Step 1: Build a simple model
# =============================================================================
model = FERS()

steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)
section = Section.from_name("IPE200", steel)

node1 = Node(0, 0, 0)
node2 = Node(3, 0, 0)
node3 = Node(6, 0, 0)

beam1 = Member(start_node=node1, end_node=node2, section=section)
beam2 = Member(start_node=node2, end_node=node3, section=section)

node1.nodal_support = NodalSupport()  # fixed
node3.nodal_support = NodalSupport()  # fixed

ms = MemberSet(members=[beam1, beam2])
model.add_member_set(ms)

lc = model.create_load_case(name="Center load")
NodalLoad(node=node2, load_case=lc, magnitude=-20_000, direction=(0, 1, 0))

print("Original model:")
print(f"  Nodes : {model.number_of_nodes()}")
print(f"  Members: {model.number_of_elements()}")


# =============================================================================
# Step 2: Save to JSON
# =============================================================================
output_dir = os.path.join(os.path.dirname(__file__), "json_input_solver")
os.makedirs(output_dir, exist_ok=True)
json_path = os.path.join(output_dir, "805_JSON_Import_Export.json")

model.save_to_json(json_path, indent=2)
file_size_kb = os.path.getsize(json_path) / 1024
print(f"\nSaved model to: {json_path}  ({file_size_kb:.1f} KB)")


# =============================================================================
# Step 3: Reload from JSON
# =============================================================================
reloaded = FERS.from_json(json_path)

print("\nReloaded model:")
print(f"  Nodes : {reloaded.number_of_nodes()}")
print(f"  Members: {reloaded.number_of_elements()}")


# =============================================================================
# Step 4: Run analysis on the reloaded model
# =============================================================================
print("\nRunning analysis on reloaded model...")
reloaded.run_analysis()

dy = reloaded.resultsbundle.loadcases["Center load"].displacement_nodes["2"].dy
print(f"Mid-span deflection dy = {dy*1e3:.4f} mm")


# =============================================================================
# Step 5: Verify the saved JSON contains results
# =============================================================================
json_path_results = os.path.join(output_dir, "805_JSON_Import_Export_with_results.json")
reloaded.save_to_json(json_path_results, indent=2)
file_size_kb2 = os.path.getsize(json_path_results) / 1024
print(f"\nSaved model+results to: {json_path_results}  ({file_size_kb2:.1f} KB)")
print(f"(File grew from {file_size_kb:.1f} KB to {file_size_kb2:.1f} KB because results are included.)")


# =============================================================================
# Step 6: dict-based round-trip (no file needed)
# =============================================================================
data = model.to_dict(include_results=False)
print(f"\nto_dict() keys: {list(data.keys())}")

model_copy = FERS.from_dict(data)
print(f"from_dict() → Nodes: {model_copy.number_of_nodes()}, Members: {model_copy.number_of_elements()}")
model_copy.run_analysis()
dy3 = model_copy.resultsbundle.loadcases["Center load"].displacement_nodes["2"].dy
print(f"from_dict() analysis deflection: {dy3*1e3:.4f} mm  (matches: {abs(dy - dy3) < 1e-12})")
