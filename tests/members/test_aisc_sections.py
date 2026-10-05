"""AISC shapes: the US gap-fill behind British Steel's ASTM datasheet.

Read straight from AISC's workbook rather than transcribed from a PDF, so the
meshed comparison runs on every fourth row only; it is there to catch a column
read from the wrong block or an axis swapped, which would move every row.
"""

import pytest

from fers_core import Material, list_sections, section_catalogue
from fers_core.members.section import Section
from fers_core.sections import aisc, british_steel, section_source
from fers_core.sections.steel_sections_en import _build_tabulated

S235 = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)

SAMPLE = [name for rows, _, _ in aisc.FAMILIES.values() for name in list(rows)[::4]]

# kind -> property -> largest honest spread. Round: the Manual's design wall for
# heavy pipe moves A by up to 3 %. I: the warping constant of the jumbo W14s
# ignores fillets that the mesh includes.
TOLERANCE = {
    "I": {
        "A": 0.01,
        "I_major": 0.01,
        "I_minor": 0.015,
        "Wel_major": 0.01,
        "Wpl_major": 0.01,
        "J": 0.02,
        "H": 0.06,
    },
    "RECT": {"A": 0.01, "I_major": 0.01, "I_minor": 0.01, "Wel_major": 0.01, "Wpl_major": 0.01, "J": 0.03},
    "ROUND": {
        "A": 0.035,
        "I_major": 0.035,
        "I_minor": 0.035,
        "Wel_major": 0.035,
        "Wpl_major": 0.035,
        "J": 0.035,
    },
}


def test_family_counts():
    counts = {fam: len(rows) for fam, (rows, _, _) in aisc.FAMILIES.items()}
    assert counts == {"W": 129, "HP": 11, "HSS": 525, "HSSR": 189, "PIPE": 51}
    assert len(list_sections()) == 348 + 405 + 905


def test_british_steel_wins_where_both_list_a_shape():
    bs_names = {n for rows, _, _ in british_steel.FAMILIES.values() for n in rows}
    aisc_names = {n for rows, _, _ in aisc.FAMILIES.values() for n in rows}
    assert not bs_names & aisc_names
    assert section_source("W10X22") == "british_steel"
    assert section_source("W44X335") == "aisc"
    assert section_source("IPE200") == "en"


@pytest.mark.parametrize("name", SAMPLE)
def test_tabulated_values_match_the_meshed_section(name):
    meshed = _build_tabulated(aisc, aisc.family_of(name), name, S235)
    p = aisc.published_si(name)
    got = {
        "A": meshed.area,
        "I_major": meshed.i_z,
        "I_minor": meshed.i_y,
        "Wel_major": meshed.wel_z,
        "Wpl_major": meshed.wpl_z,
        "J": meshed.j,
        "H": meshed.i_w,
    }
    for prop, tol in TOLERANCE[aisc.kind_of(name)].items():
        if p[prop] is not None:
            assert got[prop] == pytest.approx(p[prop], rel=tol), prop


def test_tabulated_values_reach_the_section_in_si():
    w = Section.from_name("W44X335", S235)
    inch = 0.0254
    assert w.area == pytest.approx(98.5 * inch**2, rel=1e-12)
    assert w.i_z == pytest.approx(31100 * inch**4, rel=1e-12)
    assert w.i_y == pytest.approx(1200 * inch**4, rel=1e-12)
    assert w.i_w == pytest.approx(535000 * inch**6, rel=1e-12)
    assert aisc.published_si("W44X335")["mass"] == pytest.approx(335 * 0.45359237 / 0.3048, rel=1e-12)
    assert aisc.published_si("W44X335")["metric_designation"] == "W1100X499"


def test_hollow_sections():
    rect = Section.from_name("HSS6X4X1/4", S235)
    assert rect.i_z > rect.i_y
    assert (rect.ec3["buckling_curve_z"], rect.ec3["buckling_curve_y"]) == ("C", "C")
    round_ = Section.from_name("hss 6.000 x 0.250", S235)
    assert round_.name == "HSS6.000X0.250"
    assert round_.i_y == round_.i_z
    assert Section.from_name("pipe 6 std", S235).name == "Pipe6STD"


def test_every_aisc_shape_is_in_the_us_catalogue():
    assert {section_catalogue(n) for n in SAMPLE} == {"us"}
