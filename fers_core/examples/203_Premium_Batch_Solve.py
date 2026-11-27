"""
203: solving a batch of models unattended.

With an API key each solve first checks the licence with ferscloud.com. A stalled
check raises FersTimeoutError before the solve starts, so it is safe to retry; a
RuntimeError (bad key, rejected model) fails the same way every time, so it is
recorded and skipped. license_timeout bounds the check, not the solve.

Set FERS_API_KEY to solve at Premium limits; without it the batch runs at Free tier.
"""

import os
import tempfile

import fers_calculations

from fers_core.builders import create_beam

API_KEY = os.environ.get("FERS_API_KEY")  # None: Free tier, no network call
LICENSE_TIMEOUT = 60.0  # seconds; None uses the engine default (30 s, or FERS_LICENSE_TIMEOUT)
MAX_ATTEMPTS = 3

OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "fers_batch_203")

CONFIGURATIONS = [
    {"name": f"span{span:g}m_udl{udl // 1000:g}kNm", "span": span, "udl": -float(udl)}
    for span in (4.0, 5.0, 6.0, 7.0)
    for udl in (3000, 6000)
]

os.makedirs(OUTPUT_DIR, exist_ok=True)

solved: list[str] = []
skipped: list[tuple[str, str]] = []

print(
    f"Solving {len(CONFIGURATIONS)} configurations "
    f"({'Premium' if API_KEY else 'Free tier; set FERS_API_KEY for Premium'})\n"
)

for config in CONFIGURATIONS:
    model = create_beam(config["span"], "IPE180", udl=config["udl"])
    output_path = os.path.join(OUTPUT_DIR, f"{config['name']}.json")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # The engine writes the results to disk; they never pass through Python.
            model.run_analysis_to_file(
                output_path,
                api_key=API_KEY,
                license_timeout=LICENSE_TIMEOUT,
            )
            solved.append(config["name"])
            break

        except fers_calculations.FersTimeoutError as error:
            if attempt < MAX_ATTEMPTS:
                print(f"  {config['name']}: licence timeout, retrying ({attempt}/{MAX_ATTEMPTS})")
                continue
            skipped.append((config["name"], f"licence timeout after {attempt} attempts: {error}"))

        except RuntimeError as error:
            skipped.append((config["name"], str(error)))
            break

print(f"\nSolved  : {len(solved)}/{len(CONFIGURATIONS)}")
print(f"Output  : {OUTPUT_DIR}")

if skipped:
    print(f"\nSkipped : {len(skipped)}")
    for name, reason in skipped:
        print(f"  {name}: {reason[:120]}")
else:
    print("\nNo configurations were skipped.")
