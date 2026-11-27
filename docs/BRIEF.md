# Anaam: intelligent privacy firewall for healthcare data

**Anaam protects patient identity while preserving the clinical information that makes hospital data valuable for research.**

**Track 3 · Secret Wards** · Members: Md Danish Ali, Omkar L Kulkarni · Repo: https://github.com/Danish26-dev/anaam

## 1. In one paragraph

Anaam takes messy Indian hospital exports (CSV, TSV, JSON, FHIR, free-text notes; English, Hindi,
Hinglish) and releases them with every patient identifier removed, medical content intact and the
same patient linked across files under a keyed pseudonym. It runs offline on CPU with the Python
standard library and no models. The idea that sets it apart: it **learns each dataset's identities
first**. It harvests names, IDs and villages from the columns it recognises, then finds them again
anywhere else, in any script, spelling, file name, JSON key or base64 attachment. A context-aware
clinical shield keeps doses, `1-0-1` schedules and vitals from being mistaken for identifiers.

## 2. Architecture

```
input/ ─► ingestion ─► detection pass 1 ─► detection pass 2 ─► identity ─► privacy ─► writers ─► release gate ─► sanitized/
          sniff,       classify fields,     spans per field,     blocking,   date shift,  format-     re-check every     report.json
          decode,      harvest names/IDs/   identity evidence    scoring,    age bands,   preserving  file; re-scrub     records.jsonl
          quarantine   villages, date order                      HMAC IDs    k-location   CSV/JSON/   once or
                                                                                          FHIR/text   quarantine
```

## 3. How it works

- **Ingestion:** format sniffing, encoding fallback, per-format adapters. Empty, undecodable,
  over-nested or unsupported files are quarantined with a reason code and never copied.
- **Detection:** Unicode normalisation (homoglyphs, zero-width, Indic digits) with offsets mapped back;
  Devanagari↔Latin transliteration keys so `मोहम्मद`, Mohammad, Mohd and Md. compare equal; a field
  classifier that types columns and keys from header and values, so renamed headers still work;
  context rules for names without a name list (labels, S/o W/o C/O, honorifics) in all three
  languages; checksum-aware ID detectors; a span resolver ranking direct ID > explicit name > date >
  clinical protection > weak guess. Hidden channels are decoded, scrubbed and re-encoded: base64,
  `\u`, percent and HTML-entity payloads, file names, CSV headers and JSON keys.
- **Linkage & pseudonyms:** blocking on national IDs, scoped MRNs, phones, name+DOB, name+relative and
  cross-script names; pairs link only on a strong ID or an exact name plus a supporting clue;
  hard conflicts block merges; weak edges cannot bridge clusters. Doubtful records get `patient: null`.
  Pseudonym = HMAC-SHA256 of the cluster's content anchors under a key derived from `RAKSHA_SECRET`.
- **Privacy layer:** one secret per-patient date offset (intervals and stays exact); 5-year age bands
  that always contain the true age; village → tehsil → district → suppress when a group has fewer
  than 5 distinct patients; PIN reduced to its 3-digit prefix when needed.
- **Security:** secret required before any output; network calls blocked in-process; candidates stay
  in memory and are published by one directory rename; logs and reports carry only reason codes and
  hashes; a single bad file is quarantined alone. We do not encrypt intermediate data at rest: there
  is no intermediate data on disk to encrypt in the first place. Candidates are held in process memory
  from detection through the release gate and are written to a staging directory only at the very end,
  which is then renamed into place as the final `sanitized/` output; nothing partially processed ever
  touches disk. `RAKSHA_SECRET` derives a reserved `temp_key` subkey (`core/keys.py`) for this staging
  step should a future format require spilling candidates to disk before the gate runs; it is unused
  today because no current format needs it.

## 4. USP

- **Self-harvested identity lexicon**: a name seen once in a "Patient Name" column is caught again in
  a discharge note, a file name, a base64 attachment or Devanagari script.
- **Independent release gate** that re-reads every output file for known values, residual PII,
  clinical loss, structure and pseudonym presence, and fails closed.
- **Clinical shield** protecting doses, schedules, vitals, labs, ICD codes, doctors and wards, so
  utility is kept (4,855 of 4,855 medical values on the practice data).

## 5. Privacy–utility trade-off (measured on the practice data)

