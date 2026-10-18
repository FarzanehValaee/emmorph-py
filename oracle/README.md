# oracle/

This directory contains **frozen outputs of the original Perl scripts**,
used as the reference for the differential harness.

## How the oracle is generated

```bash
python harness/generate_oracle.py --perl-dir ../emmorph-perl --out .
```

Each Perl leaf script is run with `PERL_HASH_SEED=0` to stabilise hash
ordering, and its stdout is written to a file named `<script>_perl.out`.

## When to regenerate the oracle

Regenerate when:
1. The Perl originals are patched (e.g. applying the `use FindBin;` fix
   for bug B6 in `scripts/perl_patches/`).
2. A new leaf script is added to `harness/manifest.yaml`.
3. The input corpus changes.

## Why commit the oracle

The oracle is committed to the repository so that the differential harness
can run on any CI runner, including those that don't have Perl installed
or that fail to install hfst. The Python port is the only thing under
active development; the Perl side is treated as a fixed reference.

## Current contents

| File | Source script | Status |
|------|---------------|--------|
| `getsfxtags_perl.out` | `pl/mkavs/getsfxtags.pl` | pending |
| `bsort_perl.out` | `pl/generic/bsort.pl` | pending |
| `lcase_perl.out` | `pl/generic/lcase.pl` | pending |
| `sort_perl.out` | `pl/generic/sort.pl` | pending |
| `uniq_perl.out` | `pl/mkavs/uniq.pl` | pending |

Once you have run `generate_oracle.py`, replace this README with the actual
oracle files and remove this status table.
