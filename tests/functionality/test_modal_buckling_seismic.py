"""Authoring + round-trip + end-to-end coverage for the optional modal,
buckling and seismic analysis blocks added in solver 0.2.37."""

import math

from fers_core import (
    FERS,
    Node,
    Member,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    NodalLoad,
    modal_analysis,
    buckling_analysis,
    seismic_analysis,
    eurocode_spectrum,
    direct_spectrum,
    custom_spectrum,
    load_case_ref,
    load_combination_ref,
    seismic_mass_source,
)
from fers_core.types.pydantic_models import (
    ModalAnalysisSettings,
    BucklingAnalysisSettings,
    SeismicAnalysisSettings,
)


# ── small reusable models ────────────────────────────────────────────────────


def _cantilever(length=5.0, b=0.1, n_el=10, density=7850.0):
    """Fixed-base square cantilever along global X (SI units)."""
    calc = FERS()
    mat = Material(name="S235", e_mod=210e9, g_mod=80.769e9, density=density, yield_stress=235e6)
    sec = Section(name="SQ", material=mat, i_y=b**4 / 12, i_z=b**4 / 12, j=0.1406 * b**4, area=b * b)
    nodes = [Node(length * i / n_el, 0, 0) for i in range(n_el + 1)]
    nodes[0].nodal_support = NodalSupport()
    members = [Member(start_node=nodes[i], end_node=nodes[i + 1], section=sec) for i in range(n_el)]
    calc.add_member_set(MemberSet(members=members))
    return calc, nodes


# ── authoring → wire shape ───────────────────────────────────────────────────


def test_modal_serializes_into_analysis():
    calc, _ = _cantilever()
    calc.analysis.set_modal(modal_analysis(num_modes=4, mass_formulation="CONSISTENT"))
    modal = calc.to_dict(include_results=False)["analysis"]["modal"]
    assert modal == {"num_modes": 4, "mass_formulation": "CONSISTENT"}
    ModalAnalysisSettings(**modal)  # validates against the generated schema


def test_buckling_reference_is_externally_tagged():
    calc, nodes = _cantilever()
    lc = calc.create_load_case(name="Axial")
    NodalLoad(node=nodes[-1], load_case=lc, magnitude=1000.0, direction=(-1, 0, 0))
    calc.analysis.set_buckling(buckling_analysis(num_modes=2, reference=load_case_ref(lc.id)))
    buckling = calc.to_dict(include_results=False)["analysis"]["buckling"]
    assert buckling["reference"] == {"LoadCase": lc.id}
    BucklingAnalysisSettings(**buckling)
    # the combination variant tags differently
    assert load_combination_ref(7) == {"LoadCombination": 7}


def test_seismic_spectrum_variants_and_validation():
    calc, _ = _cantilever()
    calc.analysis.set_seismic(
        seismic_analysis(
            method="MODAL_RESPONSE_SPECTRUM",
            num_modes=6,
            spectrum_x=eurocode_spectrum(ag=2.0, ground_type="B", spectrum_type="TYPE1", q=1.5),
            spectrum_y=direct_spectrum(ag=2.0, s=1.2, tb=0.15, tc=0.5, td=2.0, q=1.5),
            spectrum_z=custom_spectrum([[0.0, 1.0], [1.0, 2.5], [3.0, 0.5]]),
            mass_sources=[seismic_mass_source(1, 1.0)],
            directions=["X", "Y", "Z"],
            modal_combination="CQC",
            directional_combination="PERCENT30",
            damping=0.05,
        )
    )
    seismic = calc.to_dict(include_results=False)["analysis"]["seismic"]
    assert "EurocodeParametric" in seismic["spectrum_x"]
    assert "DirectParameters" in seismic["spectrum_y"]
    assert "CustomPoints" in seismic["spectrum_z"]
    assert seismic["directional_combination"] == "PERCENT30"
    SeismicAnalysisSettings(**seismic)


def test_unset_blocks_are_omitted_from_wire():
    calc, _ = _cantilever()
    analysis = calc.to_dict(include_results=False)["analysis"]
    assert "modal" not in analysis
    assert "buckling" not in analysis
    assert "seismic" not in analysis


# ── round-trip ───────────────────────────────────────────────────────────────


