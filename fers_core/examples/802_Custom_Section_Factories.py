"""
802 — Custom Section Factories
===============================
Demonstrates how to create sections from explicit dimensions using
the factory methods:

  • Section.create_rhs()            — Rectangular Hollow Section
  • Section.create_shs()            — Square Hollow Section
  • Section.create_angle_section()  — L-section (equal / unequal angle)
  • Section.create_welded_i_section() — Welded / built-up I-section
  • Section.create_cfs_c()          — Cold-formed steel lipped C
  • Section.create_cfs_z()          — Cold-formed steel lipped Z

These are useful when the profile is non-standard or not included in
the built-in library.  All dimensions are in metres.
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
# Step 2: Create sections using factory methods
# =============================================================================

# --- Rectangular Hollow Section 200×100×8 with 2t outer corner radius ---
rhs = Section.create_rhs(
    name="RHS 200x100x8",
    material=steel,
    h=0.200,
    b=0.100,
    t=0.008,
    r_out=0.016,  # typically 2·t for hot-finished
)

# --- Square Hollow Section 120×120×6 ---
shs = Section.create_shs(
    name="SHS 120x120x6",
    material=steel,
    b=0.120,
    t=0.006,
)

# --- Equal angle L 100×100×10 ---
angle = Section.create_angle_section(
    name="L 100x100x10",
    material=steel,
    h=0.100,
    b=0.100,
    t=0.010,
    r_root=0.012,
)

# --- Unequal angle L 150×90×12 ---
angle_uneq = Section.create_angle_section(
    name="L 150x90x12",
    material=steel,
    h=0.150,
    b=0.090,
    t=0.012,
    r_root=0.013,
)

# --- Welded I-section (built from plates, no root fillet) ---
welded_i = Section.create_welded_i_section(
    name="Welded I 600×300×20×12",
    material=steel,
    h=0.600,
    b=0.300,
    t_f=0.020,
    t_w=0.012,
)

# --- Cold-formed lipped C channel ---
cfs_c = Section.create_cfs_c(
    name="CFS C 200×75×20×2.0",
    material=steel,
    h=0.200,
    b=0.075,
    lip=0.020,
    t=0.002,
    r_out=0.004,  # 2·t
)

# --- Cold-formed lipped Z purlin ---
cfs_z = Section.create_cfs_z(
    name="CFS Z 200×75×75×20×2.0",
    material=steel,
    h=0.200,
    b_top=0.075,
    b_bot=0.075,
    lip=0.020,
    t=0.002,
    r_out=0.004,
)


# =============================================================================
# Step 3: Print summary of all sections
# =============================================================================
sections = [rhs, shs, angle, angle_uneq, welded_i, cfs_c, cfs_z]

print(f"{'Section':<30s}  {'A (cm²)':>10s}  {'I_y (cm⁴)':>12s}  " f"{'I_z (cm⁴)':>12s}  {'J (cm⁴)':>12s}")
print("-" * 85)
for sec in sections:
    print(
        f"{sec.name:<30s}  {sec.area*1e4:10.2f}  {sec.i_y*1e8:12.2f}  "
        f"{sec.i_z*1e8:12.2f}  {sec.j*1e8:12.4f}"
    )


# =============================================================================
# Step 4: Quick cantilever analysis with the welded I
# =============================================================================
model = FERS()

node1 = Node(0, 0, 0)
node2 = Node(8, 0, 0)

beam = Member(start_node=node1, end_node=node2, section=welded_i)
node1.nodal_support = NodalSupport()

ms = MemberSet(members=[beam])
model.add_member_set(ms)

lc = model.create_load_case(name="End load")
NodalLoad(node=node2, load_case=lc, magnitude=-50_000, direction=(0, 1, 0))

print("\nRunning analysis with welded I 600×300...")
model.run_analysis()

dy = model.resultsbundle.loadcases["End load"].displacement_nodes["2"].dy
print(f"Tip deflection dy = {dy*1e3:.3f} mm")


# =============================================================================
# Step 5 (optional): Visualise the cross-sections
# =============================================================================
# Uncomment any of the lines below to see the cross-section plot:
# rhs.plot()
# shs.plot()
# angle.plot()
# welded_i.plot()
# cfs_c.plot()
# cfs_z.plot()
