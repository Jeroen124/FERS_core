"""Coverage for the ``fers`` command line (fers_core.cli)."""

import json
import shutil
import subprocess
import sys

import pytest

from fers_core import (
    FERS,
    AnalysisOrder,
    Material,
    Member,
    MemberSet,
    NodalLoad,
    NodalSupport,
    Node,
    Section,
    cli,
)
from fers_core.builders import check_beam, create_beam


@pytest.fixture
def beam_file(tmp_path):
    path = tmp_path / "beam.json"
    create_beam(5.0, "IPE180", udl=5000.0).save_to_json(str(path), indent=2)
    return path


@pytest.fixture
def broken_file(beam_file, tmp_path):
    document = json.loads(beam_file.read_text(encoding="utf-8"))
    document["analysis"]["options"]["order"] = "QUADRATIC"
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _run(capsys, argv):
    code = cli.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def test_version_names_both_packages(capsys):
    code, out, _ = _run(capsys, ["version"])
    assert code == cli.EXIT_OK
    assert out.startswith("FERS ") and "fers_calculations" in out


def test_solve_streams_the_results_to_a_file_and_prints_one_line(beam_file, tmp_path, capsys):
    out_path = tmp_path / "results.json"
    code, out, _ = _run(capsys, ["solve", str(beam_file), "--out", str(out_path)])
    assert code == cli.EXIT_OK
    assert out.count("\n") == 1
    assert out.startswith("solved: 1 load cases, 0 combinations")
    document = json.loads(out_path.read_text(encoding="utf-8"))
    assert document["results"]["loadcases"]


def test_solve_defaults_to_a_results_file_beside_the_model(beam_file, capsys):
    code, out, _ = _run(capsys, ["solve", str(beam_file)])
    assert code == cli.EXIT_OK
    assert (beam_file.parent / "beam_results.json").is_file()


def test_solve_json_summary_is_pure_json(beam_file, tmp_path, capsys):
    code, out, _ = _run(capsys, ["solve", str(beam_file), "--out", str(tmp_path / "r.json"), "--json"])
    assert code == cli.EXIT_OK
    summary = json.loads(out)
    assert summary["ok"] is True
    assert summary["load_cases"] == 1
    assert summary["solve_failures"] == 0 and summary["load_case_failures"] == 0


def test_solve_refuses_a_missing_file_and_invalid_json(tmp_path, capsys):
    code, _, err = _run(capsys, ["solve", str(tmp_path / "missing.json")])
    assert code == cli.EXIT_INPUT and "no such file" in err
    not_json = tmp_path / "not.json"
    not_json.write_text("{", encoding="utf-8")
    code, _, _ = _run(capsys, ["solve", str(not_json)])
    assert code == cli.EXIT_INPUT


def test_solve_reports_an_engine_refusal_with_its_message(broken_file, capsys):
    code, _, err = _run(capsys, ["solve", str(broken_file)])
    assert code == cli.EXIT_ENGINE
    assert "QUADRATIC" in err


def test_solve_over_the_free_cap_without_a_key_is_a_licence_exit(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("FERS_API_KEY", raising=False)
    model = FERS()
    model.settings.analysis_options.order = AnalysisOrder.LINEAR
    steel = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)
    section = Section(name="IPE180", material=steel, i_y=1.01e-6, i_z=13.21e-6, j=0.027e-6, area=0.00196)
    nodes = [Node(i * 0.1, 0, 0) for i in range(102)]
    nodes[0].nodal_support = NodalSupport()
    members = [Member(start_node=nodes[i], end_node=nodes[i + 1], section=section) for i in range(101)]
    model.add_member_set(MemberSet(members=members))
    case = model.create_load_case(name="Tip")
    NodalLoad(node=nodes[-1], load_case=case, magnitude=-1000, direction=(0, 1, 0))
    path = tmp_path / "over_cap.json"
    model.save_to_json(str(path))
    code, _, err = _run(capsys, ["solve", str(path)])
    assert code == cli.EXIT_LICENCE
    assert "101" in err


