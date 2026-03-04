"""
801 — Section Library Lookup
============================
Demonstrates how to use the built-in European steel section library
to create sections by name (e.g. "IPE200", "HEB300", "RHS 200x100x8")
instead of entering dimensions manually.

Key features shown:
  • Section.from_name(name, material)  – one-liner section creation
  • Section.list_available(series)      – list all profiles in a series
  • Section.plot()                      – quick visual check of the shape
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
# Step 1: Material
# =============================================================================
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)


# =============================================================================
# Step 2: Pick a section straight from the library
# =============================================================================
# All European standard sections are available by name:
ipe200 = Section.from_name("IPE200", steel)
heb300 = Section.from_name("HEB300", steel)
rhs_200x100 = Section.from_name("RHS 200x100x8", steel)
shs_100 = Section.from_name("SHS 100x100x6", steel)
angle_100 = Section.from_name("L 100x100x10", steel)
chs_168 = Section.from_name("CHS 168.3x5", steel)
upe200 = Section.from_name("UPE200", steel)

# Print basic properties
for sec in [ipe200, heb300, rhs_200x100, shs_100, angle_100, chs_168, upe200]:
    print(
        f"{sec.name:25s}  A={sec.area*1e4:8.2f} cm²  "
        f"I_y={sec.i_y*1e8:10.2f} cm⁴  I_z={sec.i_z*1e8:10.2f} cm⁴  "
        f"J={sec.j*1e8:10.4f} cm⁴"
    )


# =============================================================================
# Step 3: List what is available
# =============================================================================
print("\n--- All IPE sizes ---")
print(Section.list_available("IPE"))

print("\n--- All SHS sizes ---")
print(Section.list_available("SHS"))

print(f"\nTotal sections in library: {len(Section.list_available())}")


# =============================================================================
# Step 4: Use a library section in a simple analysis
# =============================================================================
model = FERS()

node1 = Node(0, 0, 0)
node2 = Node(6, 0, 0)

beam = Member(start_node=node1, end_node=node2, section=ipe200)

node1.nodal_support = NodalSupport()  # fixed

member_set = MemberSet(members=[beam])
model.add_member_set(member_set)

lc = model.create_load_case(name="Tip load")
NodalLoad(node=node2, load_case=lc, magnitude=-10_000, direction=(0, 1, 0))

print("\nRunning analysis with IPE200 from library...")
model.run_analysis()

dy = model.resultsbundle.loadcases["Tip load"].displacement_nodes["2"].dy
print(f"Tip deflection dy = {dy*1e3:.3f} mm")


# =============================================================================
# Step 5 (optional): Plot the cross-section
# =============================================================================
# Uncomment the line below to show the cross-section plot:
# ipe200.plot()
