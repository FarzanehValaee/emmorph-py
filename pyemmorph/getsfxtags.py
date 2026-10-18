"""pyemmorph.getsfxtags — Python port of pl/mkavs/getsfxtags.pl.

Reads the suffix specification file (src/sfx.1) and emits three Perl data
structures used by the encoder:
    $sfxtags  — regex alternation of all suffix tags
    %mcat     — mapping from suffix tag to morphological category (D=...)
    %dercat   — mapping from derivational suffix tag to its target category
    $dertags  — regex alternation of all derivational suffix tags

Bug fixes relative to the Perl original:

* B4 (Major): the Perl original emits %mcat and %dercat in hash iteration
  order, which is randomised. This port emits them in sorted key order.

* B5 (Minor): the Perl original produces 'D==MN' for the FOK (comparative)
  entry because the regex captures the '=' from 'mcat:>=Adj' and prepends
  another 'D='. This port has the same behaviour for now (pending Prof.
  Indig's decision on whether the data or the script is wrong); the fix
  will land in a follow-up commit.

* B6 (Major): the Perl original uses ``do 'sfxtags0.hpl'`` which fails on
  Perl 5.26+ because '.' was removed from @INC. Not applicable here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


# Stem-tag regex — matches the major lexical categories (Noun, Adj, Num, V, Adv)
# Perl: '\||(?:^|\+)(?:FN|MN|SZN|IGE|HA|NU)(?=$|[+|])'
STEM_TAGS_RE = re.compile(r"\||(?:^|\+)(?:FN|MN|SZN|IGE|HA|NU)(?=$|[+|])")

# Tag-name pattern: in vhrm.pl it is 'humor'; here we use 'humor' by default
# but allow it to be overridden.
TAGNAME = "humor"

# cat2hum mapping from vhrm.pl line 409:
#   %cat2hum=(qw/N FN Adj MN Num SZN V IGE Adv HA Vpfx IK Sup FF Part MN/,'X','');
# This maps the abstract grammatical categories used in the source data
# (N, Adj, Num, V, Adv, etc.) to the Humor-internal suffix codes (FN, MN,
# SZN, IGE, HA, etc.). The getsfxtags.pl script defines `sub cat2hum{$_[0]}`
# locally but then `require 'vhrm.pl'` overrides it with this mapping.
CAT2HUM: dict[str, str] = {
    "N":     "FN",
    "Adj":   "MN",
    "Num":   "SZN",
    "V":     "IGE",
    "Adv":   "HA",
    "Vpfx":  "IK",
    "Sup":   "FF",
    "Part":  "MN",
    "X":     "",
}


def cat2hum(cat: str) -> str:
    """Translate an abstract grammatical category to its Humor code.

    Mirrors vhrm.pl:411-414. Raises KeyError if the category is unknown,
    matching the Perl `die1` behaviour.
    """
    if cat not in CAT2HUM:
        raise KeyError(f"cat2hum not defined for {cat!r}")
    return CAT2HUM[cat]


def parse_sfx_file(lines: list[str]) -> tuple[set[str], dict[str, str], dict[str, str]]:
    """Parse the suffix specification file and return:
        (set_of_all_suffix_tags, mcat_dict, dercat_dict)

    Mirrors the Perl main loop (getsfxtags.pl:72-88).
    """
    sfxtags: set[str] = set()
    mcat: dict[str, str] = {}
    dercat: dict[str, str] = {}

    tag_pattern = re.compile(rf"{TAGNAME}:([^;]+)")

    for raw_line in lines:
        m = tag_pattern.search(raw_line)
        if not m:
            continue
        tag = m.group(1)
        line = raw_line  # Perl uses $a = $_, then matches against $a

        for piece in tag.split("+"):
            # Skip stem tags
            if STEM_TAGS_RE.search(piece):
                continue
            if not piece:
                continue
            sfxtags.add(piece)
            if piece in mcat:
                continue
            # Try to match mcat:...>... in the line
            mcat_match = re.search(
                r"mcat:[^;>]*>(=?)([^;]+)",
                line,
            )
            if not mcat_match:
                mcat[piece] = "I"
                continue
            equals_prefix = mcat_match.group(1)
            category = cat2hum(mcat_match.group(2))
            dercat[piece] = f"{equals_prefix}{category}"
            mcat[piece] = f"D={dercat[piece]}"

    return sfxtags, mcat, dercat


def emit(sfxtags: set[str], mcat: dict[str, str], dercat: dict[str, str]) -> str:
    """Emit the four data structures as Perl source, matching the Perl
    original's output format exactly (line 89-93).

    The only intentional difference from the Perl original is that all
    keys are emitted in sorted order (fixes B4).
    """
    out_lines: list[str] = []

    # $sfxtags='(?:tag1|tag2|...)(?=$|[]+])';
    # Perl joins the raw tag names here (no quotemeta). Only $dertags is escaped.
    sorted_tags = sorted(sfxtags)
    sfxtags_regex = "|".join(sorted_tags)
    out_lines.append(
        f"$sfxtags='(?:{sfxtags_regex})(?=$|[]+])';"
    )

    # %mcat=('k1','v1','k2','v2',...);
    # Emit in sorted key order — fixes B4.
    mcat_pairs = ",".join(
        f"'{k}','{mcat[k]}'" for k in sorted(mcat.keys())
    )
    out_lines.append(f"%mcat=({mcat_pairs});")

    # %dercat=('k1','v1','k2','v2',...);
    dercat_pairs = ",".join(
        f"'{k}','{dercat[k]}'" for k in sorted(dercat.keys())
    )
    out_lines.append(f"%dercat=({dercat_pairs});")

    # $dertags='(?:tag1|tag2|...)(?=$|[]+])';
    # Perl: map(quotemeta, sort keys %dercat). quotemeta backslashes every
    # character outside [A-Za-z0-9_], including '='.
    sorted_dertags = sorted(dercat.keys())
    dertags_regex = "|".join(_perl_quotemeta(t) for t in sorted_dertags)
    out_lines.append(
        f"$dertags='(?:{dertags_regex})(?=$|[]+])';"
    )

    out_lines.append("1;")
    return "\n".join(out_lines) + "\n"


def _perl_quotemeta(s: str) -> str:
    """Mirror Perl ``quotemeta``: backslash every non-word byte.

    Perl treats ``[A-Za-z0-9_]`` as word characters here, so ``=`` and ``*``
    are escaped. Used for ``$dertags`` only; ``$sfxtags`` is joined raw.
    """
    return re.sub(r"([^A-Za-z0-9_])", r"\\\1", s)


def _escape_for_regex(s: str) -> str:
    """Escape regex metacharacters. ``=`` is left alone; ``*`` is escaped."""
    return re.sub(r"([\\^$.|?*+()\[\]{}])", r"\\\1", s)


# ─── CLI entry point ────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """Read sfx.1 from the file(s) given on the command line and emit the
    Perl data structures to stdout.

    Usage:
        python -m pyemmorph.getsfxtags src/sfx.1
    """
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print("usage: getsfxtags.py <sfx.1> [<sfx.1> ...]", file=sys.stderr)
        return 2

    all_lines: list[str] = []
    for path in argv:
        text = Path(path).read_text(encoding="utf-8")
        all_lines.extend(text.splitlines())

    sfxtags, mcat, dercat = parse_sfx_file(all_lines)
    sys.stdout.write(emit(sfxtags, mcat, dercat))
    return 0


if __name__ == "__main__":
    sys.exit(main())
