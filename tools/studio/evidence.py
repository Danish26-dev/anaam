"""Build the measured-evidence file the Release Studio shows (practice data, local only).

    python tools/studio/evidence.py --kit ../Secret-Wards-ToolKit [--holdout]

Runs the real CLI (`main.py`) on the Team Kit practice data, then the kit's own checkers
(`validate_output.py`, `check_dev.py`) and the local attack lab (A1, A3, A4, A5 on the
protected release AND on an unprotected copy of the same inputs, A6, A7). With `--holdout`
it also runs the sealed chaos seeds. Writes `out/studio/evidence.json`.

The file holds counts, rates and labels only: no names, identifiers or record text. It is
written under `out/` (git-ignored) because it is derived from practice data; it is never
committed. RAKSHA_SECRET values used here are never written anywhere.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tools.attack_lab.a1_direct import run_a1  # noqa: E402
from tools.attack_lab.a3_linkage import run_a3  # noqa: E402
from tools.attack_lab.a4_profiles import run_a4  # noqa: E402
from tools.attack_lab.a5_targeted import run_a5  # noqa: E402
from tools.attack_lab.common import load_known_facts, load_registry  # noqa: E402
from tools.attack_lab.load_release import load_release_records  # noqa: E402
from verify.clinical import protected_multiset  # noqa: E402

PY = sys.executable
WORK = ROOT / "out" / "studio" / "evidence"


def _run(args: list[str], secret: str | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("RAKSHA_SECRET", None)
    if secret is not None:
        env["RAKSHA_SECRET"] = secret
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _fresh(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    return path


def run_pipeline(inp: Path, out: Path, secret: str) -> dict:
    t0 = dt.datetime.now()
    proc = _run([PY, "main.py", "--input", str(inp), "--output", str(_fresh(out))], secret)
    last = (proc.stdout.strip().splitlines() or [""])[-1]
    return {"exit_code": proc.returncode, "summary": last if proc.returncode == 0 else "failed",
            "wall_seconds": round((dt.datetime.now() - t0).total_seconds(), 2)}


def validate(kit: Path, inp: Path, out: Path) -> dict:
    proc = _run([PY, str(kit / "validate_output.py"), "--input", str(inp), "--output", str(out)])
    text = proc.stdout + proc.stderr
    return {"contract_ok": "CONTRACT OK" in text,
            "errors": sum(1 for ln in text.splitlines() if ln.strip().startswith("ERROR")),
            "warnings": sum(1 for ln in text.splitlines() if ln.strip().startswith("WARN"))}


def _pct(s: str) -> float:
    return float(s.strip().rstrip("%"))


def check_dev(kit: Path, out: Path, truth: Path) -> dict:
    """Parse the kit checker's summary (counts and rates only; --show 0 prints no values)."""
    proc = _run([PY, str(kit / "check_dev.py"), "--output", str(out), "--truth", str(truth), "--show", "0"])
    text = proc.stdout
    res: dict = {"available": proc.returncode == 0}
    if m := re.search(r"PERSONAL DATA: (\d+) of (\d+) pieces still visible \(\s*([\d.]+)%", text):
        res["pii"] = {"visible": int(m[1]), "total": int(m[2]), "rate": float(m[3])}
    res["pii_by_category"] = [
        {"category": m[1], "visible": int(m[2]), "total": int(m[3])}
        for m in re.finditer(r"^\s+([A-Z_]+)\s+leaked\s+(\d+) / (\d+)", text, re.M)]
    if m := re.search(r"by language: (.+)", text):
        res["pii_by_language"] = {k.strip(): _pct(v) for k, v in (p.split() for p in m[1].split(","))}
    if m := re.search(r"by hiding place: (.+)", text):
        res["pii_by_channel"] = {k.strip(): _pct(v) for k, v in (p.split() for p in m[1].split(","))}
    if m := re.search(r"CANARIES: (\d+) of (\d+)", text):
        res["canaries"] = {"found": int(m[1]), "total": int(m[2])}
    if m := re.search(r"MEDICAL DATA KEPT: (\d+) of (\d+)", text):
        res["medical"] = {"kept": int(m[1]), "total": int(m[2])}
    if m := re.search(r"precision ([\d.]+), recall ([\d.]+), F0\.5 ([\d.]+).*?different people: (\d+)", text):
        res["linking"] = {"precision": float(m[1]), "recall": float(m[2]), "f05": float(m[3]),
                          "wrong_merges": int(m[4])}
    if m := re.search(r"RAW COPIES: (\d+)", text):
        res["raw_copies"] = int(m[1])
    return res


