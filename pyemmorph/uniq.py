"""pyemmorph.uniq — Python port of pl/mkavs/uniq.pl.

Filters adjacent duplicate lines. This is not a sort: a line is printed
unless it is equal to the immediately previous line. The first line is
always kept.
"""

from __future__ import annotations

import sys
from typing import Iterable, List, Optional, TextIO


def uniq_lines(lines: Iterable[str]) -> List[str]:
    """Drop lines that repeat the previous line. Order is otherwise kept."""
    kept: List[str] = []
    previous: Optional[str] = None
    for line in lines:
        if line != previous:
            kept.append(line)
        previous = line
    return kept


def _read_inputs(paths: List[str], stdin: TextIO) -> List[str]:
    if not paths:
        return stdin.readlines()
    lines: List[str] = []
    for path in paths:
        with open(path, encoding="utf-8", newline="") as handle:
            lines.extend(line.replace("\r\n", "\n").replace("\r", "\n") for line in handle)
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    """Usage: python -m pyemmorph.uniq [file ...]

    With no files, read stdin, as Perl's ``<>`` does.
    """
    if argv is None:
        argv = sys.argv[1:]
    for line in uniq_lines(_read_inputs(list(argv), sys.stdin)):
        sys.stdout.write(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
