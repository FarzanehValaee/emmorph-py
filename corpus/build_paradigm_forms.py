#!/usr/bin/env python3
"""Generate surface forms by running an emMorph FST in generator mode.

Every lemma in a Humor lexicon (``src/st5dbw2s.lx1`` by default in the
Perl tree) is paired with a small canonical tag set. Nouns receive case
and number tags, verbs receive infinitive and a present form, adjectives
receive positive and comparative tags. Each pair is given to
``hfst-lookup -g``. Successful generations are deduplicated and written
one surface form per line, sorted.

Usage:
    python corpus/build_paradigm_forms.py \\
        --fst emmorph-perl/hfst/hu.hfstol \\
        --lexicon emmorph-perl/src/st5dbw2s.lx1 \\
        --out corpus/generated/paradigm_forms.txt \\
        --limit 100
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# Tags named in the task, plus a few frequent nominal and verbal cells.
NOUN_TAGS: tuple[str, ...] = (
    "[/N][Nom]",
    "[/N][Acc]",
    "[/N][Dat]",
    "[/N][Pl][Nom]",
)
VERB_TAGS: tuple[str, ...] = (
    "[/V][Inf]",
    "[/V][Prs.NDef.3Sg]",
)
ADJ_TAGS: tuple[str, ...] = (
    "[/Adj][Nom]",
    "[/Adj][Comp]",
)

_CATEGORY_TAGS: dict[str, tuple[str, ...]] = {
    "FN": NOUN_TAGS,
    "IGE": VERB_TAGS,
    "MN": ADJ_TAGS,
}


def extract_lemma(line: str) -> tuple[str, str] | None:
    """Return ``(lemma, category)`` from one lexicon line, or ``None``.

    License banners and comments are skipped. A leading ``*`` on a real
    entry (``*a[DET]``) is stripped. Compounding ``+`` signs are removed
    so the generator sees a single stem.
    """
    text = line.strip()
    if not text or text.startswith("#") or set(text) <= {"*"}:
        return None
    if text.startswith("*"):
        # License prose starts with "*  ". Real entries look like "*a[DET]".
        if len(text) < 2 or not text[1].isalnum():
            return None
        text = text[1:]
    if "[" not in text:
        return None
    head, rest = text.split("[", 1)
    lemma = "".join(head.split()).replace("+", "")
    if not lemma:
        return None
    category = rest.split("]", 1)[0].split("|", 1)[0]
    return lemma, category


def iter_lemmas(path: Path, limit: int | None = None) -> list[tuple[str, str]]:
    """Read lemmas from a lexicon file, optionally stopping after ``limit``."""
    found: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        item = extract_lemma(line)
        if item is None:
            continue
        found.append(item)
        if limit is not None and len(found) >= limit:
            break
    return found


def generator_inputs(lemmas: list[tuple[str, str]]) -> list[str]:
    """Pair each lemma with the canonical tags for its category."""
    inputs: list[str] = []
    for lemma, category in lemmas:
        tags = _CATEGORY_TAGS.get(category, NOUN_TAGS)
        for tag in tags:
            inputs.append(f"{lemma}{tag}")
    return inputs


def generate_surfaces(fst: Path, inputs: list[str], hfst_lookup: str = "hfst-lookup") -> list[str]:
    """Run ``hfst-lookup -g`` and return sorted unique surface forms.

    Lines whose output ends in ``+?`` are generations the transducer
    rejected. They are not written.
    """
    if not inputs:
        return []
    result = subprocess.run(
        [hfst_lookup, "-g", str(fst)],
        input="\n".join(inputs) + "\n",
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"hfst-lookup exited {result.returncode}")
    surfaces: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        surface = parts[1].strip()
        if not surface or surface.endswith("+?"):
            continue
        surfaces.add(surface)
    return sorted(surfaces)


def main(argv: list[str] | None = None) -> int:
    """Entry point. See the module docstring for the CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fst", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of lemmas.")
    parser.add_argument("--hfst-lookup", default="hfst-lookup")
    args = parser.parse_args(argv)

    if not args.fst.is_file():
        print(f"error: fst not found: {args.fst}", file=sys.stderr)
        return 2
    if not args.lexicon.is_file():
        print(f"error: lexicon not found: {args.lexicon}", file=sys.stderr)
        return 2

    lemmas = iter_lemmas(args.lexicon, args.limit)
    inputs = generator_inputs(lemmas)
    try:
        surfaces = generate_surfaces(args.fst, inputs, args.hfst_lookup)
    except FileNotFoundError:
        print(f"error: {args.hfst_lookup} was not found on PATH", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"error: generator failed: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(surfaces) + ("\n" if surfaces else ""), encoding="utf-8")
    print(f"lemmas: {len(lemmas)}")
    print(f"generator inputs: {len(inputs)}")
    print(f"surface forms: {len(surfaces)}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
