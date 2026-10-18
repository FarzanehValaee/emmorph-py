"""Unit tests for the bsort, lcase, sort, and uniq ports."""

from __future__ import annotations

from pyemmorph.bsort import sort_lines
from pyemmorph.lcase import transform_line
from pyemmorph.sort import rev_sort_key
from pyemmorph.uniq import uniq_lines


class TestUniq:
    def test_drops_only_adjacent_duplicates(self):
        lines = ["alma\n", "korte\n", "alma\n", "szilva\n", "korte\n", "korte\n", "alma\n"]
        assert uniq_lines(lines) == [
            "alma\n",
            "korte\n",
            "alma\n",
            "szilva\n",
            "korte\n",
            "alma\n",
        ]

    def test_empty(self):
        assert uniq_lines([]) == []

    def test_keeps_first_line(self):
        assert uniq_lines(["a\n"]) == ["a\n"]


class TestBsort:
    def test_sorts_by_code_point(self):
        assert sort_lines(["c\n", "a\n", "b\n"]) == ["a\n", "b\n", "c\n"]

    def test_uniq_after_sort(self):
        assert sort_lines(["b\n", "a\n", "b\n", "a\n"], uniq=True) == ["a\n", "b\n"]

    def test_hungarian_codepoints(self):
        # Á (U+00C1) sorts after Z, matching Perl cmp on Unicode strings.
        assert sort_lines(["Á\n", "Z\n", "A\n"]) == ["A\n", "Z\n", "Á\n"]


class TestLcase:
    def test_pass_through_when_no_mixed_case(self):
        assert transform_line("type:infl;tag:PL\n") == ["type:infl;tag:PL\n"]

    def test_splits_mixed_case_surface(self):
        line = "stem:Abba\trest\n"
        assert transform_line(line) == [
            "@P.LCA.+@stem:@P.LCA.+@abba\trest\n",
            "@P.LCA.-@stem:@P.LCA.-@Abba\trest\n",
        ]

    def test_splices_marker_without_bracket(self):
        line = "keep @D.A.+@ tail\n"
        assert transform_line(line) == ["keep @D.A.+@@D.LCA.+@ tail\n"]

    def test_splices_marker_with_bracket(self):
        line = "keep @D.A.+@ [x] tail\n"
        assert transform_line(line) == [
            "keep @D.A.+@ @D.LCA.+@ @D.LCA.-@ @P.LCA.+@ @P.LCA.-@ @C.LCA@ [x] tail\n"
        ]


class TestRevSortKey:
    def test_reverses_and_strips_hash(self):
        assert rev_sort_key("#name of property") == (
            "ytreporp fo eman\x04ytreporp fo eman\x04"
        )

    def test_deletes_dot_and_hyphen_only_from_folded_copy(self):
        key = rev_sort_key("A-B")
        folded, reversed_field, bracket = key.split("\x04")
        assert reversed_field == "B-A"
        assert folded == "ba"
        assert bracket == ""
