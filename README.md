# FERS_core

**FERS_core** is an open-source Finite Element Method (FEM) library written in Rust with a Python interface. It provides the foundational tools and components necessary for performing FEM analysis. This core package is designed for users who need a reliable and efficient FEM solver.

## Features

- Basic Finite Element Method (FEM) solvers
- Mesh generation and manipulation tools
- Support for various types of finite elements
- Easy-to-use Python interface for integration with existing workflows
- Designed for high performance with Rust

## Installation

You can install `FERS_core` via pip:

```bash
pip install FERS
```

## Solving a model

```python
from fers_core.builders import create_beam

model = create_beam(5.0, "IPE180", udl=-5000.0)   # 5 m span, 5 kN/m downward
model.run_analysis()
print(model.resultsbundle)
```

Use `run_analysis_to_file(path, ...)` instead when the result is large — it
streams the JSON straight to disk rather than through the Python heap.

## Premium solves and timeouts

Without an API key the solver runs at Free-tier limits (100 members) and makes
**no network call at all**. Passing `api_key` raises those limits:

```python
model.run_analysis(api_key=KEY)
```

A key means each solve first verifies the licence with ferscloud.com, so that
handshake is bounded. If the licence server does not answer within
`license_timeout` seconds (default 30) the call raises `FersTimeoutError`
**before the solve starts** — so retrying is always safe:

```python
import fers_calculations

try:
    model.run_analysis(api_key=KEY, license_timeout=60)
except fers_calculations.FersTimeoutError:
    ...   # transient stall — retry or skip this model
except RuntimeError:
    ...   # definitive — bad key, non-premium account, or a rejected model
```

Keeping those two arms apart is the point: retrying a `RuntimeError` fails
identically, while collapsing both into `except Exception` turns a retryable
blip into a lost result. See `fers_core/examples/203_Premium_Batch_Solve.py`
for the full unattended-batch pattern.

`FersTimeoutError` subclasses the built-in `TimeoutError`, so a plain
`except TimeoutError` catches it too.

Set `FERS_LICENSE_TIMEOUT` (seconds) to change the default without editing any
call sites. It must be a real environment variable — `.env` files are not read
by the engine.

> `license_timeout` bounds the **licence handshake, not the solve**. A solve is
> native code with no cancellation point, so no in-process timeout can interrupt
> it. For a hard ceiling on total wall time per model, run each solve in a
> killable subprocess — that also reclaims its memory.

Requires engine `fers_calculations >= 0.2.53`.
