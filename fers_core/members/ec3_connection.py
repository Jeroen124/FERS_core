"""EN 1993-1-3 §8.3 bolted connections in thin steel sheet.

A cold-formed member is rarely limited by the member. It is bolted through one
of its own walls, and both of the things that follow from that — the bearing
and net-section resistance of a 2 or 3 mm sheet, and the eccentricity between
the bolt line and the section's centroid — routinely govern well below the
§6.3 buckling resistance the member would otherwise reach.

`ec3_section` derives what the cross-section is; this module derives what the
connection lets it carry, and pairs the two through the linear interaction in
`eccentric_compression_capacity`.

Everything is SI: metres, pascals, newtons.

Two limits are deliberately absent. Block tearing (EN 1993-1-8 §3.10.2) needs
the full bolt-group geometry rather than one representative pitch, and the
shear/tension interaction on the bolt itself does not arise for a brace that
transfers load in shear only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

__all__ = [
    "GAMMA_M2",
    "BOLT_STRESS_AREA",
    "BoltedLap",
    "ConnectionResistance",
    "bearing_resistance",
    "bolt_shear_resistance",
    "net_section_resistance",
    "detailing_warnings",
    "connection_resistance",
    "eccentric_compression_capacity",
]

#: EN 1993-1-8 / EN 1993-1-3 partial factor for a resistance governed by rupture.
GAMMA_M2 = 1.25

#: Tensile stress area A_s of a coarse-pitch metric bolt, in m^2.
BOLT_STRESS_AREA: Dict[float, float] = {
    0.005: 14.2e-6,
    0.006: 20.1e-6,
    0.008: 36.6e-6,
    0.010: 58.0e-6,
    0.012: 84.3e-6,
    0.014: 115.0e-6,
    0.016: 157.0e-6,
    0.020: 245.0e-6,
    0.024: 353.0e-6,
}

#: (f_ub, alpha_v with the threads in the shear plane) per EN 1993-1-8 Table 3.4.
_GRADES: Dict[str, Tuple[float, float]] = {
    "4.6": (400.0e6, 0.6),
    "4.8": (400.0e6, 0.5),
    "5.6": (500.0e6, 0.6),
    "5.8": (500.0e6, 0.5),
    "6.8": (600.0e6, 0.5),
    "8.8": (800.0e6, 0.6),
    "10.9": (1000.0e6, 0.5),
}

Sense = Literal["compression", "tension"]


@dataclass(frozen=True)
class BoltedLap:
    """One end connection of a thin-gauge member.

    Args:
        d: bolt shank diameter.
        t: thickness of the connected sheet — the member's own wall, or the
            thinner part if the bracket is thinner still.
        f_u: ultimate tensile strength of that sheet.
        e1: end distance from the bolt centre to the sheet edge, measured in
            the direction the load is transferred.
        e2: edge distance perpendicular to it.
        d_0: hole diameter. Defaults to `d + 1 mm`, normal clearance up to M14.
        n_bolts: bolts in this end connection.
        n_at_section: bolts crossing the critical net section — usually all of
            them for one transverse line, one of them for a staggered pair.
        p1: pitch along the load. Only used for the detailing checks.
        p2: spacing across the load. Caps `u` in the net-section rule, and is
            used for the detailing checks.
        grade: bolt grade, EN 1993-1-8 Table 3.1.
        threads_in_shear_plane: False puts the unthreaded shank in shear, which
            raises `alpha_v` to 0.6 and uses the gross bolt area.
        shear_planes: 1 for a lap joint, 2 for a member between two cleats.
    """

    d: float
    t: float
    f_u: float
    e1: float
    e2: float
    d_0: Optional[float] = None
    n_bolts: int = 1
    n_at_section: int = 1
    p1: Optional[float] = None
    p2: Optional[float] = None
    grade: str = "8.8"
    threads_in_shear_plane: bool = True
    shear_planes: int = 1

    def __post_init__(self):
        for name in ("d", "t", "f_u", "e1", "e2"):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive")
        if self.n_bolts < 1 or self.n_at_section < 1:
            raise ValueError("n_bolts and n_at_section must be at least 1")
        if self.n_at_section > self.n_bolts:
            raise ValueError("n_at_section cannot exceed n_bolts")
        if self.grade not in _GRADES:
            raise ValueError(f"unknown bolt grade {self.grade!r}; expected one of {sorted(_GRADES)}")

    @property
    def hole(self) -> float:
        """Hole diameter, defaulting to normal clearance."""
        return self.d + 1.0e-3 if self.d_0 is None else self.d_0

    @property
    def f_ub(self) -> float:
        return _GRADES[self.grade][0]

    @property
    def alpha_v(self) -> float:
        return _GRADES[self.grade][1] if self.threads_in_shear_plane else 0.6

    @property
    def bolt_area(self) -> float:
        """Area resisting shear: A_s through the threads, the shank otherwise."""
        if not self.threads_in_shear_plane:
            return 0.25 * math.pi * self.d * self.d
        try:
            return BOLT_STRESS_AREA[round(self.d, 6)]
        except KeyError:
            raise ValueError(
                f"no tabulated stress area for a {self.d * 1000:.1f} mm bolt; "
                "pass threads_in_shear_plane=False or add the size to BOLT_STRESS_AREA"
            ) from None


@dataclass(frozen=True)
class ConnectionResistance:
    """What one end connection allows, and which rule decided it."""

    bearing: float
    bolt_shear: float
    net_section: Optional[float]
    value: float
    governing: str
    warnings: Tuple[str, ...] = ()


def bearing_resistance(lap: BoltedLap) -> float:
    """EN 1993-1-3 Table 8.4, summed over the bolts in the connection.

        F_b,Rd = 2.5 * alpha_b * k_t * f_u * d * t / gamma_M2

    `k_t` relieves the very thinnest sheet only; `alpha_b` is the end-distance
    reduction, so a short `e1` cuts the resistance in proportion.
    """
    t_mm = lap.t * 1000.0
    k_t = 1.0 if t_mm > 1.25 else (0.8 * t_mm + 1.5) / 2.5
    alpha_b = min(1.0, lap.e1 / (3.0 * lap.d))
    per_bolt = 2.5 * alpha_b * k_t * lap.f_u * lap.d * lap.t / GAMMA_M2
    return per_bolt * lap.n_bolts


def bolt_shear_resistance(lap: BoltedLap) -> float:
    """EN 1993-1-8 §3.6.1 Table 3.4, summed over the bolts and shear planes."""
    per_plane = lap.alpha_v * lap.f_ub * lap.bolt_area / GAMMA_M2
    return per_plane * lap.n_bolts * lap.shear_planes


def net_section_resistance(lap: BoltedLap, a_gross: float) -> float:
    """EN 1993-1-3 Table 8.4 net-section resistance, in TENSION.

        F_n,Rd = (1 + 3 r (d_0/u - 0.3)) A_net f_u / gamma_M2  <=  A_net f_u / gamma_M2

    with `r` the fraction of the connection's bolts that cross this section and
    `u = 2 e2`, capped at `p2`. The bracketed term is an enhancement for a
    connection whose bolts are well spread across the width; it is clamped at 1
    so a narrow member never gains from it.

    Compression takes no deduction at all — the bolt fills the hole, EN 1993-1-1
    §6.2.4(1) — so this is not part of the compression envelope. Prefer
    `connection_resistance`, which knows that.
    """
    a_net = a_gross - lap.n_at_section * lap.hole * lap.t
    if a_net <= 0.0:
        raise ValueError("the holes remove the whole section; check d_0, t and a_gross")
    u = 2.0 * lap.e2
    if lap.p2 is not None:
        u = min(u, lap.p2)
    r = lap.n_at_section / lap.n_bolts
    factor = min(1.0, 1.0 + 3.0 * r * (lap.hole / u - 0.3))
    return factor * a_net * lap.f_u / GAMMA_M2


def detailing_warnings(lap: BoltedLap) -> List[str]:
    """The geometric limits EN 1993-1-3 Table 8.4 assumes, plus §8.3(5).

    Violating one does not make the arithmetic above wrong so much as make it
    inapplicable, so these are surfaced rather than raised.
    """
    out: List[str] = []
    d_0 = lap.hole
    if lap.t < 0.75e-3:
        out.append(f"t = {lap.t * 1000:.2f} mm is below the 0.75 mm floor of EN 1993-1-3 Table 8.4")
    if lap.e1 < 1.2 * d_0:
        out.append(f"e1 = {lap.e1 * 1000:.1f} mm is below the 1.2 d_0 = {1.2 * d_0 * 1000:.1f} mm minimum")
    if lap.e2 < 1.5 * d_0:
        out.append(f"e2 = {lap.e2 * 1000:.1f} mm is below the 1.5 d_0 = {1.5 * d_0 * 1000:.1f} mm minimum")
    if lap.p1 is not None and lap.p1 < 3.0 * d_0:
        out.append(f"p1 = {lap.p1 * 1000:.1f} mm is below the 3 d_0 = {3.0 * d_0 * 1000:.1f} mm minimum")
    if lap.p2 is not None and lap.p2 < 3.0 * d_0:
        out.append(f"p2 = {lap.p2 * 1000:.1f} mm is below the 3 d_0 = {3.0 * d_0 * 1000:.1f} mm minimum")
    if bolt_shear_resistance(lap) < 1.2 * bearing_resistance(lap):
        out.append(
            "EN 1993-1-3 §8.3(5): F_v,Rd < 1.2 F_b,Rd, so the bolt shears before the "
            "sheet yields in bearing — the brittle failure that clause exists to prevent"
        )
    return out


def connection_resistance(
    lap: BoltedLap,
    *,
    a_gross: Optional[float] = None,
    sense: Sense = "compression",
) -> ConnectionResistance:
    """The governing resistance of one end connection.

    In compression the envelope is bearing against bolt shear: the hole is
    filled by the bolt, so EN 1993-1-1 §6.2.4(1) takes the gross section and no
    net-section deduction applies. In tension the net section joins them, and
    `a_gross` becomes required.
    """
    bearing = bearing_resistance(lap)
    shear = bolt_shear_resistance(lap)
    candidates = {"bearing (EN 1993-1-3 §8.3)": bearing, "bolt shear (EN 1993-1-8 §3.6)": shear}
    net: Optional[float] = None
    if sense == "tension":
        if a_gross is None:
            raise ValueError("a_gross is required for a tension check (net section)")
        net = net_section_resistance(lap, a_gross)
        candidates["net section (EN 1993-1-3 §8.4)"] = net
    elif sense != "compression":
        raise ValueError(f"sense must be 'compression' or 'tension', not {sense!r}")
    governing = min(candidates, key=lambda k: candidates[k])
    return ConnectionResistance(
        bearing=bearing,
        bolt_shear=shear,
        net_section=net,
        value=candidates[governing],
        governing=governing,
        warnings=tuple(detailing_warnings(lap)),
    )


def eccentric_compression_capacity(
    n_b_rd: float,
    *,
    w_eff: float,
    f_y: float,
    e: float,
    gamma_m0: float = 1.0,
) -> float:
    """Largest axial compression a strut takes when the load misses its centroid.

    The eccentricity turns part of the axial force into a moment, and the two
    are checked together:

        N / N_b,Rd  +  N e / (W_eff f_y / gamma_M0)  <=  1

    which solves directly, since both terms are linear in N:

        N = 1 / (1/N_b,Rd + e gamma_M0 / (W_eff f_y))

    Args:
        n_b_rd: the member's own buckling resistance, from the solver.
        w_eff: minimum elastic modulus of the EFFECTIVE section about the axis
            the moment acts on — `FlexuralEffective.w_eff_y` for a load offset
            along local z.
        e: distance from the point the load is applied to the EFFECTIVE
            centroid. Measuring to the effective centroid is what makes this one
            calculation rather than two: a load applied at the gross centroid
            leaves `e = |e_N|` and the result is EN 1993-1-1 §6.2.9.3, while a
            load applied at a bolt line further out simply has a larger `e`.
            Adding §6.2.9.3 on top of a connection eccentricity already measured
            this way would count the same shift twice.

    The interaction is the conservative linear one. EN 1993-1-1 §6.3.3 would
    relieve it through its interaction factors, and EN 1993-1-3 §6.2.11 through
    its exponents; neither is applied here.
    """
    if n_b_rd <= 0.0:
        raise ValueError("n_b_rd must be positive")
    if e < 0.0:
        raise ValueError("e must be a non-negative distance")
    if e == 0.0:
        return n_b_rd
    if w_eff <= 0.0 or f_y <= 0.0:
        raise ValueError("w_eff and f_y must be positive")
    m_rd = w_eff * f_y / gamma_m0
    return 1.0 / (1.0 / n_b_rd + e / m_rd)
