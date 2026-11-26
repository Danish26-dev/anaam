#!/usr/bin/env python3
"""A6 runner: pseudonym inversion, checked against the practice answer key.

Builds, per true patient (PT id in dev/truth/truth.json):
  * a set of "original" strings: every entity surface truth.json records for that
    patient with a critical identifier type (MRN/UHID, AADHAAR, ABHA_NUMBER, PAN, PHONE)
    plus the patient's full name;
  * the pseudonym Anaam actually assigned, read back from records.jsonl by matching each
    truth (file, loc) unit to the exported (file, loc) manifest entry.

Then runs a6_inversion.run_a6 to see whether any assigned pseudonym equals, prefixes, or
embeds a transform of its own patient's originals.

Usage:
    python tools/attack_lab/run_inversion.py --output my_output --truth dev/truth/truth.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from tools.attack_lab.a6_inversion import run_a6  # noqa: E402

_CRITICAL_ID_TYPES = {"MRN", "AADHAAR", "ABHA_NUMBER", "PAN", "PHONE"}


def _load_truth(truth_path: Path) -> dict:
    return json.loads(truth_path.read_text(encoding="utf-8"))


def _build_patient_originals(truth: dict) -> dict[str, list[str]]:
    originals: dict[str, set[str]] = {}
    for file_path, file_truth in truth.get("files", {}).items():
        for loc, unit in file_truth.get("units", {}).items():
            patient = unit.get("patient")
            if not patient:
                continue
            bucket = originals.setdefault(patient, set())
            for entity in unit.get("entities", []):
                if entity.get("type") == "PATIENT_NAME" or entity.get("type") in _CRITICAL_ID_TYPES:
                    surface = entity.get("surface")
                    if surface:
                        bucket.add(surface)
    return {k: sorted(v) for k, v in originals.items()}


def _build_truth_unit_lookup(truth: dict) -> dict[tuple[str, str], str]:
    """Maps (input relative file path, input loc) -> true patient id, so we can match a
    records.jsonl entry (which carries the OUTPUT file path and the INPUT `loc`) back to
    truth by `loc` plus the original relative path encoded in the sanitized/ mirror.
    """
    lookup: dict[tuple[str, str], str] = {}
    for file_path, file_truth in truth.get("files", {}).items():
        for loc, unit in file_truth.get("units", {}).items():
            patient = unit.get("patient")
            if patient:
                lookup[(file_path, loc)] = patient
    return lookup


def _load_manifest(output_dir: Path) -> list[dict]:
    entries = []
    manifest_path = output_dir / "records.jsonl"
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def _build_pseudonym_by_patient(manifest: list[dict], unit_lookup: dict[tuple[str, str], str]) -> dict[str, str]:
    """For each manifest entry, strip the "sanitized/" prefix to recover the original
    relative path, look up the true patient for that (path, loc), and record the
    pseudonym Anaam assigned. If a patient's records disagree on pseudonym (should not
    happen if clustering is correct), the first one encountered wins and a warning is
    printed -- that disagreement itself is useful signal, not something to hide.
    """
    result: dict[str, str] = {}
    conflicts = 0
    for entry in manifest:
        file_path = entry["file"]
        if file_path.startswith("sanitized/"):
            file_path = file_path[len("sanitized/"):]
        loc = entry.get("loc")
        true_patient = unit_lookup.get((file_path, loc))
        pseudonym = entry.get("patient")
        if not true_patient or not pseudonym:
            continue
        if true_patient in result and result[true_patient] != pseudonym:
            conflicts += 1
            continue
        result[true_patient] = pseudonym
    if conflicts:
        print(f"NOTE: {conflicts} manifest entries disagreed with an already-recorded "
              f"pseudonym for the same true patient (inconsistent linking).", file=sys.stderr)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Anaam local attacker simulator (A6)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--truth", default="dev/truth/truth.json")
    args = ap.parse_args()

    truth = _load_truth(Path(args.truth))
    patient_originals = _build_patient_originals(truth)
    unit_lookup = _build_truth_unit_lookup(truth)
    manifest = _load_manifest(Path(args.output))
    pseudonym_by_patient = _build_pseudonym_by_patient(manifest, unit_lookup)

    result = run_a6(patient_originals, pseudonym_by_patient)

    print("=" * 64)
    print(" LOCAL ATTACK MEASUREMENT -- NOT the official score".center(64))
    print(" A6: pseudonym inversion (unkeyed-hash / transform dictionary attack)")
    print("=" * 64)
    print(f"patients checked (had an assigned pseudonym) : {len(pseudonym_by_patient)} "
          f"of {result.total_patients_checked} known truth patients")
    print(f"patients with an invertible pseudonym          : {len(result.inverted_patients)} "
          f"({result.inversion_rate:.1%}) -- should be 0%")
    if result.inverted_patients:
        print(f"  inverted: {', '.join(result.inverted_patients[:10])}"
              f"{' ...' if len(result.inverted_patients) > 10 else ''}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
