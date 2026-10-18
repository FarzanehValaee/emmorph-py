#!/usr/bin/env python3
"""Extrinsic comparison of two emMorph transducers on one word list.

Layer 3 of the evaluation plan. Each word is analysed with FST A (the
Perl-compiled transducer) and FST B (the Python-port transducer). The
preferred backend is ``EmMorphPy`` from nytud/emmorphpy. If that package
cannot be imported, the script calls ``hfst-lookup`` directly.

A run exits 0 only when every word has the same analysis set on both
transducers and neither side reports an error.

Usage:
    python harness/extrinsic_eval.py \\
        --corpus corpus/generated/fuzzed_forms.txt \\
        --fst-a emmorph-perl/hfst/hu.hfstol \\
        --fst-b emmorph-perl/hfst/hu.hfstol \\
        --emmorphpy-dir ../emmorphpy
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, Sequence


Analysis = tuple[str, ...]
Analyzer = Callable[[str], Analysis]


def load_corpus(path: Path) -> list[str]:
    """Read one word per line. Blank lines and ``#`` comments are ignored."""
    words: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line)
    return words


def compare_pair(left: Analysis, right: Analysis) -> str:
    """Return ``match`` or ``mismatch`` for two analysis tuples."""
    return "match" if tuple(left) == tuple(right) else "mismatch"


def _import_emmorphpy(emmorphpy_dir: Path | None) -> type | None:
    """Import ``EmMorphPy``, optionally from a checkout that is not installed."""
    if emmorphpy_dir is not None:
        sys.path.insert(0, str(emmorphpy_dir))
    try:
        from emmorphpy import EmMorphPy
    except ImportError:
        return None
    return EmMorphPy


def emmorphpy_analyzer(emmorph_cls: type, fst: Path) -> Analyzer:
    """Build an analyzer that returns ``EmMorphPy.analyze`` results as a tuple."""
    engine = emmorph_cls(fsa=str(fst), task="analyze")

    def analyze(word: str) -> Analysis:
        result = engine.analyze(word)
        return tuple(sorted(str(item) for item in result))

    return analyze


def hfst_lookup_analyzer(fst: Path, hfst_lookup: str = "hfst-lookup") -> Analyzer:
    """Analyse one word per ``hfst-lookup`` invocation.

    ``hfst-lookup`` prints ``input\\toutput\\tweight`` and a blank line after
    each cohort. Outputs ending in ``+?`` are unknown-word markers and are
    dropped, matching an empty analysis.
    """

    def analyze(word: str) -> Analysis:
        result = subprocess.run(
            [hfst_lookup, str(fst)],
            input=word + "\n",
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"hfst-lookup exited {result.returncode}")
        analyses: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            output = parts[1]
            if output.endswith("+?"):
                continue
            analyses.append(output)
        return tuple(sorted(set(analyses)))

    return analyze


def open_analyzer(
    fst: Path,
    emmorph_cls: type | None,
    hfst_lookup: str,
) -> tuple[Analyzer, str]:
    """Prefer emmorphpy. Fall back to ``hfst-lookup`` if the import failed."""
    if emmorph_cls is not None:
        return emmorphpy_analyzer(emmorph_cls, fst), "emmorphpy"
    return hfst_lookup_analyzer(fst, hfst_lookup), "hfst-lookup"


def evaluate(
    words: Iterable[str],
    analyze_a: Analyzer,
    analyze_b: Analyzer,
) -> tuple[int, int, int, list[str]]:
    """Return ``(matches, mismatches, errors, sample lines)``."""
    matches = mismatches = errors = 0
    samples: list[str] = []
    for word in words:
        try:
            left = analyze_a(word)
            right = analyze_b(word)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            errors += 1
            if len(samples) < 20:
                samples.append(f"ERROR {word}: {exc}")
            continue
        kind = compare_pair(left, right)
        if kind == "match":
            matches += 1
        else:
            mismatches += 1
            if len(samples) < 20:
                samples.append(f"MISMATCH {word}: {left} != {right}")
    return matches, mismatches, errors, samples


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. See the module docstring for the CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--fst-a", type=Path, required=True)
    parser.add_argument("--fst-b", type=Path, required=True)
    parser.add_argument("--emmorphpy-dir", type=Path, default=None)
    parser.add_argument("--hfst-lookup", default="hfst-lookup")
    args = parser.parse_args(argv)

    if not args.corpus.is_file():
        print(f"error: corpus not found: {args.corpus}", file=sys.stderr)
        return 2
    for label, path in (("fst-a", args.fst_a), ("fst-b", args.fst_b)):
        if not path.is_file():
            print(f"error: {label} not found: {path}", file=sys.stderr)
            return 2

    words = load_corpus(args.corpus)
    emmorph_cls = _import_emmorphpy(args.emmorphpy_dir)
    try:
        analyze_a, backend = open_analyzer(args.fst_a, emmorph_cls, args.hfst_lookup)
        analyze_b, _backend_b = open_analyzer(args.fst_b, emmorph_cls, args.hfst_lookup)
    except (OSError, RuntimeError) as exc:
        print(f"error: could not open an analyzer: {exc}", file=sys.stderr)
        return 2

    print(f"backend: {backend}")
    print(f"words: {len(words)}")
    matches, mismatches, errors, samples = evaluate(words, analyze_a, analyze_b)
    print(f"matches: {matches}")
    print(f"mismatches: {mismatches}")
    print(f"errors: {errors}")
    for line in samples:
        print(line)
    return 0 if mismatches == 0 and errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
