"""EN 1993-1-1 cross-section classification and EN 1993-1-5 effective areas.

The solver consumes `Section.ec3` (section class, buckling curves, `a_eff`) but
never derives it: classification needs the flange/web decomposition, and a
`Section` only stores integrated properties. This module supplies that missing
step for the parametric profiles the section factories build, so a section
created from dimensions arrives at the solver already carrying its class, its
effective area and its buckling curves.

Two things it deliberately does not do:

* **CHS.** A tube has no plate elements, and a class 4 tube is EN 1993-1-6
  (shell buckling), not an effective width. The class is reported; `a_eff` is
  refused rather than guessed.
* **Edge-stiffened cold-formed elements** (a lipped C, a hat). Those need
  EN 1993-1-3 §5.5.3 — an iterative spring-stiffness/distortional calculation
  this module does not implement. A lip is accepted only where it is long
  enough to count under §5.5.3.1(3) (`0.2 <= c/b <= 0.6`); otherwise the flange
  is treated as the plain outstand it effectively is, which is the correct
  reading, not a fallback.

All lengths are in metres and stresses in pascals, matching `Section`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Sequence, Tuple

__all__ = [
    "PlateElement",
    "EffectiveSection",
    "epsilon",
    "plate_class",
    "plate_rho",
    "channel_plates",
    "channel_fibres",
    "i_plates",
    "rhs_plates",
    "effective_section",
    "FlexuralEffective",
    "effective_flexural_properties",
    "tube_class",
    "angle_class",
    "buckling_curves",
    "ec3_params",
    "section_ec3",
]

PlateKind = Literal["internal", "outstand"]
Fabrication = Literal["hot_rolled", "hot_finished", "cold_formed", "welded"]

# EN 1993-1-1 Table 5.2, uniform compression (psi = 1).
_LIMITS = {
    # sheet 1: internal compression parts
    "internal": (33.0, 38.0, 42.0),
    # sheet 2: outstand flanges
    "outstand": (9.0, 10.0, 14.0),
}

# EN 1993-1-5 Table 4.1 / 4.2 buckling factors at psi = 1.
_K_SIGMA = {"internal": 4.0, "outstand": 0.43}


def epsilon(f_y: float) -> float:
    """EN 1993-1-1 §5.5.2: eps = sqrt(235 MPa / f_y), with f_y in pascals."""
    if f_y <= 0.0:
        raise ValueError("f_y must be positive (Pa)")
    return math.sqrt(235.0e6 / f_y)


def plate_class(kind: PlateKind, c_over_t: float, eps: float) -> int:
    """Class 1-4 of one compression element (EN 1993-1-1 Table 5.2, psi = 1)."""
    c1, c2, c3 = _LIMITS[kind]
    if c_over_t <= c1 * eps:
        return 1
    if c_over_t <= c2 * eps:
        return 2
    if c_over_t <= c3 * eps:
        return 3
    return 4


def plate_rho(kind: PlateKind, c_over_t: float, eps: float) -> Tuple[float, float]:
    """EN 1993-1-5 §4.4 reduction factor for one element in uniform compression.

    Returns `(rho, lambda_p_bar)`. `rho` is 1.0 on the plateau, so this is safe
    to call for any class.
    """
    k_sigma = _K_SIGMA[kind]
    lambda_p = c_over_t / (28.4 * eps * math.sqrt(k_sigma))
    if kind == "internal":
        # psi = 1 -> plateau at 0.5 + sqrt(0.085 - 0.055) = 0.673
        plateau = 0.5 + math.sqrt(0.085 - 0.055 * 1.0)
        if lambda_p <= plateau:
            return 1.0, lambda_p
        rho = (lambda_p - 0.055 * (3.0 + 1.0)) / (lambda_p * lambda_p)
    else:
        if lambda_p <= 0.748:
            return 1.0, lambda_p
        rho = (lambda_p - 0.188) / (lambda_p * lambda_p)
    return min(rho, 1.0), lambda_p


@dataclass
class PlateElement:
    """One flat compression element, on the section's mid-line.

    `p1`/`p2` are the ends of the FLAT portion in section local `(y, z)`, so the
    centroid of the effective section — and with it the EN 1993-1-1 §6.2.9.3
    shift `e_N` — falls out of the same description that gives `c`.

    For an outstand, `supported_end` says which end is attached to the rest of
    the section: EN 1993-1-5 Table 4.2 measures `b_eff` from there, leaving the
    non-effective strip at the free edge. For an internal element at psi = 1 the
    non-effective strip sits in the middle (Table 4.1, `b_e1 = b_e2 = 0.5 b_eff`),
    which is symmetric and so does not move the centroid along the element.
    """

    name: str
    kind: PlateKind
    p1: Tuple[float, float]
    p2: Tuple[float, float]
    t: float
    supported_end: int = 1

    @property
    def c(self) -> float:
        return math.dist(self.p1, self.p2)

    def effective_spans(self, rho: float) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """`[(end, end), ...]` of the effective parts of this element.

        Endpoints rather than midpoints, because a second moment needs the
        direction the flat runs in, not just where its centre sits.
        """
        c = self.c
        if c <= 0.0:
            return []
        eff = rho * c
        if eff >= c:
            return [(self.p1, self.p2)]
        if self.kind == "outstand":
            a = self.p1 if self.supported_end == 1 else self.p2
            b = self.p2 if self.supported_end == 1 else self.p1
            return [(a, _along(a, b, eff))]
        # internal: half the effective width against each supported edge
        half = 0.5 * eff
        return [
            (self.p1, _along(self.p1, self.p2, half)),
            (self.p2, _along(self.p2, self.p1, half)),
        ]

    def effective_segments(self, rho: float) -> List[Tuple[Tuple[float, float], float]]:
        """`[(midpoint, length), ...]` of the effective parts of this element."""
        return [(_mid(a, b), math.dist(a, b)) for a, b in self.effective_spans(rho)]


def _mid(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
    return (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))


def _along(a: Tuple[float, float], b: Tuple[float, float], d: float) -> Tuple[float, float]:
    length = math.dist(a, b)
    if length == 0.0:
        return a
    f = d / length
    return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))


@dataclass
class ElementResult:
    name: str
    kind: PlateKind
    c: float
    t: float
    c_over_t: float
    section_class: int
    lambda_p: float
    rho: float

    @property
    def b_eff(self) -> float:
        return self.rho * self.c


@dataclass
class EffectiveSection:
    """Classification + EN 1993-1-5 effective area for one section."""

    section_class: int
    a_gross: float
    a_eff: float
    #: Shift of the effective centroid from the gross centroid, local (y, z).
    #: EN 1993-1-1 §6.2.9.3 asks for an added moment `N_Ed * e_N` about the
    #: corresponding axis. The solver does not apply this automatically.
    e_n_y: float = 0.0
    e_n_z: float = 0.0
    elements: List[ElementResult] = field(default_factory=list)

    @property
    def is_class4(self) -> bool:
        return self.section_class >= 4

    @property
    def area_ratio(self) -> float:
        return self.a_eff / self.a_gross if self.a_gross else float("nan")


def effective_section(plates: Sequence[PlateElement], a_gross: float, f_y: float) -> EffectiveSection:
    """Classify `plates` and reduce them per EN 1993-1-5 §4.4, uniform compression.

    `a_eff` is `a_gross` minus the non-effective flats, so it inherits the true
    gross area (corner radii and all) rather than a mid-line approximation of it.
    """
    eps = epsilon(f_y)
    results: List[ElementResult] = []
    lost = 0.0
    worst = 1
    for pl in plates:
        c = pl.c
        cot = c / pl.t
        cls = plate_class(pl.kind, cot, eps)
        rho, lam = plate_rho(pl.kind, cot, eps)
        # Only a class 4 element is actually reduced: classes 1-3 reach f_y over
        # their full width by definition, and rho can dip below 1 just inside the
        # class 3 limit, which would double-count the slenderness.
        if cls < 4:
            rho = 1.0
        results.append(ElementResult(pl.name, pl.kind, c, pl.t, cot, cls, lam, rho))
        lost += (1.0 - rho) * c * pl.t
        worst = max(worst, cls)

    a_eff = a_gross - lost
    e_y, e_z = _centroid_shift(plates, results)
    return EffectiveSection(
        section_class=worst,
        a_gross=a_gross,
        a_eff=a_eff,
        e_n_y=e_y,
        e_n_z=e_z,
        elements=results,
    )


def _centroid_shift(plates: Sequence[PlateElement], results: Sequence[ElementResult]) -> Tuple[float, float]:
    """Effective-centroid offset from the gross centroid, on the mid-line model.

    Both centroids come from the same mid-line description, so the systematic
    error of ignoring the corner arcs cancels in the difference.
    """
    gy = gz = ga = 0.0
    ey = ez = ea = 0.0
    for pl, res in zip(plates, results):
        c = pl.c
        if c <= 0.0:
            continue
        a = c * pl.t
        m = _mid(pl.p1, pl.p2)
        gy += m[0] * a
        gz += m[1] * a
        ga += a
        for mid, length in pl.effective_segments(res.rho):
            aa = length * pl.t
            ey += mid[0] * aa
            ez += mid[1] * aa
            ea += aa
    if ga <= 0.0 or ea <= 0.0:
        return 0.0, 0.0
    return (ey / ea - gy / ga, ez / ea - gz / ga)


@dataclass
class FlexuralEffective:
    """Bending properties of the effective section, about its own centroid.

    Needed wherever a class 4 compression member is not loaded through the
    effective centroid: EN 1993-1-1 §6.2.9.3 asks for the added moment
    `N_Ed * e_N`, and a bolted end connection usually adds a far larger
    eccentricity of its own. Both are the same calculation once the effective
    centroid is known, so nothing here is §6.2.9.3-specific.

    `i_eff_*` inherit the true gross second moment, scaled by the reduction the
    mid-line model measures -- the same construction `a_eff` uses for area, and
    it holds for the same reason: the mid-line model's systematic error (it
    ignores the corner arcs, and seats each outstand flat at the web mid-line
    rather than past the radius) is common to numerator and denominator and
    cancels in the ratio. `w_eff_*` are minimum moduli, taken to the furthest
    fibre of the gross outline.

    Axes follow the rest of the module: `i_y = ∫ z^2 dA`, so `w_eff_y` divides
    `i_eff_y` by a distance measured along z.
    """

    centroid_gross: Tuple[float, float]
    centroid_eff: Tuple[float, float]
    i_eff_y: float
    i_eff_z: float
    w_eff_y: float
    w_eff_z: float
    reduction_y: float
    reduction_z: float


def _line_props(segs: Sequence[Tuple[Tuple[float, float], Tuple[float, float], float]]):
    """Area, centroid and centroidal second moments of a set of thin flats.

    Each flat is a rectangle of length `L` and thickness `t`, so its own second
    moment has a term along the flat (`A L^2/12`, projected onto the axis) and a
    much smaller one across the thickness (`A t^2/12`, projected the other way).
    Returns `(area, (cy, cz), i_y, i_z)`, the second moments about the centroid.
    """
    a_tot = sy = sz = 0.0
    for pa, pb, t in segs:
        length = math.dist(pa, pb)
        if length <= 0.0:
            continue
        a = length * t
        m = _mid(pa, pb)
        a_tot += a
        sy += m[0] * a
        sz += m[1] * a
    if a_tot <= 0.0:
        return 0.0, (0.0, 0.0), 0.0, 0.0
    cy, cz = sy / a_tot, sz / a_tot
    i_y = i_z = 0.0
    for pa, pb, t in segs:
        length = math.dist(pa, pb)
        if length <= 0.0:
            continue
        a = length * t
        dy, dz = pb[0] - pa[0], pb[1] - pa[1]
        m = _mid(pa, pb)
        i_y += a * dz * dz / 12.0 + a * t * t / 12.0 * (dy / length) ** 2 + a * (m[1] - cz) ** 2
        i_z += a * dy * dy / 12.0 + a * t * t / 12.0 * (dz / length) ** 2 + a * (m[0] - cy) ** 2
    return a_tot, (cy, cz), i_y, i_z


def effective_flexural_properties(
    plates: Sequence[PlateElement],
    eff: EffectiveSection,
    *,
    i_y_gross: float,
    i_z_gross: float,
    fibre_y: Tuple[float, float],
    fibre_z: Tuple[float, float],
    centroid_gross: Optional[Tuple[float, float]] = None,
) -> FlexuralEffective:
    """Bending properties of the effective section that `eff` describes.

    Args:
        plates: the same decomposition `eff` was built from.
        eff: the result of `effective_section` on those plates.
        i_y_gross: true gross second moment about local y, in m^4 -- take it
            from `Section.i_y`, which comes from a meshed analysis and so
            includes the corner arcs the mid-line model drops.
        i_z_gross: likewise about local z.
        fibre_y: `(y_max, y_min)` of the gross outline in the plate frame; see
            `channel_fibres`.
        fibre_z: `(z_max, z_min)` of the gross outline in the plate frame.
        centroid_gross: true gross centroid in the plate frame, when it is
            known. The effective centroid is then that point plus the shift the
            mid-line model measures, which is more accurate than the mid-line
            centroid itself -- the shift is a difference between two readings of
            the same model, the position is not. Defaults to the mid-line
            centroid.
    """
    gross_segs = [(pl.p1, pl.p2, pl.t) for pl in plates]
    eff_segs = [(a, b, pl.t) for pl, res in zip(plates, eff.elements) for a, b in pl.effective_spans(res.rho)]
    _, c_mid_gross, iy_mid_gross, iz_mid_gross = _line_props(gross_segs)
    _, c_mid_eff, iy_mid_eff, iz_mid_eff = _line_props(eff_segs)

    red_y = iy_mid_eff / iy_mid_gross if iy_mid_gross > 0.0 else 1.0
    red_z = iz_mid_eff / iz_mid_gross if iz_mid_gross > 0.0 else 1.0
    i_eff_y = i_y_gross * red_y
    i_eff_z = i_z_gross * red_z

    base = c_mid_gross if centroid_gross is None else centroid_gross
    c_eff = (
        base[0] + (c_mid_eff[0] - c_mid_gross[0]),
        base[1] + (c_mid_eff[1] - c_mid_gross[1]),
    )

    d_z = max(abs(fibre_z[0] - c_eff[1]), abs(fibre_z[1] - c_eff[1]))
    d_y = max(abs(fibre_y[0] - c_eff[0]), abs(fibre_y[1] - c_eff[0]))
    return FlexuralEffective(
        centroid_gross=base,
        centroid_eff=c_eff,
        i_eff_y=i_eff_y,
        i_eff_z=i_eff_z,
        w_eff_y=i_eff_y / d_z if d_z > 0.0 else math.inf,
        w_eff_z=i_eff_z / d_y if d_y > 0.0 else math.inf,
        reduction_y=red_y,
        reduction_z=red_z,
    )


# ── plate decompositions ────────────────────────────────────────────────────
#
# Local axes follow the section factories: i_y = sp.iyy_c and i_z = sp.ixx_c, so
# local y runs along the depth and local z along the width. Flat widths are the
# notional flats between corner midpoints (EN 1993-1-3 §5.1 for cold-formed,
# the same c as EN 1993-1-1 Table 5.2 for rolled shapes).


def channel_plates(h: float, b: float, t_f: float, t_w: float, r: float = 0.0) -> List[PlateElement]:
    """A plain (unlipped) channel: one internal web, two outstand flanges."""
    hm = h - t_f  # web mid-line length
    c_web = h - 2.0 * t_f - 2.0 * r
    c_fl = b - t_w - r
    z_web = 0.0
    return [
        PlateElement("web", "internal", (-0.5 * c_web, z_web), (0.5 * c_web, z_web), t_w),
        PlateElement(
            "flange (top)",
            "outstand",
            (0.5 * hm, z_web),
            (0.5 * hm, z_web + c_fl),
            t_f,
            supported_end=1,
        ),
        PlateElement(
            "flange (bottom)",
            "outstand",
            (-0.5 * hm, z_web),
            (-0.5 * hm, z_web + c_fl),
            t_f,
            supported_end=1,
        ),
    ]


def channel_fibres(
    h: float, b: float, t_f: float, t_w: float
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Extreme fibres of a plain channel's TRUE outline, in the plate frame.

    `channel_plates` puts the web mid-line at `z = 0` and the flange mid-lines at
    `y = +-(h - t_f)/2`. The physical outline reaches further: `+-h/2` in y, and
    from the back of the web at `-t_w/2` out to the flange tip at `b - t_w/2`.
    An elastic modulus is taken to the extreme fibre of the gross outline even
    when part of that outline has been discounted from the effective area, so
    these are the distances `effective_flexural_properties` needs.

    Returns `((y_max, y_min), (z_max, z_min))`.
    """
    return ((0.5 * h, -0.5 * h), (b - 0.5 * t_w, -0.5 * t_w))