def test_validate_accepts_a_model_and_names_the_failing_field(beam_file, broken_file, capsys):
    code, out, _ = _run(capsys, ["validate", str(beam_file)])
    assert code == cli.EXIT_OK
    assert out.startswith("valid: 9 nodes, 8 members")
    code, _, err = _run(capsys, ["validate", str(broken_file)])
    assert code == cli.EXIT_INPUT
    assert "analysis.options.order" in err


def test_schema_lists_definitions_and_prints_one(capsys):
    code, out, _ = _run(capsys, ["schema", "--list"])
    assert code == cli.EXIT_OK
    names = [line.split()[0] for line in out.splitlines() if line.strip()]
    assert names[0] == "FERS" and "Analysis" in names and "Member" in names
    code, out, _ = _run(capsys, ["schema", "Analysis"])
    assert code == cli.EXIT_OK
    assert "options" in json.loads(out)["properties"]
    code, _, err = _run(capsys, ["schema", "NoSuchRoot"])
    assert code == cli.EXIT_INPUT and "NoSuchRoot" in err


def test_schema_writes_the_whole_schema_to_a_file(tmp_path, capsys):
    out_path = tmp_path / "schema.json"
    code, _, _ = _run(capsys, ["schema", "--out", str(out_path)])
    assert code == cli.EXIT_OK
    assert "$defs" in json.loads(out_path.read_text(encoding="utf-8"))


def test_sections_and_materials(capsys):
    code, out, _ = _run(capsys, ["sections", "list", "--series", "IPE"])
    assert code == cli.EXIT_OK and "IPE200" in out.split()
    code, out, _ = _run(capsys, ["sections", "get", "IPE200", "--json"])
    assert code == cli.EXIT_OK
    section = json.loads(out)
    assert section["h"] == pytest.approx(0.2) and section["catalogue"] == "en"
    code, _, _ = _run(capsys, ["sections", "get", "IPE9999"])
    assert code == cli.EXIT_INPUT
    code, out, _ = _run(capsys, ["materials", "list"])
    assert code == cli.EXIT_OK and "S235" in out.splitlines()
    code, out, _ = _run(capsys, ["materials", "get", "S355", "--json"])
    assert code == cli.EXIT_OK and json.loads(out)["yield_stress"] == pytest.approx(355e6)


def test_examples_list_and_show(capsys):
    code, out, _ = _run(capsys, ["examples", "list"])
    assert code == cli.EXIT_OK
    names = out.split()
    assert any(n.startswith("001_") for n in names)
    # The 1xx unity-check examples were hidden with the visual ones until 0.2.0.
    assert any(n.startswith("100_Unity_Check") for n in names)
    numbers = [n[:3] for n in names]
    assert len(numbers) == len(set(numbers)), "every example has its own number, so `run NNN` is unambiguous"
    code, out, _ = _run(capsys, ["examples", "show", "001"])
    assert code == cli.EXIT_OK and "run_analysis" in out
    code, _, _ = _run(capsys, ["examples", "show", "999999"])
    assert code == cli.EXIT_INPUT


def test_check_prints_the_utilization_and_its_json_is_pure(tmp_path, capsys):
    path = tmp_path / "check.json"
    check_beam(6.0, "IPE300", material="S235", support="simply_supported", udl=10000.0).save_to_json(
        str(path)
    )
    solved = tmp_path / "solved.json"
    code, out, _ = _run(capsys, ["check", str(path), "--out", str(solved)])
    assert code == cli.EXIT_OK
    assert out.startswith("ec3: ") and "utilization 0." in out
    assert solved.is_file()
    code, out, _ = _run(capsys, ["check", str(path), "--json"])
    assert code == cli.EXIT_OK
    checks = json.loads(out)["checks"]
    assert checks[0]["check"] == "ec3" and 0 < checks[0]["utilization"] < 1


