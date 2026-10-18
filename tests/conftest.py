"""tests/conftest.py — shared pytest fixtures."""

import sys
from pathlib import Path

# Make the project importable from anywhere
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
