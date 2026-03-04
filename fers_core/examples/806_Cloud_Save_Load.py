"""
806 — Cloud Save / Load  (FERS Cloud)
======================================
Demonstrates how to persist and retrieve a FERS model using the
FERS Cloud service.

Prerequisites:
  • A FERS Cloud account — register at https://app.fers.cloud
  • Your personal API key (found in your account settings)

Key features shown:
  • model.cloud_connect(api_key)       — authenticate with the API
  • model.cloud_save(name)             — upload the model
  • model.cloud_list()                 — list saved models
  • model.cloud_load(model_id)         — download a model
  • model.cloud_delete(model_id)       — remove a model

NOTE: This example will *not* run without valid credentials.
      Replace the placeholder API key below with your own.
"""

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
# Step 1: Build a small model
# =============================================================================
model = FERS()

steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)
section = Section.from_name("IPE200", steel)

node1 = Node(0, 0, 0)
node2 = Node(4, 0, 0)

beam = Member(start_node=node1, end_node=node2, section=section)

node1.nodal_support = NodalSupport()  # fully fixed
node2.nodal_support = NodalSupport(
    rotation_conditions={"X": "Free", "Y": "Free", "Z": "Free"},
)  # pin (translations fixed, rotations free)

ms = MemberSet(members=[beam])
model.add_member_set(ms)

lc = model.create_load_case(name="Gravity")
NodalLoad(node=node2, load_case=lc, magnitude=-10_000, direction=(0, 1, 0))


# =============================================================================
# Step 2: Connect to FERS Cloud
# =============================================================================
API_KEY = "your-api-key-here"  # ← replace with your real API key

try:
    model.cloud_connect(api_key=API_KEY)
    print("Connected to FERS Cloud ✓")
except Exception as e:
    print(f"Could not connect: {e}")
    print("Skipping cloud operations — provide a valid API key to run this example.")
    exit()


# =============================================================================
# Step 3: Save the model to the cloud
# =============================================================================
model.run_analysis()
saved_info = model.cloud_save(name="806_example_model")
print(f"Saved to cloud: {saved_info}")


# =============================================================================
# Step 4: List all models in your cloud account
# =============================================================================
models = model.cloud_list()
print(f"\nModels in your account ({len(models)}):")
for m in models:
    print(f"  • {m}")


# =============================================================================
# Step 5: Reload the model from the cloud
# =============================================================================
# Use the model ID from Step 3 or from the list above
if models:
    first_model_id = models[0].get("id") or models[0].get("_id")
    reloaded = model.cloud_load(first_model_id)
    print(
        f"\nReloaded model from cloud — Nodes: {reloaded.number_of_nodes()}, "
        f"Members: {reloaded.number_of_elements()}"
    )


# =============================================================================
# Step 6 (optional): Delete the model from the cloud
# =============================================================================
# Uncomment the following lines to clean up after the example:
#
# model.cloud_delete(first_model_id)
# print(f"Deleted model {first_model_id} from cloud")
