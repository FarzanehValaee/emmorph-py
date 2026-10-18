# scripts/perl_patches/

This directory contains patches to the original Perl codebase that fix
the bugs identified in the audit report (§4 of `docs/baseline_audit_report.pdf`).

These patches are applied to the Perl submodule so that the oracle outputs
can be regenerated on modern Perl. They are NOT modifications of the
emMorph project itself — they are local patches applied on top of the
`nytud/emmorph` master branch.

## Patch files

Each patch is a unified diff that can be applied with `patch -p1` from
the repository root.

### `01_use_findbin_for_inc_paths.diff` — fixes B6

Adds `use FindBin;` to the eight scripts that use `do 'foo.hpl';` patterns
that rely on `.` being in `@INC` (removed in Perl 5.26).

Affected scripts:
- `pl/generic/metadict.pl`
- `pl/generic/encode.pl`
- `pl/generic/lex2.pl`
- `pl/generic/morphlex.pl`
- `pl/mkavs/fixpron.pl`
- `pl/mkavs/getsfxtags.pl`

### `02_sort_keys_in_getsfxtags.diff` — fixes B4

Emits `%mcat` and `%dercat` as key/value pairs sorted by key, so the
output is deterministic across runs. Pairs stay intact (`sort keys`, then
the value); a flat `sort(%hash)` would separate keys from values.

### `03_sort_keys_in_set_pl.diff` — fixes B1, B2

- `set.pl:78` — replace `each()` with `for(sort(keys(%a)))`.
- `set.pl:104` — wrap both `keys()` calls in `sort`.

### `04_sort_keys_in_encode_pl.diff` — fixes B3

Wrap the seven `for(keys(...))` loops in `encode.pl` (lines 413, 443,
571, 735, 758, 1167, 1181) with `sort`.

## Applying the patches

```bash
cd emmorph-perl
for p in ../scripts/perl_patches/*.diff; do
    patch -p1 < "$p"
done
```

## Note on B5

Bug B5 (`D==MN` typo in getsfxtags output) is left unfixed pending
Prof. Indig's decision on whether the source data (`src/sfx.1` line 167,
`mcat:>=Adj`) or the script (`getsfxtags.pl:84`, regex captures the `=`)
is wrong. Once the decision is made, the appropriate patch will be added
to this directory.