def _sha_index(inp: Path) -> dict[str, Path]:
    return {hashlib.sha256(p.read_bytes()).hexdigest(): p for p in inp.rglob("*") if p.is_file()}


def build_raw_release(inp: Path, protected: Path, raw: Path) -> None:
    """An unprotected copy of the same inputs with the same record locators: the attack
    baseline. Local only, under out/."""
    _fresh(raw)
    report = json.loads((protected / "report.json").read_text(encoding="utf-8"))
    by_sha = _sha_index(inp)
    out_to_in: dict[str, str] = {}
    for f in report["files"]:
        if f.get("status") == "sanitized" and f.get("output") and f["input_sha256"] in by_sha:
            src = by_sha[f["input_sha256"]]
            rel = src.relative_to(inp).as_posix()
            dest = raw / "sanitized" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            out_to_in[f["output"]] = f"sanitized/{rel}"
    lines = []
    for line in (protected / "records.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            if e["file"] in out_to_in:
                lines.append(json.dumps({"file": out_to_in[e["file"]], "loc": e["loc"], "patient": None}))
    (raw / "records.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def attacks(release: Path, attacker: Path) -> dict:
    registry = load_registry(attacker / "registry.csv")
    facts = load_known_facts(attacker / "known_facts.jsonl")
    records = load_release_records(release)
    a1, a3 = run_a1(records, registry), run_a3(records, registry)
    a4, a5 = run_a4(records, registry), run_a5(records, facts, registry)
    return {
        "records": len(records),
        "A1": {"exposed": len(a1.exposed_rids), "total": a1.total_people, "rate": round(a1.exposure_rate, 4)},
        "A3": {"mean_top_candidate_share": round(a3.mean_top_candidate_share, 4),
               "records_with_candidate": a3.records_with_any_candidate, "total": a3.total_records},
        "A4": {"reidentified": a4.profiles_reidentified, "total": a4.total_profiles,
               "rate": round(a4.reidentification_rate, 4)},
        "A5": {"found": a5.found_known_facts, "total": a5.total_known_facts,
               "rate": round(a5.targeted_success_rate, 4), "global_shift_recoverable": a5.global_shift_recoverable},
    }


def a6(protected: Path, truth: Path) -> dict:
    proc = _run([PY, "tools/attack_lab/run_inversion.py", "--output", str(protected), "--truth", str(truth)])
    checked = re.search(r"patients checked.*?: (\d+)", proc.stdout)
    inv = re.search(r"invertible pseudonym\s*: (\d+)", proc.stdout)
    return {"checked": int(checked[1]) if checked else None, "invertible": int(inv[1]) if inv else None}


def a7(protected: Path, inp: Path) -> dict:
    other = WORK / "protected_other_secret"
    run_pipeline(inp, other, secrets.token_hex(16))   # a different secret, never stored
    proc = _run([PY, "tools/attack_lab/run_cross_release.py", "--release-a", str(protected), "--release-b", str(other)])
    get = lambda rx: (m := re.search(rx, proc.stdout)) and m[1]  # noqa: E731
    shutil.rmtree(other, ignore_errors=True)
    return {"pairs": int(get(r"record pairs compared\s*: (\d+)") or 0),
            "stable_pseudonyms": int(get(r"stable pseudonyms across runs\s*: (\d+)") or 0),
            "stable_dates": int(get(r"stable dates across runs\s*: (\d+)") or 0),
            "risk_rate": float(get(r"A7 risk \(max of the two\)\s*: ([\d.]+)%") or 0) / 100}


def clinical_by_category(inp: Path, protected: Path) -> list[dict]:
    """Protected clinical values per category before and after, matched by input hash."""
    report = json.loads((protected / "report.json").read_text(encoding="utf-8"))
    by_sha = _sha_index(inp)
    before, after = Counter(), Counter()
    for f in report["files"]:
        if f.get("status") != "sanitized" or f["input_sha256"] not in by_sha:
            continue
        src = by_sha[f["input_sha256"]].read_text(encoding="utf-8", errors="replace")
        dst = (protected / f["output"]).read_text(encoding="utf-8", errors="replace")
        b, a = protected_multiset(src), protected_multiset(dst)
        for key, n in b.items():
            before[key[0]] += n
            after[key[0]] += min(n, a.get(key, 0))
    return [{"category": k, "before": before[k], "kept": after[k]} for k in sorted(before)]


def inventory(protected: Path) -> dict:
    report = json.loads((protected / "report.json").read_text(encoding="utf-8"))
    records = [json.loads(x) for x in (protected / "records.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    per_file = Counter(r["file"] for r in records)
    clusters: dict[str, list[str]] = {}
    for r in records:
        if r.get("patient"):
            clusters.setdefault(r["patient"], []).append(r["file"])
    files = [{"output": f.get("output"), "status": f["status"], "reason": f.get("reason"),
              "input_sha256_prefix": f["input_sha256"][:12],
              "records": per_file.get(f.get("output") or "", 0),
              "format": Path(f["output"]).suffix.lstrip(".") if f.get("output") else None}
             for f in report["files"]]
    sizes = Counter(len(v) for v in clusters.values())
    return {"report_counts": report.get("counts", {}), "timing": report.get("timing", {}),
            "resources": report.get("resources", {}), "files": files,
            "clusters": {"total": len(clusters), "size_histogram": {str(k): v for k, v in sorted(sizes.items())},
                         "multi_file": sum(1 for v in clusters.values() if len(set(v)) > 1)}}


def holdout(kit: Path, seed: str) -> dict:
    base = WORK / seed
    gen = _run([PY, "tools/chaos/generate.py", "--seed", seed, "--out", str(_fresh(base)), "--n", "60"])
    if gen.returncode != 0:
        return {"seed": seed, "available": False}
    run = run_pipeline(base / "input", base / "run", secrets.token_hex(16))
    res = {"seed": seed, "pipeline": run, "contract": validate(kit, base / "input", base / "run"),
           "check_dev": check_dev(kit, base / "run", base / "truth" / "truth.json")}
    return res


def git_commit() -> str | None:
    proc = _run(["git", "rev-parse", "--short", "HEAD"])
    return proc.stdout.strip() or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", default=str(ROOT.parent / "Secret-Wards-ToolKit"))
    ap.add_argument("--holdout", action="store_true", help="also run the sealed chaos seeds")
    a = ap.parse_args()
    kit = Path(a.kit).resolve()
    inp, truth, attacker = kit / "dev" / "input", kit / "dev" / "truth" / "truth.json", kit / "dev" / "attacker"
    if not inp.is_dir():
        print("ERROR kit_not_found", file=sys.stderr)
        return 2
    WORK.mkdir(parents=True, exist_ok=True)
    protected, raw = WORK / "protected", WORK / "raw_baseline"

    ev: dict = {"schema": "anaam-evidence/1", "source": "practice",
                "source_label": "Team Kit practice data (dev/input), measured locally",
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "git_commit": git_commit(),
                "notes": ["Local measurements, not official or hidden-dataset scores.",
                          "Attack results come from the project's attack lab, an approximation of the kit's ATTACKS.md."]}
    print("pipeline ...", flush=True)
    ev["pipeline"] = run_pipeline(inp, protected, "practice")
    if ev["pipeline"]["exit_code"] != 0:
        print("ERROR pipeline_failed", file=sys.stderr)
        return 1
    ev["contract"] = validate(kit, inp, protected)
    print("check_dev ...", flush=True)
    ev["check_dev"] = check_dev(kit, protected, truth)
    ev["inventory"] = inventory(protected)
    ev["clinical_by_category"] = clinical_by_category(inp, protected)
    print("attacks ...", flush=True)
    build_raw_release(inp, protected, raw)
    ev["attacks"] = {"protected": attacks(protected, attacker), "unprotected_baseline": attacks(raw, attacker),
                     "A6": a6(protected, truth), "A7": a7(protected, inp)}
    shutil.rmtree(raw, ignore_errors=True)          # the baseline is a raw copy: do not keep it
    if a.holdout:
        print("holdout ...", flush=True)
        ev["holdout"] = [holdout(kit, s) for s in ("holdout-1", "holdout-2")]
    dest = ROOT / "out" / "studio" / "evidence.json"
    dest.write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    print(dest.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
