# API keys, solve tokens and timeouts

Without an API key the solver runs at Free-tier limits (100 members) and makes
no network call at all. The free tier is for non-commercial use; commercial use
needs a Pro key at any model size. Passing `api_key` raises those limits, to
10,000 members with a Pro key and 1,000,000 with an Enterprise one (granted by
agreement):

```python
model.run_analysis(api_key=KEY)
```

A key of a Free account solves at Free-tier limits, with a `UserWarning` that
says so. `--solve-token` on the command line, or `run_analysis(solve_token=...)`,
takes a short-lived token from FERS Cloud instead, which the engine checks
offline: Premium limits on a machine that cannot reach ferscloud.com.

## Licence timeouts

With a key, each solve first verifies the licence with ferscloud.com. If the
licence server does not answer within `license_timeout` seconds (default 30),
the call raises `FersTimeoutError` before the solve starts, so retrying is
always safe:

```python
import fers_calculations

try:
    model.run_analysis(api_key=KEY, license_timeout=60)
except fers_calculations.FersTimeoutError:
    ...   # the licence server stalled; retry or skip this model
except RuntimeError:
    ...   # a bad key or a rejected model; retrying fails the same way
```

Keep the two apart: catching both as `Exception` turns a retryable stall into a
lost result. `FersTimeoutError` subclasses the built-in `TimeoutError`.
`fers_core/examples/203_Premium_Batch_Solve.py` runs a batch this way.

Set `FERS_LICENSE_TIMEOUT` (seconds) to change the default without editing any
call sites. It must be a real environment variable; the engine does not read
`.env` files.

`license_timeout` bounds the licence handshake, not the solve. A solve is native
code with no cancellation point, so for a hard ceiling on wall time per model,
run each solve in a subprocess you can kill, which also reclaims its memory.
