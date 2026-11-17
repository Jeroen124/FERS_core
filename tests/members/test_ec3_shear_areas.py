"""EN 1993-1-1 §6.2.6(3) shear areas.

Hand calculations against the clause, with the nominal areas the steel tables
print, so each value can be read off a table and checked.
"""

import math

import pytest

from fers_core import Material
from fers_core.members.ec3_section import code_shear_areas, section_ec3
from fers_core.sections import british_steel
from fers_core.sections.steel_sections_en import resolve_section

S235 = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)

# IPE 300: A = 53.81 cm², b = 150, t_f = 10.7, t_w = 7.1, r = 15 (mm).
IPE300 = dict(h=0.300, b=0.150, t_f=0.0107, t_w=0.0071, r=0.015)
IPE300_A = 53.81e-4


def test_a_rolled_i_along_its_web():
    av = code_shear_areas("i", "hot_rolled", IPE300_A, **IPE300)
    # 5381 - 2·150·10.7 + (7.1 + 2·15)·10.7 = 2568 mm²
    assert av == {"a_v_y": pytest.approx(25.68e-4, rel=1e-3)}


def test_a_heb300_matches_the_tables():
    # HEB 300: A = 149.1 cm², b = 300, t_f = 19, t_w = 11, r = 27; tables: A_vz = 47.43 cm².
    av = code_shear_areas("i", "hot_rolled", 149.1e-4, h=0.300, b=0.300, t_f=0.019, t_w=0.011, r=0.027)
    assert av["a_v_y"] == pytest.approx(47.43e-4, rel=1e-3)


def test_a_the_web_bound_governs_when_the_formula_falls_below_it():
    h_w_t_w = (IPE300["h"] - 2 * IPE300["t_f"]) * IPE300["t_w"]
    av = code_shear_areas("i", "hot_rolled", 0.6 * IPE300_A, **IPE300)
    assert av["a_v_y"] == pytest.approx(h_w_t_w)


def test_b_a_rolled_channel_along_its_web():
    # UPE 200: A = 29.0 cm², b = 80, t_f = 11, t_w = 6, r = 13.
    av = code_shear_areas("channel", "hot_rolled", 29.0e-4, h=0.200, b=0.080, t_f=0.011, t_w=0.006, r=0.013)
    # 2900 - 2·80·11 + (6 + 13)·11 = 1349 mm²
    assert av == {"a_v_y": pytest.approx(13.49e-4, rel=1e-3)}


def test_d_e_a_welded_i_both_ways():
    a = 2 * 0.200 * 0.015 + 0.470 * 0.008  # 500 x 200, t_f 15, t_w 8
    av = code_shear_areas("i", "welded", a, h=0.500, b=0.200, t_f=0.015, t_w=0.008)
    assert av["a_v_y"] == pytest.approx(0.470 * 0.008)
    assert av["a_v_z"] == pytest.approx(a - 0.470 * 0.008)


def test_e_a_welded_channel_only_along_its_flanges():
    av = code_shear_areas("channel", "welded", 30.0e-4, h=0.200, b=0.080, t_f=0.011, t_w=0.006)
    assert set(av) == {"a_v_z"}


def test_f_a_rolled_rhs_by_its_depth_and_width():
    # RHS 200 x 100 x 8: A = 44.8 cm².
    for fabrication in ("hot_finished", "cold_formed"):
        av = code_shear_areas("rhs", fabrication, 44.8e-4, h=0.200, b=0.100, t=0.008)
        assert av["a_v_y"] == pytest.approx(44.8e-4 * 200 / 300)
        assert av["a_v_z"] == pytest.approx(44.8e-4 * 100 / 300)


def test_g_a_chs_both_ways():
    av = code_shear_areas("chs", "hot_finished", 25.7e-4)
    assert av == {
        "a_v_y": pytest.approx(2 * 25.7e-4 / math.pi),
        "a_v_z": pytest.approx(2 * 25.7e-4 / math.pi),
    }


def test_no_formula_no_area():
    assert code_shear_areas("angle", "hot_rolled", 19.2e-4, h=0.1, b=0.1, t=0.01) == {}
    # Cold-formed open sections are EN 1993-1-3.
    assert code_shear_areas("channel", "cold_formed", 5.26e-4, h=0.08, b=0.05, t=0.003) == {}


def test_the_block_carries_them_whatever_classify_for_says():
    for classify_for in (None, "compression"):
        block, _ = section_ec3("i", 235e6, IPE300_A, classify_for=classify_for, **IPE300)
        assert block["a_v_y"] == pytest.approx(25.68e-4, rel=1e-3)


def test_a_library_section_sends_them_to_the_solver():
    section = resolve_section("IPE300", S235)
    a_v_y = section.ec3["a_v_y"]
    expected = section.area - 2 * 0.150 * 0.0107 + (0.0071 + 2 * 0.015) * 0.0107
    assert a_v_y == pytest.approx(expected, rel=1e-9)
    assert a_v_y > section.a_sz  # the stiffness area it replaces in §6.2.6
    assert section.to_dict()["ec3"]["a_v_y"] == a_v_y


def test_a_tabulated_section_uses_its_published_area():
    name = "UB 457x191x67"
    section = resolve_section(name, S235)
    d = british_steel.dimensions(name)
    expected = section.area - 2 * d["b"] * d["t_f"] + (d["t_w"] + 2 * d["r"]) * d["t_f"]
    assert section.area == british_steel.published_si(name)["A"]
    assert section.ec3["a_v_y"] == pytest.approx(expected, rel=1e-12)
