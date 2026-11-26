"""The skill's API reference runs as written: agents copy these blocks verbatim."""

import re
from pathlib import Path

import fers_core

SKILL = Path(fers_core.__file__).parent / "skills" / "fers"
REFERENCE = SKILL / "reference" / "api.md"


def test_every_python_block_in_the_reference_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    blocks = re.findall(r"```python\n(.*?)```", REFERENCE.read_text(encoding="utf-8"), re.S)
    assert len(blocks) >= 4
    namespace: dict = {}
    for block in blocks:
        # A block without imports continues the one before it.
        if block.lstrip().startswith(("from ", "import ")):
            namespace = {}
        exec(compile(block, str(REFERENCE), "exec"), namespace)
    out = capsys.readouterr().out
    assert out.count("EC3 ") == 3 and "sway" in out
    assert (tmp_path / "model.json").is_file()


def test_the_skill_points_only_at_files_it_ships():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for path in re.findall(r"`(reference/[\w./-]+)`", text):
        assert (SKILL / path).is_file(), path


REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "fers"


def _files(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in folder.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def test_the_plugin_ships_the_packaged_skill():
    # An installer fetches the plugin folder alone, so it carries a copy.
    assert _files(PLUGIN / "skills" / "fers") == _files(SKILL), (
        "plugins/fers/skills/fers differs from fers_core/skills/fers: copy the package's skill over it"
    )


def test_the_plugin_is_versioned_with_the_sdk():
    import json
    import tomllib

    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert plugin["version"] == project["version"]
    # The directory takes an MCP server that runs on the user's computer only from a
    # Verified organization, so the plugin carries the hosted connector, not npx.
    mcp = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"] == {"fers": {"type": "http", "url": "https://ferscloud.com/api/mcp"}}
