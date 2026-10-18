"""normalize.py — deterministic normalisation of script outputs.

The hardest part of the differential harness is making outputs comparable.
Perl scripts emit hashes in random order (the B3/B4 bugs from the audit);
the Python port will emit them in sorted order. Without normalisation,
every hash output would diff. The normaliser:

1. For lines that look like `%mcat=('k1','v1','k2','v2',...)`, sorts the
   key-value pairs alphabetically by key.
2. For other lines, leaves them unchanged.
3. Optionally applies script-specific normalisation rules from the manifest.
"""

from __future__ import annotations

import re
from typing import List


class NormalizationError(Exception):
    pass


# Regex matching Perl hash assignments like:
#   %mcat=('k1','v1','k2','v2',...);
#   %dercat=('k1','v1','k2','v2',...);
HASH_ASSIGN_RE = re.compile(
    r"^(?P<prefix>%\w+=\()(?P<body>.*?)(?P<suffix>\);)\s*$"
)


def sort_hash_pairs(body: str) -> str:
    """Sort the key-value pairs of a hash body.

    Input looks like: 'k1','v1','k2','v2','k3','v3'
    Output: pairs sorted by key.
    """
    # Split on ',' (not inside single quotes; this is a simple implementation
    # that assumes no escaped commas inside values — emMorph values don't
    # contain commas)
    parts = [p.strip().strip("'") for p in body.split(",") if p.strip()]
    if len(parts) % 2 != 0:
        # Odd number of elements — can't pair them. Return as-is.
        return body
    pairs = list(zip(parts[::2], parts[1::2]))
    pairs.sort(key=lambda kv: kv[0])
    return ",".join(f"'{k}','{v}'" for k, v in pairs)


def normalize_line(line: str) -> str:
    """Apply line-level normalisation."""
    # Sort hash assignments
    m = HASH_ASSIGN_RE.match(line)
    if m:
        return f"{m.group('prefix')}{sort_hash_pairs(m.group('body'))}{m.group('suffix')}"
    return line


def normalize_output(raw_output: str, manifest_entry: dict) -> str:
    """Normalise the raw output of a script.

    Args:
        raw_output: the raw stdout of the script.
        manifest_entry: the manifest dict, may contain a `normalize` key
            with a list of additional normalisation rules.

    Returns:
        The normalised output, one normalised line per input line.
    """
    if not raw_output:
        return ""

    lines = raw_output.splitlines()
    normalised = [normalize_line(l) for l in lines]

    # Apply manifest-specified extra normalisations
    extra_rules = manifest_entry.get("normalize_extra", [])
    for rule in extra_rules:
        if rule == "strip_timestamps":
            # Strip lines that look like timestamps
            normalised = [
                l for l in normalised
                if not re.match(r"^<<<\w{3} \w{3} +\d+ ", l)
            ]
        elif rule == "sort_lines":
            normalised = sorted(normalised)

    return "\n".join(normalised)
