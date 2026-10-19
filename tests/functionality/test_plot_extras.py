"""With FERS[plot] installed, plotting still works: 0.2.0 imports matplotlib on first use."""

import pytest

from fers_core import FERS, Member, MemberSet, MaterialLibrary, Node, NodalSupport
from fers_core.sections.steel_sections_en import resolve_section


@pytest.fixture
def pyplot(monkeypatch):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda *args, **kwargs: None)
    yield plt
    plt.close("all")


def test_a_section_and_a_member_set_plot(pyplot):
    FERS()
    section = resolve_section("UPE200", MaterialLibrary.get("S235"))
    section.plot()
    a, b = Node(0, 0, 0, nodal_support=NodalSupport()), Node(0, 0, 3)
    MemberSet(members=[Member(start_node=a, end_node=b, section=section)]).plot()
    assert pyplot.get_fignums()
