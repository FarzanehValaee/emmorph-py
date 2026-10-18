"""Tests for the layer-2 hash check, layer-3 comparison, and the fuzzer."""

from __future__ import annotations

import tempfile
from pathlib import Path

from corpus.build_paradigm_forms import extract_lemma, generator_inputs
from corpus.fuzz_corpus import generate_forms, harmony_of
from harness.extrinsic_eval import compare_pair, load_corpus
from harness.intermediate_state_diff import classify_pair, normalised_sha256
from harness.normalize import normalize_line


class TestIntermediateState:
    def test_hash_line_order_does_not_change_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            self._hash_line_order(Path(directory))

    def _hash_line_order(self, tmp_path: Path):
        left = tmp_path / "a.hpl"
        right = tmp_path / "b.hpl"
        left.write_text("%mcat=('b','2','a','1');\n", encoding="utf-8")
        right.write_text("%mcat=('a','1','b','2');\n", encoding="utf-8")
        assert normalised_sha256(left) == normalised_sha256(right)
        assert normalize_line("%mcat=('b','2','a','1');").startswith("%mcat=('a','1'")

    def test_missing_and_unstable(self):
        with tempfile.TemporaryDirectory() as directory:
            self._missing_and_unstable(Path(directory))

    def _missing_and_unstable(self, tmp_path: Path):
        present = tmp_path / "one"
        present.write_text("alma\n", encoding="utf-8")
        other = tmp_path / "two"
        other.write_text("korte\n", encoding="utf-8")
        assert classify_pair(present, other)[0] == "UNSTABLE"
        assert classify_pair(present, present)[0] == "STABLE"
        assert classify_pair(present, tmp_path / "absent")[0] == "MISSING"


class TestExtrinsic:
    def test_compare_pair(self):
        assert compare_pair(("a", "b"), ("a", "b")) == "match"
        assert compare_pair(("a",), ("b",)) == "mismatch"

    def test_load_corpus_skips_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "words.txt"
            path.write_text("# comment\n\nalma\nkorte\n", encoding="utf-8")
            assert load_corpus(path) == ["alma", "korte"]


class TestParadigmLemmas:
    def test_extracts_stem_and_category(self):
        assert extract_lemma("Aba[FN];isa:település;") == ("Aba", "FN")
        assert extract_lemma("  próba+baba[FN];") == ("próbababa", "FN")
        assert extract_lemma("*a[DET];") == ("a", "DET")
        assert extract_lemma("**** START OF LICENSE ****") is None

    def test_noun_gets_nominative_and_accusative(self):
        inputs = generator_inputs([("alma", "FN")])
        assert "alma[/N][Nom]" in inputs
        assert "alma[/N][Acc]" in inputs

    def test_verb_gets_infinitive(self):
        inputs = generator_inputs([("ír", "IGE")])
        assert "ír[/V][Inf]" in inputs


class TestFuzz:
    def test_seed_is_reproducible_and_sized(self):
        first = generate_forms(20, seed=42)
        second = generate_forms(20, seed=42)
        assert first == second
        assert len(first) == 20
        assert first == sorted(first)

    def test_harmony_picks_back_suffix_for_back_stem(self):
        assert harmony_of("alma") == "back"
        assert harmony_of("könyv") == "front-rounded"
        assert harmony_of("szék") == "front"
        forms = generate_forms(20, seed=42, max_suffix_depth=1, min_stem_len=4, max_stem_len=6)
        assert all(form.isalpha() or any(ch in form for ch in "aáeéoóöőuúüűií") for form in forms)