def i_plates(h: float, b: float, t_f: float, t_w: float, r: float = 0.0) -> List[PlateElement]:
    """An I/H section: one internal web, four outstand half-flanges."""
    hm = h - t_f
    c_web = h - 2.0 * t_f - 2.0 * r
    c_fl = 0.5 * (b - t_w - 2.0 * r)
    out: List[PlateElement] = [PlateElement("web", "internal", (-0.5 * c_web, 0.0), (0.5 * c_web, 0.0), t_w)]
    for sy, ly in (("top", 0.5 * hm), ("bottom", -0.5 * hm)):
        for sz, sign in (("+z", 1.0), ("-z", -1.0)):
            out.append(
                PlateElement(
                    f"flange ({sy} {sz})",
                    "outstand",
                    (ly, 0.0),
                    (ly, sign * c_fl),
                    t_f,
                    supported_end=1,
                )
            )
    return out


def rhs_plates(h: float, b: float, t: float, r_out: float = 0.0) -> List[PlateElement]:
    """A rectangular/square hollow section: four internal walls."""
    r_in = max(r_out - t, 0.0)
    c_h = h - 2.0 * t - 2.0 * r_in
    c_b = b - 2.0 * t - 2.0 * r_in
    zz = 0.5 * (b - t)
    yy = 0.5 * (h - t)
    return [
        PlateElement("web (+z)", "internal", (-0.5 * c_h, zz), (0.5 * c_h, zz), t),
        PlateElement("web (-z)", "internal", (-0.5 * c_h, -zz), (0.5 * c_h, -zz), t),
        PlateElement("flange (+y)", "internal", (yy, -0.5 * c_b), (yy, 0.5 * c_b), t),
        PlateElement("flange (-y)", "internal", (-yy, -0.5 * c_b), (-yy, 0.5 * c_b), t),
    ]


