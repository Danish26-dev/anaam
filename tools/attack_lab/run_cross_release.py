#!/usr/bin/env python3
"""A7 runner: compares two releases of the same input produced with different secrets.

Usage:
    $env:RAKSHA_SECRET="secretA"; python main.py --input dev/input --output releaseA
    $env:RAKSHA_SECRET="secretB"; python main.py --input dev/input --output releaseB
    python tools/attack_lab/run_cross_release.py --release-a releaseA --release-b releaseB
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from tools.attack_lab.a7_cross_release import run_a7  # noqa: E402
from tools.attack_lab.load_release import load_release_records  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Anaam local attacker simulator (A7)")
    ap.add_argument("--release-a", required=True)
    ap.add_argument("--release-b", required=True)
    args = ap.parse_args()

    records_a = load_release_records(Path(args.release_a))
    records_b = load_release_records(Path(args.release_b))

    result = run_a7(records_a, records_b)

    print("=" * 64)
    print(" LOCAL ATTACK MEASUREMENT -- NOT the official score".center(64))
    print(" A7: cross-release linkability")
    print("=" * 64)
    print(f"record pairs compared         : {result.total_record_pairs_compared}")
    print(f"unmatched release records     : {result.unmatched_records} -- should be 0")
    print(f"stable pseudonyms across runs : {result.stable_pseudonym_pairs} "
          f"({result.pseudonym_stability_rate:.1%}) -- should be ~0%")
    print(f"stable dates across runs      : {result.stable_date_pairs} "
          f"({result.date_stability_rate:.1%}) -- should be ~0%, aside from rare coincidence")
    print(f"A7 risk (max of the two)       : {result.risk:.1%}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
