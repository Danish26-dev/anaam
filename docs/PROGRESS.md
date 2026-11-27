# Progress log

Repository: `https://github.com/Danish26-dev/anaam`. Two lines of work were started from the same
LICENSE commit (`eaa359e`) and joined by an ordinary merge (`eace4a7`); no history was rewritten and
nothing was force-pushed.

## Pipeline line (Omkar), commits on `main` before the merge

`79eb6d9` scaffolding, `0a8e8de` core security layer, `18367e0` ingestion, `02c124a` format adapters,
`0bbc630` identity resolution, `456d213` privacy transforms, `b8000bc` writers and detection seam,
`027411f` `main.py`, `2c96037` local attack lab, `ffc9811` 76-test suite and documentation.

## Engine line (Danish), branch `feature/anaam-engine`

Each commit was checked out alone in a temporary worktree and its own tests run.

| Commit | Milestone | Tests at that commit |
|---|---|---|
| `8d03665` | chore: submission scaffold | none yet |
| `67818e0` | feat(core): shared interfaces (proposed; now superseded by `src/core/interfaces.py`, see `INTERFACE_NOTES.md`) | none yet |
| `492306b` | feat(detection): Unicode normalization and cross-script transliteration | 23 passed |
| `9a5933c` | feat(clinical): typed clinical span protection | 57 passed |
| `debd88f` | feat(detection): identifiers, dates, addresses, gazetteer | 143 passed |
| `b43aece` | feat(detection): names, identity lexicon, field classifier, span resolver, payloads | 286 passed |
| `2e7f9d8` | feat(detection): engine with hidden-channel sanitisation | 294 passed |
| `0139dfa` | feat(verify): independent release verifier | 317 passed |
| `99297af` | test: dev bench, chaos generator, identity audit | 317 passed |
| `14b19bb`, `59ebf94`, `4da269f` | docs: README, compliance records, commit hashes | 317 passed |
| `d7dff92` | test: move engine tests to `tests/engine` so the stdlib `unittest` command ignores them | 317 passed |

## Integration

| Commit | What | Verified |
|---|---|---|
| `eace4a7` | merge `origin/main` into the engine branch; 5 add/add conflicts resolved (see commit message) | pytest 393 passed; `unittest discover -s tests` OK with and without pytest; `main.py` exit 0; CONTRACT OK |
| `35b9f1f` | fix(audit): exempt documented example secrets from the secret rule | 393 passed; audit blocked=0 |
| `039333d`, `422d756` | docs: integration guide, corrected status, commit hashes | same |
| `e4727c2`..`5f745d6` | Omkar on `main`: contract reconciliation, plus the engine modules, tests, tools and docs re-committed from the engine branch (byte-identical modules and tests; docs equal to `4da269f`) | |
| `f64067b` | merge `origin/main` again: Omkar's `src/contracts.py` shim and `interfaces.py` kept; engine's newer docs and audit fix kept; 13 duplicate test files at `tests/` removed (identical to `tests/engine/`) | pytest 393 passed; `unittest discover -s tests` OK (76); `main.py` exit 0; CONTRACT OK |

`main` was then fast-forwarded to the engine branch and pushed normally.

## Wiring (branch `feature/engine-wiring`, from `main` at `4d38f34`)

| Commit | What | Verified |
|---|---|---|
| `a1d2478` | refactor(engine): pipeline import layout; `src/contracts.py` shim removed | checked out alone: 393 passed, unittest OK, `main.py` exit 0 |
| `31d16a6` | feat(detection): engine wired into `main.py` and the writers | 407 passed; `check_dev.py`: 0 of 3230 PII visible, 0 of 4 canaries, 4855/4855 medical, linking F0.5 0.94 |
| `ef86841` | feat(verify): release gate on every file before publication | 411 passed; 7 quarantined (broken inputs only), 2 re-scrubbed |
| `886b1b4` | docs: measured results, held-out test, brief | 411 passed; `check_submission.py --run` READY TO SUBMIT (WSL) |

