#!/usr/bin/env python3
"""
reproducibility_check.py — verify that Perl leaf scripts produce
deterministic output when run with two different PERL_HASH_SEED values.

This is the operational implementation of Prof. Indig's first recommendation:
handle Perl hash ordering explicitly. The check runs each script twice with
PERL_HASH_SEED=0 and PERL_HASH_SEED=1, normalises the outputs (sorts hash
keys), and fails if the normalised outputs differ — because that means the
script is producing different *content* (not just different ordering) on
different runs.

Usage:
    python harness/reproducibility_check.py --perl-dir emmorph-perl
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Reuse the same entries as the oracle generator
sys.path.insert(0, str(Path(__file__).parent))
from generate_oracle import ORACLE_ENTRIES
from normalize import normalize_output


def run_perl_with_seed(
    perl_dir: Path,
    script: str,
    args: List[str],
    env_extra: Dict[str, str],
    seed: str,
    stdin_data: str | None = None,
) -> Tuple[int, str, str]:
    """Run a Perl script with a specific PERL_HASH_SEED."""
    script_path = perl_dir / script
    if not script_path.exists():
        return 1, "", f"script not found: {script_path}"

    env = os.environ.copy()
    env["PERL_HASH_SEED"] = seed
    env["PERL_USE_UNSAFE_INC"] = "1"
    env.update(env_extra)

    try:
        result = subprocess.run(
            ["perl", str(script_path), *args],
            cwd=str(perl_dir),
            env=env,
            capture_output=True,
            text=True,
            input=stdin_data,
            timeout=60,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after 60s: {script}"


def check_one(perl_dir: Path, entry) -> Tuple[bool, str]:
    """Run a script with two seeds and compare. Returns (ok, message)."""
    script = entry[0]
    args = entry[1]
    env = entry[2]
    stdin_data = None
    if script == "pl/mkavs/uniq.pl":
        stdin_data = "alma\nkorte\nalma\nszilva\nkorte\nkorte\nalma\n"

    # Run with seed=0
    c0, out0, err0 = run_perl_with_seed(perl_dir, script, args, env, "0", stdin_data)
    if c0 != 0:
        return False, f"seed=0 failed (exit {c0}): {err0[:200]}"

    # Run with seed=1
    c1, out1, err1 = run_perl_with_seed(perl_dir, script, args, env, "1", stdin_data)
    if c1 != 0:
        return False, f"seed=1 failed (exit {c1}): {err1[:200]}"

    # Normalise both (sort hash keys)
    manifest_entry = {"name": script}
    norm0 = normalize_output(out0, manifest_entry)
    norm1 = normalize_output(out1, manifest_entry)

    if norm0 != norm1:
        # Show first diff line
        lines0 = norm0.splitlines()
        lines1 = norm1.splitlines()
        diff_lines = []
        for i, (a, b) in enumerate(zip(lines0, lines1)):
            if a != b:
                diff_lines.append(f"  line {i}: seed0={a!r}  vs  seed1={b!r}")
                if len(diff_lines) >= 3:
                    break
        if len(lines0) != len(lines1):
            diff_lines.append(
                f"  (also different line counts: seed0={len(lines0)}, seed1={len(lines1)})"
            )
        return False, "normalised outputs differ:\n" + "\n".join(diff_lines)

    return True, "deterministic"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--perl-dir", type=Path, required=True,
        help="Path to the cloned nytud/emmorph repository.",
    )
    args = parser.parse_args()

    if not args.perl_dir.is_dir():
        print(f"error: --perl-dir {args.perl_dir} does not exist", file=sys.stderr)
        return 2

    print(f"Reproducibility check on {len(ORACLE_ENTRIES)} scripts")
    failures = 0
    for entry in ORACLE_ENTRIES:
        script = entry[0]
        print(f"  → {script} ...", end=" ", flush=True)
        ok, msg = check_one(args.perl_dir, entry)
        print("OK" if ok else "FAIL")
        if not ok:
            print(f"    {msg}")
            failures += 1

    print(f"\nReproducibility: {len(ORACLE_ENTRIES) - failures} ok, {failures} fail")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
