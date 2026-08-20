"""
203 — Premium Batch Solve  (unattended runs that cannot hang)
============================================================
The pattern for solving many models in one unattended run: a load table, a
parametric sweep, a nightly job. This is the scenario that motivated the
bounded licence handshake in engine 0.2.53.

Why this example exists
-----------------------
  Solving with an ``api_key`` raises the Free-tier 100-member limit, but it
  also means each solve first contacts the licence server. Before 0.2.53 that
  handshake had no read timeout, so a stalled licence server could block a
  batch **indefinitely** — one reported run sat for ~6 hours at 0 % CPU with no
  exception raised, and no way to interrupt it from Python.

  Since 0.2.53 the handshake is always bounded (30 s by default) and a stall
  raises ``FersTimeoutError`` *before the solve starts*, which is what makes the
  retry loop below correct: a timeout means no work was done, so retrying is
  always safe.

The two error classes, and why the distinction matters
------------------------------------------------------
  ``FersTimeoutError``  -- transient. The licence server did not answer in time.
                           Nothing was solved. Retry.
  ``RuntimeError``      -- definitive. Bad key, non-premium account, unreachable
                           host, or a model the solver rejected. Retrying will
                           fail identically, so skip and record it.

  Catching only ``Exception`` collapses these two and turns a retryable blip
  into a lost row (or an infinite retry loop on a permanently bad model).

Bounding the solve itself
-------------------------
  ``license_timeout`` bounds the *licence handshake*, not the solve. A solve is
  native compiled code with no cancellation point, so no in-process timeout can
  interrupt it. If you need a hard ceiling on total wall time per model, run
  each solve in a killable subprocess — that also reclaims its memory, which
  abandoning an in-process thread cannot.

Running it
----------
  Set FERS_API_KEY to solve at Premium limits:      set FERS_API_KEY=...
  Without it the example still runs, at Free tier, exercising the same loop.
  Set FERS_LICENSE_TIMEOUT to change the default budget without touching code.
"""

import os
import tempfile

import fers_calculations

from fers_core.builders import create_beam

# =============================================================================
# 1.  Configuration
# =============================================================================
# Omitted (None) => Free tier, and no network call is made at all.
API_KEY = os.environ.get("FERS_API_KEY")

# Seconds to wait for the licence handshake. None uses the engine default
# (30 s, or FERS_LICENSE_TIMEOUT). Raise it on a slow or distant link.
LICENSE_TIMEOUT = 60.0

# A stalled licence server is transient, so it is worth a couple of retries
# before giving up on a row.
MAX_ATTEMPTS = 3

OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "fers_batch_203")

# =============================================================================
# 2.  The batch — a small span/load table
# =============================================================================
CONFIGURATIONS = [
    {"name": f"span{span:g}m_udl{udl // 1000:g}kNm", "span": span, "udl": -float(udl)}
    for span in (4.0, 5.0, 6.0, 7.0)
    for udl in (3000, 6000)
]

# =============================================================================
# 3.  Solve each configuration, streaming results straight to disk
# =============================================================================
os.makedirs(OUTPUT_DIR, exist_ok=True)

solved: list[str] = []
skipped: list[tuple[str, str]] = []

print(
    f"Solving {len(CONFIGURATIONS)} configurations "
    f"({'Premium' if API_KEY else 'Free tier — set FERS_API_KEY for Premium'})\n"
)

for config in CONFIGURATIONS:
    model = create_beam(config["span"], "IPE180", udl=config["udl"])
    output_path = os.path.join(OUTPUT_DIR, f"{config['name']}.json")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # run_analysis_to_file streams the result JSON straight to disk, so
            # a large result never has to fit in the Python heap alongside the
            # parsed model. Use run_analysis() instead when you want the values
            # back in `model.resultsbundle`.
            model.run_analysis_to_file(
                output_path,
                api_key=API_KEY,
                license_timeout=LICENSE_TIMEOUT,
            )
            solved.append(config["name"])
            break

        except fers_calculations.FersTimeoutError as error:
            # Transient: the licence server stalled and the solve never started.
            if attempt < MAX_ATTEMPTS:
                print(f"  {config['name']}: licence timeout, retrying ({attempt}/{MAX_ATTEMPTS})")
                continue
            skipped.append((config["name"], f"licence timeout after {attempt} attempts: {error}"))

        except RuntimeError as error:
            # Definitive: retrying would fail identically.
            skipped.append((config["name"], str(error)))
            break

# =============================================================================
# 4.  Summary — always report what did not get solved
# =============================================================================
print(f"\nSolved  : {len(solved)}/{len(CONFIGURATIONS)}")
print(f"Output  : {OUTPUT_DIR}")

if skipped:
    print(f"\nSkipped : {len(skipped)}")
    for name, reason in skipped:
        print(f"  {name}: {reason[:120]}")
else:
    print("\nNo configurations were skipped.")
