#!/usr/bin/env python3
"""Generate reproducible Hungarian-like word forms.

Stems are built from legal onsets, a vowel nucleus, and an optional coda.
Vowel harmony then picks the suffix chain: a stem with a back vowel takes
back suffixes (``-ban``, ``-nak``, ``-hoz``), a stem with a front rounded
vowel takes front rounded suffixes (``-ben``, ``-nek``, ``-höz``), and any
other stem takes front unrounded suffixes. ``i`` and ``í`` are transparent,
as in the real harmony system.

``--seed`` fixes the random stream, so the same flags always rewrite
``corpus/generated/fuzzed_forms.txt`` byte for byte.

Usage:
    python corpus/fuzz_corpus.py -n 20 --seed 42 -o corpus/generated/fuzzed_forms.txt
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path


# Word-initial onsets that occur in Hungarian, including the empty onset.
ONSETS: tuple[str, ...] = (
    "", "b", "c", "cs", "d", "f", "g", "gy", "h", "j", "k", "l", "ly",
    "m", "n", "ny", "p", "r", "s", "sz", "t", "ty", "v", "z", "zs",
    "st", "sk", "sp", "sz", "tr", "kr", "gr", "pr", "fr",
)
CODAS: tuple[str, ...] = (
    "", "k", "t", "n", "m", "l", "r", "s", "sz", "gy", "ny", "cs",
    "nt", "lt", "rt", "nk", "sk",
)
BACK_VOWELS: tuple[str, ...] = ("a", "á", "o", "ó", "u", "ú")
FRONT_UNROUNDED: tuple[str, ...] = ("e", "é", "i", "í")
FRONT_ROUNDED: tuple[str, ...] = ("ö", "ő", "ü", "ű")
# (back, front-unrounded, front-rounded). The vowel of the suffix agrees
# with the stem. Linking vowels are already baked into each allomorph.
SUFFIXES: tuple[tuple[str, str, str], ...] = (
    ("ban", "ben", "ben"),
    ("nak", "nek", "nek"),
    ("hoz", "hez", "höz"),
    ("tól", "től", "től"),
    ("ok", "ek", "ök"),
    ("on", "en", "ön"),
    ("val", "vel", "vel"),
    ("ra", "re", "re"),
)


def harmony_of(stem: str) -> str:
    """Return ``back``, ``front-rounded``, or ``front`` for a stem.

    Front rounded vowels dominate. A back vowel wins over transparent
    ``i``/``í``. A stem with only transparent vowels is treated as front
    unrounded.
    """
    vowels = [ch for ch in stem if ch in set(BACK_VOWELS + FRONT_UNROUNDED + FRONT_ROUNDED)]
    if any(ch in FRONT_ROUNDED for ch in vowels):
        return "front-rounded"
    if any(ch in BACK_VOWELS for ch in vowels):
        return "back"
    return "front"


def _suffix_for(harmony: str, triple: tuple[str, str, str]) -> str:
    """Pick the allomorph that matches ``harmony``."""
    back, front, rounded = triple
    if harmony == "back":
        return back
    if harmony == "front-rounded":
        return rounded
    return front


def _syllable(rng: random.Random, harmony: str) -> str:
    """One onset + nucleus + coda, with the nucleus in the stem's class."""
    if harmony == "back":
        nucleus = rng.choice(BACK_VOWELS)
    elif harmony == "front-rounded":
        nucleus = rng.choice(FRONT_ROUNDED)
    else:
        nucleus = rng.choice(FRONT_UNROUNDED)
    return rng.choice(ONSETS) + nucleus + rng.choice(CODAS)


def _stem(rng: random.Random, min_len: int, max_len: int) -> str:
    """Build a stem whose length is between ``min_len`` and ``max_len``."""
    harmony = rng.choice(("back", "front", "front-rounded"))
    parts: list[str] = []
    while True:
        piece = _syllable(rng, harmony)
        if parts and len("".join(parts)) + len(piece) > max_len:
            break
        parts.append(piece)
        if len("".join(parts)) >= min_len and rng.random() < 0.45:
            break
        if len(parts) >= 4:
            break
    stem = "".join(parts)
    if len(stem) > max_len:
        stem = stem[:max_len]
    if len(stem) < min_len:
        stem = stem + _syllable(rng, harmony)
        stem = stem[:max_len]
    return stem


def generate_forms(
    n: int,
    seed: int,
    min_stem_len: int = 3,
    max_stem_len: int = 8,
    max_suffix_depth: int = 2,
) -> list[str]:
    """Return ``n`` unique forms, sorted, for a fixed ``seed``.

    Raises ``ValueError`` if the length bounds cannot produce a stem.
    """
    if n < 0:
        raise ValueError("n must be >= 0")
    if min_stem_len < 1 or max_stem_len < min_stem_len:
        raise ValueError("stem length bounds are inconsistent")
    rng = random.Random(seed)
    found: set[str] = set()
    guard = 0
    limit = max(1000, n * 50)
    while len(found) < n and guard < limit:
        guard += 1
        stem = _stem(rng, min_stem_len, max_stem_len)
        if not stem or not any(ch.isalpha() for ch in stem):
            continue
        harmony = harmony_of(stem)
        form = stem
        depth = rng.randint(0, max_suffix_depth)
        pool = list(SUFFIXES)
        rng.shuffle(pool)
        for triple in pool[:depth]:
            form += _suffix_for(harmony, triple)
        found.add(form)
    if len(found) < n:
        raise RuntimeError(f"only produced {len(found)} unique forms, wanted {n}")
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    """Entry point. See the module docstring for the CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", type=int, default=1000, help="Number of forms.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-stem-len", type=int, default=3)
    parser.add_argument("--max-stem-len", type=int, default=8)
    parser.add_argument("--max-suffix-depth", type=int, default=2)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("corpus/generated/fuzzed_forms.txt"),
    )
    args = parser.parse_args(argv)
    forms = generate_forms(
        args.n,
        args.seed,
        min_stem_len=args.min_stem_len,
        max_stem_len=args.max_stem_len,
        max_suffix_depth=args.max_suffix_depth,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(forms) + ("\n" if forms else ""), encoding="utf-8")
    print(f"wrote {len(forms)} forms to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
