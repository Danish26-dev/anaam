"""O-side wiring for Danish's independent release verifier (src/verify/release.py).

Writers already produce CandidateFile objects before anything is published (see
candidate.py's module docstring: "Danish's independent verifier can inspect the
candidate list before publish_candidates is called"). This module is that seam: for
each rendered candidate it builds the richer `verify.release.FileCandidate` the gate
needs (original text/json, claimed pseudonyms, row/column counts for CSV, exempt JSON
prefixes for generalized fields) and runs verify_and_fix, so a file whose output still
leaks a known value, drops below the clinical-loss budget, or fails a structural check
gets one rescrub attempt and then quarantine -- it never reaches `sanitized/` unverified.

Deliberately does not try to verify FHIR bundles against a flat JSON shape check
(check_fhir_references already covers FHIR-specific reference integrity in `_structure`,
but the generic JSON shape/exempt-prefix comparison in ReleaseGate assumes a plain
pointer tree, which does not match how O10 generalizes inside FHIR narrative text) --
FHIR candidates are verified for leaks and the FHIR-specific structural check only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from verify.release import FileCandidate, ReleaseGate


@dataclass
class VerifiedCandidate:
    relative_path: str
    text: str
    format: str
    result: object  # core.interfaces.VerificationResult
    rescrubbed: bool


def exempt_prefixes_for(field_transformations) -> tuple[str, ...]:
    """JSON pointer prefixes ReleaseGate's shape check must not flag as JSON_PATHS_LOST
    / JSON_TYPE_CHANGED: O10 generalization can blank or reshape these on purpose
    (e.g. suppressing a village down to "", or replacing an age with a band string).

    Two normalizations are needed because verify.structure._paths() -- what
    ReleaseGate's shape check actually compares exempt_prefixes against -- has a
    specific shape of its own:
      * json_generalize.py builds FieldTransformation.path as "key/child" (no leading
        slash for the top-level key); _paths() always starts with "/".
      * _paths() collapses every list index to the literal segment "*" (a list is
        exempted structurally, not element-by-element), while json_generalize.py's
        walk() records the real integer index for each array element it touches.
    Without both fixes, an age-banding or village-suppression transformation inside a
    JSON array would never match the exempt prefix it needs to.
    """
    out = []
    for t in field_transformations:
        path = t.path if t.path.startswith("/") else f"/{t.path}"
        path = re.sub(r"/\d+(?=/|$)", "/*", path)
        out.append(path)
    return tuple(out)


def verify_csv_candidate(
    gate: ReleaseGate,
    out_rel: str,
    original_text: str,
    rendered_text: str,
    header: list[str],
    n_rows: int,
    delimiter: str,
    pseudonyms: list[str | None],
) -> VerifiedCandidate:
    cand = FileCandidate(
        text=rendered_text,
        original_text=original_text,
        fmt="csv" if delimiter == "," else "tsv",
        pseudonyms=tuple(p for p in pseudonyms if p),
        n_columns=len(header),
        n_rows=n_rows,
        delimiter=delimiter,
    )
    # ReleaseGate's default rescrub (rescrub_text) runs the detector over the WHOLE
    # candidate text as one flat string with no column/row boundary awareness. Found by
    # direct observation: on a real CSV/TSV row, a detected span can straddle a column
    # delimiter, so redacting it deletes the delimiter along with the cell content --
    # merging two cells and shifting every later column left by one for that row. A
    # structural corruption like that is worse than the leak it was trying to fix, so
    # CSV/TSV gets the same no-op rescrub as JSON/FHIR: a residual leak goes straight to
    # quarantine instead of a "fix" that can silently corrupt the row.
    result, fixed = gate.verify_and_fix(cand, rescrub=lambda c: c)
    return VerifiedCandidate(out_rel, fixed.text, cand.fmt, result, False)


def verify_json_candidate(
    gate: ReleaseGate,
    out_rel: str,
    original_data: object,
    rendered_text: str,
    pseudonyms: list[str | None],
    exempt_prefixes: tuple[str, ...],
) -> VerifiedCandidate:
    cand = FileCandidate(
        text=rendered_text,
        fmt="json",
        pseudonyms=tuple(p for p in pseudonyms if p),
        original_json=original_data,
        exempt_json_prefixes=exempt_prefixes,
    )
    result, fixed = gate.verify_and_fix(cand, rescrub=lambda c: c)  # structured: no safe text rescrub
    return VerifiedCandidate(out_rel, fixed.text, "json", result, False)


def verify_fhir_candidate(
    gate: ReleaseGate,
    out_rel: str,
    rendered_text: str,
    pseudonym: str | None,
) -> VerifiedCandidate:
    cand = FileCandidate(
        text=rendered_text,
        fmt="fhir",
        pseudonyms=(pseudonym,) if pseudonym else (),
    )
    result, fixed = gate.verify_and_fix(cand, rescrub=lambda c: c)  # structured: no safe text rescrub
    return VerifiedCandidate(out_rel, fixed.text, "fhir", result, False)


def verify_text_candidate(
    gate: ReleaseGate,
    out_rel: str,
    original_text: str,
    rendered_text: str,
    pseudonym: str | None,
) -> VerifiedCandidate:
    cand = FileCandidate(
        text=rendered_text,
        original_text=original_text,
        fmt="text",
        pseudonyms=(pseudonym,) if pseudonym else (),
    )
    result, fixed = gate.verify_and_fix(cand)
    return VerifiedCandidate(out_rel, fixed.text, "text", result, fixed.text != rendered_text)
