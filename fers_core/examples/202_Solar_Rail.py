"""
202 — Solar Rail  (Ballasted Flat-Roof 2x2 Solar Panel Mounting Frame)
=======================================================================
Models the complete aluminium rail frame for a 2x2 ballasted solar panel
array on a flat or low-slope roof.  No roof penetrations are used.

Geometry
--------
  The panels are tilted at 15 degrees from horizontal (Z = south-facing).
  Each foot location has a vertical leg from the ballast base (Y = 0) up
  to the tilted rail frame above.

  Front (low side, Z = 0): leg height = 150 mm
  Back  (high side, Z = 3.5 m): leg height = 1 088 mm   (150 + 3.5*tan15)

  Base foot grid (Y = 0, all pinned):
      X=0    X=1.1   X=2.2
  Z=0  b1 ---- b2 ---- b3
       |        |        |     <- vertical legs (SHS 40x40x2)
  Z=1.75 b4 --- b5 ---- b6
       |        |        |
  Z=3.5 b7 ---- b8 ---- b9

  Rail frame (elevated, tilted 15 deg):
      X=0    X=1.1   X=2.2
  Z=0  r1 ---- r2 ---- r3     Y = 0.150 m  <- front cross-rail
       |        |        |     <- longitudinal rails (RHS 60x40x2, tilted)
  Z=1.75 r4 --- r5 ---- r6   Y = 0.619 m  <- mid cross-rail
       |        |        |
  Z=3.5 r7 ---- r8 ---- r9   Y = 1.088 m  <- back cross-rail

Panel dimensions (standard 400 Wp portrait)
--------------------------------------------
  Width  : 1 100 mm  ->  2 panels wide = 2 200 mm total (X)
  Height : 1 750 mm  ->  2 panels tall = 3 500 mm total (Z-slope)
  Mass   : 21 kg each  ->  84 kg for 4 panels

Sections (aluminium EN AW-6005A T6, analytical thin-wall properties)
---------------------------------------------------------------------
  Longitudinal rails : RHS 60x40x2 mm  (h=60 mm vertical, strong axis)
  Cross-rails + legs : SHS 40x40x2 mm

Load cases
----------
  G   - Permanent : panel self-weight distributed to longitudinal rails.
                    Loads applied per unit MEMBER length (cos-corrected for tilt).
  S   - Snow      : EN 1991-1-3  mu1=0.8, sk=0.70 kN/m2  -> s=0.56 kN/m2
                    Applied per unit member length (cos(15) correction).
  Wu  - Wind uplift: EN 1991-1-4 edge zone  Cp,net=2.0, qp=0.80 kN/m2
                    Applied per unit member length (cos(15) correction).

Load combinations (EN 1990 STR, Eq. 6.10)
------------------------------------------
  ULS gravity : 1.35 G + 1.5 S
  ULS uplift  : 1.0 G  + 1.5 Wu
  SLS         : 1.0 G  + 1.0 S

Cloud
-----
  Saves the solved model to FERS Cloud as "202_solar_rail".
  Replace API_KEY with your own key from https://ferscloud.com/settings/api-keys.
"""

import math
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
# 0.  Geometry constants
# =============================================================================
TILT_DEG  = 15.0
_cos_tilt = math.cos(math.radians(TILT_DEG))
_tan_tilt = math.tan(math.radians(TILT_DEG))

Y_FRONT = 0.150                           # front leg height (m)
Y_MID   = Y_FRONT + 1.75 * _tan_tilt     # 0.619 m
Y_BACK  = Y_FRONT + 3.50 * _tan_tilt     # 1.088 m

# =============================================================================
# 1.  Material
# =============================================================================
model = FERS()
model.settings.analysis_options.order = AnalysisOrder.LINEAR

aluminum = Material(
    name="EN AW-6005A T6",
    e_mod=70_000e6,
    g_mod=26_000e6,
    density=2_700,
    yield_stress=215e6,
)

# =============================================================================
# 2.  Sections with ShapePaths for the 3-D viewer
# =============================================================================