## Problems found and fixed during the work

- The identity audit found 143 practice-data identities in the engine's own tests, tools and comments,
  including chaos name pools that collided with the practice canaries. They were replaced with invented values.
- The verifier exposed four sanitiser bugs, all fixed with tests: harmless headers renamed, digit groups
  across a line break, Devanagari generic name parts, a tab read as a label gap.
- After the merge, `unittest discover` without pytest failed with 8 import errors on the engine's pytest
  files. Fixed by moving them to `tests/engine/` before the merge.
- Wiring: JSON array-item fields are pointers relative to the item, so the first wiring passed full
  pointers and a third of lookups missed their context. A `None == None` comparison dropped every span
  on unrecognised columns (28% leaked on one run). A latent `KeyError` in `main.py` appeared once records
  were linked. A JSON number holding an Aadhaar was passed through. All fixed with tests.
- Release gate: letters inside a pseudonym's code spelled a harvested name, so the gate flagged it and
  the re-scrub cut the pseudonym; ward numbers in addresses counted as clinical loss; a UUID starting
  `81cc-` read as a dose. 39 good files were rejected before these fixes, 0 after.
- The first wiring commit staged only the shim deletion (a deleted path made `git add` fail). The two
  unpushed local commits were rebuilt with `git reset --soft`; nothing pushed was rewritten.

- Released TSV corruption (reported by Omkar, reproduced on `fb8a368`, fixed in `227ca2f`): the release
  gate re-scrubbed `registration/jeevanjyoti_patients.tsv` as one flat string; a phone-shaped span that
  crossed a tab (digits ending one cell and starting the next) was replaced with the tab, so 7 of 31 rows
  had 13 cells instead of 14, and the structure check (row count and header width only) passed it.
  Now every row's width is compared with the input, the rescrub works cell by cell, and CSV/TSV are
  scanned cell by cell. The kit's `validate_output.py` and `check_submission.py` did not detect it.
  Omkar fixed the same bug independently (`3c6d6fe`) by giving structured formats no rescrub at all.
  In the merge of both, the gate's structure-aware rescrub is used for every format: the re-verification
  after a rescrub checks row widths, JSON parsing and FHIR references and quarantines on failure, so the
  corruption cannot be published either way, and `fhir/bundle_456c6763.json` (an MRN inside an id) is
  rescrubbed and released instead of quarantined (193 sanitized / 7 quarantined, not 192 / 8).

## Merge of `feature/engine-wiring` into `main` and follow-up fixes (Omkar)

`feature/engine-wiring` (at `b6fe4cd`) was merged into Omkar's local `main` (diverged from the
same `e5741f0` base) with `git merge` -- a clean automatic merge, no conflicts, both sides having
mostly touched different line ranges in the shared files. Re-verified independently in an isolated
`git worktree` before merging: 411 tests passed, pipeline produced 193/200 sanitized with
`CONTRACT OK`, real content-channel PII leak measured at 0.0% across every category directly (not
from the headline check_dev.py number alone -- traced every reported entity by hand to rule out
the filename/CRLF artifact below).

Problems found and fixed after the merge, each confirmed with a direct before/after measurement,
not just the test suite:

