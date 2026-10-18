"""pyemmorph.lcase — Python port of pl/generic/lcase.pl.

Rewrites lexicon lines that mix upper- and lower-case in the surface form
into a pair of ``@P.LCA.+@`` / ``@P.LCA.-@`` variants, and splices LCA
markers into ``@D.A.+@`` / ``@P.[OD].+@`` annotations.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from typing import Iterable, List, Optional, TextIO


_NO_BRACKET_A = re.compile(r"(@D\.A\.\+@)")
_NO_BRACKET_P = re.compile(r"(@P\.[OD]\.\+@)")
_WITH_BRACKET_A = re.compile(r"(@D\.A\.\+@)")
_LEX_LINE = re.compile(r"^(.+?[^%]):(.+?)\t(.*)")


def _has_case_transition(text: str) -> bool:
    """True when ``text`` matches Perl ``/\\p{Lu}\\p{Ll}|\\p{Ll}\\p{Lu}/``."""
    categories = [unicodedata.category(ch) for ch in text]
    for left, right in zip(categories, categories[1:]):
        if (left, right) in {("Lu", "Ll"), ("Ll", "Lu")}:
            return True
    return False


def _split_terminator(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\n"
    return line, ""


def transform_line(line: str) -> List[str]:
    """Apply the lcase.pl body to one input record.

    Returns the output records, each already terminated the way Perl's
    ``print`` would terminate them.
    """
    body, terminator = _split_terminator(line)

    if "[" not in body:
        body = _NO_BRACKET_A.sub(r"\1@D.LCA.+@", body, count=1)
        body = _NO_BRACKET_P.sub(r"\1@D.LCA.-@@C.LCA@", body, count=1)
    else:
        body = _WITH_BRACKET_A.sub(
            r"\1 @D.LCA.+@ @D.LCA.-@ @P.LCA.+@ @P.LCA.-@ @C.LCA@",
            body,
            count=1,
        )

    match = _LEX_LINE.match(body)
    if match and _has_case_transition(match.group(2)):
        lex, surface, rest = match.group(1), match.group(2), match.group(3)
        lowered = surface.lower()
        return [
            f"@P.LCA.+@{lex}:@P.LCA.+@{lowered}\t{rest}\n",
            f"@P.LCA.-@{lex}:@P.LCA.-@{surface}\t{rest}\n",
        ]
    return [body + terminator]


def transform_lines(lines: Iterable[str]) -> List[str]:
    output: List[str] = []
    for line in lines:
        output.extend(transform_line(line))
    return output


def _read_inputs(paths: List[str], stdin: TextIO) -> List[str]:
    if not paths:
        return stdin.readlines()
    lines: List[str] = []
    for path in paths:
        with open(path, encoding="utf-8", newline="") as handle:
            lines.extend(handle.readlines())
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    """Usage: python -m pyemmorph.lcase [file ...]"""
    if argv is None:
        argv = sys.argv[1:]
    for line in transform_lines(_read_inputs(list(argv), sys.stdin)):
        sys.stdout.write(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
