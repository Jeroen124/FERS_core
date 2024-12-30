import os
import subprocess
import sys

# Path to the examples folder
examples_folder = "../examples"

# Initialize counters for results
passed = []
failed = []

# Find all Python scripts in the examples folder
example_scripts = [f for f in os.listdir(examples_folder) if f.endswith(".py")]

print(f"Found {len(example_scripts)} example scripts.")

# Run each script
for script in example_scripts:
    script_path = os.path.join(examples_folder, script)
    print(f"\nRunning: {script_path}")

    try:
        # Run the script and capture its output
        result = subprocess.run(
            [sys.executable, script_path],  # Execute the script using the current Python interpreter
            check=True,  # Raise an error if the script exits with a non-zero code
            stdout=subprocess.PIPE,  # Capture standard output
            stderr=subprocess.PIPE,  # Capture standard error
        )
        # Log success
        passed.append(script)
        print(f"✅ {script} passed.")
    except subprocess.CalledProcessError as e:
        # Log failure and capture error details
        failed.append(script)
        print(f"❌ {script} failed with exit code {e.returncode}.")
        print(f"Error Output:\n{e.stderr.decode()}")

# Print summary
print("\n===================================")
print("Execution Summary:")
print(f"Passed: {len(passed)}")
print(f"Failed: {len(failed)}")

if failed:
    print("\nThe following scripts failed:")
    for script in failed:
        print(f" - {script}")

# Exit with a non-zero code if any script failed
if failed:
    sys.exit(1)