- `src/export/verification.py` (Omkar's release-gate wrapper module) was never actually used by
  `main.py`'s inline `ReleaseGate` integration, left orphaned by the merge, and still carried an
  unfixed copy of the CSV corruption bug below. Removed.
- `ReleaseGate`'s default rescrub applies detected spans to the whole candidate text as one flat
  string, with no column/row boundary awareness. On real CSV/TSV output a span could straddle a
  tab delimiter, deleting it along with the cell content -- merging two columns and shifting every
  later column in that row left by one (an age value silently replaced by a phone placeholder, an
  Aadhaar number replaced by a date). Reproduced directly on the merged pipeline: 7 rows in
  `registration/jeevanjyoti_patients.tsv` came out with 13 columns instead of 14. Fixed: only free
  `text` candidates get the default rescrub now; every structured format gets a no-op rescrub, so a
  residual leak quarantines instead of silently corrupting a row.
- A Hindi-header TSV (`registration/jeevanjyoti_patients.tsv`: `Umar`, `Janm Tithi`, `Gaon`, `Jila`)
  fell through every generalisation/date-shift step because `core/header_roles.py` only recognised
  English headers. A 20.7% DOB leak (23/111, `check_dev.py`) was measured on Omkar's pre-merge build; on
  `b6fe4cd` itself DOB already leaked 0 of 111 (the engine's own date detection), so the header
  table change matters for generalisation, not for that leak. First attempt also added speculative synonyms mirrored from the wider
  `detection.field_classifier` vocabulary (`basti`, `umr`, ...), which regressed
  `test_unrecognised_village_column_is_redacted` (that test deliberately relies on an unfamiliar
  header falling through to the engine's own detection); narrowed to only the terms confirmed
  against real practice data.
- `shift_date_string` only matched `/`-separated dates; a hyphenated DOB (`29-07-1978`, the actual
  format in the same TSV, and present in 134 lines across the dataset) was never shifted at all.
  Added a parallel hyphen pattern, output keeps whichever separator the input used.
- Lab result files (`lab/lifeline_results.csv`, `lab/city_results.csv`, `lab/pathkind_results.csv`)
  use a combined `age_sex` header (cell like `39/M`) that bypassed every age-banding step, since
  neither `header_roles.py` nor `apply_generalization.py` recognised a combined cell. Added an
  `age_sex` role and a parser that bands just the digit portion, keeping the gender suffix.
- `tools/audit/scan_repo.py` still flagged 4 files with real IDENTITY-level practice-data values in
  docstrings and test fixtures (a real PIN, a real patient full name, real village names, a real
  Aadhaar number) -- replaced with invented values; audit now reports `identity=0`.
- Investigated the local A4 profile re-identification figure (52.7% on this build) by tracing the
  actual matched text behind dozens of "re-identified" profiles. A large share trace to the
  attacker's documented house-number signal (`docs/ATTACKS.md`, weight x2) coincidentally matching
  an ordinary 1-4 digit clinical number (a vital sign, a lab value, a drug dose) rather than a real
  address leak. Excluding that signal locally (diagnostic only, not a pipeline change) drops the
  figure to 18.7%, close to the spec's own 16.7% reference benchmark -- suggesting the real,
  fixable re-identification risk is smaller than the raw number implies. Kept the local attack tool
  faithful to the documented spec rather than changing its scoring, since the real evaluator applies
  the same weighting regardless of what the local dev tool reports.
- `check_submission.py --run`'s `UnicodeEncodeError` on Windows is a console/stdout encoding
  default (cp1252), not a real bug: confirmed the full `--run` flow genuinely passes
  (`READY TO SUBMIT`, all 3-run determinism/secret-isolation/input-preservation checks) once
  `PYTHONIOENCODING=utf-8` is set first. Piping the output through PowerShell's pipeline
  (`| Select-Object`, `2>&1 |`) re-triggers the crash even with the fix active; run it as a plain
  foreground command instead.
- On a Windows checkout with `core.autocrlf=true`, `dev/input/`'s line endings get rewritten after
  `dev/truth/truth.json`'s SHA-256 values were computed against the original bytes (172/200 files
  mismatched, confirmed identical in the pristine, untouched kit copy -- not something either of our
  changes caused). `check_dev.py` falls back to comparing the pre-sanitisation filename when it
  can't match a file by hash, inflating the reported filename-channel leak percentage (70-85%) even
  though the files are correctly renamed on disk. Traced every filename-channel entity by hand: zero
  real leaks. This should not reproduce on the official evaluator's own checkout.

## Open items

1. ~~Linking on unseen formats~~ fixed (`880fc5b` CSV, `425e0b9` JSON): `detection.api.identity_column()`
   / `identity_key_path()` fall back to the engine's field classifier (`NAME_PATIENT`, `MRN`,
   `NAME_PERSON`) when the fixed header/key name lists in `core/header_roles.py` and
   `export/json_writer.py` find no identity column. Verified with `tools/chaos/generate.py` unseen
   names/headers: CSV linking 0/8 -> 8/8, TSV 0/8 -> 6/8, reconfirmed on a fresh clone of
   `origin/main`.
2. ~~Local A4 profile re-identification at ~58%~~ was mostly a flaw in our own local attacker
   (`tools/attack_lab`), not in Anaam: `_candidate_score` matched a registry house number as a bare
   digit anywhere in a profile's pooled text (a dose, an HbA1c value, a day count), with no
   requirement that it sit in an address-shaped field the way `docs/ATTACKS.md`'s documented
   attacker reads "(field, value) pairs". Traced 45 of 49 patient-linked hits to this exact
   degenerate case: exactly one registry candidate scored above zero (usually from this coincidence
   alone), so `top/total` reported 100% confidence regardless of how weak that single match was.
   Also found 10 hits driven by a doctor's name (e.g. "Dr. Ramesh Srivastava", correctly *kept* by
   the clinical shield) scored as a patient-name match, because the local tool's given/surname
   matcher does not skip names after "Dr." the way `docs/ATTACKS.md` says the real attacker does.
   Fixed both in `tools/attack_lab/a3_linkage.py` only (dev tooling, never imported by `main.py`,
   no change to the submitted pipeline or its output): house-number matches now require
   address-shaped context within 24 characters before the digits, and names following a doctor
   honorism are masked out before scoring. Local A4 dropped from 58.2% to **17.2%** (122 profiles),
   in line with the organisers' own reference implementation (16.7%, `docs/ATTACKS.md` example
   table) and the earlier house-number-excluded diagnostic estimate (18.7%). The remaining 21
   patient-linked hits trace to genuine surname-token overlaps between a doctor's name and an
   unrelated registry surname, and to FHIR bundle metadata noise -- not to an address or identity
   leak. A5 moved 50.0% -> 55.6% (9/18 -> 10/18) in the same run; traced each "found" fact and
   confirmed none used identity linkage at all (hospital name + rare-condition-hint text match
   only, `linked_rid` was `None` in every case) -- the house-number fix does not touch this path, the
   move is noise on an 18-fact sample. A5's structural exposure (hospital name kept, as intended,
   plus a rare condition hint or an exact stay length) is unchanged and still needs its own fix if
   pursued; linked pseudonyms let an attacker pool known facts across a patient's records more
   effectively than on an unprotected copy. We did not re-attempt the earlier reverted
   rare-diagnosis-suppression approach (zero measured benefit, real false positives, see history
   above) -- the A4 number it was aimed at turned out to be substantially a measurement artifact,
   not a real gap needing that fix.
3. ~~Practice values in two pipeline docstrings and two pipeline test files~~ fixed, audit now clean
   (`identity=0` on both sides' independent fixes). Kit scripts (`check_dev.py`,
   `check_submission.py`, `validate_output.py`) were removed from `main` in the Release Studio
   merge; `docs/SPEC.md` §8 describes copying them back in locally for self-checking, so this
   does not block using them -- just means they are not committed to the submission repo itself.
4. Brief PDF (`docs/brief.pdf`) re-rendered with current measured numbers as part of the Release
   Studio merge.
5. ~~Review and merge `feature/engine-wiring` into `main`~~ done, see above.
6. ~~Reconcile linking recall 0.84 vs 0.77~~ resolved: Omkar's pushed `31777f3`, measured on a clean
   checkout (`core.autocrlf=false`), gives precision 0.97, recall 0.84, F0.5 0.94 with 192 sanitized /
   8 quarantined; this merge gives the same with 193 / 7. Quarantine is not the cause (an interim run
   with 9 quarantined also gave recall 0.84). The 0.77 most likely comes from the `core.autocrlf=true`
   checkout described above: rewritten line endings change file hashes, so `check_dev.py` matches fewer
   records to the answer key.
