"""The shipped mesh table: complete for the catalogue, and true to a fresh mesh.

`pip install FERS` builds catalogue sections without sectionproperties by reading
fers_core/members/mesh_table.json.gz. A changed factory, property extraction or
sectionproperties pin makes it stale: rebuild it with scripts/build_mesh_table.py.
"""

import importlib.util
import math

import pytest

from fers_core import Material, list_sections
from fers_core.members import _mesh_table
from fers_core.members import section as section_module
from fers_core.members.section import Section

S235 = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)


class _NoMesher:
    def __getattr__(self, name):
        raise AssertionError(
            f"meshed with {name}: a catalogue geometry is missing from mesh_table.json.gz. "
            "Rebuild it: python scripts/build_mesh_table.py"
        )


def test_every_catalogue_section_is_read_from_the_table(monkeypatch):
    monkeypatch.setattr(section_module, "_sp_library", _NoMesher())
    monkeypatch.setattr(section_module, "_sp_analysis", _NoMesher())
    for name in list_sections():
        Section.from_name(name, S235)


# One per generator and per catalogue: EN, British Steel, AISC.
SAMPLE = [
    "IPE200",
    "HEB300",
    "UPE200",
    "CHS 168.3x5",
    "RHS 200x100x8",
    "SHS 100x100x6",
    "L 100x100x10",
    "UB 457x191x67",
    "UC 305x305x97",
    "PFC 300x100x46",
    "W14X30",
    "HP12X53",
    "HSS6X4X1/4",
    "HSS6.000X0.250",
    "Pipe6STD",
]


def _noise_floors(props: dict) -> dict:
    """Absolute floors for quantities that are zero for a symmetric section.

    The solver returns those as noise (an IPE200's y_s is 3.2e-8 m, a tube's i_w
    is near nothing), and the noise differs between platforms, so a relative
    tolerance cannot compare them. Each floor is a billionth of the section's
    own scale.
    """
    inertia = abs(props["i_y"]) + abs(props["i_z"])
    return {
        **dict.fromkeys(("y_s", "z_s", "centroid_y", "centroid_z"), 1e-9),
        "i_w": 1e-9 * inertia * abs(props["area"]),
        "i_yz": 1e-9 * inertia,
    }


def _assert_same(shipped, fresh, where, floors):
    if isinstance(fresh, dict):
        assert isinstance(shipped, dict) and shipped.keys() == fresh.keys(), where
        for k in fresh:
            _assert_same(shipped[k], fresh[k], f"{where}.{k}", floors)
    elif fresh is None:
        assert shipped is None, where
    else:
        # A stale table drifts by far more than platforms' sparse solvers differ.
        floor = floors.get(where.rsplit(".", 1)[-1], 0.0)
        assert math.isclose(shipped, fresh, rel_tol=1e-7, abs_tol=floor), (where, shipped, fresh)


@pytest.mark.skipif(importlib.util.find_spec("sectionproperties") is None, reason="needs FERS[sections]")
@pytest.mark.parametrize("name", SAMPLE)
def test_the_table_matches_a_fresh_mesh(name, monkeypatch):
    monkeypatch.setattr(_mesh_table, "recording", {})
    Section.from_name(name, S235)
    fresh = dict(_mesh_table.recording)
    monkeypatch.setattr(_mesh_table, "recording", None)
    assert fresh, name
    for key, props in fresh.items():
        shipped = _mesh_table.lookup(key)
        assert shipped is not None, f"{name}: {key} is not in the table"
        _assert_same(shipped, props, name, _noise_floors(props))
