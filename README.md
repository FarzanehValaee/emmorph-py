# emmorph-py — Python port of the emMorph Hungarian morphological analyser

This repository contains the Python port of [nytud/emmorph](https://github.com/nytud/emmorph),
the open-source Hungarian morphological analyser originally developed by Attila Novák.
The port is being conducted as part of a doctoral research project under the supervision of
Prof. Balázs Indig at Eötvös Loránd University.

## Project status

**Phase 1 — Baseline audit and scaffolding (18 Oct 2026 → 8 Nov 2026).**

The v0.1 audit is in [`docs/baseline_audit_report.pdf`](docs/baseline_audit_report.pdf).
Prof. Indig's three additions (17 Oct 2026) are written up in
[`docs/addendum_v0_2.pdf`](docs/addendum_v0_2.pdf). `set`, `getsfxtags`, `bsort`, `lcase`, `sort`, and `uniq` are ported.
`getsfxtags`, `bsort`, `lcase`, `sort`, and `uniq` are in the differential harness.

## Repository layout

```
emmorph-py/
├── .github/workflows/ci.yml      # CI pipeline (6 jobs)
├── docs/
│   ├── baseline_audit_report.pdf  # v0.1 audit report
│   └── addendum_v0_2.pdf          # v0.2 addendum (Indig, 17 Oct 2026)
├── corpus/                        # word lists for layer 3
│   ├── sources/README.md          #   where to download external corpora
│   ├── build_paradigm_forms.py    #   lemma × tag, via hfst-lookup -g
│   └── fuzz_corpus.py             #   reproducible Hungarian-like forms
├── harness/                       # three evaluation layers
│   ├── run_diff.py                #   (1) leaf-script differential harness
│   ├── classify.py                #   diff → OLD_BUG / NEW_BUG / INTENTIONAL
│   ├── normalize.py               #   deterministic normalisation of hash outputs
│   ├── generate_oracle.py         #   freeze Perl outputs as the reference oracle
│   ├── intermediate_state_diff.py #   (2) gen/ stability across hash seeds
│   ├── extrinsic_eval.py          #   (3) emmorphpy / hfst-lookup comparison
│   └── manifest.yaml              #   intentional-change manifest
├── oracle/                        # frozen Perl outputs (committed)
│   └── README.md
├── pyemmorph/                     # the Python port
│   ├── __init__.py
│   ├── set.py                     # port of pl/generic/set.pl
│   ├── getsfxtags.py
│   ├── bsort.py
│   ├── lcase.py
│   ├── sort.py
│   └── uniq.py
├── scripts/                       # developer utilities
│   └── perl_patches/              # patches to the Perl originals
├── tests/                         # pytest test suite
│   ├── test_differential.py       #   harness wrapper
│   ├── test_set.py                #   unit tests for set.py
│   └── conftest.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Three evaluation layers

1. **Leaf-script differential harness.** Every ported Python module is run beside
   the original Perl script on identical inputs. Differences are classified as
   `OLD_BUG` (Perl wrong, Python correct), `NEW_BUG` (Python wrong, Perl correct),
   or `INTENTIONAL_CHANGE` (recorded in `harness/manifest.yaml`). A module is
   ported when the harness reports no `NEW_BUG` and no unclassified diff.
   The same leaf scripts are also run twice, with `PERL_HASH_SEED=0` and
   `PERL_HASH_SEED=1`; a normalised difference is a hash-order bug.

   ```bash
   python harness/run_diff.py --manifest harness/manifest.yaml --perl-dir emmorph-perl
   python harness/reproducibility_check.py --perl-dir emmorph-perl
   ```

2. **Intermediate-state comparison.** `make -f mak/uhun.make xlx` writes about
   thirty files under `gen/` (`metadict.txt`, `sfxtags.hpl`, `stemgenX.lx2`,
   `encodingXbit2mtx.hpl`, and the rest of the `xlx` closure). The build runs
   once with each hash seed. A file whose normalised sha256 changes is an
   unstable producer; a file the build did not write is missing.

   ```bash
   python harness/intermediate_state_diff.py --perl-dir emmorph-perl
   ```

3. **Extrinsic evaluation.** The same word list is analysed with the
   Perl-compiled transducer and the Python-compiled transducer, through
   [emmorphpy](https://github.com/nytud/emmorphpy) when it imports, and
   through `hfst-lookup` otherwise. The list can be an external Hungarian
   corpus, every form the generator will emit, or a seeded fuzz set.

   ```bash
   python corpus/fuzz_corpus.py -n 1000 --seed 42 -o corpus/generated/fuzzed_forms.txt
   python harness/extrinsic_eval.py \
       --corpus corpus/generated/fuzzed_forms.txt \
       --fst-a emmorph-perl/hfst/hu.hfstol \
       --fst-b emmorph-perl/hfst/hu.hfstol \
       --emmorphpy-dir ../emmorphpy
   ```

## Long-term vision

The port is organised in three phases, following Prof. Indig's note of
17 October 2026: keep emMorph and emmorphpy together, and stop paying for
a process spawn on every lookup.

- **Phase 1 (current).** Port the Perl compilation pipeline to Python. The
  transducer it writes must be byte-identical to the Perl-compiled one, so
  the existing emmorphpy wrapper runs unchanged against either file.
- **Phase 2.** Bring emmorphpy into this repository (or a sister repository
  that is released with it). The compiler, the transducer, and the
  user-facing API then move together.
- **Phase 3.** Extend libhfst with Python bindings, via cffi or pybind11,
  that expose the optimised in-process lookup already available to C++
  callers. emmorphpy then calls that API instead of `subprocess.Popen`.

`Popen` is slow for two independent reasons. Every call pays process
startup (loading `hfst-lookup` and the transducer) and every word pays a
round trip through pipes. An in-process binding removes both: the
transducer stays mapped for the life of the process, and a lookup is a
function call rather than a write to stdin and a read from stdout.

## Quick start

```bash
# clone the original Perl codebase as a submodule
git submodule add https://github.com/nytud/emmorph.git emmorph-perl

# install Python dependencies
pip install -r requirements.txt

# generate the oracle (requires Perl + the emMorph Perl codebase)
python harness/generate_oracle.py --perl-dir emmorph-perl --out oracle/

# run the differential harness
python harness/run_diff.py --manifest harness/manifest.yaml --perl-dir emmorph-perl

# layer 2: intermediate gen/ files across two hash seeds
python harness/intermediate_state_diff.py --perl-dir emmorph-perl

# layer 3: fuzz a word list, then compare two transducers
python corpus/fuzz_corpus.py -n 1000 --seed 42 -o corpus/generated/fuzzed_forms.txt
python harness/extrinsic_eval.py \
    --corpus corpus/generated/fuzzed_forms.txt \
    --fst-a emmorph-perl/hfst/hu.hfstol \
    --fst-b emmorph-perl/hfst/hu.hfstol

# run the test suite
pytest tests/ -v
```

## Acknowledgements

The original emMorph / Humor analyser was developed by Attila Novák and is licensed under
CC BY-NC-SA 4.0 (database) and GPL v3 (code). The original publications are:

- Novák, A. (2014). *A New Form of Humor — Mapping Constraint-Based Computational
  Morphologies to a Finite-State Representation.* LREC 2014.
- Novák, A., Siklósi, B., & Oravecz, Cs. (2016). *A New Integrated Open-source
  Morphological Analyzer for Hungarian.* LREC 2016.
- Novák, A. (2003). *Milyen a jó Humor?* MSZNY 2003.

## Contact

Farzaneh Velaeishekan — farzaneh.valaee79@gmail.com