def test_check_exit_codes_say_why_a_design_does_not_pass(tmp_path, capsys):
    failing = tmp_path / "failing.json"
    check_beam(6.0, "IPE200", udl=30000.0).save_to_json(str(failing))
    code, out, _ = _run(capsys, ["check", str(failing)])
    assert code == cli.EXIT_FAILS and "fail: ec3 utilization" in out
    code, out, _ = _run(capsys, ["check", str(failing), "--json"])
    report = json.loads(out)
    assert report["verdict"] == "fail" and report["exit_code"] == cli.EXIT_FAILS and not report["ok"]

    unchecked = tmp_path / "unchecked.json"
    create_beam(5.0, "IPE180", udl=5000.0).save_to_json(str(unchecked))
    code, out, _ = _run(capsys, ["check", str(unchecked)])
    assert code == cli.EXIT_UNDECIDED and "nothing was checked" in out


def _planar_truss_loaded_out_of_plane(path):
    """A pinned triangle in XY under a load with a Z part: it swings about its base."""
    model = FERS()
    steel = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)
    bar = Section(name="Bar", material=steel, i_y=1e-6, i_z=1e-6, j=1e-7, area=1e-3)
    free = {"X": "Free", "Y": "Free", "Z": "Free"}
    pin = NodalSupport(rotation_conditions=free)
    roller = NodalSupport(displacement_conditions={"X": "Free"}, rotation_conditions=free)
    n1, n2, n3 = Node(0, 0, 0, nodal_support=pin), Node(4, 0, 0, nodal_support=roller), Node(2, 2, 0)
    pairs = ((n1, n2), (n2, n3), (n1, n3))
    members = [Member(start_node=p, end_node=q, section=bar, member_type="Truss") for p, q in pairs]
    model.add_member_set(MemberSet(members=members))
    case = model.create_load_case(name="Apex")
    NodalLoad(node=n3, load_case=case, magnitude=10_000.0, direction=(0, -1, 0.1))
    model.settings.analysis_options.order = AnalysisOrder.LINEAR
    model.save_to_json(str(path))


def test_solve_refuses_to_bless_a_mechanism(tmp_path, capsys):
    # Engine 0.2.71 solves this, flags singular_model and returns numbers; before
    # 0.2.0 `fers solve` exited 0 on them.
    path = tmp_path / "mechanism.json"
    _planar_truss_loaded_out_of_plane(path)
    code, out, _ = _run(capsys, ["solve", str(path), "--out", str(tmp_path / "r.json")])
    assert code == cli.EXIT_UNTRUSTWORTHY
    assert "DO NOT USE these results" in out and "mechanism" in out
    code, out, _ = _run(capsys, ["solve", str(path), "--out", str(tmp_path / "r.json"), "--json"])
    summary = json.loads(out)
    assert summary["verdict"] == "untrustworthy" and "singular_model" in summary["error_codes"]


def test_a_refused_solve_token_is_a_licence_error(beam_file, tmp_path, capsys, monkeypatch):
    # A valid token needs FERS Cloud's private key; the engine's own tests sign
    # with a test key. Here: a refusal reaches the caller as a licence failure.
    monkeypatch.delenv("FERS_API_KEY", raising=False)
    out = str(tmp_path / "r.json")
    code, _, err = _run(capsys, ["solve", str(beam_file), "--out", out, "--solve-token", "not.a.token"])
    assert code == cli.EXIT_LICENCE and "solve token" in err
    monkeypatch.setenv("FERS_SOLVE_TOKEN", "not.a.token")
    code, _, err = _run(capsys, ["check", str(beam_file)])
    assert code == cli.EXIT_LICENCE and "solve token" in err


def test_validate_names_keys_the_engine_would_ignore(beam_file, tmp_path, capsys):
    document = json.loads(beam_file.read_text(encoding="utf-8"))
    document["analysis"]["options"]["ordr"] = "LINEAR"
    document["model"]["members"][0]["rotation_angel"] = 90
    path = tmp_path / "typos.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    code, out, _ = _run(capsys, ["validate", str(path)])
    assert code == cli.EXIT_OK
    assert "$.analysis.options.ordr" in out and "$.model.members[0].rotation_angel" in out
    code, out, _ = _run(capsys, ["validate", str(path), "--strict", "--json"])
    assert code == cli.EXIT_INPUT and len(json.loads(out)["unknown_keys"]) == 2
    code, out, _ = _run(capsys, ["validate", str(beam_file), "--strict"])
    assert code == cli.EXIT_OK and "unknown" not in out


