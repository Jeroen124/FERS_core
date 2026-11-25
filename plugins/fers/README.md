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
- **The FERS connector**, the hosted MCP server at `https://ferscloud.com/api/mcp`.
  It gives Claude tools such as `check_beam`, `create_frame`, `build_model` and
  `solve_model`.

## What it runs and sends

- The connector asks you to sign in to a FERS account (OAuth) the first time
  Claude uses it. It receives the models Claude builds, validates them and keeps
  a copy for 24 hours behind a link. It runs no solver: opening the link solves
  the model in your browser.
- For numbers inside the chat, the skill runs `pip install FERS`, which downloads
  the SDK and engine from PyPI and solves on your machine, with nothing sent to
  FERS.
- To solve inside the chat through MCP instead, add the local server yourself:
  `claude mcp add fers-local -- npx -y @ferscloud/fers-mcp` (Node.js 18 or newer).
  It solves on your machine and sends the model nowhere.

## Licence

The plugin's files are under the BSD 3-Clause License (`LICENSE`). The engine
behind the connector, the local server and the SDK is free for non-commercial use, up to 100 members
per model; commercial use needs a FERS Cloud Pro plan
(https://ferscloud.com/pricing).

More: https://ferscloud.com/mcp
