"""pyemmorph — Python port of the emMorph / Humor morphological analyser.

This package ports the Perl code from nytud/emmorph to Python, module by
module. Each ported module is validated against the original Perl output
via the differential harness in ``harness/``.

The audit report (``docs/baseline_audit_report.pdf``) documents the six bugs
found during the baseline audit and the planned order of porting.
"""

__version__ = "0.1.0.dev0"