def tube_class(d: float, t: float, f_y: float) -> int:
    """EN 1993-1-1 Table 5.2 sheet 3, circular hollow sections."""
    eps2 = epsilon(f_y) ** 2
    dt = d / t
    if dt <= 50.0 * eps2:
        return 1
    if dt <= 70.0 * eps2:
        return 2
    if dt <= 90.0 * eps2:
        return 3
    return 4


def angle_class(h: float, b: float, t: float, f_y: float) -> int:
    """EN 1993-1-1 Table 5.2 sheet 3, angles in uniform compression.

    Both conditions must hold for class 3; there is no class 1 or 2 row for an
    angle under uniform compression, so anything that satisfies them is reported
    as class 3.
    """
    eps = epsilon(f_y)
    if h / t <= 15.0 * eps and (b + h) / (2.0 * t) <= 11.5 * eps:
        return 3
    return 4


def angle_plates(h: float, b: float, t: float, r: float = 0.0) -> List[PlateElement]:
    """An angle's two legs, each an outstand supported at the heel."""
    c_h = h - t - r
    c_b = b - t - r
    return [
        PlateElement("leg (y)", "outstand", (0.0, 0.0), (c_h, 0.0), t, supported_end=1),
        PlateElement("leg (z)", "outstand", (0.0, 0.0), (0.0, c_b), t, supported_end=1),
    ]


