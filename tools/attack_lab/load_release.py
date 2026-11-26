"""Load a produced release using only attacker-visible output artifacts."""
from __future__ import annotations

import csv
import io
import json
from collections import Counter
from pathlib import Path

from .common import ReleaseRecord


def _flatten_json(obj: object) -> str:
    if isinstance(obj, dict):
        return " ".join(f"{key}: {_flatten_json(value)}" for key, value in obj.items())
    if isinstance(obj, list):
        return " ".join(_flatten_json(value) for value in obj)
    return "" if obj is None else str(obj)


def _source_keys_by_output(output_dir: Path) -> dict[str, str]:
    try:
        report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    occurrences: Counter[str] = Counter()
    result: dict[str, str] = {}
    for entry in report.get("files", []):
        output = entry.get("output")
        sha256 = entry.get("input_sha256")
        if not output or not sha256:
            continue
        occurrence = occurrences[sha256]
        occurrences[sha256] += 1
        result[str(output)] = f"{sha256}:{occurrence}"
    return result


def _record(entry: dict, text: str, source_keys: dict[str, str]) -> ReleaseRecord:
    return ReleaseRecord(
        pseudonym=entry.get("patient"),
        text=text,
        source_key=source_keys.get(entry["file"]),
        file=entry["file"],
        loc=entry.get("loc"),
    )


def _try_json(text: str) -> object | None:
    if not text.lstrip().startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load_release_records(output_dir: Path) -> list[ReleaseRecord]:
    manifest_path = output_dir / "records.jsonl"
    if not manifest_path.exists():
        return []

    entries = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    source_keys = _source_keys_by_output(output_dir)

    by_file: dict[str, list[dict]] = {}
    for entry in entries:
        by_file.setdefault(entry["file"], []).append(entry)

    records: list[ReleaseRecord] = []
    for relative_file, file_entries in by_file.items():
        path = output_dir / relative_file
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        json_data = _try_json(text)

        # Content wins over extension: the challenge includes JSON hidden behind .csv.
        if json_data is not None:
            for entry in file_entries:
                output_locator = entry.get("out") or entry["loc"]
                node = json_data if output_locator == "doc" else _resolve_pointer(json_data, output_locator)
                if node is not None:
                    records.append(_record(entry, _flatten_json(node), source_keys))
            continue

        suffix = path.suffix.lower()
        if suffix in (".csv", ".tsv"):
            delimiter = "\t" if suffix == ".tsv" else ","
            rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
            header, body = (rows[0], rows[1:]) if rows else ([], [])
            for entry in file_entries:
                output_locator = entry.get("out") or entry["loc"]
                if not output_locator.startswith("row:"):
                    continue
                index = int(output_locator.split(":", 1)[1])
                if 0 <= index < len(body):
                    flattened = " ".join(
                        f"{key}: {value}" for key, value in zip(header, body[index])
                    )
                    records.append(_record(entry, flattened, source_keys))
            continue

        records.extend(_record(entry, text, source_keys) for entry in file_entries)

    return records


def _resolve_pointer(data: object, pointer: str) -> object | None:
    if not pointer.startswith("/"):
        return None
    node = data
    for token in pointer.strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            node = node[int(token)] if isinstance(node, list) else node[token]
        except (KeyError, IndexError, ValueError, TypeError):
            return None
    return node
