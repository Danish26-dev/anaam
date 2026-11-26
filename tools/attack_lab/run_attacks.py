#!/usr/bin/env python3
"""O11: local attacker simulator runner.

Reads dev/attacker/* (practice-only) and a release folder, runs A1/A3/A5, and prints a
clearly-labeled LOCAL MEASUREMENT report. Never used during `run` and never reads
anything the real evaluator would consider hidden truth for the hidden datasets --
dev/attacker/* ships only in the kit, for practice-data self-testing.

Usage:
    python tools/attack_lab/run_attacks.py --output my_output --attacker dev/attacker
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from tools.attack_lab.a1_direct import run_a1  # noqa: E402
from tools.attack_lab.a3_linkage import run_a3  # noqa: E402
from tools.attack_lab.a4_profiles import run_a4  # noqa: E402
from tools.attack_lab.a5_targeted import run_a5  # noqa: E402
from tools.attack_lab.common import load_known_facts, load_registry  # noqa: E402
from tools.attack_lab.load_release import load_release_records  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Anaam local attacker simulator (A1/A3/A4/A5)")
    ap.add_argument("--output", required=True, help="path to a produced {output} directory")
    ap.add_argument("--attacker", default="dev/attacker", help="path to dev/attacker (practice only)")
    args = ap.parse_args()

    output_dir = Path(args.output)
    attacker_dir = Path(args.attacker)

    registry = load_registry(attacker_dir / "registry.csv")
    known_facts = load_known_facts(attacker_dir / "known_facts.jsonl")
    records = load_release_records(output_dir)

    a1 = run_a1(records, registry)
    a3 = run_a3(records, registry)
    a4 = run_a4(records, registry)
    a5 = run_a5(records, known_facts, registry)

    print("=" * 64)
    print(" LOCAL ATTACK MEASUREMENT -- NOT the official score".center(64))
    print(" (approximation of docs/ATTACKS.md A1/A3/A4/A5, for dev feedback only)")
    print("=" * 64)
    print(f"records loaded from release : {len(records)}")
    print()
    print(f"A1 direct exposure           : {len(a1.exposed_rids)} / {a1.total_people} "
          f"people ({a1.exposure_rate:.1%})")
    print(f"A3 mean top-candidate share  : {a3.mean_top_candidate_share:.3f} "
          f"(records with >=1 candidate: {a3.records_with_any_candidate}/{a3.total_records})")
    print(f"A4 profiles re-identified    : {a4.profiles_reidentified} / {a4.total_profiles} "
          f"({a4.reidentification_rate:.1%})")
    print(f"A5 targeted facts found      : {a5.found_known_facts} / {a5.total_known_facts} "
          f"({a5.targeted_success_rate:.1%})")
    if a5.global_shift_recoverable:
        print(f"A5 GLOBAL SHIFT RECOVERABLE  : offset={a5.recovered_offset_days} days "
              f"-- date shifting is NOT per-patient, fix this before submitting")
    else:
        print("A5 global shift recovery     : not recoverable (good -- shifts look per-patient)")
    print("=" * 64)
    print("Run tools/attack_lab/run_cross_release.py separately for A7 (needs two releases).")
    print("Run tools/attack_lab/run_inversion.py separately for A6 (needs dev/truth/truth.json).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
