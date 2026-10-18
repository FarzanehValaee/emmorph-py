"""tests/test_set.py — unit tests for pyemmorph.set.

These are property-based tests of the set algebra primitives, independent
of the Perl original. The differential harness (test_differential.py)
covers the cross-implementation comparison.
"""

import random

import pytest

from pyemmorph.set import (
    equal1, equal2, intersect, issubset, union,
)


class TestUnion:
    def test_two_lists(self):
        assert union(["a", "b"], ["b", "c"]) == ["a", "b", "c"]

    def test_disjoint(self):
        assert union(["a"], ["b"]) == ["a", "b"]

    def test_identical(self):
        assert union(["a", "b"], ["a", "b"]) == ["a", "b"]

    def test_empty(self):
        assert union([], []) == []

    def test_one_empty(self):
        assert union(["a"], []) == ["a"]

    def test_returns_sorted(self):
        # B1/B4 fix: union must return sorted output
        assert union(["c", "a", "b"], ["d"]) == ["a", "b", "c", "d"]


class TestIntersect:
    def test_two_lists(self):
        assert intersect(["a", "b", "c"], ["b", "c", "d"]) == ["b", "c"]

    def test_disjoint(self):
        assert intersect(["a"], ["b"]) == []

    def test_identical(self):
        assert intersect(["a", "b"], ["a", "b"]) == ["a", "b"]

    def test_empty(self):
        assert intersect([], []) == []

    def test_returns_sorted(self):
        # B2 fix: intersect must return sorted output
        assert intersect(["c", "a"], ["a", "b", "c"]) == ["a", "c"]


class TestIssubset:
    def test_true(self):
        assert issubset(["a", "b"], ["a", "b", "c"]) is True

    def test_false(self):
        assert issubset(["a", "d"], ["a", "b", "c"]) is False

    def test_empty_is_subset_of_anything(self):
        assert issubset([], ["a", "b"]) is True

    def test_empty_is_subset_of_empty(self):
        assert issubset([], []) is True

    def test_nonempty_not_subset_of_empty(self):
        assert issubset(["a"], []) is False


class TestEqual1:
    def test_equal_unordered(self):
        assert equal1(["a", "b", "c"], ["c", "b", "a"]) is True

    def test_not_equal(self):
        assert equal1(["a", "b"], ["a", "c"]) is False

    def test_empty(self):
        assert equal1([], []) is True

    def test_one_empty(self):
        assert equal1(["a"], []) is False


class TestEqual2:
    """B1 regression tests: equal2 must be deterministic."""

    def test_equal_unordered(self):
        assert equal2(["a", "b", "c"], ["c", "b", "a"]) is True

    def test_not_equal(self):
        assert equal2(["a", "b"], ["a", "c"]) is False

    def test_empty(self):
        assert equal2([], []) is True

    def test_one_empty(self):
        assert equal2(["a"], []) is False

    @pytest.mark.parametrize("seed", range(20))
    def test_deterministic_under_permutation(self, seed):
        """Run equal2 20 times with different input permutations.
        All runs must return True. This is the regression test for B1.
        """
        rng = random.Random(seed)
        a = list("abcdefghijklmnopqrstuvwxyz")
        b = a.copy()
        rng.shuffle(b)
        assert equal2(a, b) is True, "equal2 returned False for equal sets (B1 regression)"


class TestSetAlgebraLaws:
    """Mathematical laws that the set primitives must satisfy."""

    @pytest.mark.parametrize("seed", range(10))
    def test_union_commutative(self, seed):
        rng = random.Random(seed)
        a = [chr(rng.randint(97, 122)) for _ in range(rng.randint(0, 10))]
        b = [chr(rng.randint(97, 122)) for _ in range(rng.randint(0, 10))]
        assert union(a, b) == union(b, a)

    @pytest.mark.parametrize("seed", range(10))
    def test_intersect_commutative(self, seed):
        rng = random.Random(seed)
        a = [chr(rng.randint(97, 122)) for _ in range(rng.randint(0, 10))]
        b = [chr(rng.randint(97, 122)) for _ in range(rng.randint(0, 10))]
        assert intersect(a, b) == intersect(b, a)

    @pytest.mark.parametrize("seed", range(10))
    def test_union_contains_both(self, seed):
        rng = random.Random(seed)
        a = [chr(rng.randint(97, 122)) for _ in range(rng.randint(0, 10))]
        b = [chr(rng.randint(97, 122)) for _ in range(rng.randint(0, 10))]
        u = union(a, b)
        assert issubset(a, u)
        assert issubset(b, u)

    @pytest.mark.parametrize("seed", range(10))
    def test_intersect_subset_of_both(self, seed):
        rng = random.Random(seed)
        a = [chr(rng.randint(97, 122)) for _ in range(rng.randint(0, 10))]
        b = [chr(rng.randint(97, 122)) for _ in range(rng.randint(0, 10))]
        i = intersect(a, b)
        assert issubset(i, a)
        assert issubset(i, b)
