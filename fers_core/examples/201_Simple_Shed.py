"""
201 — Simple Shed  (3-D Portal Frame Structure with Bracing)
============================================================
A steel portal-frame shed modelled in 3-D, with cross-bracing in the
side walls and roof panels, and longitudinal base tie beams.

Geometry
--------
  Plan  : 6 m wide (X) x 8 m long (Z)
  Height: 3.0 m eave, 4.2 m at ridge (approx. 22 deg roof pitch)
  Two portal frames at Z = 0 m and Z = 8 m

         Ridge (3, 4.2, z)
            /\\
           /  \\
          /    \\
  Eave   /      \\   Eave
(0,3,z)           (6,3,z)
  |                   |
  |                   |
(0,0,z)           (6,0,z)

Bracing layout
--------------
  Side walls (left X=0, right X=6): X-brace between column base and
    opposite eave across the 8 m bay.
  Roof panels (left rafter side, right rafter side): X-brace between
    eave and opposite ridge node across the 8 m bay.
  Base ties: longitudinal IPE 100 beams connecting column bases
    along Z on both sides.

Sections (EN 10365 steel S235)
-------------------------------
  Columns   : HEA 140  -- ShapePath.create_he_profile
  Rafters   : IPE 160  -- ShapePath.create_ipe_profile
  Purlins   : IPE 120  -- ShapePath.create_ipe_profile
  Base ties : IPE 100  -- ShapePath.create_ipe_profile
  Bracing   : CHS 48.3x3.2  -- ShapePath.create_chs_profile

Supports
--------
  Column bases pinned (translations fixed, all rotations free).

Load cases
----------
  G  -- Permanent (self-weight as UDL on rafters and purlins)
  S  -- Snow      (EN 1991-1-3, s = mu1 x sk = 0.8 x 0.7 = 0.56 kN/m2,
                   tributary width per rafter = 3 m -> q = 1 680 N/m)
  W  -- Wind      (simplified horizontal UDL on windward columns, 0.6 kN/m)

Load combinations (EN 1990 STR, Eq. 6.10)
------------------------------------------
  ULS  : 1.35 G + 1.5 S
  SLS  : 1.0 G  + 1.0 S

Cloud
-----
  Saves the solved model to FERS Cloud under the name "201_simple_shed".
  Replace API_KEY with your own key from https://ferscloud.com/settings/api-keys.
"""

import os

from fers_core import (
    FERS,
    Node,
    Member,
    MemberSet,
    Material,
    Section,
    ShapePath,
    NodalSupport,
    DistributedLoad,
    AnalysisOrder,
)

# =============================================================================
# 0.  Shared properties
# =============================================================================
model = FERS()
model.settings.analysis_options.order = AnalysisOrder.LINEAR

