# The `fers` command

`pip install FERS` puts a `fers` command on the path: a thin layer over the
Python objects and the engine, for shells, scripts, CI jobs and coding agents.
Every large output goes to a file; stdout carries one line per command, or a
JSON object with `--json`.

```bash
fers validate model.json                 # the input schema: the failing field, and keys the engine ignores
fers solve model.json --out results.json # the engine streams the results to the file
fers check model.json                    # solve, print each unity check's utilization and a verdict
fers report results.json --out report.html
fers schema                              # the schema's definitions; `fers schema Member` prints one
fers sections get IPE200                 # catalogue properties in SI; `sections list` names the series
fers materials list
fers examples list                       # the numbered examples; `examples show 001`, `examples run 001`
fers skill --install .                   # the skill for coding agents, into .claude/skills
fers skill --zip fers-skill.zip          # the same skill as a zip to upload to Claude.ai
fers doctor                              # versions, and whether the key is accepted
```

`fers solve` sends the file to the engine as it is, and reads the results back
only for its summary line: load cases, combinations, recorded failures,
non-converged result sets and messages. A model that writes hundreds of
megabytes costs this process nothing.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | done; for `check`, every check passes |
| 1 | the engine refused or failed the solve |
| 2 | bad input: a missing file, invalid JSON, a model that fails the schema (with `validate --strict`, also a key the schema does not know) |
| 3 | licence: no key where one is needed, a rejected key, a licence timeout |
| 4 | solved, but **do not use the numbers**: a result set has errors (a mechanism is `singular_model`), did not converge, or failures were recorded. The output says why. |
| 5 | `check`: nothing decided: a check is Indeterminate, left combinations unsolved, or the model has no checks |
| 6 | `check`: a check fails (utilization above 1) |

A `check` that meets several of these exits with the first of 4, 6, 5. With
`--json`, `solve` and `check` add a `verdict` and its `reasons`. After "DO NOT
USE these results" comes the reason: the solver's first error, or the error a
load case or combination recorded when it failed outright. `fers check` names
what governs each check, `governing member 4 (Column, HEA300) in "ULS 1"
(combination 2)`, and `--json` carries the same as `governing_entity_label` and
`governing_combination_name`.

`FERS_API_KEY` supplies the key when `--api-key` is not given, and
`FERS_SOLVE_TOKEN` a solve token; see [keys and timeouts](keys-and-timeouts.md).

## Coding agents

The skill is the working loop on one page: which route to take (MCP tools, a
shell or code sandbox, or a file for FERS Studio), validate, solve, check, and
the conventions that change answers, with runnable models in `reference/api.md`.
It ships in the package (`fers_core/skills/fers/`). `fers skill --install .`
copies it to `.claude/skills/fers/`, `fers skill --zip fers-skill.zip` packs it
for upload to Claude.ai, and `fers skill --path` names `SKILL.md` for any other
agent.

MCP clients can run the same engine as a local MCP server
(`npx -y @ferscloud/fers-mcp`, which solves on the user's machine); clients that
cannot start a program use the hosted server at https://ferscloud.com/api/mcp,
which returns a link that solves the model in the browser. Setup for each
client: https://ferscloud.com/mcp. In Claude Code, the skill and the hosted
server come as one plugin: `/plugin install fers --marketplace Jeroen124/FERS_core`.

`fers_core/examples/811_Command_Line_Workflow.py` runs the loop end to end.