def test_round_trip_preserves_all_three_blocks():
    calc, nodes = _cantilever()
    lc = calc.create_load_case(name="Axial")
    NodalLoad(node=nodes[-1], load_case=lc, magnitude=1000.0, direction=(-1, 0, 0))
    calc.analysis.set_modal(modal_analysis(num_modes=3))
    calc.analysis.set_buckling(buckling_analysis(num_modes=2, reference=load_case_ref(lc.id)))
    calc.analysis.set_seismic(
        seismic_analysis(
            method="BOTH",
            num_modes=3,
            spectrum_x=direct_spectrum(ag=1.0, s=1.0, tb=0.1, tc=0.5, td=2.0, q=1.0),
            mass_sources=[seismic_mass_source(lc.id, 1.0)],
        )
    )
    data = calc.to_dict(include_results=False)
    rebuilt = FERS.from_dict(data)
    assert rebuilt.modal == calc.modal
    assert rebuilt.buckling == calc.buckling
    assert rebuilt.seismic == calc.seismic


# ── result accessors ─────────────────────────────────────────────────────────


def test_result_accessors_default_none():
    calc, _ = _cantilever()
    assert calc.modal_results() is None
    assert calc.buckling_results() is None
    assert calc.seismic_results() is None


# ── end-to-end (solver) ──────────────────────────────────────────────────────


def test_modal_end_to_end_matches_euler_frequency():
    E, rho, b, L = 210e9, 7850.0, 0.1, 5.0
    calc, _ = _cantilever(length=L, b=b, density=rho)
    calc.analysis.set_modal(modal_analysis(num_modes=2))
    calc.run_analysis()
    modal = calc.modal_results()
    assert modal is not None and len(modal["modes"]) >= 1
    inertia, area = b**4 / 12, b * b
    f1 = 1.875104**2 / (2 * math.pi) * math.sqrt(E * inertia / (rho * area * L**4))
    assert abs(modal["modes"][0]["natural_frequency"] - f1) / f1 < 0.02


def test_buckling_end_to_end_matches_euler_load():
    E, b, L, p_ref = 210e9, 0.1, 5.0, 1000.0
    calc, nodes = _cantilever(length=L, b=b)
    lc = calc.create_load_case(name="Axial")
    NodalLoad(node=nodes[-1], load_case=lc, magnitude=p_ref, direction=(-1, 0, 0))
    calc.analysis.set_buckling(buckling_analysis(num_modes=1, reference=load_case_ref(lc.id)))
    calc.run_analysis()
    buckling = calc.buckling_results()
    assert buckling is not None and len(buckling["modes"]) >= 1
    inertia = b**4 / 12
    alpha = math.pi**2 * E * inertia / (2 * L) ** 2 / p_ref  # cantilever effective length 2L
    got = buckling["modes"][0]["critical_load_factor"]
    assert abs(got - alpha) / alpha < 0.03


def test_seismic_end_to_end_sdof_base_shear():
    E, inertia, area, H, g, m_tip = 210e9, 1.0e-4, 0.01, 4.0, 9.81, 10_000.0
    calc = FERS()
    mat = Material(name="S235", e_mod=E, g_mod=80.769e9, density=7850, yield_stress=235e6)
    sec = Section(name="SQ", material=mat, i_y=inertia, i_z=inertia, j=1e-5, area=area)
    base, top = Node(0, 0, 0), Node(0, H, 0)
    base.nodal_support = NodalSupport()
    calc.add_member_set(MemberSet(members=[Member(start_node=base, end_node=top, section=sec)]))
    grav = calc.create_load_case(name="Gravity")
    NodalLoad(node=top, load_case=grav, magnitude=m_tip * g, direction=(0, -1, 0))
    calc.analysis.set_seismic(
        seismic_analysis(
            method="BOTH",
            num_modes=2,
            spectrum_x=direct_spectrum(ag=1.0, s=1.0, tb=0.1, tc=0.5, td=2.0, q=1.0, beta=0.2),
            mass_sources=[seismic_mass_source(grav.id, 1.0)],
            include_structural_mass=False,
            directions=["X"],
        )
    )
    calc.run_analysis()
    seismic = calc.seismic_results()
    assert seismic is not None
    k = 3.0 * E * inertia / H**3
    t1 = 2.0 * math.pi * math.sqrt(m_tip / k)
    sd = max(2.5 * 0.5 / t1, 0.2)
    expected = m_tip * sd
    mrsa = seismic["modal_response_spectrum"]["per_direction"][0]
    assert abs(mrsa["base_shear"] - expected) / expected < 0.05
    assert mrsa["participating_mass_ratio"] > 0.97
    assert seismic["lateral_force"] is not None