S235 = Material(name="S235", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# ---------------------------------------------------------------------------
# HEA 140  (columns)
# EN 10365: A=31.4 cm2, Iy=1033 cm4, Iz=389.3 cm4, J=8.13 cm4
# ---------------------------------------------------------------------------
_sp_col = ShapePath(
    name="HEA140",
    shape_commands=ShapePath.create_he_profile(h=0.133, b=0.140, t_f=0.0085, t_w=0.0055, r=0.012),
)
sec_column = Section(
    name="HEA140", material=S235,
    area=31.4e-4, i_z=1033e-8, i_y=389.3e-8, j=8.13e-8,
    h=0.133, b=0.140, shape_path=_sp_col,
)

# ---------------------------------------------------------------------------
# IPE 160  (rafters)
# EN 10365: A=20.1 cm2, Iy=869 cm4, Iz=68.3 cm4, J=3.60 cm4
# ---------------------------------------------------------------------------
_sp_raf = ShapePath(
    name="IPE160",
    shape_commands=ShapePath.create_ipe_profile(h=0.160, b=0.082, t_f=0.0074, t_w=0.0050, r=0.009),
)
sec_rafter = Section(
    name="IPE160", material=S235,
    area=20.1e-4, i_z=869e-8, i_y=68.3e-8, j=3.60e-8,
    h=0.160, b=0.082, shape_path=_sp_raf,
)

# ---------------------------------------------------------------------------
# IPE 120  (purlins)
# EN 10365: A=13.2 cm2, Iy=318 cm4, Iz=27.7 cm4, J=1.74 cm4
# ---------------------------------------------------------------------------
_sp_purl = ShapePath(
    name="IPE120",
    shape_commands=ShapePath.create_ipe_profile(h=0.120, b=0.064, t_f=0.0063, t_w=0.0044, r=0.007),
)
sec_purlin = Section(
    name="IPE120", material=S235,
    area=13.2e-4, i_z=318e-8, i_y=27.7e-8, j=1.74e-8,
    h=0.120, b=0.064, shape_path=_sp_purl,
)

# ---------------------------------------------------------------------------
# IPE 100  (base tie beams)
# EN 10365: A=10.3 cm2, Iy=171 cm4, Iz=15.9 cm4, J=1.27 cm4
# ---------------------------------------------------------------------------
_sp_tie = ShapePath(
    name="IPE100",
    shape_commands=ShapePath.create_ipe_profile(h=0.100, b=0.055, t_f=0.0057, t_w=0.0041, r=0.007),
)
sec_tie = Section(
    name="IPE100", material=S235,
    area=10.3e-4, i_z=171e-8, i_y=15.9e-8, j=1.27e-8,
    h=0.100, b=0.055, shape_path=_sp_tie,
)

# ---------------------------------------------------------------------------
# CHS 48.3x3.2  (cross-bracing, wall and roof)
# EN 10219: A=4.53 cm2, I=11.6 cm4 (symmetric), J=23.2 cm4
# ---------------------------------------------------------------------------
_sp_brace = ShapePath(
    name="CHS 48.3x3.2",
    shape_commands=ShapePath.create_chs_profile(d=0.0483, t=0.0032),
)
sec_brace = Section(
    name="CHS 48.3x3.2", material=S235,
    area=4.53e-4, i_z=11.6e-8, i_y=11.6e-8, j=23.2e-8,
    h=0.0483, b=0.0483, shape_path=_sp_brace,
)

# Pinned base: translations fixed, all rotations free
pinned_base = NodalSupport(
    displacement_conditions={"X": "Fixed", "Y": "Fixed", "Z": "Fixed"},
    rotation_conditions={"X": "Free", "Y": "Free", "Z": "Free"},
)

# =============================================================================
# 1.  Nodes  (Y = vertical up)
# =============================================================================
# Portal frame at Z = 0
n1  = Node(0, 0,   0, nodal_support=pinned_base)   # left  column base
n2  = Node(6, 0,   0, nodal_support=pinned_base)   # right column base
n3  = Node(0, 3.0, 0)                               # left  eave
n4  = Node(3, 4.2, 0)                               # ridge
n5  = Node(6, 3.0, 0)                               # right eave

# Portal frame at Z = 8
n6  = Node(0, 0,   8, nodal_support=pinned_base)   # left  column base
n7  = Node(6, 0,   8, nodal_support=pinned_base)   # right column base
n8  = Node(0, 3.0, 8)                               # left  eave
n9  = Node(3, 4.2, 8)                               # ridge
n10 = Node(6, 3.0, 8)                               # right eave

# =============================================================================
# 2.  Members
# =============================================================================

# --- Portal frames -----------------------------------------------------------
col_L1    = Member(n1,  n3,  section=sec_column)
col_R1    = Member(n2,  n5,  section=sec_column)
rafter_L1 = Member(n3,  n4,  section=sec_rafter)
rafter_R1 = Member(n4,  n5,  section=sec_rafter)

col_L2    = Member(n6,  n8,  section=sec_column)
col_R2    = Member(n7,  n10, section=sec_column)
rafter_L2 = Member(n8,  n9,  section=sec_rafter)
rafter_R2 = Member(n9,  n10, section=sec_rafter)

# --- Purlins (eaves + ridge) -------------------------------------------------
purlin_eave_L = Member(n3,  n8,  section=sec_purlin)
purlin_eave_R = Member(n5,  n10, section=sec_purlin)
purlin_ridge  = Member(n4,  n9,  section=sec_purlin)

# --- Base tie beams (IPE 100, connecting column bases along Z) ---------------
tie_L = Member(n1, n6, section=sec_tie)   # left  base tie
tie_R = Member(n2, n7, section=sec_tie)   # right base tie

# --- Side wall cross-bracing (CHS 48.3x3.2, X-brace each side wall) ---------
# Left wall  (X = 0): base-to-opposite-eave diagonals
brace_wall_L1 = Member(n1, n8,  section=sec_brace)   # base Z=0 -> eave Z=8
brace_wall_L2 = Member(n3, n6,  section=sec_brace)   # eave Z=0 -> base Z=8

# Right wall (X = 6): base-to-opposite-eave diagonals
brace_wall_R1 = Member(n2, n10, section=sec_brace)   # base Z=0 -> eave Z=8
brace_wall_R2 = Member(n5, n7,  section=sec_brace)   # eave Z=0 -> base Z=8

# --- Roof cross-bracing (CHS 48.3x3.2, X-brace each roof panel) -------------
# Left roof panel  (eave L <-> ridge): eave/ridge at Z=0 vs Z=8
brace_roof_L1 = Member(n3, n9,  section=sec_brace)   # eave Z=0 -> ridge Z=8
brace_roof_L2 = Member(n4, n8,  section=sec_brace)   # ridge Z=0 -> eave Z=8

# Right roof panel (ridge <-> eave R):
brace_roof_R1 = Member(n4, n10, section=sec_brace)   # ridge Z=0 -> eave Z=8
brace_roof_R2 = Member(n5, n9,  section=sec_brace)   # eave Z=0 -> ridge Z=8

# =============================================================================
# 3.  Member sets
# =============================================================================
ms_frame1  = MemberSet(
    members=[col_L1, col_R1, rafter_L1, rafter_R1],
    classification="Frame Z=0",
)
ms_frame2  = MemberSet(
    members=[col_L2, col_R2, rafter_L2, rafter_R2],
    classification="Frame Z=8",
)
ms_purlins = MemberSet(
    members=[purlin_eave_L, purlin_eave_R, purlin_ridge],
    classification="Purlins",
)
ms_ties = MemberSet(
    members=[tie_L, tie_R],
    classification="Base ties",
)
ms_wall_bracing = MemberSet(
    members=[brace_wall_L1, brace_wall_L2, brace_wall_R1, brace_wall_R2],
    classification="Wall bracing",
)
ms_roof_bracing = MemberSet(
    members=[brace_roof_L1, brace_roof_L2, brace_roof_R1, brace_roof_R2],
    classification="Roof bracing",
)

model.add_member_set(
    ms_frame1, ms_frame2,
    ms_purlins,
    ms_ties,
    ms_wall_bracing,
    ms_roof_bracing,
)

# =============================================================================
# 4.  Load cases
# =============================================================================
lc_G = model.create_load_case(name="G - Permanent")
lc_S = model.create_load_case(name="S - Snow")
lc_W = model.create_load_case(name="W - Wind")

# G: steel self-weight as uniform downward UDL on rafters and purlins
# IPE 160 approx. 15.8 kg/m -> 155 N/m;  IPE 120 approx. 10.4 kg/m -> 102 N/m
for rafter in [rafter_L1, rafter_R1, rafter_L2, rafter_R2]:
    DistributedLoad(member=rafter, load_case=lc_G, magnitude=155, direction=(0, -1, 0))
for purlin in [purlin_eave_L, purlin_eave_R, purlin_ridge]:
    DistributedLoad(member=purlin, load_case=lc_G, magnitude=102, direction=(0, -1, 0))

# S: snow -- EN 1991-1-3  s = mu1 x sk = 0.8 x 0.7 kN/m2 = 0.56 kN/m2
# Each rafter carries a tributary width of 3 m -> line load = 1 680 N/m (vertical)
for rafter in [rafter_L1, rafter_R1, rafter_L2, rafter_R2]:
    DistributedLoad(member=rafter, load_case=lc_S, magnitude=1_680, direction=(0, -1, 0))

# W: simplified wind pressure on windward columns (horizontal, +X direction)
for col in [col_L1, col_L2]:
    DistributedLoad(member=col, load_case=lc_W, magnitude=600, direction=(1, 0, 0))

# =============================================================================
# 5.  Load combinations  (EN 1990 STR)
# =============================================================================
model.create_load_combination(
    name="ULS: 1.35G + 1.5S",
    load_cases_factors={lc_G: 1.35, lc_S: 1.5},
    situation="ULS",
    check="ALL",
)
model.create_load_combination(
    name="SLS: G + S",
    load_cases_factors={lc_G: 1.0, lc_S: 1.0},
    situation="SLS",
    check="ALL",
)

# =============================================================================
# 6.  Run analysis
# =============================================================================
print("Running analysis: 201 Simple Shed (with bracing)")
model.run_analysis()

rb = model.resultsbundle
sls_res = rb.loadcombinations["SLS: G + S"]
uls_res = rb.loadcombinations["ULS: 1.35G + 1.5S"]

print("\n--- Ridge displacements (SLS: G + S) ---")
for label, node_id in [("Z=0", n4.id), ("Z=8", n9.id)]:
    d = sls_res.displacement_nodes.get(str(node_id))
    if d:
        print(f"  Ridge {label}: dy = {d.dy * 1000:.2f} mm")

print("\n--- Column base reactions (ULS: 1.35G + 1.5S) ---")
support_labels = {
    str(n1.id): "n1 left  Z=0", str(n2.id): "n2 right Z=0",
    str(n6.id): "n6 left  Z=8", str(n7.id): "n7 right Z=8",
}
for k, rn in uls_res.reaction_nodes.items():
    f = rn.nodal_forces
    label = support_labels.get(k, k)
    print(f"  {label}: Fy = {f.fy / 1000:.2f} kN   Fx = {f.fx / 1000:.2f} kN")

# =============================================================================
# 7.  Save JSON
# =============================================================================
_here = os.path.dirname(os.path.abspath(__file__))
_cloud_public = os.path.normpath(
    os.path.join(_here, "..", "..", "..", "FERS_cloud", "public")
)
json_path = os.path.join(_cloud_public, "201_Simple_Shed.json")
os.makedirs(os.path.dirname(json_path), exist_ok=True)
model.save_to_json(json_path, indent=4)
print(f"\nJSON saved -> {json_path}")

# =============================================================================
# 8.  Save to FERS Cloud
# =============================================================================
API_KEY = "your-api-key-here"  # <- replace with your real API key

try:
    model.cloud_connect(api_key=API_KEY)
    print("\nConnected to FERS Cloud")
    saved = model.cloud_save(name="201_simple_shed")
    print(f"Saved to cloud - ID: {saved.get('id')}")
except Exception as e:
    print(f"\nCloud save skipped: {e}")
    print("Provide a valid API key to upload the model.")
