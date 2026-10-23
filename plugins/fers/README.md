# FERS plugin

FERS: structural finite-element analysis (3D frames, trusses, plates, Eurocode 3
checks) for engineers and AI agents. With this plugin, Claude computes
deflections, reactions, internal forces, buckling loads, natural frequencies and
EN 1993-1-1 steel member checks with a finite-element engine, instead of by hand.

In Claude Code:

```
/plugin install fers --marketplace Jeroen124/FERS_core
```

## What it contains

- **The FERS skill** (`skills/fers/`): which route to take, the modelling loop,
  how to read a verdict, and the conventions that change answers (axes, units,
  supports, load directions, limit states). `reference/api.md` holds Python
  models that run as written.
- **The local FERS MCP server**, `@ferscloud/fers-mcp` version 2.75.0, pinned.
  It gives Claude tools such as `check_beam`, `create_frame`, `build_model` and
  `solve_model`.

## What it runs and sends

- When the plugin loads, `npx` downloads `@ferscloud/fers-mcp@2.75.0` from npm
  (once, then cached) and starts it on your machine. It needs Node.js 18 or newer.
- The server solves on your machine. Without an API key it sends nothing
  anywhere. With `FERS_API_KEY` set, it exchanges the key at ferscloud.com for a
  licence token that lasts 30 minutes; the model itself never leaves your machine.
- Where Claude has a code sandbox but no MCP server, the skill may run
  `pip install FERS` there, which downloads the SDK and engine from PyPI. That
  solves in the sandbox, with nothing sent to FERS.

## Licence

The plugin's files are under the BSD 3-Clause License (`LICENSE`). The engine
the MCP server and the SDK run is free for non-commercial use, up to 100 members
per model; commercial use needs a FERS Cloud Pro plan
(https://ferscloud.com/pricing).

More: https://ferscloud.com/mcp
