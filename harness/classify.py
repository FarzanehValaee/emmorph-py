"""classify.py — diff classifier for the differential harness.

Takes the normalised outputs of the Perl and Python implementations, computes
the unified diff, and classifies every diff hunk into one of four buckets:
OLD_BUG, NEW_BUG, INTENTIONAL_CHANGE, UNCLASSIFIED.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import Enum
from typing import List


class DiffBucket(str, Enum):
    OLD_BUG = "OLD_BUG"
    NEW_BUG = "NEW_BUG"
    INTENTIONAL_CHANGE = "INTENTIONAL_CHANGE"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass
class Diff:
    """A single classified diff hunk between Perl and Python output."""
    bucket: DiffBucket
    description: str
    perl_line: str = ""
    python_line: str = ""


def classify_diff(
    perl_output: str,
    python_output: str,
    intentional_changes: List[dict] | None = None,
) -> List[Diff]:
    """Classify the diff between two normalised outputs.

    Args:
        perl_output: normalised Perl output (one line per element).
        python_output: normalised Python output (one line per element).
        intentional_changes: list of dicts from the manifest, each with
            at least a `kind` field and an optional `description`.

    Returns:
        A list of Diff objects, one per non-matching hunk.
    """
    if intentional_changes is None:
        intentional_changes = []

    perl_lines = perl_output.splitlines()
    python_lines = python_output.splitlines()

    diff_lines = list(difflib.unified_diff(
        perl_lines, python_lines,
        fromfile="perl", tofile="python",
        lineterm="",
    ))

    if not diff_lines:
        return []

    results: List[Diff] = []
    i = 0
    while i < len(diff_lines):
        line = diff_lines[i]

        # Skip hunk headers (@@ ...)
        if line.startswith("@@"):
            i += 1
            continue

        # Collect one removed/added pair
        perl_part: List[str] = []
        python_part: List[str] = []
        while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
            l = diff_lines[i]
            if l.startswith("---") or l.startswith("+++"):
                i += 1
                continue
            if l.startswith("-"):
                perl_part.append(l[1:])
            elif l.startswith("+"):
                python_part.append(l[1:])
            else:
                # Context line — both have it
                pass
            i += 1

        # If only perl_part and no python_part → Python is missing something
        # If only python_part and no perl_part → Python added something
        # If both → Python replaced something
        perl_str = "\n".join(perl_part)
        python_str = "\n".join(python_part)

        # Check against intentional changes first
        matched_intentional = False
        for ic in intentional_changes:
            if _matches_intentional(perl_str, python_str, ic):
                results.append(Diff(
                    bucket=DiffBucket.INTENTIONAL_CHANGE,
                    description=ic.get("description", ic.get("kind", "intentional")),
                    perl_line=perl_str,
                    python_line=python_str,
                ))
                matched_intentional = True
                break

        if matched_intentional:
            continue

        # If Python output is empty where Perl had content → NEW_BUG
        # (regression: Python dropped something)
        if perl_str and not python_str:
            results.append(Diff(
                bucket=DiffBucket.NEW_BUG,
                description="Python output is missing content present in Perl output",
                perl_line=perl_str,
                python_line=python_str,
            ))
            continue

        # If Python output has content where Perl was empty → check if it's
        # an intentional addition (e.g. fixed the D==MN typo)
        if python_str and not perl_str:
            results.append(Diff(
                bucket=DiffBucket.UNCLASSIFIED,
                description="Python output has additional content not in Perl",
                perl_line=perl_str,
                python_line=python_str,
            ))
            continue

        # Both have content but they differ → unclassified for now
        results.append(Diff(
            bucket=DiffBucket.UNCLASSIFIED,
            description="Outputs differ in content",
            perl_line=perl_str,
            python_line=python_str,
        ))

    return results


def _matches_intentional(perl_str: str, python_str: str, ic: dict) -> bool:
    """Check whether a diff matches an intentional change rule."""
    kind = ic.get("kind", "")
    if kind == "hash_ordering_fixed":
        # If the perl and python strings contain the same set of key-value
        # pairs (in different order), this is the hash-ordering fix.
        # Compare as sets after splitting on a delimiter.
        perl_set = set(perl_str.split())
        python_set = set(python_str.split())
        return perl_set == python_set
    elif kind == "typo_fix_D_double_equals":
        # The D==MN typo fix
        return "D==MN" in perl_str and "D=MN" in python_str
    elif kind == "findbin_path_fix":
        return "is no longer in @INC" in perl_str
    elif kind == "explicit":
        # Manifest can list exact perl/python pairs that are intentional
        return perl_str == ic.get("perl", "") and python_str == ic.get("python", "")
    return False
