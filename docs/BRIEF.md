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
  hashes; a single bad file is quarantined alone.

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
| personal data leaked (overall / Hindi / Hinglish), `check_dev.py` | 0.0% / 0.0% / 0.0% (0 of 3,230); 0 of 4 canaries |
| leaked by hiding place (file name, base64, metadata, key, header) | 0.0% each |
| medical values kept | 100% (4,855 of 4,855) |
| linking precision / recall / F0.5 | 0.97 / 0.84 / 0.94 (1 wrong merge) |
| re-identification risk (local attack lab, unprotected copy → Anaam) | A1 direct exposure 33.8% → 4.6%; A3 records with any registry candidate 708 → 301 of 817 (top-candidate share among them 0.67 → 0.68); A4 profiles 57.7% → 51.7%; A5 global shift recoverable → not recoverable; A6 inversion 0%; A7 stable pseudonyms and dates 0% |
| run time / peak memory (Linux, 200 files) | 16.5 s / 48 MB |
| on data we did not tune on (2 sealed seeds) | 1 of 826 PII pieces visible (0.1%), medical 302 of 302; linking not measured; CSV/TSV records got no pseudonym |

We keep villages and exact PINs where a group is large enough, because the scoring rewards truthful
location detail, and we shift rather than remove dates, so stays and intervals stay exact. The price
is the A4 figure: profiles pooled across visits are still distinctive. Stricter group sizes (10 or 20)
and 10-year bands did not lower it, so the remaining risk is in other combined evidence (visit dates,
diagnoses, hospital), not in band width. Ages in combined "39/M" cells are now banded too.

## 6. Known limitations

- **Linking on unseen formats:** CSV/TSV records got no pseudonym on the held-out seeds. The pipeline
  embeds one only where its header table recognises the identity column, although the engine's
  classifier identifies those columns. Linking accuracy there is unmeasured (no patient labels).
- **A4 profile re-identification at 51.7%** needs record-level generalisation of rare diagnoses and
  coarser visit dates for small profiles. Tracing the matches suggests a large share come from the
  attacker's house-number signal hitting ordinary clinical numbers (18.7% with that signal excluded,
  a diagnostic only). **A5** matches more known facts on our release (11 of 18) than on an
  unprotected copy (5 of 18): linked pseudonyms let an attacker pool facts per patient.
- Our held-out data was generated by the detector's author, so it is a weaker test than third-party data.
- Multi-patient FHIR Bundles are quarantined, not partitioned. Encryption of intermediate data at rest
  is not implemented; candidates stay in memory until a staging folder is written and renamed into place.
