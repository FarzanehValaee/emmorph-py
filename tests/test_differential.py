"""tests/test_differential.py — pytest wrapper around harness/run_diff.py.

This module invokes the differential harness programmatically and asserts
that no NEW_BUG diffs are reported. It is the gate that prevents a Python
regression from being merged.

If the emMorph Perl submodule is not present (e.g. on a CI runner that
checks out only the Python repo), the tests are skipped.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make harness importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))


def _perl_submodule_present() -> bool:
    return (ROOT / "emmorph-perl").is_dir()


def _oracle_present() -> bool:
    return (ROOT / "oracle").is_dir() and any(
        (ROOT / "oracle").glob("*_perl.out")
    )


@pytest.mark.skipif(
    not _perl_submodule_present() and not _oracle_present(),
    reason="emmorph-perl submodule and oracle/ both missing; "
           "run 'git submodule update --init' or 'python harness/generate_oracle.py'",
)
def test_differential_harness_clean():
    """Run the differential harness and assert no NEW_BUG diffs."""
    import run_diff

    manifest_path = ROOT / "harness" / "manifest.yaml"
    perl_dir = ROOT / "emmorph-perl"
    oracle_dir = ROOT / "oracle"

    # If the Perl submodule is present, run live; otherwise use the oracle only
    if not perl_dir.is_dir():
        perl_dir = ROOT  # placeholder; harness will fall back to oracle

    # run_diff.main() uses argparse which reads sys.argv directly.
    # We need to set sys.argv ourselves.
    old_argv = sys.argv
    sys.argv = [
        "run_diff.py",
        "--manifest", str(manifest_path),
        "--perl-dir", str(perl_dir),
        "--oracle-dir", str(oracle_dir),
    ]
    try:
        exit_code = run_diff.main()
    finally:
        sys.argv = old_argv

    assert exit_code == 0, (
        "differential harness reported NEW_BUG or unclassified diffs; "
        "see the harness output above for details"
    )