# ── buckling curves (EN 1993-1-1 Table 6.2) ─────────────────────────────────


def buckling_curves(
    kind: str,
    fabrication: Fabrication,
    f_y: float,
    h: Optional[float] = None,
    b: Optional[float] = None,
    t_f: Optional[float] = None,
) -> Tuple[str, str, Optional[str]]:
    """`(curve_y, curve_z, curve_lt)` per EN 1993-1-1 Table 6.2.

    `curve_y` is about local y and `curve_z` about local z, matching the section
    factories' `i_y = sp.iyy_c` / `i_z = sp.ixx_c` mapping — so for an I-section
    or a channel, local z is the STRONG axis and local y the weak one, and the
    table's "y-y" row maps onto `curve_z` here.

    Cold-formed members are EN 1993-1-3 §6.2.2, whose Table 6.3 sends anything
    that is not a lipped channel or a hollow section to curve c; the entries
    below agree with Table 6.2 for the shapes covered here.
    """
    high_grade = f_y >= 420.0e6  # S460 row

    if kind in ("chs", "rhs", "shs", "hollow"):
        if fabrication == "cold_formed":
            return ("c", "c", "c")
        curve = "a0" if high_grade else "a"
        return (curve, curve, curve)

    if kind in ("channel", "u", "t", "solid"):
        # "U, T and solid sections" - curve c about any axis.
        return ("c", "c", "d")

    if kind in ("angle", "l"):
        return ("b", "b", "b")

    if kind in ("i", "h", "ipe", "hea", "heb", "hem"):
        if fabrication == "welded":
            # Welded I: depends on flange thickness; strong axis b / weak c
            # (t_f <= 40 mm), c / d above it.
            if t_f is not None and t_f > 0.040:
                return ("d", "c", "d")
            return ("c", "b", "d")
        # Rolled I. Table 6.2 keys on h/b and t_f; "y-y" is the strong axis,
        # which is local z here.
        if h and b and t_f is not None:
            slim = (h / b) > 1.2
            if slim and t_f <= 0.040:
                strong, weak = ("a0", "a0") if high_grade else ("a", "b")
            elif slim:
                strong, weak = ("a", "a") if high_grade else ("b", "c")
            elif t_f <= 0.100:
                strong, weak = ("a", "a") if high_grade else ("b", "c")
            else:
                strong, weak = ("c", "c") if high_grade else ("d", "d")
            return (weak, strong, "d")
        return ("b", "b", "d")

    # Unknown family: curve c is the table's catch-all for a plain section.
    return ("c", "c", "d")