# --- RHS 60x40x2 mm  (longitudinal rails) ------------------------------------
_h, _b, _t, _r = 0.060, 0.040, 0.002, 0.004
_sp_rhs = ShapePath(
    name="RHS 60x40x2",
    shape_commands=ShapePath.create_rhs_profile(h=_h, b=_b, t=_t, r_out=_r),
)
sec_long = Section(
    name="RHS 60x40x2",
    material=aluminum,
    area=2 * _t * (_h + _b - 2 * _t),
    i_z=(_b * _h**3 - (_b - 2*_t) * (_h - 2*_t)**3) / 12,
    i_y=(_h * _b**3 - (_h - 2*_t) * (_b - 2*_t)**3) / 12,
    j=4 * ((_h - _t) * (_b - _t))**2 * _t / (2 * ((_h - _t) + (_b - _t))),
    h=_h, b=_b, shape_path=_sp_rhs,
)

# --- SHS 40x40x2 mm  (cross-rails and support legs) -------------------------
_s, _ts, _rs = 0.040, 0.002, 0.004
_sp_shs = ShapePath(
    name="SHS 40x40x2",
    shape_commands=ShapePath.create_rhs_profile(h=_s, b=_s, t=_ts, r_out=_rs),
)
sec_cross = Section(
    name="SHS 40x40x2",
    material=aluminum,
    area=2 * _ts * (_s + _s - 2 * _ts),
    i_z=(_s * _s**3 - (_s - 2*_ts)**4) / 12,
    i_y=(_s * _s**3 - (_s - 2*_ts)**4) / 12,
    j=4 * ((_s - _ts)**2)**2 * _ts / (4 * (_s - _ts)),
    h=_s, b=_s, shape_path=_sp_shs,
)

# =============================================================================
# 3.  Nodes
# =============================================================================
foot = NodalSupport(
    displacement_conditions={"X": "Fixed", "Y": "Fixed", "Z": "Fixed"},
    rotation_conditions={"X": "Free", "Y": "Free", "Z": "Free"},
)

# --- Base foot nodes (Y = 0, ballast level, all pinned) ----------------------
b1 = Node(0.0, 0, 0.00, nodal_support=foot)   # front-left  base
b2 = Node(1.1, 0, 0.00, nodal_support=foot)   # front-centre base
b3 = Node(2.2, 0, 0.00, nodal_support=foot)   # front-right  base
b4 = Node(0.0, 0, 1.75, nodal_support=foot)   # mid-left     base
b5 = Node(1.1, 0, 1.75, nodal_support=foot)   # mid-centre   base
b6 = Node(2.2, 0, 1.75, nodal_support=foot)   # mid-right    base
b7 = Node(0.0, 0, 3.50, nodal_support=foot)   # back-left    base
b8 = Node(1.1, 0, 3.50, nodal_support=foot)   # back-centre  base
b9 = Node(2.2, 0, 3.50, nodal_support=foot)   # back-right   base

# --- Rail frame nodes (elevated, tilted at 15 deg) ---------------------------
r1 = Node(0.0, Y_FRONT, 0.00)    # front-left  rail
r2 = Node(1.1, Y_FRONT, 0.00)    # front-centre rail
r3 = Node(2.2, Y_FRONT, 0.00)    # front-right  rail
r4 = Node(0.0, Y_MID,   1.75)    # mid-left     rail
r5 = Node(1.1, Y_MID,   1.75)    # mid-centre   rail
r6 = Node(2.2, Y_MID,   1.75)    # mid-right    rail
r7 = Node(0.0, Y_BACK,  3.50)    # back-left    rail
r8 = Node(1.1, Y_BACK,  3.50)    # back-centre  rail
r9 = Node(2.2, Y_BACK,  3.50)    # back-right   rail

# =============================================================================
# 4.  Members
# =============================================================================

