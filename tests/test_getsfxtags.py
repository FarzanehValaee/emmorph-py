"""tests/test_getsfxtags.py — unit tests for pyemmorph.getsfxtags."""

from __future__ import annotations

import re

import pytest

from pyemmorph.getsfxtags import (
    emit, parse_sfx_file, _escape_for_regex,
)


# ─── Sample sfx.1 fragments for testing ─────────────────────────────────────
# These are reduced versions of the real entries, just enough to exercise
# each branch of the parser.

SAMPLE_SFX_1 = """\
type:infl;tag:PL;humor:PL;phon:LVkL;mcat:PL;#gloss:#-s
type:infl;tag:ACC;humor:ACC;phon:LVt;mcat:CASE;#gloss:#,SYN
type:deriv;tag:DATE;humor:DATUM;phon:LVd%ik%A;mcat:Num>N;#gloss:#the ...th
type:deriv;tag:NAbeli;humor:BELI;phon:FbeliL;mcat:N>Adj;#gloss:#being situated at
type:deriv;tag:CMP;humor:FOK;phon:LA0bbL;mcat:>=Adj;#gloss:#-er (comparative)
type:deriv;tag:TEM;humor:TEM;phon:AnV;mcat:*>Adv;#gloss:#...ly
"""

SAMPLE_SFX_2_NO_MCAT = """\
tag:NOM;type:infl;humor:NOM;phon:n
tag:DAT;type:infl;humor:DAT;phon:nAk
"""


class TestParseSfxFile:
    def test_parses_simple_entries(self):
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_1.splitlines())
        # The script reads humor:NAME, not tag:NAME.
        assert "PL" in sfxtags       # humor:PL
        assert "ACC" in sfxtags       # humor:ACC
        assert "DATUM" in sfxtags     # humor:DATUM
        assert "BELI" in sfxtags      # humor:BELI
        assert "FOK" in sfxtags       # humor:FOK
        assert "TEM" in sfxtags       # humor:TEM

    def test_mcat_for_infl_no_arrow(self):
        """Entries with mcat:NAME (no '>') are inflectional — get 'I'."""
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_1.splitlines())
        # PL has mcat:PL, no '>' — inflectional.
        assert mcat["PL"] == "I"
        assert "PL" not in dercat
        # ACC has mcat:CASE, no '>' — inflectional.
        assert mcat["ACC"] == "I"

    def test_mcat_for_deriv_source_to_target(self):
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_1.splitlines())
        # DATUM: mcat:Num>N → no '=', cat2hum('N')='FN'
        # → dercat[DATUM]='FN', mcat[DATUM]='D=FN'
        assert dercat["DATUM"] == "FN"
        assert mcat["DATUM"] == "D=FN"
        # BELI: mcat:N>Adj → cat2hum('Adj')='MN'
        # → dercat[BELI]='MN', mcat[BELI]='D=MN'
        assert dercat["BELI"] == "MN"
        assert mcat["BELI"] == "D=MN"

    def test_mcat_for_comparative_with_equals(self):
        """B5 bug: mcat:>=Adj produces 'D==MN' (double =) due to regex
        capturing the '=' and the code prepending another 'D='."""
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_1.splitlines())
        # FOK: mcat:>=Adj → $1='=', $2='Adj' → cat2hum='MN'
        # → dercat[FOK]='=MN', mcat[FOK]='D==MN'  (B5 typo, preserved)
        assert dercat["FOK"] == "=MN"
        assert mcat["FOK"] == "D==MN"

    def test_mcat_for_star_target(self):
        """mcat:*>Adv is the same as mcat:>=Adv but with '*' (any source)."""
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_1.splitlines())
        # TEM: mcat:*>Adv → cat2hum('Adv')='HA' →
        # dercat[TEM]='HA', mcat[TEM]='D=HA'
        assert dercat["TEM"] == "HA"
        assert mcat["TEM"] == "D=HA"

    def test_entries_without_mcat_get_I(self):
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_2_NO_MCAT.splitlines())
        assert mcat["NOM"] == "I"
        assert mcat["DAT"] == "I"
        assert "NOM" not in dercat
        assert "DAT" not in dercat


class TestEmit:
    def test_emits_all_four_structures(self):
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_1.splitlines())
        out = emit(sfxtags, mcat, dercat)
        assert "$sfxtags=" in out
        assert "%mcat=(" in out
        assert "%dercat=(" in out
        assert "$dertags=" in out
        assert out.endswith("1;\n")

    def test_keys_emitted_in_sorted_order(self):
        """B4 regression test: keys must be emitted in sorted order."""
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_1.splitlines())
        out = emit(sfxtags, mcat, dercat)

        # Find the %mcat= line and parse its key order
        m = re.search(r"%mcat=\((.*)\);", out)
        assert m
        body = m.group(1)
        # Body looks like 'k1','v1','k2','v2',...
        parts = [p.strip().strip("'") for p in body.split(",") if p.strip()]
        keys = parts[::2]
        assert keys == sorted(keys), f"keys not sorted: {keys}"

    def test_sfxtags_regex_includes_all_tags(self):
        sfxtags, mcat, dercat = parse_sfx_file(SAMPLE_SFX_1.splitlines())
        out = emit(sfxtags, mcat, dercat)
        # All four humor tags (PL, ACC, FOK, TEM) should appear in $sfxtags.
        # The line looks like: $sfxtags='(?:ACC|FOK|PL|TEM)(?=$|[]+])';
        m = re.search(r"\$sfxtags='([^']*)'", out)
        assert m
        body = m.group(1)
        for tag in ("PL", "ACC", "FOK", "TEM"):
            assert tag in body, f"{tag} missing from $sfxtags"


class TestEscapeForRegex:
    def test_plain_text(self):
        assert _escape_for_regex("ABC") == "ABC"

    def test_dollar(self):
        assert _escape_for_regex("FOK") == "FOK"
        # Test a tag that contains regex metacharacters
        assert _escape_for_regex("HIN=ttOn") == "HIN=ttOn"
        # The = is not a regex metacharacter, so it should not be escaped

    def test_asterisk(self):
        # NIVALO* contains an asterisk
        assert _escape_for_regex("NIVALO*") == "NIVALO\\*"

    def test_backslash(self):
        assert _escape_for_regex("a\\b") == "a\\\\b"
