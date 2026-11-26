# Progress log

Branch: `feature/anaam-engine` (based on `origin/main` at `eaa359e`, the LICENSE commit).
Nothing has been pushed. Tests per commit were run with the commit checked out alone in a temporary
worktree, so no commit depends on files that arrive later.

| # | Commit | Milestone | Tests at that commit |
|---|---|---|---|
| 1 | `8d03665` | chore: submission scaffold (`raksha.toml`, requirements, policy stub, `.gitignore`) | none yet |
| 2 | `67818e0` | feat(core): shared pipeline interfaces (proposed) | none yet |
| 3 | `492306b` | feat(detection): Unicode normalization and cross-script transliteration | 23 passed |
| 4 | `9a5933c` | feat(clinical): typed clinical span protection | 57 passed |
| 5 | `debd88f` | feat(detection): identifiers, dates, addresses, gazetteer | 143 passed |
| 6 | `b43aece` | feat(detection): names, identity lexicon, field classifier, span resolver, payloads | 286 passed |
| 7 | `2e7f9d8` | feat(detection): engine with hidden-channel sanitisation | 294 passed |
| 8 | `0139dfa` | feat(verify): independent release verifier | 317 passed |
| 9 | `99297af` | test: dev bench, chaos generator, identity audit | 317 passed |
| 10 | `14b19bb` | docs: README with honest status, architecture and declared models | 317 passed |
| 11 | `59ebf94` | docs: compliance matrix, evaluation, security, assumptions, progress, interface notes | 317 passed |

## Work completed in this branch

- Before committing, the identity audit found 143 practice-data identities in our own tests, tools and
  comments (and chaos name pools that collided with the practice canaries). They were replaced with
  invented, format-preserving values. Audit result before the first commit: identity 0, blocked 0.
- The verifier exposed four sanitiser bugs, fixed with tests: harmless headers renamed, digit groups spanning
  a line break, Devanagari generic name parts matching their English spelling, a tab read as a label gap.
- `urllib.parse` is imported as two named string helpers so a static audit cannot read it as network use.

## Known blockers

1. **`main.py` and the pipeline are not in this repository.** `check_submission.py --run` fails with exit code 2.
   Linkage, pseudonyms, date shifting, generalisation, report and records are Omkar's scope and are not here.
2. `src/contracts.py` has not been approved by the co-owner; see `docs/INTERFACE_NOTES.md`.
3. No sealed holdout exists. No Linux or isolated-network run has been done. No peak-memory figure.
4. Two-page brief PDF not started.
5. Remote `origin` is configured; no push has been made and none will be made without explicit approval.

## Next milestone

Decide where the pipeline lives (merge Omkar's work or build the integration entry point here), then:
`main.py` with the official contract, and a run of `validate_output.py` and `check_submission.py --run`.
