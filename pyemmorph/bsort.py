"""pyemmorph.bsort — Python port of pl/generic/bsort.pl.

Reads every line from the named files (or stdin), sorts them with Perl's
``cmp`` order (Unicode code points), and writes them to stdout. ``-u`` drops
adjacent duplicates after the sort, matching ``$uniq`` in the Perl script.
"""

from __future__ import annotations

import sys
from typing import Iterable, List, Optional, TextIO


def sort_lines(lines: Iterable[str], uniq: bool = False) -> List[str]:
    """Return ``lines`` sorted by code point.

    Each item must include its own trailing newline if the caller wants one
    in the output, the same way Perl's ``<>`` yields records. When ``uniq``
    is set, adjacent equal lines are collapsed after sorting.
    """
    ordered = sorted(lines)
    if not uniq:
        return ordered
    deduped: List[str] = []
    previous: Optional[str] = None
    for line in ordered:
        if line == previous:
            continue
        deduped.append(line)
        previous = line
    return deduped


def _read_inputs(paths: List[str], stdin: TextIO) -> List[str]:
    if not paths:
        return stdin.readlines()
    lines: List[str] = []
    for path in paths:
        with open(path, encoding="utf-8", newline="") as handle:
            # newline="" keeps the raw terminator; Perl's :crlf layer
            # already turned CRLF into ``\n`` before ``cmp``.
            lines.extend(line.replace("\r\n", "\n").replace("\r", "\n") for line in handle)
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    """Usage: python -m pyemmorph.bsort [-u] [file ...]"""
    if argv is None:
        argv = sys.argv[1:]

    uniq = False
    paths: List[str] = []
    for arg in argv:
        if arg == "-u":
            uniq = True
        elif arg.startswith("-") and arg != "-":
            print(f"bsort: unknown option {arg}", file=sys.stderr)
            return 2
        else:
            paths.append(arg)

    for line in sort_lines(_read_inputs(paths, sys.stdin), uniq=uniq):
        sys.stdout.write(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
