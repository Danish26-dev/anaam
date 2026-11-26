"""Record the Release Studio's SYNTHETIC DEMO fixture from a real run of the CLI.

    python tools/studio/record_demo.py [--kit ../Secret-Wards-ToolKit]

1. writes the synthetic demo dataset (tools/studio/demo_data.py; every value invented);
2. runs the unchanged `main.py` on it with a fixed, published demo secret;
3. computes the same release summary the local server computes (server.assurance);
4. saves frontend/src/fixtures/demo-release.json, plus before/after text for the landing page.

The fixture is engine output on invented data, so it is safe to commit. It is labelled
SYNTHETIC DEMO everywhere it is shown.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "studio"))
sys.path.insert(0, str(ROOT / "src"))

import demo_data  # noqa: E402
import server  # noqa: E402

DEMO_SECRET = "anaam-synthetic-demo"   # published on purpose: demo data only


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", default=str(ROOT.parent / "Secret-Wards-ToolKit"))
    a = ap.parse_args()
    work = ROOT / "out" / "studio" / "demo"
    inp, out = work / "input", work / "output"
    if work.exists():
        shutil.rmtree(work)
    demo_data.build(inp)
    env = dict(os.environ, RAKSHA_SECRET=DEMO_SECRET, PYTHONIOENCODING="utf-8")
    t0 = dt.datetime.now()
    proc = subprocess.run([sys.executable, "main.py", "--input", str(inp), "--output", str(out)], cwd=ROOT,
                          env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print("ERROR pipeline_failed", file=sys.stderr)
        return 1
    kit = Path(a.kit)
    server.STATE["kit"] = kit.resolve() if (kit / "validate_output.py").is_file() else None
    server.STATE["secret"] = DEMO_SECRET
    summary = {
        "id": "synthetic-demo", "source": "demo",
        "label": "Synthetic demo workspace: 3 fictional hospitals, 5 invented patients",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "status": "complete",
        "files_uploaded": sum(1 for p in inp.rglob("*") if p.is_file()),
        "pipeline": {"exit_code": 0, "seconds": round((dt.datetime.now() - t0).total_seconds(), 2),
                     "message": proc.stdout.strip().splitlines()[-1]},
        "assurance": server.assurance(inp, out, True),
    }
    # input names are shown in demo mode only: they are synthetic and help explain the demo
    import hashlib
    names = {hashlib.sha256(p.read_bytes()).hexdigest(): p.relative_to(inp).as_posix() for p in inp.rglob("*") if p.is_file()}
    for f in summary["assurance"]["files"]:
        f["input_name"] = names.get(f["input_sha256"])
    pairs = []
    for f in summary["assurance"]["files"]:
        if f["status"] == "sanitized" and f["input_name"] and f["input_name"].endswith((".txt", ".csv")):
            pairs.append({"input_name": f["input_name"], "output": f["output"],
                          "before": (inp / f["input_name"]).read_text(encoding="utf-8"),
                          "after": (out / f["output"]).read_text(encoding="utf-8")})
    summary["examples"] = pairs
    dest = ROOT / "frontend" / "src" / "fixtures" / "demo-release.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    # the same synthetic files, for the Studio's "Load synthetic demo files" action
    pub = ROOT / "frontend" / "public" / "demo-input"
    if pub.exists():
        shutil.rmtree(pub)
    shutil.copytree(inp, pub)
    index = sorted(p.relative_to(pub).as_posix() for p in pub.rglob("*") if p.is_file())
    (pub / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    a_ = summary["assurance"]
    print(dest.relative_to(ROOT).as_posix(), "|", summary["pipeline"]["message"], "| verdict", a_["status"],
          "| residual", a_["residual"], "| clinical", a_["clinical"]["kept"], "/", a_["clinical"]["before"],
          "| patients", a_["identity"]["patients"], "linked", a_["identity"]["linked_records"], "/", a_["identity"]["records"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
