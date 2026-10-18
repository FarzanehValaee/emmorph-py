"""pyemmorph.set — Python port of pl/generic/set.pl.

This is the first leaf module ported, per §8 of the audit report. It
provides the basic set-algebra primitives used throughout emMorph:
``union``, ``intersect``, ``issubset``, ``equal1``, ``equal2``.

The Perl original contains three bugs that this port fixes:

* B1 (Critical): ``set.pl:104`` — ``equal2()`` compares two hashes by joining
  their keys without ``sort``. Two semantically equal hashes may compare as
  unequal ~60% of the time on modern Perl (>=5.18) due to hash randomisation.
  This port uses ``sorted()`` for the comparison.

* B2 (Major): ``set.pl:78`` — ``intersect()`` uses ``each()`` which is
  stateful and returns elements in non-deterministic order. This port
  iterates ``sorted(d.items())`` for deterministic output.

* B6 (Major): the Perl original uses ``do 'foo.hpl'`` patterns that rely on
  ``.`` in ``@INC`` (removed in Perl 5.26). Not applicable here — the
  Python port uses ``__file__`` for path resolution.

The differential harness (``harness/manifest.yaml``) verifies that the
output of these functions matches the Perl original on a fixed input corpus.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import List, Optional


def union(a: Iterable[str], b: Iterable[str]) -> List[str]:
    """Return the union of two iterables as a sorted list.

    Perl original (``set.pl:62``):

        sub union {
            my ($a,$b)=@_;
            my (%a);
            @a{@$a}=();
            @a{@$b}=();
            return [keys(%a)];
        }

    Difference from Perl: returns a *sorted* list, not a hash-iteration-order
    list. Marked as INTENTIONAL_CHANGE in the manifest under
    ``hash_ordering_fixed``.
    """
    result: set[str] = set()
    result.update(a)
    result.update(b)
    return sorted(result)


def intersect(a: Iterable[str], b: Iterable[str]) -> List[str]:
    """Return the intersection of two iterables as a sorted list.

    Perl original (``set.pl:71``):

        sub intersect {
            my ($a,$b)=@_;
            my($x,$y);
            my (@c,%a);
            for(@$a){$a{$_}++};
            for(@$b){$a{$_}--};
            while(($x,$y)=each(%a)){push(@c,$x) if !$y}
            return \\@c;
        }

    Difference from Perl: the Perl version uses ``each()``, which is
    stateful and returns keys in non-deterministic order. This version
    iterates ``sorted()`` for deterministic output (fixes bug B2).
    """
    a_list = list(a)
    b_list = list(b)
    counts: dict[str, int] = {}
    for x in a_list:
        counts[x] = counts.get(x, 0) + 1
    for x in b_list:
        counts[x] = counts.get(x, 0) - 1
    # Items that appear the same number of times in both lists have count 0
    return sorted(k for k, v in counts.items() if v == 0)


def issubset(a: Iterable[str], b: Iterable[str]) -> bool:
    """Return True if every element of ``a`` is in ``b``.

    Perl original (``set.pl:82``):

        sub issubset {
            my ($a,$b)=@_;
            my ($res,%b);
            @b{@$b}=();
            $res=1;
            for(@$a){$res&&=exists($b{$_})};
            return $res;
        }
    """
    b_set: set[str] = set(b)
    return all(x in b_set for x in a)


def equal1(a: Iterable[str], b: Iterable[str]) -> bool:
    """Return True if the two iterables contain the same elements (order
    independent).

    Perl original (``set.pl:92``):

        sub equal1 {
            my ($a,$b)=@_;
            return join('\\xff',sort(@$a)) eq join('\\xff',sort(@$b));
        }

    This implementation is already correct in Perl — it uses ``sort`` — so the
    Python port mirrors it directly.
    """
    return sorted(a) == sorted(b)


def equal2(a: Iterable[str], b: Iterable[str]) -> bool:
    """Return True if the two iterables contain the same set of elements.

    Perl original (``set.pl:98``):

        sub equal2 {
            my ($a,$b)=@_;
            my (%a,%b);
            @a{@$a}=();
            @b{@$b}=();
            return join('\\xff',keys(%a)) eq join('\\xff',keys(%b));
        }

    The Perl version is buggy (B1): ``keys()`` returns hash iteration order,
    which is randomised since Perl 5.18, so two equal sets may compare as
    unequal. The Python port uses ``sorted()`` to make the comparison
    deterministic.
    """
    return set(a) == set(b)


# ─── CLI entry point ────────────────────────────────────────────────────────
# Invoked by the differential harness as ``python -m pyemmorph.set ...``.
# Currently the module has no CLI in the Perl original (it is a library),
# so the CLI just runs the self-test.

def _selftest() -> int:
    """Run a small self-test of the set primitives."""
    a = ["foo", "bar", "baz"]
    b = ["baz", "foo", "bar"]
    assert union(a, b) == ["bar", "baz", "foo"], "union failed"
    assert intersect(a, b) == ["bar", "baz", "foo"], "intersect failed"
    assert issubset(a, b), "issubset failed"
    assert issubset(b, a), "issubset (reversed) failed"
    assert equal1(a, b), "equal1 failed"
    assert equal2(a, b), "equal2 failed"

    # Edge cases
    assert union([], []) == []
    assert intersect([], []) == []
    assert issubset([], ["a"])  # empty set is subset of everything
    assert not issubset(["a"], [])
    assert equal1([], [])
    assert equal2([], [])

    print("OK: pyemmorph.set self-test passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
