#!/usr/bin/env python3
"""Compare intermediate ``gen/`` files across two Perl hash seeds.

Prof. Indig's layer-2 check: the emMorph build is modular, so hash-order
bugs show up as unstable intermediate files. This script runs

    make -f mak/uhun.make xlx

twice, with ``PERL_HASH_SEED=0`` and ``PERL_HASH_SEED=1``, and hashes every
file the ``xlx`` dependency closure is expected to write under ``gen/``.
Hash-like Perl lines are normalised with ``harness.normalize.normalize_line``
before the digest, so a pure reordering of ``%hash`` pairs is not unstable.

The variable settings match ``mak/mkX.sh`` (``APP=X``, ``GSFX=X``,
``BIT2MTX=1``), which is how the public build names those files
(``stemgenX.lx2``, ``encodingXbit2mtx.hpl``, and so on).

Exit status is 0 only when every expected file is STABLE. UNSTABLE or
MISSING exits 1. ``PERL_USE_UNSAFE_INC=1`` is set so Perl 5.26+ can still
``do`` a file from the current directory until the FindBin patches land.

Usage:
    python harness/intermediate_state_diff.py --perl-dir emmorph-perl
    python harness/intermediate_state_diff.py --perl-dir emmorph-perl --skip-build
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize_line


# Products of `xlx` and the rules that feed it, with APP=X and BIT2MTX.
# `normform.pl` is a hand-written source, not a generated intermediate.
# ``gen/timestamp`` is a makefile target whose recipe only prints the clock
# to stderr, so it is not a content file and is not hashed.
EXPECTED_GEN_FILES: tuple[str, ...] = (
    "metadict.txt",
    "encodingXbit2mtx.hpl",
    "sfxtags.hpl",
    "stemalt1.pl",
    "sfxalt1.pl",
    "st5dbw3s1.lx1",
    "st5dbw3s.lx1",
    "st5dbw3si.lx1",
    "2adds.lx1",
    "2adds1.lx1",
    "2addsi.lx1",
    "irreg.lx1",
    "Xsu1.lx1",
    "Xsu.lx1",
    "Xs1.lx1",
    "Xsi.lx1",
    "stemgenX.lx2",
    "stemgenX.propsets",
    "stemgenX.avs",
    "stems2addgenX.lx2",
    "stems2addgenX.propsets",
    "stems2addgenX.avs",
    "prongenX.lx2",
    "prongenX.propsets",
    "prongenX.avs",
    "genX.lx2",
    "genX.propsets",
    "genX.avs",
    "sfxgenX.lx2",
    "sfxgenX.propsets",
    "sfxgenX.avs",
    "sfxX.lx2",
    "sfxX.propsets",
)


def normalised_sha256(path: Path) -> str:
    """Hash file bytes after sorting any Perl ``%hash=(...)`` line.

    Non-UTF-8 files are hashed raw. Text files are normalised line by line
    so hash-key order alone cannot flip the digest.
    """
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return hashlib.sha256(raw).hexdigest()
    normalised = "\n".join(normalize_line(line) for line in text.splitlines())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _make_env(seed: str, perl_dir: Path) -> dict[str, str]:
    """Environment for one seeded build. Inherits the parent environment."""
    env = os.environ.copy()
    env["PERL_HASH_SEED"] = seed
    env["PERL_USE_UNSAFE_INC"] = "1"
    env["hpldir"] = str(perl_dir)
    env["APP"] = "X"
    env["GSFX"] = "X"
    env["BIT2MTX"] = "1"
    env["ANA"] = "1"
    env["METADICT"] = "metadict"
    return env


def run_xlx(perl_dir: Path, seed: str) -> tuple[int, str]:
    """Run ``make -f mak/uhun.make xlx`` once. Returns ``(code, tail)``."""
    env = _make_env(seed, perl_dir)
    command = ["make", "-f", "mak/uhun.make", "ROOT=.", "xlx"]
    try:
        result = subprocess.run(
            command,
            cwd=str(perl_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError:
        return 127, "make was not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, "make timed out after 600s"
    tail = (result.stderr or result.stdout or "")[-500:]
    return result.returncode, tail.strip()


def snapshot_tree(src: Path, dest: Path) -> None:
    """Copy every file under ``src`` into an empty ``dest`` directory."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if not src.is_dir():
        return
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        target = dest / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def reset_gen(gen_dir: Path) -> None:
    """Remove generated files so the next seed cannot reuse them."""
    if gen_dir.exists():
        shutil.rmtree(gen_dir)
    gen_dir.mkdir(parents=True)