# --- Vertical support legs (base -> rail, 9 members) ------------------------
leg_1 = Member(b1, r1, section=sec_cross)
leg_2 = Member(b2, r2, section=sec_cross)
leg_3 = Member(b3, r3, section=sec_cross)
leg_4 = Member(b4, r4, section=sec_cross)
leg_5 = Member(b5, r5, section=sec_cross)
leg_6 = Member(b6, r6, section=sec_cross)
leg_7 = Member(b7, r7, section=sec_cross)
leg_8 = Member(b8, r8, section=sec_cross)
leg_9 = Member(b9, r9, section=sec_cross)

# --- Longitudinal rails (tilted at 15 deg, run along Z, 6 members) ----------
long_L1 = Member(r1, r4, section=sec_long)   # left  rail, front bay
long_L2 = Member(r4, r7, section=sec_long)   # left  rail, back  bay
long_C1 = Member(r2, r5, section=sec_long)   # centre rail, front bay
long_C2 = Member(r5, r8, section=sec_long)   # centre rail, back  bay
long_R1 = Member(r3, r6, section=sec_long)   # right rail, front bay
long_R2 = Member(r6, r9, section=sec_long)   # right rail, back  bay

# --- Cross-rails (horizontal, run along X, 6 members) -----------------------
cross_F1 = Member(r1, r2, section=sec_cross)  # front cross-rail, left  bay
cross_F2 = Member(r2, r3, section=sec_cross)  # front cross-rail, right bay
cross_M1 = Member(r4, r5, section=sec_cross)  # mid   cross-rail, left  bay
cross_M2 = Member(r5, r6, section=sec_cross)  # mid   cross-rail, right bay
cross_B1 = Member(r7, r8, section=sec_cross)  # back  cross-rail, left  bay
cross_B2 = Member(r8, r9, section=sec_cross)  # back  cross-rail, right bay

ms_legs  = MemberSet(
    members=[leg_1, leg_2, leg_3, leg_4, leg_5, leg_6, leg_7, leg_8, leg_9],
    classification="Support legs",
)
ms_long  = MemberSet(
    members=[long_L1, long_L2, long_C1, long_C2, long_R1, long_R2],
    classification="Longitudinal rails",
)
ms_cross = MemberSet(
    members=[cross_F1, cross_F2, cross_M1, cross_M2, cross_B1, cross_B2],
    classification="Cross-rails",
)

model.add_member_set(ms_legs, ms_long, ms_cross)

# =============================================================================
# 5.  Load cases
# =============================================================================
lc_G  = model.create_load_case(name="G - Permanent")
lc_S  = model.create_load_case(name="S - Snow")
lc_Wu = model.create_load_case(name="Wu - Wind Uplift")

# Loads are applied per unit member length on the tilted longitudinal rails.
# A load q [N/m2] on the horizontal plan projects to q * trib_width * cos(tilt)
# [N/m] along the inclined member.

# Panel self-weight: 84 kg * 9.81 N/kg = 823.8 N over 2.2 m x 3.5 m plan area
# = 107.0 N/m2  ->  per unit rail length (cos-corrected):
#   outer rail (trib 0.55 m): 107.0 * 0.55 * cos15 = 57 N/m
#   centre rail (trib 1.10 m): 107.0 * 1.10 * cos15 = 114 N/m
_G_outer  = round(107.0 * 0.55 * _cos_tilt)   # 57 N/m
_G_centre = round(107.0 * 1.10 * _cos_tilt)   # 114 N/m

outer_rails  = [long_L1, long_L2, long_R1, long_R2]
centre_rails = [long_C1, long_C2]

for m in outer_rails:
    DistributedLoad(member=m, load_case=lc_G, magnitude=_G_outer,  direction=(0, -1, 0))
for m in centre_rails:
    DistributedLoad(member=m, load_case=lc_G, magnitude=_G_centre, direction=(0, -1, 0))

# Snow: s = mu1 * sk = 0.8 * 0.70 = 0.56 kN/m2
# outer rail: 560 * 0.55 * cos15 = 298 N/m
# centre rail: 560 * 1.10 * cos15 = 595 N/m
_S_outer  = round(560 * 0.55 * _cos_tilt)   # 298 N/m
_S_centre = round(560 * 1.10 * _cos_tilt)   # 595 N/m

