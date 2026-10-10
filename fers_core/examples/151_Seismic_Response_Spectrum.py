"""
151 — Seismic Response Spectrum (EN 1998-1)
===========================================

A single-bay steel portal frame under horizontal earthquake load along its
span, analysed with both of the solver's methods:

  • modal response-spectrum analysis (MRSA), with the modes combined by CQC;
  • the lateral-force method, one static load shaped by the first mode.

The roof beam carries cladding, so its self-weight is overridden with
``Member.weight_override``. The solver uses that value as the beam's mass too.
The roof finishes are a permanent load case, turned into seismic mass with
``mass_sources``.

Cross-check:  the frame sways as one storey. The lateral-force base shear is
              EN 1998-1 (4.5) with λ = 1, the whole mass m at the first period:

                  F_b = S_d(T₁) · m

              MRSA counts the first mode's effective mass instead, close to the
              roof plus half of each column:

                  F_b ≈ S_d(T₁) · (m_roof + m_columns / 2)
"""

from fers_core import (
    FERS,
    DistributedLoad,
    Material,
    Member,
    MemberSet,
    NodalSupport,
    Node,
    Section,
    SeismicAnalysisSettings,
)
from fers_core.supports.supportcondition import SupportCondition

# =============================================================================
# Parameters
# =============================================================================
SPAN = 6.0  # [m]
HEIGHT = 4.0  # [m]
ROOF_WEIGHT = 3500.0  # beam + cladding self-weight [N/m], gravity included
FINISHES = 2000.0  # permanent roof finishes [N/m]

# EN 1998-1 Type 1 spectrum, ground type C: S = 1.15, T_B = 0.2 s, T_C = 0.6 s,
# T_D = 2.0 s.
AG = 2.0  # design ground acceleration [m/s²]
Q = 2.0  # behaviour factor

steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
heb200 = Section.from_name("HEB200", steel)
ipe300 = Section.from_name("IPE300", steel)

# =============================================================================
# Model: two fixed-base columns and a roof beam in the X-Y plane
# =============================================================================
model = FERS()

# The roof is held out of plane, as a wall brace would, so every mode sways in
# the frame's own plane.
braced = NodalSupport(
    displacement_conditions={"X": SupportCondition.free(), "Y": SupportCondition.free()},
    rotation_conditions={"Z": SupportCondition.free()},
)
left_base = Node(0.0, 0.0, 0.0, nodal_support=NodalSupport())
right_base = Node(SPAN, 0.0, 0.0, nodal_support=NodalSupport())
left_top = Node(0.0, HEIGHT, 0.0, nodal_support=braced)
right_top = Node(SPAN, HEIGHT, 0.0, nodal_support=braced)

# Split the beam so the solver can find its vertical modes as well.
roof_nodes = [left_top] + [Node(SPAN * i / 4, HEIGHT, 0.0) for i in range(1, 4)] + [right_top]
roof = [Member(a, b, section=ipe300, weight_override=ROOF_WEIGHT) for a, b in zip(roof_nodes, roof_nodes[1:])]
columns = [
    Member(left_base, left_top, section=heb200, rotation_angle=90.0),
    Member(right_base, right_top, section=heb200, rotation_angle=90.0),
]
model.add_member_set(MemberSet(members=columns + roof))

finishes = model.create_load_case("Roof finishes")
for member in roof:
    DistributedLoad(member=member, load_case=finishes, magnitude=FINISHES, direction=(0.0, -1.0, 0.0))

model.add_seismic_analysis(
    SeismicAnalysisSettings.eurocode_spectrum(ag=AG, ground_type="C", spectrum_type="TYPE1", q=Q),
    method="BOTH",
    directions=["X"],
    num_modes=6,
    mass_sources=[(finishes, 1.0)],
)

model.run_analysis()

# =============================================================================
# Results
# =============================================================================
results = model.resultsbundle.seismic
mrsa = results["modal_response_spectrum"]["per_direction"][0]
lateral = results["lateral_force"]["per_direction"][0]

print("=" * 72)
print("Modes, X direction")
print(f"  {'mode':>4}  {'T [s]':>7}  {'mass share':>10}  {'S_d [m/s²]':>10}")
for mode in mrsa["modes"]:
    print(
        f"  {mode['mode']:>4}  {mode['period']:7.3f}  {mode['effective_mass_ratio']:10.1%}"
        f"  {mode['spectral_acceleration']:10.3f}"
    )
print(f"  participating mass: {mrsa['participating_mass_ratio']:.1%} of {mrsa['total_seismic_mass']:.0f} kg")

# Hand check. S_d(T) for T_B <= T <= T_D (EN 1998-1 (3.14), (3.15)).
G = 9.81
roof_mass = (ROOF_WEIGHT + FINISHES) * SPAN / G
column_mass = 2 * HEIGHT * heb200.area * steel.density
period = mrsa["modes"][0]["period"]
s, t_c = 1.15, 0.6
s_d = AG * s * 2.5 / Q * min(1.0, t_c / period)
print("=" * 72)
print(f"Base shear, lateral force          {lateral['base_shear'] / 1000:7.2f} kN")
print(f"  S_d(T1) x all of the mass        {s_d * (roof_mass + column_mass) / 1000:7.2f} kN")
print(f"Base shear, MRSA                   {mrsa['base_shear'] / 1000:7.2f} kN")
print(f"  S_d(T1) x (roof + columns / 2)   {s_d * (roof_mass + column_mass / 2) / 1000:7.2f} kN")
print("=" * 72)