def classify_pair(left: Path | None, right: Path | None) -> tuple[str, str]:
    """Return ``(status, detail)`` for one expected file across two seeds."""
    if left is None or right is None or not left.is_file() or not right.is_file():
        missing = []
        if left is None or not left.is_file():
            missing.append("seed 0")
        if right is None or not right.is_file():
            missing.append("seed 1")
        return "MISSING", "absent from " + " and ".join(missing)
    digest_left = normalised_sha256(left)
    digest_right = normalised_sha256(right)
    if digest_left == digest_right:
        return "STABLE", digest_left[:12]
    return "UNSTABLE", f"{digest_left[:12]} vs {digest_right[:12]}"


def compare_snapshots(seed0: Path, seed1: Path) -> list[tuple[str, str, str]]:
    """Classify every expected ``gen/`` file. Each row is name, status, detail."""
    rows: list[tuple[str, str, str]] = []
    for name in EXPECTED_GEN_FILES:
        status, detail = classify_pair(seed0 / name, seed1 / name)
        rows.append((name, status, detail))
    return rows


def _print_report(rows: list[tuple[str, str, str]], build_notes: list[str]) -> int:
    """Print the summary and return the process exit code."""
    for note in build_notes:
        print(note)
    print(f"{'File':<32} {'Status':<10} Detail")
    print("-" * 72)
    counts = {"STABLE": 0, "UNSTABLE": 0, "MISSING": 0}
    for name, status, detail in rows:
        counts[status] = counts.get(status, 0) + 1
        print(f"{name:<32} {status:<10} {detail}")
    print("-" * 72)
    print(
        f"Total: {counts['STABLE']} stable, "
        f"{counts['UNSTABLE']} unstable, {counts['MISSING']} missing"
    )
    return 0 if counts["UNSTABLE"] == 0 and counts["MISSING"] == 0 else 1


def build_both_seeds(perl_dir: Path, gen_dir: Path, work: Path) -> list[str]:
    """Run the pipeline twice and leave ``seed-0`` and ``seed-1`` under ``work``."""
    notes: list[str] = []
    backup = gen_dir.with_name(gen_dir.name + ".pre-intermediate-diff")
    had_gen = gen_dir.exists()
    if had_gen:
        if backup.exists():
            shutil.rmtree(backup)
        shutil.move(str(gen_dir), str(backup))
    try:
        for seed, label in (("0", "seed-0"), ("1", "seed-1")):
            reset_gen(gen_dir)
            code, tail = run_xlx(perl_dir, seed)
            snapshot_tree(gen_dir, work / label)
            notes.append(f"seed {seed}: make exited {code}")
            if code != 0 and tail:
                notes.append(f"  {tail.splitlines()[-1]}")
    finally:
        if gen_dir.exists():
            shutil.rmtree(gen_dir)
        if had_gen and backup.exists():
            shutil.move(str(backup), str(gen_dir))
    return notes


def main(argv: list[str] | None = None) -> int:
    """Entry point. See the module docstring for the CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perl-dir", type=Path, required=True)
    parser.add_argument(
        "--gen-dir",
        type=Path,
        default=None,
        help="Directory the makefile writes (default: PERL_DIR/gen).",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Compare existing seed-0/ and seed-1/ directories under --gen-dir.",
    )
    args = parser.parse_args(argv)

    perl_dir = args.perl_dir.absolute()
    gen_dir = (args.gen_dir or (perl_dir / "gen")).absolute()
    if not perl_dir.is_dir():
        print(f"error: --perl-dir {perl_dir} does not exist", file=sys.stderr)
        return 2

    notes: list[str] = []
    if args.skip_build:
        seed0 = gen_dir / "seed-0"
        seed1 = gen_dir / "seed-1"
        if not seed0.is_dir() or not seed1.is_dir():
            print(
                "error: --skip-build needs seed-0/ and seed-1/ under --gen-dir",
                file=sys.stderr,
            )
            return 2
    else:
        work = Path(tempfile.mkdtemp(prefix="emmorph-state-"))
        notes = build_both_seeds(perl_dir, gen_dir, work)
        seed0 = work / "seed-0"
        seed1 = work / "seed-1"

    rows = compare_snapshots(seed0, seed1)
    return _print_report(rows, notes)


if __name__ == "__main__":
    sys.exit(main())