def test_schema_and_sections_list_start_from_an_index(capsys):
    code, out, _ = _run(capsys, ["schema"])
    assert code == cli.EXIT_OK and out.startswith("FERS ") and "`fers schema <name>`" in out
    code, out, _ = _run(capsys, ["sections", "list"])
    assert code == cli.EXIT_OK and "series:" in out.splitlines()[0]
    assert "IPE200" not in out
    code, out, _ = _run(capsys, ["sections", "list", "--json"])
    listing = json.loads(out)
    assert listing["series"]["IPE"] > 0 and listing["count"] == sum(listing["series"].values())
    code, out, _ = _run(capsys, ["sections", "list", "--all"])
    assert "IPE200" in out.split()


def test_report_renders_html_from_a_solved_document(tmp_path, capsys):
    path = tmp_path / "check.json"
    check_beam(6.0, "IPE300", material="S235", support="simply_supported", udl=10000.0).save_to_json(
        str(path)
    )
    solved = tmp_path / "solved.json"
    assert cli.main(["check", str(path), "--out", str(solved)]) == cli.EXIT_OK
    capsys.readouterr()
    html = tmp_path / "report.html"
    code, out, _ = _run(capsys, ["report", str(solved), "--out", str(html)])
    assert code == cli.EXIT_OK
    assert html.stat().st_size > 0 and "<" in html.read_text(encoding="utf-8")


def test_report_refuses_a_document_without_checks(beam_file, tmp_path, capsys):
    results = tmp_path / "results.json"
    assert cli.main(["solve", str(beam_file), "--out", str(results)]) == cli.EXIT_OK
    capsys.readouterr()
    code, _, err = _run(capsys, ["report", str(results), "--out", str(tmp_path / "r.html")])
    assert code == cli.EXIT_INPUT and "unity checks" in err


def test_skill_prints_and_installs_the_skill_file(tmp_path, capsys):
    code, out, _ = _run(capsys, ["skill"])
    assert code == cli.EXIT_OK and out.startswith("---\nname: fers")
    code, out, _ = _run(capsys, ["skill", "--path"])
    assert code == cli.EXIT_OK and out.strip().endswith("SKILL.md")
    code, out, _ = _run(capsys, ["skill", "--install", str(tmp_path)])
    assert code == cli.EXIT_OK
    installed = tmp_path / ".claude" / "skills" / "fers"
    assert (installed / "SKILL.md").read_text(encoding="utf-8").startswith("---\nname: fers")
    assert (installed / "reference" / "api.md").is_file(), "SKILL.md points at reference/api.md"


def test_skill_zips_the_folder_for_upload(tmp_path, capsys):
    import zipfile

    archive = tmp_path / "fers-skill.zip"
    code, _, _ = _run(capsys, ["skill", "--zip", str(archive)])
    assert code == cli.EXIT_OK
    names = zipfile.ZipFile(archive).namelist()
    assert "fers/SKILL.md" in names and "fers/reference/api.md" in names
    assert all(name.startswith("fers/") for name in names)


def test_doctor_offline_reports_versions(capsys, monkeypatch):
    monkeypatch.delenv("FERS_API_KEY", raising=False)
    code, out, _ = _run(capsys, ["doctor", "--offline", "--json"])
    assert code == cli.EXIT_OK
    report = json.loads(out)
    assert report["engine"] and report["api_key"].startswith("not set")
    assert "licence" not in report


def test_module_runs_as_a_subprocess():
    completed = subprocess.run(
        [sys.executable, "-m", "fers_core.cli", "version"], capture_output=True, text=True, encoding="utf-8"
    )
    assert completed.returncode == 0
    assert completed.stdout.startswith("FERS ")


def test_console_script_is_on_the_path():
    script = shutil.which("fers")
    if script is None:
        pytest.skip("the package is not installed with its entry point in this environment")
    completed = subprocess.run([script, "version"], capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0 and completed.stdout.startswith("FERS ")
