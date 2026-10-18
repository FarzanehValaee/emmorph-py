#!/usr/bin/env python3
"""
generate_oracle.py — freeze the outputs of the original Perl scripts as a
reference oracle.

The oracle is the source of truth against which the Python port is compared.
Every Perl leaf script is run with PERL_HASH_SEED=0 to stabilise hash ordering,
and its stdout is captured to a file under oracle/.

Usage:
    python harness/generate_oracle.py --perl-dir emmorph-perl --out oracle/

The output files are named <script>_perl.out. They are committed to the
repository so the differential harness can run without a working Perl
installation.

This script should be re-run whenever:
  - the Perl originals are patched (e.g. fix B6 by adding `use FindBin;`)
  - a new leaf script is added to the manifest
  - the input corpus changes
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ─── Oracle entries ──────────────────────────────────────────────────────────
# Each entry maps a leaf Perl script to its fixed inputs and environment.
# Scripts are listed in dependency order: leaf scripts first, then scripts
# that depend on other leaf outputs.
#
# Format: (script_relative_path, args, env, output_filename)
ORACLE_ENTRIES: List[Tuple[str, List[str], Dict[str, str], str]] = [
    # ─── Leaf scripts (no dependencies on missing scripts) ────────────────────
    (
        "pl/mkavs/getsfxtags.pl",
        ["src/sfx.1"],
        {"hpldir": "."},
        "getsfxtags_perl.out",
    ),
    (
        "pl/generic/bsort.pl",
        ["src/sfx.1"],
        {"hpldir": "."},
        "bsort_perl.out",
    ),
    (
        "pl/generic/lcase.pl",
        ["src/sfx.1"],
        {"hpldir": "."},
        "lcase_perl.out",
    ),
    (
        "pl/generic/sort.pl",
        ["-q", "src/rev.srt", "src/sfx.1"],
        # sort.pl shells out to bsort.pl; PL tells it where that script lives
        # when the working directory is the repository root.
        {"hpldir": ".", "PL": "pl/generic"},
        "sort_perl.out",
    ),
    # uniq.pl is a filter — input comes via stdin
    (
        "pl/mkavs/uniq.pl",
        [],  # stdin
        {},
        "uniq_perl.out",
    ),
    # ─── Scripts that need Perl 5.26+ fixes applied first ────────────────────
    # These will fail until the FindBin patches are applied to the Perl
    # originals (see scripts/perl_patches/). They are listed here so the
    # harness knows about them; the generator will skip them with a warning
    # if they fail.
    # (
    #     "pl/generic/metadict.pl",
    #     ["-files=src/filesX.hpl", "src/metadict.txt"],
    #     {"hpldir": "."},
    #     "metadict_perl.out",
    # ),
    # (
    #     "pl/generic/encode.pl",
    #     ["-files=src/filesX.hpl", "-store", "-gen=X",
    #      "-out=encodingX.hpl"],
    #     {"hpldir": "."},
    #     "encode_perl.out",
    # ),
]


def run_perl_script(
    perl_dir: Path,
    script: str,
    args: List[str],
    env_extra: Dict[str, str],
    stdin_data: str | None = None,
) -> Tuple[int, str, str]:
    """Run a Perl script with PERL_HASH_SEED=0 and capture its output.

    Returns (exit_code, stdout, stderr).
    """
    # absolute() keeps a `subst` drive letter. resolve() expands it back to
    # the real path, which Strawberry Perl cannot open when that path
    # contains non-ASCII characters.
    script_path = (perl_dir / script).absolute()
    perl_dir = perl_dir.absolute()
    if not script_path.exists():
        return 1, "", f"script not found: {script_path}"

    env = os.environ.copy()
    env["PERL_HASH_SEED"] = "0"
    env["PERL_USE_UNSAFE_INC"] = "1"  # workaround for Perl 5.26+ @INC change
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
    except Exception as exc:
        return 1, "", f"exception: {exc!r}"


def generate_oracle(perl_dir: Path, out_dir: Path) -> int:
    """Run every ORACLE_ENTRY and write its stdout to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)

    successes = 0
    failures: List[Tuple[str, str]] = []

    for script, args, env, out_name in ORACLE_ENTRIES:
        print(f"  → {script} → {out_name} ...", end=" ", flush=True)

        # Special case: uniq.pl reads from stdin
        stdin_data = None
        if script == "pl/mkavs/uniq.pl":
            # feed a deterministic list with duplicates
            stdin_data = (
                "alma\nkorte\nalma\nszilva\nkorte\nkorte\nalma\n"
            )

        code, out, err = run_perl_script(perl_dir, script, args, env, stdin_data)

        if code == 0:
            (out_dir / out_name).write_text(out, encoding="utf-8")
            print("OK")
            successes += 1
        else:
            print(f"FAIL (exit {code})")
            if err:
                # Print only the last 200 chars of stderr to keep it readable
                tail = err[-200:] if len(err) > 200 else err
                print(f"    stderr: {tail.strip()}")
            failures.append((script, err))

    print(f"\nOracle generation: {successes} ok, {len(failures)} failed")
    if failures:
        print("\nFailed scripts:")
        for script, err in failures:
            print(f"  - {script}")
            if err:
                print(f"    {err.strip()[:300]}")
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--perl-dir",
        type=Path,
        required=True,
        help="Path to the cloned nytud/emmorph repository.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("oracle"),
        help="Output directory for oracle files (default: oracle/).",
    )
    args = parser.parse_args()

    if not args.perl_dir.is_dir():
        print(f"error: --perl-dir {args.perl_dir} does not exist", file=sys.stderr)
        return 2

    print(f"Generating oracle from {args.perl_dir} into {args.out}/")
    return generate_oracle(args.perl_dir, args.out)


if __name__ == "__main__":
    sys.exit(main())
