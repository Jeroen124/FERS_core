# Working on FERS_core

FERS_core is the Python SDK of FERS (`pip install FERS`): the modelling objects,
the result classes, the `fers` command and the agent skill. The solver is the
compiled `fers_calculations` wheel, built from a separate private repository;
this one pins its version (`pyproject.toml` and `requirements.txt` agree, and
`tests/functionality/test_engine_pin_consistency.py` checks it).

## Set up and check

```bash
pip install -e ".[all]" pytest ruff==0.15.12
pip install -r requirements.txt       # the exact versions CI tests with
pytest                                # the whole suite, about 20 s
ruff check . && ruff format --check .
```

## Rules the code depends on

- `pip install FERS` installs no plotting, section-meshing or DXF stack. Import
  matplotlib, pyvista, sectionproperties, scipy or ezdxf only through
  `fers_core/_optional.py` (`lazy` or `require`), never at module level:
  `tests/functionality/test_lean_import.py` runs FERS with them blocked.
- Catalogue sections read their meshed properties from
  `fers_core/members/mesh_table.json.gz`. After changing a `Section.create_*`
  factory, `Section._extract_advanced_props`, the catalogue or the
  sectionproperties pin, rebuild it with `python scripts/build_mesh_table.py`
  (with `requirements.txt` installed); `tests/members/test_mesh_table.py` fails
  until you do.
- `fers_core/types/pydantic_models.py` is generated from the engine's OpenAPI
  contract by `scripts/regenerate_types.py`; never edit it by hand. A
  hand-written `to_dict()` must validate against it and must not write a key it
  lacks: the engine ignores such keys, and `fers validate` reports them.
- `fers` prints one line, or one JSON object with `--json`. Its exit codes are
  documented in `fers_core/cli.py` and tested in `tests/functionality/test_cli.py`.
- Examples are `fers_core/examples/NNN_Name.py`, each number used once, so
  `fers examples run NNN` stays unambiguous.
- `plugins/fers/` is the Claude plugin, listed by `.claude-plugin/marketplace.json`.
  Its `skills/fers/` is a copy of `fers_core/skills/fers/` (an installer fetches
  the plugin folder alone), its version follows `pyproject.toml`, and its MCP
  server is pinned to an exact `@ferscloud/fers-mcp` version, as Anthropic's
  directory requires. `tests/functionality/test_skill_reference.py` checks all
  three; `claude plugin validate --strict` checks both manifests.
- Every snippet in `fers_core/skills/fers/reference/api.md` must run as written:
  the same test executes them.
- Every release gets a CHANGELOG entry; a change a user will notice gets its own
  heading there.
- This repository is public. Compare results with closed-form solutions only,
  and never commit a credential or an API key.
