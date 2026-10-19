"""`pip install FERS` installs no plotting, section-design or DXF stack (0.2.0).

Those are extras now, so nothing an agent runs to model, solve or check may import
them. Each probe runs in a fresh interpreter with the extras blocked, which is what
a sandbox without them gets, even when this suite runs with them installed.
"""

import subprocess
import sys

EXTRAS = ("matplotlib", "pyvista", "vtk", "scipy", "sectionproperties", "ezdxf")

_PROBE = """
import importlib.abc
import sys

attempted = set()


class _Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        root = name.split(".")[0]
        if root in {extras!r}:
            attempted.add(root)
            raise ImportError(f"{{root}} is blocked: the probe runs FERS without its extras")
        return None


sys.meta_path.insert(0, _Blocker())
{code}
print("ATTEMPTED:" + ",".join(sorted(attempted)))
"""


def _run(code: str) -> subprocess.CompletedProcess:
    probe = _PROBE.format(extras=EXTRAS, code=code)
    return subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)


def _extras_attempted(code: str) -> list[str]:
    out = _run(code)
    assert out.returncode == 0, out.stderr
    line = [ln for ln in out.stdout.splitlines() if ln.startswith("ATTEMPTED:")][-1]
    return [m for m in line.removeprefix("ATTEMPTED:").split(",") if m]


def test_import_fers_core_needs_no_extra():
    assert _extras_attempted("import fers_core") == []


def test_fers_version_needs_no_extra():
    assert _extras_attempted("from fers_core.cli import main\nmain(['version'])") == []


def test_a_catalogue_beam_solves_without_extras():
    code = (
        "from fers_core import create_beam\n"
        "m = create_beam(span=6.0, section='IPE200', udl=10_000.0)\n"
        "m.run_analysis()\n"
    )
    assert _extras_attempted(code) == []


def test_an_ec3_check_runs_without_extras():
    code = (
        "from fers_core import check_beam\n"
        "m = check_beam(span=6.0, section='HEA200', udl=10_000.0)\n"
        "m.run_analysis()\n"
    )
    assert _extras_attempted(code) == []


def test_a_custom_geometry_names_the_extra_it_needs():
    code = (
        "from fers_core import Material, Section\n"
        "steel = Material(name='S235', e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)\n"
        "try:\n"
        "    Section.create_welded_i_section('W', steel, h=0.5, b=0.2, t_f=0.016, t_w=0.01)\n"
        "except ImportError as exc:\n"
        "    print('ERROR:', exc)\n"
    )
    out = _run(code)
    assert 'pip install "FERS[sections]"' in out.stdout, out.stdout + out.stderr
