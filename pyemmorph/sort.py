"""pyemmorph.sort — Python port of pl/generic/sort.pl for src/rev.srt.

``sort.pl`` is a pattern-driven external sort: a script file sets ``$pat``,
each input line is reduced to a key, the keys are ordered by ``bsort.pl``,
and the original lines are emitted in that order. The harness runs it as::

    perl pl/generic/sort.pl -q src/rev.srt src/sfx.1

``src/rev.srt`` reverses the first semicolon-separated field and folds case.
This module implements that driver and that pattern. The byte offset of each
line is part of the key, matching ``printf "%s\\001%09d"`` in sort.pl, so
equal keys keep file order.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple


# Character class plus the three other alternatives in rev.srt's $pat.
_STRIP_RE = re.compile(r'[?!#=+%@&^(){}"]|[\[<].*?[\]>]|\.\.\.|_.*')
_FIELD_RE = re.compile(r"^\s*;?([^;]+)")
_TRAILING_BRACKET_RE = re.compile(r"(\[[^\]]*\])$")

_CASEFOLD_FROM = "ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÖÜŐŰ"
_CASEFOLD_TO = "abcdefghijklmnopqrstuvwxyzáéíóúöüőű"
_CASEFOLD = str.maketrans(_CASEFOLD_FROM, _CASEFOLD_TO)

_REV_MARKERS = ("$a=reverse($a)", "reverse($a)")


def _casefold_delete(text: str) -> str:
    """Perl ``tr/A-ZÁÉÍÓÚÖÜŐŰ.-/a-záéíóúöüőű/d``.

    The search list is longer than the replacement, and ``/d`` deletes the
    extras, which are ``.`` and the trailing ``-``.
    """
    folded = text.translate(_CASEFOLD)
    return folded.replace(".", "").replace("-", "")


def rev_sort_key(line: str) -> str:
    """Evaluate the ``$pat`` block from ``src/rev.srt`` on one chomped line."""
    field_match = _FIELD_RE.search(line)
    if field_match is None:
        field = ""
        bracket = ""
    else:
        field = field_match.group(1)
        bracket_match = _TRAILING_BRACKET_RE.search(field)
        bracket = bracket_match.group(1) if bracket_match else ""
    field = _STRIP_RE.sub("", field)
    reversed_field = field[::-1]
    folded = _casefold_delete(reversed_field)
    return f"{folded}\x04{reversed_field}\x04{bracket}"


def _iter_records(path: Path) -> List[Tuple[int, str]]:
    """Return ``(byte_offset, text_line)`` for each record.

    Offsets are positions in the raw file, including CR bytes. That is what
    Perl's ``tell`` recorded for ``src/sfx.1`` under the :crlf layer, and
    what ``sort.pl`` writes into the tempfile as ``%09d``.
    """
    data = path.read_bytes()
    records: List[Tuple[int, str]] = []
    position = 0
    while position < len(data):
        newline_at = data.find(b"\n", position)
        if newline_at == -1:
            raw = data[position:]
            next_position = len(data)
        else:
            raw = data[position:newline_at + 1]
            next_position = newline_at + 1
        text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        records.append((position, text))
        position = next_position
    return records


def _script_is_reverse_pattern(script: Path) -> bool:
    text = script.read_text(encoding="utf-8")
    return all(marker in text for marker in _REV_MARKERS[:1]) or "reverse($a)" in text


def sort_with_script(script: Path, infile: Path) -> List[str]:
    """Sort ``infile`` with the pattern in ``script`` and return the lines."""
    if not _script_is_reverse_pattern(script):
        raise ValueError(
            f"{script} is not the rev.srt reverse-field pattern; "
            "only that pattern is ported"
        )
    keyed: List[Tuple[str, str]] = []
    for offset, text in _iter_records(infile):
        body = text[:-1] if text.endswith("\n") else text
        key = rev_sort_key(body)
        if len(key) > 240:
            key = key[:240]
        keyed.append((f"{key}\x01{offset:09d}", text))
    keyed.sort(key=lambda item: item[0])
    return [text for _sortable, text in keyed]


def main(argv: Optional[List[str]] = None) -> int:
    """Usage: python -m pyemmorph.sort [-q] script infile"""
    if argv is None:
        argv = sys.argv[1:]

    positional: List[str] = []
    for arg in argv:
        if arg.startswith("-") and not arg.startswith("---"):
            # -q, -keeptmp, -v affect stderr progress only.
            continue
        positional.append(arg)

    if len(positional) < 2:
        print("usage: sort.py [options] script infile", file=sys.stderr)
        return 2

    script = Path(positional[0])
    infile = Path(positional[1])
    try:
        lines = sort_with_script(script, infile)
    except (OSError, ValueError) as exc:
        print(f"sort: {exc}", file=sys.stderr)
        return 1
    for line in lines:
        sys.stdout.write(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