# ── the block the solver actually reads ─────────────────────────────────────


def ec3_params(
    eff: Optional[EffectiveSection],
    curves: Tuple[str, str, Optional[str]],
    section_class: Optional[int] = None,
    *,
    classify: bool = True,
) -> dict:
    """Build a `Section.ec3` block from a classification result and curve set.

    Buckling curves go out uppercase because that is how the solver's
    `BucklingCurve` enum is spelled on the wire (`"A0" | "A" | "B" | "C" | "D"`).

    `a_eff` is emitted only for a class 4 section: for classes 1-3 the effective
    area equals the gross one, and sending it anyway would make the solver
    substitute a rounded copy of a number it already has.

    With `classify=False` only the buckling curves go out. Those do not depend on
    the stress distribution, whereas the class does — see `section_ec3`.
    """
    curve_y, curve_z, curve_lt = curves
    cls = section_class if section_class is not None else (eff.section_class if eff else None)
    if not classify:
        cls = None
        eff = None
    out: dict = {
        "buckling_curve_y": curve_y.upper(),
        "buckling_curve_z": curve_z.upper(),
    }
    if curve_lt:
        out["buckling_curve_lt"] = curve_lt.upper()
    if cls is not None:
        out["section_class"] = int(cls)
    if eff is not None and eff.is_class4:
        out["a_eff"] = eff.a_eff
    return out


