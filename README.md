# emmorph-py — Python port of the emMorph Hungarian morphological analyser

This repository contains the Python port of [nytud/emmorph](https://github.com/nytud/emmorph),
the open-source Hungarian morphological analyser originally developed by Attila Novák.
The port is being conducted as part of a doctoral research project under the supervision of
Prof. Balázs Indig at Eötvös Loránd University.

## Project status

**Phase 1 — Baseline audit and scaffolding (18 Oct 2026 → 8 Nov 2026).**

The audit report is in [`docs/baseline_audit_report.pdf`](docs/baseline_audit_report.pdf).
The differential harness scaffolding and the CI pipeline are in place; the first five leaf
modules are being ported.

## Repository layout

```
emmorph-py/
├── .github/workflows/ci.yml      # CI pipeline (4 jobs)
├── docs/
│   └── baseline_audit_report.pdf  # v0.1 audit report
├── harness/                       # differential harness
│   ├── run_diff.py                #   main entry point
│   ├── classify.py                #   diff → OLD_BUG / NEW_BUG / INTENTIONAL
│   ├── normalize.py               #   deterministic normalisation of hash outputs
│   ├── generate_oracle.py         #   freeze Perl outputs as the reference oracle
│   └── manifest.yaml              #   intentional-change manifest
├── oracle/                        # frozen Perl outputs (committed)
│   └── README.md
├── pyemmorph/                     # the Python port
│   ├── __init__.py
│   ├── set.py                     # port of pl/generic/set.pl
│   └── ...
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

## The two quality instruments

1. **Reproducibility test** — every Perl leaf script is run twice with two different
   `PERL_HASH_SEED` values; outputs are normalised (hash keys sorted) and diffed. Any
   non-determinism that survives the sort-keys fix is a CI failure.

2. **Differential harness** — every ported Python module is run side-by-side with the
   original Perl script on identical inputs. Output differences are classified as
   `OLD_BUG` (Perl wrong, Python correct), `NEW_BUG` (Python wrong, Perl correct), or
   `INTENTIONAL_CHANGE` (documented in `harness/manifest.yaml`). A module is considered
   ported when the harness reports only `INTENTIONAL_CHANGE` diffs against the oracle.

## Quick start

```bash
# clone the original Perl codebase as a submodule
git submodule add https://github.com/nytud/emmorph.git emmorph-perl

# install Python dependencies
pip install -r requirements.txt

# generate the oracle (requires Perl + the emMorph Perl codebase)
python harness/generate_oracle.py --perl-dir emmorph-perl --out oracle/

# run the differential harness
python harness/run_diff.py --manifest harness/manifest.yaml

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
