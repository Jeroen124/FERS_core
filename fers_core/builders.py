"""Convenience builders — a ready-to-solve model from a few keyword arguments.

These compose the core objects (``Node`` / ``Member`` / ``Section`` / ``LoadCase`` …)
into a solvable :class:`FERS` model, so you can go from an idea to results without
wiring nodes and supports by hand::

    from fers_core import create_beam

    beam = create_beam(6.0, "IPE180", support="simply_supported", udl=10_000)
    beam.run_analysis()
    dy = beam.resultsbundle.loadcases["Load"].displacement_nodes["5"].dy

Units are SI throughout: metres, newtons, newtons/metre.
"""

from __future__ import annotations

from typing import Optional, Union

from .fers.fers import FERS
from .nodes.node import Node
from .members.member import Member
from .members.memberset import MemberSet
from .members.material import Material
from .members.section import Section
from .supports.nodalsupport import NodalSupport
from .loads.nodalload import NodalLoad
from .loads.distributedload import DistributedLoad
from .loads.memberpointload import MemberPointLoad
from .loads.loadcombination import LoadCombination
from .loads.enums import LimitState
from .settings.enums import AnalysisOrder, Dimensionality
from .unity_checks import ec3_steel_check, all_members

# Nominal EN steel grades (SI). E/G/ρ are common to all; only f_y differs.
_STEEL_GRADES = {
    "S235": dict(e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6),
    "S275": dict(e_mod=210e9, g_mod=81e9, density=7850, yield_stress=275e6),
    "S355": dict(e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6),
    "S460": dict(e_mod=210e9, g_mod=81e9, density=7850, yield_stress=460e6),
}

_SUPPORTS = ("simply_supported", "cantilever", "fixed")


def _resolve_material(material: Union[str, Material]) -> Material:
    if isinstance(material, Material):
        return material
    grade = str(material).upper()
    if grade not in _STEEL_GRADES:
        raise ValueError(
            f"Unknown steel grade '{material}'. Known: {', '.join(_STEEL_GRADES)}. Or pass a Material object."
        )
    return Material(name=grade, **_STEEL_GRADES[grade])


def _resolve_section(section: Union[str, Section], material: Material) -> Section:
    if isinstance(section, Section):
        return section
    # Named European section (IPE/HEA/HEB/UPE/RHS/CHS/…). `Section.from_name`
    # needs the optional `sectionproperties` dependency to compute properties.
    return Section.from_name(str(section), material)


def create_beam(
    span: float,
    section: Union[str, Section],
    *,
    material: Union[str, Material] = "S235",
    support: str = "simply_supported",
    udl: Optional[float] = None,
    point_load: Optional[float] = None,
    point_position: Optional[float] = None,
    n_elements: int = 8,
    load_case_name: str = "Load",
) -> FERS:
    """Build a ready-to-solve single-span beam.

    Args:
        span: Beam length in metres.
        section: A :class:`Section`, or a European section name such as ``"IPE180"``.
        material: A :class:`Material`, or a steel grade — ``"S235"``, ``"S275"``,
            ``"S355"`` or ``"S460"``.
        support: ``"simply_supported"`` (pin + roller), ``"cantilever"`` (fixed at
            the start), or ``"fixed"`` (fixed–fixed).
        udl: Uniformly distributed load in N/m, downward (−Y), over the whole span.
        point_load: Point load in N, downward (−Y).
        point_position: Fraction along the span (0..1) for the point load; snapped
            to the nearest node. Defaults to the tip (1.0) for a cantilever, else
            mid-span (0.5).
        n_elements: Number of finite elements along the span (default 8).
        load_case_name: Name of the created load case.

    Returns:
        A :class:`FERS` model — call ``.run_analysis()`` and read ``.resultsbundle``.
    """
    if span <= 0:
        raise ValueError("span must be a positive length in metres.")
    support = str(support).lower()
    if support not in _SUPPORTS:
        raise ValueError(f"support must be one of {_SUPPORTS}; got {support!r}.")
    n = max(2, int(n_elements))

    mat = _resolve_material(material)
    sec = _resolve_section(section, mat)

    calc = FERS()
    # First-order 2D analysis → predictable, textbook results. In 2D the
    # out-of-plane DOFs are restrained, and the supports below leave them fixed.
    calc.settings.analysis_options.dimensionality = Dimensionality.TWO_DIMENSIONAL
    calc.settings.analysis_options.order = AnalysisOrder.LINEAR

    nodes = [Node(span * i / n, 0.0, 0.0) for i in range(n + 1)]

    # NodalSupport() is fully fixed; free only the DOFs each support type needs.
    if support in ("cantilever", "fixed"):
        nodes[0].nodal_support = NodalSupport()
        if support == "fixed":
            nodes[-1].nodal_support = NodalSupport()
    else:  # simply_supported: pin (free RZ) + roller (free RZ and axial X)
        nodes[0].nodal_support = NodalSupport(rotation_conditions={"Z": "Free"})
        nodes[-1].nodal_support = NodalSupport(
            displacement_conditions={"X": "Free"},
            rotation_conditions={"Z": "Free"},
        )

    members = [
        Member(
            start_node=nodes[i],
            end_node=nodes[i + 1],
            section=sec,
            classification="Beam",
        )
        for i in range(n)
    ]
    calc.add_member_set(MemberSet(members=members, classification="Beam"))

    lc = calc.create_load_case(name=load_case_name)
    if udl is not None:
        for m in members:
            DistributedLoad(member=m, load_case=lc, magnitude=udl, direction=(0.0, -1.0, 0.0))
    if point_load is not None:
        pos = point_position
        if pos is None:
            pos = 1.0 if support == "cantilever" else 0.5
        idx = min(max(round(pos * n), 0), n)
        NodalLoad(node=nodes[idx], load_case=lc, magnitude=point_load, direction=(0.0, -1.0, 0.0))

    return calc


