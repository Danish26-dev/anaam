"""In-memory candidate release files and atomic-per-file publication.

Writers produce CandidateFile objects without touching `sanitized/`. Danish's independent
verifier can inspect the candidate list before `publish_candidates` is called. The current
pipeline publishes only after every input file has rendered successfully.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil


@dataclass(frozen=True)
class CandidateFile:
    relative_path: str
    content: bytes
    format: str


def text_candidate(relative_path: str, text: str, format_name: str) -> CandidateFile:
    return CandidateFile(relative_path=relative_path, content=text.encode("utf-8"), format=format_name)


def _validated_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("unsafe_candidate_output_path")
    return path


def publish_candidates(sanitized_dir: Path, candidates: list[CandidateFile]) -> None:
    """Publish a fully rendered candidate set in deterministic path order."""
    by_path: dict[str, CandidateFile] = {}
    for candidate in candidates:
        normalized = _validated_relative_path(candidate.relative_path).as_posix()
        if normalized in by_path:
            raise ValueError("duplicate_candidate_output_path")
        by_path[normalized] = candidate

    staging_dir = sanitized_dir.parent / ".anaam-candidate-staging"
    if sanitized_dir.exists() or staging_dir.exists():
        raise ValueError("candidate_publish_target_not_empty")

    staging_dir.mkdir(parents=True, exist_ok=False)
    try:
        for relative_path in sorted(by_path):
            candidate = by_path[relative_path]
            destination = staging_dir / Path(*PurePosixPath(relative_path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(candidate.content)
        # Directory rename publishes the complete candidate tree at once.
        staging_dir.replace(sanitized_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def _fhir_references_resolve(bundle: dict) -> bool:
    entries = bundle.get("entry", []) if isinstance(bundle, dict) else []
    full_urls = {
        entry.get("fullUrl")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("fullUrl"), str)
    }
    typed_ids = {
        (resource.get("resourceType"), str(resource.get("id")))
        for entry in entries
        if isinstance(entry, dict)
        and isinstance((resource := entry.get("resource")), dict)
        and resource.get("resourceType")
        and resource.get("id") is not None
    }

    def walk(value: object) -> bool:
        if isinstance(value, dict):
            reference = value.get("reference")
            if isinstance(reference, str):
                if reference.startswith("urn:") and reference not in full_urls:
                    return False
                if (
                    "/" in reference
                    and not reference.startswith(("http://", "https://", "urn:"))
                ):
                    resource_type, identifier = reference.rsplit("/", 1)
                    resource_type = resource_type.rsplit("/", 1)[-1]
                    if (resource_type, identifier) not in typed_ids:
                        return False
            return all(walk(child) for child in value.values())
        if isinstance(value, list):
            return all(walk(child) for child in value)
        return True

    return walk(bundle)


def validate_candidate_structures(candidates: list[CandidateFile]) -> None:
    """Run format-structural checks before any candidate reaches sanitized/."""
    import csv
    import io
    import json

    for candidate in candidates:
        try:
            text = candidate.content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("candidate_not_utf8") from exc

        if candidate.format in ("csv", "tsv"):
            delimiter = "\t" if candidate.format == "tsv" else ","
            try:
                list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
            except csv.Error as exc:
                raise ValueError("candidate_csv_invalid") from exc
        elif candidate.format in ("json", "fhir"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("candidate_json_invalid") from exc
            if candidate.format == "fhir":
                if not isinstance(data, dict) or data.get("resourceType") != "Bundle":
                    raise ValueError("candidate_fhir_not_bundle")
                if not _fhir_references_resolve(data):
                    raise ValueError("candidate_fhir_reference_unresolved")