def section_ec3(
    kind: str,
    f_y: float,
    a_gross: float,
    *,
    fabrication: Fabrication = "hot_rolled",
    h: Optional[float] = None,
    b: Optional[float] = None,
    t: Optional[float] = None,
    t_f: Optional[float] = None,
    t_w: Optional[float] = None,
    r: float = 0.0,
    d: Optional[float] = None,
    classify_for: Optional[str] = None,
) -> Tuple[dict, Optional[EffectiveSection]]:
    """`(ec3_block, effective_section_or_None)` for a parametric profile.

    One call per profile family, so the section factories do not each re-derive
    the plate decomposition. A CHS gets its class but no `a_eff` — a class 4 tube
    is EN 1993-1-6, not an effective width, and inventing one would be worse than
    leaving it out.

    `classify_for` decides whether a class and an effective area are emitted at
    all, and it defaults to **off** on purpose. Classification is a property of
    the stress distribution, not of the section: an IPE600 web is class 4 under
    uniform compression and class 1 in bending (Table 5.2 allows 33·eps against
    72·eps), while `Section.ec3.section_class` is a single field the solver uses
    for both. Stamping the compression class onto a section that will be used as
    a beam would have the solver demand effective moduli for a check that never
    needed them — 28 of the 348 catalogue sections are affected.

    So the buckling curves, which do not depend on the stress state, are always
    emitted; the class and `a_eff` only when the caller says how the member is
    loaded. Pass ``classify_for="compression"`` for a strut or a brace.
    """
    if classify_for not in (None, "compression"):
        raise ValueError(
            "classify_for must be None or 'compression'; bending classification "
            "(EN 1993-1-1 Table 5.2 with psi < 1) is not implemented"
        )
    classify = classify_for == "compression"
    curves = buckling_curves(kind, fabrication, f_y, h=h, b=b, t_f=t_f)
    tf = t_f if t_f is not None else t
    tw = t_w if t_w is not None else t

    if kind in ("chs", "tube"):
        if d is None or t is None:
            return ec3_params(None, curves, classify=classify), None
        return (
            ec3_params(None, curves, section_class=tube_class(d, t, f_y), classify=classify),
            None,
        )

    if kind in ("angle", "l"):
        if h is None or b is None or t is None:
            return ec3_params(None, curves, classify=classify), None
        cls = angle_class(h, b, t, f_y)
        eff = effective_section(angle_plates(h, b, t, r), a_gross, f_y)
        # Table 5.2 sheet 3 is the classification authority for an angle; the
        # leg-by-leg reduction only supplies the effective area behind it.
        eff.section_class = cls
        if cls < 4:
            eff.a_eff = a_gross
        return ec3_params(eff, curves, section_class=cls, classify=classify), eff

    if h is None or b is None or tf is None or tw is None:
        return ec3_params(None, curves, classify=classify), None

    if kind in ("channel", "u"):
        plates = channel_plates(h, b, tf, tw, r)
    elif kind in ("rhs", "shs", "hollow"):
        plates = rhs_plates(h, b, t if t is not None else tf, r)
    elif kind in ("i", "h", "ipe", "hea", "heb", "hem"):
        plates = i_plates(h, b, tf, tw, r)
    else:
        return ec3_params(None, curves, classify=classify), None

    eff = effective_section(plates, a_gross, f_y)
    return ec3_params(eff, curves, classify=classify), eff