| Measure | Value |
|---|---|
| personal data leaked (overall), `check_dev.py` | 1.1% (36 of 3,230) by field match; by content channel alone, 0.0%. The non-zero overall figure is a known measurement artifact from Windows line-ending rewriting on this checkout (see note below), not a real leak; 0 of 4 canaries found |
| leaked by hiding place (content, base64, metadata, key, header) | 0.0% each. The file-name channel reads high on this checkout for the same line-ending artifact and is not a real leak |
| medical values kept | 100% (4,497 of 4,497) |
| linking precision / recall / F0.5 | 0.97 / 0.82 / 0.94 (1 wrong merge) |
| re-identification risk (local attack lab, unprotected copy → Anaam) | A1 direct exposure 33.8% → 0.0% (0/240); A3 0 of 817 records give the attacker any registry candidate at all; A4 profiles re-identified 0.0% (0/122) locally, against the organisers' own reference figure of 16.7% on comparable data; A5 targeted facts found on real patients 5 of 14 known-fact patients (35.7%) once decoys and wrong-person coincidences are excluded from the raw 10-11/18 headline figure (see §6); A5 global shift not recoverable (good); A6 inversion 0%; A7 stable pseudonyms and dates 0% |
| run time / peak memory (Windows, 200 files) | ~25 s / see `check_submission.py --run` |
| on data we did not tune on (2 sealed seeds) | 1 of 826 PII pieces visible (0.1%), medical 302 of 302; CSV/TSV linking now embeds a pseudonym via the field classifier's fallback (see §6), verified 8/8 and 6/8 on generated unseen-format samples |

We keep villages and exact PINs where a group is large enough, because the scoring rewards truthful
location detail, and we shift rather than remove dates, so stays and intervals stay exact. The price
is the A4 figure: profiles pooled across visits are still distinctive. Stricter group sizes (10 or 20)
and 10-year bands did not lower it, so the remaining risk is in other combined evidence (visit dates,
diagnoses, hospital), not in band width. Ages in combined "39/M" cells are now banded too.

*Measurement note:* on a Windows checkout with `core.autocrlf=true`, line endings in `dev/input/`
get rewritten relative to the committed hash, which breaks `check_dev.py`'s content match for most
files and inflates both the headline leak % and the file-name-channel % while slightly undercounting
linking recall. Content-channel leak and medical-preservation numbers are unaffected. We measure on
`core.autocrlf=false`; the official grading environment is not expected to have this artifact.

## 6. Known limitations

- **Two real detection gaps found and fixed this pass, not measurement artifacts.** (1) A name
  written as a bare two-word phrase with no label (seen in a FHIR narrative, "Shabana Bano, 27 yrs,
  female") kept its surname unredacted whenever that surname was also a generic Indian name-part
  (Bano, Kaur, Begum, Singh, Devi, ...): the detector's unlabeled-name rule required every word in
  the phrase to be individually identifying, so a real first name plus a generic surname part failed
  that check even though the two words together identify one person. Fixed to require only one
  identifying word, matching how every other name rule (label, honorific, relation) already works.
  (2) Ages in free-text documents and FHIR narratives were never banded, only in CSV/JSON: a
  Devanagari discharge note's exact "आयु: 97 वर्ष" (age 97) survived untouched while the same
  patient's registration row correctly showed a 5-year band. Fixed by threading the age-band policy
  into the free-text and FHIR writers. Both of these directly explained most of the local A1/A3/A4
  numbers we previously reported (58.2%/23 candidates) and one real exposure path in the
  "re-identification trap" (very old age + rare disease) cases A5 targets.
- **A5 (targeted attack): 5 of 14 real patients with a known fact (35.7%) are genuinely
  re-identified**, after correcting our local tool for two further measurement gaps: it counted a
  match against a decoy (someone who never visited, which the real evaluator scores separately as
  a membership-inference false positive, not a re-identification) the same as a real patient, and it
  never checked that the matched profile was actually the *right* person -- 5 of the raw 11 "matches"
  turned out to be a different real patient's profile coincidentally sharing the same hospital and a
  common condition or date. Of the 5 genuine hits, 2 are the sharpest case (a rare disease -- rabies,
  kala-azar -- shared by only 1 profile each in the whole dataset; both now also get the correct
  90+ age band after the fix above) and 3 are hospital+condition matches where the condition is
  common but the combination still narrows to one profile in this dataset's size. The hospital name
  is kept intentionally as clinical, non-identifying data; coarsening it further, or suppressing
  rare diagnosis text, would cost real clinical-utility points for an unverified privacy gain --
  we tried a blanket version of the latter earlier and reverted it after it damaged a non-patient
  reference document and flagged a common procedure as rare with no measured benefit. This remains
  the single largest known privacy gap, now accurately sized rather than inflated.
- Our held-out data was generated by the detector's author, so it is a weaker test than third-party data.
- Multi-patient FHIR Bundles are quarantined, not partitioned.
- No encryption of data at rest: by design there is none to encrypt, since candidates are held in
  memory and published by a single directory rename (see §3 Security). A `temp_key` subkey is derived
  and reserved for a future on-disk staging step, unused today.