def check_beam(
    span: float,
    section: Union[str, Section],
    *,
    material: Union[str, Material] = "S235",
    support: str = "simply_supported",
    udl: Optional[float] = None,
    point_load: Optional[float] = None,
    point_position: Optional[float] = None,
    uls_factor: float = 1.35,
    check_id: str = "ec3",
    check_name: str = "EN 1993-1-1 member check",
) -> FERS:
    """Build a beam with a full EN 1993-1-1 (EC3) steel member check.

    A single-member span, so buckling lengths default to the full span. Adds a ULS
    load combination (``uls_factor`` × the load) and an Ec3Steel unity check over
    the member. After ``.run_analysis()``, read ``.unity_check_results()`` for the
    governing utilization and the per-rule trace (bending, shear and combined N+M
    cross-section resistance).

    Args:
        span: Beam length in metres.
        section: A :class:`Section` or a European section name (e.g. ``"IPE300"``).
            Named sections carry the elastic/plastic moduli and warping constant
            the EC3 check needs.
        material: A :class:`Material` or a steel grade (``"S235"`` … ``"S460"``).
        support: ``"simply_supported"``, ``"cantilever"`` or ``"fixed"``.
        udl: Characteristic uniformly distributed load in N/m, downward (−Y).
        point_load: Characteristic point load in N, downward (−Y).
        point_position: Fraction along the span (0..1) for the point load; defaults
            to the tip (1.0) for a cantilever, else mid-span (0.5).
        uls_factor: ULS load factor applied in the load combination (default 1.35).
        check_id: Identifier for the unity check.
        check_name: Display title for the unity check.

    Returns:
        A :class:`FERS` model — call ``.run_analysis()`` then ``.unity_check_results()``.

    Note:
        Covers cross-section resistance (bending, shear, N+M) and lateral-torsional
        buckling (6.3.2), both on the actual strong (major) axis — verified against
        hand calculations. Requires ``fers_calculations >= 0.2.42`` (the major-axis
        LTB fix); an older solver reports the LTB row as 0.
    """
    if span <= 0:
        raise ValueError("span must be a positive length in metres.")
    support = str(support).lower()
    if support not in _SUPPORTS:
        raise ValueError(f"support must be one of {_SUPPORTS}; got {support!r}.")

    mat = _resolve_material(material)
    sec = _resolve_section(section, mat)

    calc = FERS()
    calc.settings.analysis_options.dimensionality = Dimensionality.TWO_DIMENSIONAL
    calc.settings.analysis_options.order = AnalysisOrder.LINEAR

    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(span, 0.0, 0.0)
    if support in ("cantilever", "fixed"):
        n1.nodal_support = NodalSupport()
        if support == "fixed":
            n2.nodal_support = NodalSupport()
    else:
        n1.nodal_support = NodalSupport(rotation_conditions={"Z": "Free"})
        n2.nodal_support = NodalSupport(
            displacement_conditions={"X": "Free"},
            rotation_conditions={"Z": "Free"},
        )

    member = Member(start_node=n1, end_node=n2, section=sec, classification="Beam")
    calc.add_member_set(MemberSet(members=[member], classification="Beam"))

    lc = calc.create_load_case(name="Q")
    if udl is not None:
        DistributedLoad(member=member, load_case=lc, magnitude=udl, direction=(0.0, -1.0, 0.0))
    if point_load is not None:
        pos = point_position
        if pos is None:
            pos = 1.0 if support == "cantilever" else 0.5
        MemberPointLoad(
            member=member,
            load_case=lc,
            magnitude=point_load,
            direction=(0.0, -1.0, 0.0),
            position=pos,
        )

    calc.add_load_combination(
        LoadCombination(
            name="ULS",
            load_cases_factors={lc: uls_factor},
            check="ULS",
            limit_state=LimitState.ULS,
        )
    )
    calc.add_unity_check(ec3_steel_check(check_id, check_name, applies_to=all_members(), limit_state="ULS"))
    return calc


