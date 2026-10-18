#!/usr/bin/env python3
"""
run_diff.py — the differential harness.

Runs the original Perl implementation and the new Python port side-by-side
on identical inputs, normalises their outputs, and classifies every diff
into one of three buckets:

    OLD_BUG             Perl output is wrong, Python output is correct.
    NEW_BUG             Python output is wrong, Perl output is correct.
    INTENTIONAL_CHANGE  The diff matches a documented intentional change
                        listed in harness/manifest.yaml.

The harness exits 0 if every script has only INTENTIONAL_CHANGE diffs (or no
diffs at all), and exits 1 if any NEW_BUG or unclassified diff is found.
OLD_BUG diffs are reported but do not fail the build (they are bugs in the
old code that the new code fixes, which is the desired outcome).

Usage:
    python harness/run_diff.py --manifest harness/manifest.yaml --perl-dir emmorph-perl
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from classify import classify_diff, DiffBucket, Diff
from normalize import normalize_output, NormalizationError


@dataclass
class ScriptResult:
    """Result of running one script pair (Perl + Python)."""
    name: str
    perl_exit: int
    python_exit: int
    perl_stdout: str = ""
    python_stdout: str = ""
    perl_stderr: str = ""
    python_stderr: str = ""
    diffs: List[Diff] = field(default_factory=list)
    error: Optional[str] = None


def run_perl(
    perl_dir: Path,
    script: str,
    args: List[str],
    env_extra: Dict[str, str],
    stdin_data: Optional[str] = None,
) -> tuple[int, str, str]:
    """Run a Perl script with PERL_HASH_SEED=0."""
    # absolute() keeps a `subst` drive letter. resolve() expands it back to
    # the real path, which Strawberry Perl cannot open when that path
    # contains non-ASCII characters.
    script_path = (perl_dir / script).absolute()
    perl_dir = perl_dir.absolute()
    if not script_path.exists():
        return 1, "", f"script not found: {script_path}"

    env = os.environ.copy()
    env["PERL_HASH_SEED"] = "0"
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
            timeout=120,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after 120s: {script}"
    except Exception as exc:
        return 1, "", f"exception: {exc!r}"


def run_python(
    module: str,
    args: List[str],
    stdin_data: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> tuple[int, str, str]:
    """Run the Python port as a CLI module.

    PYTHONPATH is set to include the project root so that the pyemmorph
    package can be imported regardless of the current working directory.

    The ``cwd`` should typically be the same directory the Perl script
    is invoked from, so that file-path arguments like ``src/sfx.1``
    resolve to the same file for both implementations.
    """
    env = os.environ.copy()
    project_root = Path(__file__).parent.parent.resolve()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{project_root}{os.pathsep}{existing}" if existing else str(project_root)
    )

    try:
        result = subprocess.run(
            ["python", "-m", module, *args],
            env=env,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            input=stdin_data,
            timeout=120,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after 120s: {module}"
    except Exception as exc:
        return 1, "", f"exception: {exc!r}"


def load_oracle(out_dir: Path, name: str) -> Optional[str]:
    """Load a previously frozen oracle output, if it exists."""
    oracle_path = out_dir / name
    if oracle_path.exists():
        return oracle_path.read_text(encoding="utf-8")
    return None


def run_one(
    perl_dir: Path,
    oracle_dir: Path,
    entry: dict,
) -> ScriptResult:
    """Run one manifest entry end-to-end."""
    name = entry["name"]
    perl_script = entry["perl"]
    python_module = entry["python"]
    args = entry.get("args", [])
    env_extra = entry.get("env", {})
    stdin_data = entry.get("stdin")
    oracle_file = entry.get("oracle", f"{name}_perl.out")
    intentional = entry.get("intentional_changes", [])

    result = ScriptResult(name=name, perl_exit=-1, python_exit=-1)

    # ── Run Perl ─────────────────────────────────────────────────────────
    # Prefer the committed oracle; only run Perl live if no oracle exists.
    oracle = load_oracle(oracle_dir, oracle_file)
    if oracle is not None:
        result.perl_exit = 0
        result.perl_stdout = oracle
    else:
        result.perl_exit, result.perl_stdout, result.perl_stderr = run_perl(
            perl_dir, perl_script, args, env_extra, stdin_data,
        )

    # ── Run Python ────────────────────────────────────────────────────────
    # Run Python with cwd=perl_dir so that file-path arguments resolve
    # to the same files as Perl does (e.g. 'src/sfx.1' → perl_dir/src/sfx.1)
    result.python_exit, result.python_stdout, result.python_stderr = run_python(
        python_module, args, stdin_data, cwd=perl_dir,
    )

    # ── If either side failed, record and return ──────────────────────────
    if result.perl_exit != 0:
        result.error = f"Perl failed (exit {result.perl_exit}): {result.perl_stderr[:200]}"
        return result
    if result.python_exit != 0:
        result.error = f"Python failed (exit {result.python_exit}): {result.python_stderr[:200]}"
        return result

    # ── Normalise both outputs ────────────────────────────────────────────
    try:
        perl_norm = normalize_output(result.perl_stdout, entry)
    except NormalizationError as exc:
        result.error = f"Perl normalisation failed: {exc}"
        return result
    try:
        python_norm = normalize_output(result.python_stdout, entry)
    except NormalizationError as exc:
        result.error = f"Python normalisation failed: {exc}"
        return result

    # ── Classify diffs ────────────────────────────────────────────────────
    if perl_norm != python_norm:
        result.diffs = classify_diff(
            perl_norm, python_norm, intentional_changes=intentional,
        )
    return result


def print_report(results: List[ScriptResult]) -> tuple[int, int, int]:
    """Print a summary report and return (old_bugs, new_bugs, intentional)."""
    print("\n" + "=" * 72)
    print("Differential harness — summary")
    print("=" * 72)
    print(f"{'Script':<25} {'Result':<25} {'Diffs':<6}")
    print("-" * 72)

    total_old = total_new = total_int = 0
    for r in results:
        if r.error:
            status = "ERROR"
            diff_count = "-"
            total_new += 1  # treat errors as new bugs
        else:
            old = sum(1 for d in r.diffs if d.bucket == DiffBucket.OLD_BUG)
            new = sum(1 for d in r.diffs if d.bucket == DiffBucket.NEW_BUG)
            int_ch = sum(1 for d in r.diffs if d.bucket == DiffBucket.INTENTIONAL_CHANGE)
            uncl = sum(1 for d in r.diffs if d.bucket == DiffBucket.UNCLASSIFIED)
            total_old += old
            total_new += new + uncl
            total_int += int_ch
            if not r.diffs:
                status = "MATCH"
            elif new == 0 and uncl == 0:
                status = f"OK ({int_ch} intentional)"
            else:
                status = f"FAIL ({new} new, {uncl} unclassified)"
            diff_count = str(len(r.diffs))

        print(f"{r.name:<25} {status:<25} {diff_count:<6}")

    print("-" * 72)
    print(f"Total: {total_old} old-bug fixes, {total_new} new bugs, "
          f"{total_int} intentional changes")
    print("=" * 72)

    # Print details for failing entries
    for r in results:
        if r.error or any(d.bucket in (DiffBucket.NEW_BUG, DiffBucket.UNCLASSIFIED)
                          for d in r.diffs):
            print(f"\n── {r.name} ─────────────────────────────────────────")
            if r.error:
                print(f"  ERROR: {r.error}")
            for d in r.diffs:
                if d.bucket in (DiffBucket.NEW_BUG, DiffBucket.UNCLASSIFIED):
                    print(f"  [{d.bucket.value}] {d.description}")
                    if d.perl_line:
                        print(f"    perl:    {d.perl_line}")
                    if d.python_line:
                        print(f"    python:  {d.python_line}")

    return total_old, total_new, total_int


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("harness/manifest.yaml"),
        help="Path to the manifest YAML file.",
    )
    parser.add_argument(
        "--perl-dir", type=Path, default=Path("emmorph-perl"),
        help="Path to the cloned nytud/emmorph repository.",
    )
    parser.add_argument(
        "--oracle-dir", type=Path, default=Path("oracle"),
        help="Directory of frozen oracle outputs.",
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"error: manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    with args.manifest.open(encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    entries = manifest.get("scripts", [])
    if not entries:
        print("error: manifest contains no scripts", file=sys.stderr)
        return 2

    print(f"Running {len(entries)} scripts from manifest: {args.manifest}")
    results: List[ScriptResult] = []
    for entry in entries:
        name = entry["name"]
        print(f"  → {name} ...", end=" ", flush=True)
        result = run_one(args.perl_dir, args.oracle_dir, entry)
        results.append(result)
        if result.error:
            print("ERROR")
        elif not result.diffs:
            print("MATCH")
        else:
            n_new = sum(1 for d in result.diffs
                        if d.bucket in (DiffBucket.NEW_BUG, DiffBucket.UNCLASSIFIED))
            print(f"{len(result.diffs)} diff(s)"
                  + ("" if n_new == 0 else f" ({n_new} need attention)"))

    _, total_new, _ = print_report(results)
    return 0 if total_new == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