for m in outer_rails:
    DistributedLoad(member=m, load_case=lc_S, magnitude=_S_outer,  direction=(0, -1, 0))
for m in centre_rails:
    DistributedLoad(member=m, load_case=lc_S, magnitude=_S_centre, direction=(0, -1, 0))

# Wind uplift: Cp,net = 2.0, qp = 0.80 kN/m2  -> q = 1.60 kN/m2
# outer: 1600 * 0.55 * cos15 = 850 N/m upward
# centre: 1600 * 1.10 * cos15 = 1700 N/m upward
_Wu_outer  = round(1600 * 0.55 * _cos_tilt)   # 850 N/m
_Wu_centre = round(1600 * 1.10 * _cos_tilt)   # 1700 N/m

for m in outer_rails:
    DistributedLoad(member=m, load_case=lc_Wu, magnitude=_Wu_outer,  direction=(0, 1, 0))
for m in centre_rails:
    DistributedLoad(member=m, load_case=lc_Wu, magnitude=_Wu_centre, direction=(0, 1, 0))

# =============================================================================
# 6.  Load combinations
# =============================================================================
model.create_load_combination(
    name="ULS: 1.35G + 1.5S",
    load_cases_factors={lc_G: 1.35, lc_S: 1.5},
    situation="ULS",
    check="ALL",
)
model.create_load_combination(
    name="ULS: 1.0G + 1.5Wu",
    load_cases_factors={lc_G: 1.0, lc_Wu: 1.5},
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
# 7.  Run analysis
# =============================================================================
print("Running analysis: 202 Solar Rail (2x2 array, 15 deg tilt)")
model.run_analysis()

rb       = model.resultsbundle
uls_grav = rb.loadcombinations["ULS: 1.35G + 1.5S"]
uls_lift = rb.loadcombinations["ULS: 1.0G + 1.5Wu"]

foot_labels = {
    str(b1.id): "front-left",   str(b2.id): "front-centre", str(b3.id): "front-right",
    str(b4.id): "mid-left",     str(b5.id): "mid-centre",   str(b6.id): "mid-right",
    str(b7.id): "back-left",    str(b8.id): "back-centre",  str(b9.id): "back-right",
}

print("\n--- Foot reactions (ULS: 1.35G + 1.5S - gravity) ---")
for k, rn in uls_grav.reaction_nodes.items():
    label = foot_labels.get(k, k)
    print(f"  {label:<16s}: Fy = {rn.nodal_forces.fy / 1000:+.3f} kN")

print("\n--- Foot reactions (ULS: 1.0G + 1.5Wu - uplift, ballast check) ---")
for k, rn in uls_lift.reaction_nodes.items():
    label = foot_labels.get(k, k)
    print(f"  {label:<16s}: Fy = {rn.nodal_forces.fy / 1000:+.3f} kN")

# =============================================================================
# 8.  Save JSON
# =============================================================================
_here = os.path.dirname(os.path.abspath(__file__))
_cloud_public = os.path.normpath(
    os.path.join(_here, "..", "..", "..", "FERS_cloud", "public")
)
json_path = os.path.join(_cloud_public, "202_Solar_Rail.json")
os.makedirs(os.path.dirname(json_path), exist_ok=True)
model.save_to_json(json_path, indent=4)
print(f"\nJSON saved -> {json_path}")

# =============================================================================
# 9.  Save to FERS Cloud
# =============================================================================
API_KEY = "your-api-key-here"  # <- replace with your real API key

try:
    model.cloud_connect(api_key=API_KEY)
    print("\nConnected to FERS Cloud")
    saved = model.cloud_save(name="202_solar_rail")
    print(f"Saved to cloud - ID: {saved.get('id')}")
except Exception as e:
    print(f"\nCloud save skipped: {e}")
    print("Provide a valid API key to upload the model.")
