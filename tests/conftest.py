# tests/conftest.py
import os
import sys

# 1) Make tests/ itself a source root so that
#    `import beam_equation_checks` resolves to tests/beam_equation_checks
tests_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, tests_dir)

# 2) Make project_root a source root so that
#    `import fers_core` resolves to your FERS_core/ directory
project_root = os.path.abspath(os.path.join(tests_dir, ".."))
sys.path.insert(0, project_root)