def check_strut(
    length: float,
    section: Union[str, Section],
    *,
    material: Union[str, Material] = "S235",
    axial_load: float = 1.0,
    k_y: float = 1.0,
    k_z: float = 1.0,
    gamma_m0: float = 1.0,
    gamma_m1: float = 1.0,
    check_id: str = "ec3",
    check_name: str = "EN 1993-1-1 compression check",
) -> FERS:
    """Build a concentrically loaded strut with an EN 1993-1-1 compression check.

    The compression counterpart to :func:`check_beam`: a single pin-ended member
    carrying pure axial compression, so §6.3.1 flexural buckling and §6.3.1.4
    torsional-flexural buckling are the checks that decide it. Both ends are held
    against translation and against twist, and free to rotate about both bending
    axes — the fork-supported strut the buckling curves are written for.

    Because there is no moment, every sub-check is linear in the axial force, so
    the allowable load follows from one solve without iterating::

        strut = check_strut(2.5, my_section, material="S355", axial_load=1_000.0)
        strut.run_analysis()
        n_allow = strut.compression_capacity()

    Args:
        length: System length in metres. With no `buckling_restraints` on the set
            this is also the buckling length, scaled by `k_y`/`k_z`.
        section: A :class:`Section`, or a European section name (e.g. ``"IPE300"``).
            Build it from one of the ``Section.create_*`` factories with
            ``classify_for="compression"`` to get the section class, buckling
            curves and effective area derived for you. Classification is opt-in
            because it depends on the stress state — the same web can be class 4
            in compression and class 1 in bending — and without it the solver
            defaults every curve to b and infers class 1 from ``wpl_y``.
        material: A :class:`Material` or a grade name (``"S235"`` … ``"S460"``).
        axial_load: Compression in newtons. Any positive value works; the
            utilization scales linearly with it.
        k_y: Effective-length factor about local y (`L_cr,y = k_y * length`).
        k_z: Effective-length factor about local z.
        gamma_m0: Partial factor for cross-section resistance.
        gamma_m1: Partial factor for member buckling resistance.
        check_id: Identifier for the unity check.
        check_name: Display title for the unity check.

    Returns:
        A :class:`FERS` model — call ``.run_analysis()``, then
        ``.compression_capacity()`` or ``.unity_check_results()``.
    """
    if length <= 0:
        raise ValueError("length must be a positive length in metres.")
    if axial_load <= 0:
        raise ValueError("axial_load must be positive (a compression, in newtons).")

    mat = _resolve_material(material)
    sec = _resolve_section(section, mat)

    calc = FERS()
    calc.settings.analysis_options.order = AnalysisOrder.LINEAR

    # Fork supports: translation and twist held, both bending rotations free.
    # Leaving RX free at either end would make the strut a torsional mechanism,
    # which is also the mode 6.3.1.4 is about — the model has to hold it while
    # the check accounts for it.
    n1 = Node(0.0, 0.0, 0.0)
    n1.nodal_support = NodalSupport(
        displacement_conditions={"X": "Fixed", "Y": "Fixed", "Z": "Fixed"},
        rotation_conditions={"X": "Fixed", "Y": "Free", "Z": "Free"},
    )
    n2 = Node(length, 0.0, 0.0)
    n2.nodal_support = NodalSupport(
        displacement_conditions={"X": "Free", "Y": "Fixed", "Z": "Fixed"},
        rotation_conditions={"X": "Fixed", "Y": "Free", "Z": "Free"},
    )

    member = Member(start_node=n1, end_node=n2, section=sec, classification="Column")
    member_set = MemberSet(members=[member], classification="Column")
    if k_y != 1.0:
        member_set.effective_length_factor_y = k_y
    if k_z != 1.0:
        member_set.effective_length_factor_z = k_z
    calc.add_member_set(member_set)

    lc = calc.create_load_case(name="N")
    NodalLoad(node=n2, load_case=lc, magnitude=axial_load, direction=(-1.0, 0.0, 0.0))

    calc.add_load_combination(
        LoadCombination(
            name="ULS",
            load_cases_factors={lc: 1.0},
            check="ULS",
            limit_state=LimitState.ULS,
        )
    )
    calc.add_unity_check(
        ec3_steel_check(
            check_id,
            check_name,
            applies_to=all_members(),
            limit_state="ULS",
            gamma_m0=gamma_m0,
            gamma_m1=gamma_m1,
            include_buckling=True,
            # No moment anywhere, so there is nothing for §6.3.2 to check.
            include_ltb=False,
        )
    )
    return calc
