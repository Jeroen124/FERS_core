"""British Steel UB / UC / PFC and ASTM W / HP sections.

The rows are transcribed from PDFs, so most of these tests are transcription guards.
Each row is held against its own redundancy (i = sqrt(I/A), Wel = 2I/h, mass = rho*A)
and against the section meshed from its printed dimensions. That is how the four
misprints in ``CORRECTIONS`` were found, and it would find a fifth.
"""

import math

import pytest

from fers_core import Material, list_sections, section_catalogue
from fers_core.members.section import Section
from fers_core.sections import british_steel as bs

S235 = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)

ALL_ROWS = [name for rows, _, _ in bs.FAMILIES.values() for name in rows]
I_SHAPES = [name for fam in ("UB", "UC", "W", "HP") for name in bs.FAMILIES[fam][0]]


def test_every_family_is_complete():
    counts = {fam: len(rows) for fam, (rows, _, _) in bs.FAMILIES.items()}
    assert counts == {"UB": 134, "UC": 62, "PFC": 12, "W": 186, "HP": 11}
    assert len(list_sections("UB")) == 134


def test_misprints_are_corrected_and_listed():
    assert set(bs.CORRECTIONS) == {"UB 406x260x132", "W16X89", "W27X94", "W16X100", "W16X67"}
    assert bs.published("UB 406x260x132")["t"] == 13.3
    assert bs.published("W27X94")["t"] == 12.4
    for name, (_, changes) in bs.CORRECTIONS.items():
        row = bs.published(name)
        for col, (_, corrected) in changes.items():
            assert row[col] == corrected, (name, col)


@pytest.mark.parametrize("name", ALL_ROWS)
def test_printed_values_agree_with_each_other(name):
    p = bs.published(name)
    # Mass (kg/m) against A (cm2) at 7850 kg/m3. The rest of the spread is the
    # datasheets rounding mass and area separately; a misprinted web shows as 6-34 %.
    assert p["mass"] == pytest.approx(0.785 * p["A"], rel=0.03)
    for axis in ("major", "minor"):
        assert math.sqrt(p[f"I_{axis}"] / p["A"]) == pytest.approx(p[f"i_{axis}"], rel=0.01)
    assert 2 * p["I_major"] / (p["D"] / 10) == pytest.approx(p["Wel_major"], rel=0.01)
    assert p["d"] / p["t"] == pytest.approx(p["d_t"], rel=0.01)


@pytest.mark.parametrize("name", ALL_ROWS)
def test_printed_values_match_the_meshed_section(name):
    """Tolerances are the largest honest spreads across all rows: small sections
    print weak-axis moduli as two-digit integers, and the warping constant of the
    heaviest W14s ignores fillets that the mesh includes."""
    fam = bs.family_of(name)
    d = bs.dimensions(name)
    factory = Section.create_u_section if fam == "PFC" else Section.create_ipe_section
    meshed = factory(name=name, material=S235, h=d["h"], b=d["b"], t_w=d["t_w"], t_f=d["t_f"], r=d["r"])
    p = bs.published_si(name)
    assert meshed.area == pytest.approx(p["A"], rel=0.01)
    assert meshed.i_z == pytest.approx(p["I_major"], rel=0.01)
    assert meshed.wel_z == pytest.approx(p["Wel_major"], rel=0.01)
    assert meshed.wpl_z == pytest.approx(p["Wpl_major"], rel=0.01)
    assert meshed.i_y == pytest.approx(p["I_minor"], rel=0.02)
    assert meshed.wel_y == pytest.approx(p["Wel_minor"], rel=0.025)
    assert meshed.wpl_y == pytest.approx(p["Wpl_minor"], rel=0.02)
    assert meshed.j == pytest.approx(p["J"], rel=0.03)
    assert meshed.i_w == pytest.approx(p["H"], rel=0.045)


def test_published_values_reach_the_section_in_si():
    ub = Section.from_name("UB 457x191x67", S235)
    assert ub.i_z == 29597e-8
    assert ub.i_y == 1452e-8
    assert ub.area == 86.0e-4
    assert ub.i_w == 0.7050e-6
    assert ub.wpl_z == 1481e-6


def test_astm_major_axis_is_local_z():
    """The ASTM sheet calls the major axis y-y, the UK sheets x-x."""
    w = Section.from_name("W10X22", S235)
    assert w.i_z == 4953e-8
    assert w.i_y == 474e-8


def test_major_axis_is_local_z_for_every_i_shape():
    for name in I_SHAPES:
        p = bs.published_si(name)
        assert p["I_major"] > p["I_minor"], name


def test_ec3_buckling_curves_follow_the_shape():
    # FERS local z is the major axis, so EN 1993-1-1 Table 6.2's y-y curve is buckling_curve_z.
    ub = Section.from_name("UB 457x191x67", S235).ec3
    assert (ub["buckling_curve_z"], ub["buckling_curve_y"]) == ("A", "B")
    uc = Section.from_name("UC 356x406x634", S235).ec3
    assert (uc["buckling_curve_z"], uc["buckling_curve_y"]) == ("B", "C")
    pfc = Section.from_name("PFC 300x100x46", S235).ec3
    assert (pfc["buckling_curve_z"], pfc["buckling_curve_y"]) == ("C", "C")


def test_channel_shear_centre_and_centroid():
    pfc = Section.from_name("PFC 300x100x46", S235)
    assert abs(pfc.y_s) < 1e-6
    assert abs(pfc.z_s) > 0.03
    # centroid_y carries the across-the-flange offset (see the note in section.py),
    # and the datasheet gives it as Cy, measured from the back of the web.
    c_y = bs.dimensions("PFC 300x100x46")["c_y"]
    assert 0.100 / 2 - abs(pfc.centroid_y) == pytest.approx(c_y, abs=1e-4)


@pytest.mark.parametrize(
    "spelling, name",
    [
        ("UB 457x191x67", "UB 457x191x67"),
        ("ub457X191x67", "UB 457x191x67"),
        ("UKB 457x191x67", "UB 457x191x67"),
        ("457 x 191 x 67 UKB", "UB 457x191x67"),
        ("457x191x67 UB", "UB 457x191x67"),
        ("UKC 305 × 305 × 97", "UC 305x305x97"),
        ("UKPFC 300x100x46", "PFC 300x100x46"),
        ("w 10 x 22", "W10X22"),
        ("W8X8X76*", "W8X8X76"),
        ("IPE 180", "IPE180"),
        ("rhs200x100x8", "RHS 200x100x8"),
    ],
)
def test_lookup_spellings(spelling, name):
    assert Section.from_name(spelling, S235).name == name


# W12X27 is no shape anywhere; W12X26 exists, but from AISC (test_aisc_sections.py).
@pytest.mark.parametrize("missing", ["W12X27", "UB 410x260x132", "W8X76", "UKB 999x1x1"])
def test_unknown_names_raise(missing):
    with pytest.raises(ValueError):
        Section.from_name(missing, S235)


def test_section_catalogue():
    assert section_catalogue("IPE200") == "en"
    assert section_catalogue("UKB 457x191x67") == "uk"
    assert section_catalogue("PFC 300x100x46") == "uk"
    assert section_catalogue("HP12X53") == "us"
