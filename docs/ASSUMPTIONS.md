# Assumptions and open decisions

Decisions that the official documents do not settle, or where they disagree.

1. **Tie-break wording differs between documents.** `docs/FAIRNESS.md` says a team ranks higher only
   when it beats another by more than 1 point on every hidden dataset; `docs/SCORING.md` says
   rank separation needs a paired significant difference of at least 0.5 points. FAIRNESS.md also
   mentions a published tie-break (for example the privacy category, then the chaos dataset) that
   `scoring.toml` does not define. Strategy used: do not collapse on any dataset. To ask the organisers.
2. **Pseudonym format.** The contract only needs a stable, keyed, non-reversible ID that appears inside the
   record. `PSN-` plus a Crockford-base32 HMAC value is proposed. Not implemented here.
3. **Generic name parts** (Kaur, Singh, Devi, Kumar, Khatoon, ji, sahab and their Devanagari spellings)
   are not treated as identifying, matching the scorer's description, but are removed when they are part
   of a detected name span.
4. **A doctor's full name without "Dr."** (for example in a gate log) is kept when that full name was
   harvested as a doctor from a doctor field or "Dr." line. A bare first name shared with a relative is
   still redacted.
5. **Weak name guesses never rename a header, key or file name on their own.** Renaming harmless headers
   costs schema-preservation points. A dict keyed mostly by Title-Case or ID-shaped strings is treated as keyed by data.
6. **Verifier ignores unlabelled ID-shaped tokens in CSV/JSON** to avoid blocking bill and sample numbers.
7. **Practice-data identities in our own files.** Rule: zero full names, canaries, ID digits, PINs,
   villages, phones. Single common first names and generic address words ("Ward 8") are tolerated as
   unavoidable overlap with any Indian-name list. Enforced by `tools/audit/scan_repo.py`.
8. **Line endings.** Windows Git converted the kit's practice files to CRLF, changing 172 of 200 SHA-256
   values and breaking `check_dev.py`'s file matching. The kit clone uses `core.autocrlf=false` and was
   rewritten from the commit. Every checkout, ours and Omkar's, needs the same setting.
9. **`check_submission.py` quick mode is not a readiness signal.** It checks files only and printed
   READY TO SUBMIT even before `main.py` existed. Only `--run` counts, and `--run` cannot pass on Windows
   when the path contains a space (POSIX quoting); it needs Linux or WSL.
10. **`python` on this machine** resolves to a Store alias; checks were run with the project venv first on `PATH`.
11. **One interface file.** `src/core/interfaces.py` is the only contract; the `src/contracts.py`
   shim was removed when the engine moved to the pipeline's import layout (`a1d2478`).
12. **Structured quasi-identifiers belong to the privacy layer when it recognises the column.** The
   scoring rewards a kept or truthfully generalised village, PIN and age band, so the engine leaves
   those whole-field values to `src/privacy` when `core.header_roles` knows the column, and redacts
   them only when it does not (`docs/INTERFACE_NOTES.md`, span policy).
13. **`check_submission.py --run` on WSL needs `python` on `PATH`.** The `run` line is
   `python main.py ...`; WSL Ubuntu ships only `python3`, so a temporary link was put on `PATH`. The
   event sandbox is assumed to provide `python`.
14. **Merge conflict choices** (`eace4a7`): `raksha.toml` and `config/policy.yaml` kept the pipeline's
   versions because `main.py` reads them (team name stays `anaam`); `.gitignore` is the union.
15. **Two test runners.** Pipeline tests use the standard library (`unittest`); engine tests use pytest
   and live in `tests/engine/`, a directory without `__init__.py` that `unittest discover` skips.
12. **Sealed holdout** must be authored by someone other than the detector's author, with different templates, and used once.
13. **Brief PDF** (2 pages, `docs/brief.pdf`) is not started.
