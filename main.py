#!/usr/bin/env python3
"""Anaam: Secret Wards Track 3 submission entry point.

Owned by Omkar (pipeline backbone). Detection and verification (src/detection, src/verify)
are Danish's scope. This file calls the detection engine through `src/detection/api.py`
(harvest over all files, then per-record detection and identity evidence) and runs the
release gate (`src/verify/release.py`) on every file before publication. Call order and
span policy: docs/INTERFACE_NOTES.md.

Usage: python main.py --input <input dir> --output <empty output dir>
Standard library only, Python 3.10+. RAKSHA_SECRET must be set in the environment.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.errors import ConfigError, IngestError, safe_reason  # noqa: E402
from core.header_roles import find_column  # noqa: E402
from core.network_guard import install_network_guard  # noqa: E402
from core.preflight import run_preflight  # noqa: E402
from core.record_ids import content_anchor  # noqa: E402
from detection.api import (  # noqa: E402
    configure as configure_detection,
    date_order as detection_date_order,
    engine as detection_engine,
    extract_identity_evidence,
    prepare as prepare_detection,
    sanitize_path,
)
from verify.release import FileCandidate, ReleaseGate  # noqa: E402
from export.candidate import (
    CandidateFile,
    publish_candidates,
    text_candidate,
    validate_candidate_structures,
)  # noqa: E402
from export.csv_writer import embeddable_pseudonyms, render_csv  # noqa: E402
from export.fhir_writer import render_fhir_bundle  # noqa: E402
from export.filename_mapper import resolve_output_relative_path  # noqa: E402
from export.json_writer import can_embed_pseudonym, render_json_doc, render_json_records  # noqa: E402
from export.records_manifest import RecordManifestEntry, write_records_jsonl  # noqa: E402
from export.report import FileReportEntry, ReportBuilder, peak_rss_mb  # noqa: E402
from export.text_writer import render_text, render_text_document  # noqa: E402
from identity.clustering import cluster_records  # noqa: E402
from ingest.csv_adapter import (
    build_records as build_csv_records,
    parse_csv,
    sniff_delimiter,
)  # noqa: E402
from ingest.encoding import decode  # noqa: E402
from ingest.fhir_adapter import build_record as build_fhir_record  # noqa: E402
from ingest.inventory import build_inventory, to_file_envelope  # noqa: E402
from ingest.json_adapter import (
    build_records as build_json_records,
    parse_json,
    pointer_escape,
    record_arrays,
)  # noqa: E402
from ingest.sniff import detect_format  # noqa: E402
from ingest.text_adapter import build_record as build_text_record  # noqa: E402
from privacy.apply_generalization import generalize_field_value  # noqa: E402
from privacy.date_shift import build_date_offset_map  # noqa: E402
from privacy.generalize import VillageHierarchy  # noqa: E402
from privacy.json_generalize import (  # noqa: E402
    collect_village_hierarchy_facts,
    find_village_and_district,
    generalize_json_record,
)
from privacy.pseudonyms import build_pseudonym_map  # noqa: E402
from privacy.transform_plans import build_transform_plans, mark_generalized  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Anaam: Secret Wards privacy firewall")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    return ap.parse_args()


_SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".json", ".txt"}


def _record_evidence_text(record) -> str:
    if record.free_text is not None:
        return record.free_text
    return " ".join(
        f"{field.path}: {field.value}"
        for field in record.fields
        if field.value is not None
    )


def _load_policy() -> dict:
    """Tiny `key: value` reader for config/policy.yaml (no PyYAML dependency needed,
    keeping main.py runnable with the standard library only, per the contract).
    """
    policy: dict = {}
    path = Path(__file__).resolve().parent / "config" / "policy.yaml"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" in line:
                k, v = (x.strip() for x in line.split(":", 1))
                policy[k] = int(v) if v.lstrip("-").isdigit() else v
    return policy


POLICY = _load_policy()


def _generalize_csv_rows(
    header: list[str],
    rows: list[list[str]],
    pids_by_row: dict[int, str | None],
    village_hierarchy,
    village_group_size: dict[str, int],
    min_group_size: int,
    age_band_years: int,
    district_group_size: dict[str, int] | None = None,
) -> tuple[list[list[str]], dict[int, list]]:
    """Apply one maximally restrictive compatible O10 plan per patient profile.

    Linked rows share a plan. Each unlinked row gets its own plan instead of inheriting
    the first unlinked person's location policy. If any linked row requires a stricter
    level, every row in that profile receives that stricter level.
    """
    from core.interfaces import FieldNode, FieldTransformation
    from privacy.profile_policy import decide_profile_plan as _decide_plan

    age_col = find_column(header, "age")
    age_sex_col = find_column(header, "age_sex")
    village_col = find_column(header, "village")
    pin_col = find_column(header, "pin")
    tehsil_col = find_column(header, "tehsil")
    district_col = find_column(header, "district")

    if age_col is None and age_sex_col is None and village_col is None and pin_col is None:
        return rows, {}

    district_group_size = district_group_size or {}
    restriction_rank = {"tehsil": 0, "district": 1, "suppress": 2}
    plan_by_profile: dict[str, object] = {}
    profile_key_by_row: dict[int, str] = {}

    for i, row in enumerate(rows):
        pid = pids_by_row.get(i)
        profile_key = f"patient:{pid}" if pid else f"unlinked-row:{i}"
        profile_key_by_row[i] = profile_key
        village = row[village_col] if village_col is not None and village_col < len(row) else None
        district = row[district_col] if district_col is not None and district_col < len(row) else None
        candidate = _decide_plan(
            pseudonym=pid or profile_key,
            group_size_by_village=village_group_size,
            village=village,
            min_group_size=min_group_size,
            age_band_years=age_band_years,
            group_size_by_district=district_group_size,
            district=district,
        )
        current = plan_by_profile.get(profile_key)
        if current is None or restriction_rank[candidate.village_level] > restriction_rank[current.village_level]:
            plan_by_profile[profile_key] = candidate

    out_rows = [list(row) for row in rows]
    transformations_by_row: dict[int, list[FieldTransformation]] = {}
    for i, row in enumerate(out_rows):
        plan = plan_by_profile[profile_key_by_row[i]]
        row_changed = False
        row_transformations: list[FieldTransformation] = []

        if age_col is not None and age_col < len(row):
            field = FieldNode(
                path=f"col:{header[age_col]}", value=row[age_col],
                value_type="str", channel="content", role_hint="age",
            )
            new_value, changed = generalize_field_value(field, plan, village_hierarchy)
            if changed and new_value is not None:
                row[age_col] = new_value
                row_transformations.append(
                    FieldTransformation(
                        path=f"col:{header[age_col]}", action="generalize",
                        replacement=new_value,
                    )
                )
                row_changed = True

        if age_sex_col is not None and age_sex_col < len(row):
            # A combined "<age>/<gender>" cell (real header: "age_sex", e.g. lab result
            # files) -- the age portion is just as identifying as a bare age column and
            # must be banded the same way, keeping the gender suffix truthful.
            field = FieldNode(
                path=f"col:{header[age_sex_col]}", value=row[age_sex_col],
                value_type="str", channel="content", role_hint="age_sex",
            )
            new_value, changed = generalize_field_value(field, plan, village_hierarchy)
            if changed and new_value is not None:
                row[age_sex_col] = new_value
                row_transformations.append(
                    FieldTransformation(
                        path=f"col:{header[age_sex_col]}", action="generalize",
                        replacement=new_value,
                    )
                )
                row_changed = True

        if village_col is not None and village_col < len(row):
            field = FieldNode(
                path=f"col:{header[village_col]}", value=row[village_col],
                value_type="str", channel="content", role_hint="village",
            )
            new_value, changed = generalize_field_value(field, plan, village_hierarchy)
            if changed:
                replacement = new_value or ""
                row[village_col] = replacement
                row_transformations.append(
                    FieldTransformation(
                        path=f"col:{header[village_col]}",
                        action="generalize" if replacement else "suppress",
                        replacement=replacement,
                    )
                )
                row_changed = True

        if pin_col is not None and pin_col < len(row):
            field = FieldNode(
                path=f"col:{header[pin_col]}", value=row[pin_col],
                value_type="str", channel="content", role_hint="pin",
            )
            new_value, changed = generalize_field_value(field, plan, village_hierarchy)
            if changed:
                replacement = new_value or ""
                row[pin_col] = replacement
                row_transformations.append(
                    FieldTransformation(
                        path=f"col:{header[pin_col]}",
                        action="generalize" if replacement else "suppress",
                        replacement=replacement,
                    )
                )
                row_changed = True

        if plan.village_level == "suppress":
            for location_col in (tehsil_col, district_col):
                if location_col is not None and location_col < len(row) and row[location_col]:
                    row[location_col] = ""
                    row_transformations.append(
                        FieldTransformation(
                            path=f"col:{header[location_col]}",
                            action="suppress",
                            replacement="",
                        )
                    )
                    row_changed = True

        if row_changed:
            transformations_by_row[i] = row_transformations

    return out_rows, transformations_by_row


def _decide_json_profile_plan(
    pseudonym: str | None,
    record_item: object,
    village_group_size: dict[str, int],
    district_group_size: dict[str, int],
    min_group_size: int,
    age_band_years: int,
):
    """One O10 profile plan per JSON record, derived from that record's own
    village/district -- mirrors the per-row plan decision `_generalize_csv_rows` makes
    for CSV, so the same "widen, then suppress as a last resort" escalation applies
    identically regardless of input format.
    """
    from privacy.profile_policy import decide_profile_plan as _decide_plan

    village, district = find_village_and_district(record_item)
    profile_key = pseudonym or f"unlinked-json:{id(record_item)}"
    return _decide_plan(
        pseudonym=profile_key,
        group_size_by_village=village_group_size,
        village=village,
        min_group_size=min_group_size,
        age_band_years=age_band_years,
        group_size_by_district=district_group_size,
        district=district,
    )


def _learn_village_hierarchy(hierarchy, header: list[str], row: list[str]) -> None:
    """Learns village -> tehsil/district from any CSV row that has all three columns,
    using the shared header-role table (core.header_roles) -- see
    privacy/apply_generalization.py for why this stays conservative rather than guessing
    on renamed headers.
    """
    village_col = find_column(header, "village")
    tehsil_col = find_column(header, "tehsil")
    district_col = find_column(header, "district")
    village = row[village_col] if village_col is not None and village_col < len(row) else None
    tehsil = row[tehsil_col] if tehsil_col is not None and tehsil_col < len(row) else None
    district = row[district_col] if district_col is not None and district_col < len(row) else None
    if village:
        hierarchy.learn(village, tehsil, district)


def main() -> int:
    install_network_guard()
    args = parse_args()

    try:
        input_root, output_root, keys = run_preflight(args.input, args.output)
    except ConfigError as exc:
        print(f"ERROR {exc.reason_code}", file=sys.stderr)
        return 1

    t0 = time.monotonic()
    sanitized_dir = output_root / "sanitized"
    configure_detection(keys.filename_key)

    inventory = build_inventory(input_root)

    report = ReportBuilder()
    record_manifest: list[RecordManifestEntry] = []
    evidence_by_record: dict = {}
    village_hierarchy = VillageHierarchy()
    # Stash enough per-file state to render after clustering produces pseudonyms.
    pending: list[dict] = []
    file_envelopes = []

    for entry in inventory:
        raw = entry.path.read_bytes()
        file_envelope = to_file_envelope(entry, "unknown", None)
        file_envelopes.append(file_envelope)

        try:
            if not raw.strip():
                raise IngestError("empty_file")
            ext = entry.path.suffix.lower()
            if ext not in _SUPPORTED_EXTENSIONS:
                raise IngestError("unsupported_format")
            text, enc = decode(raw)
            if text is None:
                raise IngestError("undecodable_text")

            fmt = detect_format(text, ext)
            if fmt in ("unsupported", "undecodable_as_text"):
                raise IngestError(fmt)

            out_rel = resolve_output_relative_path(keys.filename_key, entry.relative_path)
            file_envelope.detected_format = fmt
            file_envelope.detected_encoding = enc

            if fmt in ("csv", "tsv"):
                delimiter = "\t" if fmt == "tsv" else sniff_delimiter(text[:2048], ",")
                table = parse_csv(text, delimiter)
                file_envelope.records = build_csv_records(
                    table, entry.sha256, entry.relative_path, format_name=fmt
                )
                for row in table.rows:
                    _learn_village_hierarchy(village_hierarchy, table.header, row)
                pending_item = {
                    "kind": "csv", "entry": entry, "out_rel": out_rel,
                    "table": table, "delimiter": delimiter,
                }
            elif fmt == "json":
                data = parse_json(text)
                file_envelope.records = build_json_records(
                    data, entry.sha256, entry.relative_path
                )
                for village, tehsil, district in collect_village_hierarchy_facts(data):
                    village_hierarchy.learn(village, tehsil, district)
                pending_item = {
                    "kind": "json", "entry": entry, "out_rel": out_rel, "data": data,
                }
            elif fmt == "fhir":
                data = parse_json(text)
                patient_count = sum(
                    1
                    for bundle_entry in data.get("entry", [])
                    if isinstance(bundle_entry, dict)
                    and isinstance(bundle_entry.get("resource"), dict)
                    and bundle_entry["resource"].get("resourceType") == "Patient"
                )
                if patient_count != 1:
                    raise IngestError("fhir_patient_count_unsupported")
                fhir_record, fhir_index = build_fhir_record(
                    data, entry.sha256, entry.relative_path
                )
                file_envelope.records = [fhir_record]
                pending_item = {
                    "kind": "fhir", "entry": entry, "out_rel": out_rel,
                    "data": data, "fhir_index": fhir_index,
                    "raw_evidence_text": text,
                }
            elif fmt == "text":
                file_envelope.records = [
                    build_text_record(text, entry.sha256, entry.relative_path)
                ]
                pending_item = {
                    "kind": "text", "entry": entry, "out_rel": out_rel, "text": text,
                }
            else:
                raise IngestError("unsupported_format")

            pending_item["envelope"] = file_envelope
            pending_item["source_text"] = text  # for the verifier's clinical-loss check
            pending.append(pending_item)

        except (IngestError, UnicodeError, RecursionError) as exc:
            file_envelope.terminal_status = "quarantined"
            reason = safe_reason(exc)
            report.add_file(FileReportEntry(input_sha256=entry.sha256, output=None,
                                             status="quarantined", reason=reason))

    # ---- detection (Danish's engine): harvest over ALL parsed files, then per record ----
    detection_failures = prepare_detection([item["envelope"] for item in pending])
    still_pending = []
    for item in pending:
        envelope = item["envelope"]
        if envelope.input_sha256 in detection_failures:
            envelope.terminal_status = "quarantined"
            report.add_file(FileReportEntry(
                input_sha256=item["entry"].sha256, output=None, status="quarantined",
                reason=detection_failures[envelope.input_sha256],
            ))
            continue
        # File and folder names: the engine removes names and IDs, the mapper then
        # replaces any remaining identifier-shaped component with a keyed token.
        item["out_rel"] = resolve_output_relative_path(
            keys.filename_key, sanitize_path(item["entry"].relative_path)
        )
        for record in envelope.records:
            evidence_by_record[record.record_id] = extract_identity_evidence(record)
        still_pending.append(item)
    pending = still_pending

    # ---- identity resolution (O6/O7) across every record found so far ----
    assignments, _ledger = cluster_records(evidence_by_record)
    pseudonym_map = build_pseudonym_map(keys.pseudonym_key, assignments)
    date_shift_max_days = int(POLICY.get("date_shift_max_days", 180))
    date_offset_map = build_date_offset_map(keys.date_shift_key, assignments, date_shift_max_days)
    all_records = [
        record for envelope in file_envelopes for record in envelope.records
    ]
    transform_plans = build_transform_plans(
        all_records, assignments, pseudonym_map, date_offset_map
    )

    identifiers_detected = 0
    records_generalized = 0
    exported_files: set[str] = set()
    candidates: list[CandidateFile] = []

    # O10 group sizes count distinct patient/content anchors, not raw rows. Exact duplicate
    # files therefore cannot inflate a rare location above the k-anonymity threshold.
    village_members: dict[str, set[str]] = {}
    district_members: dict[str, set[str]] = {}

    def _add_location_member(village: str | None, district: str | None, member_key: str) -> None:
        if village:
            village_members.setdefault(village.strip().lower(), set()).add(member_key)
        if district:
            district_members.setdefault(district.strip().lower(), set()).add(member_key)

    for item in pending:
        records_by_locator = {
            record.locator: record for record in item["envelope"].records
        }

        if item["kind"] == "csv":
            table = item["table"]
            village_col = find_column(table.header, "village")
            district_col = find_column(table.header, "district")
            for row_index, row in enumerate(table.rows):
                record_id = records_by_locator[f"row:{row_index}"].record_id
                pseudonym = transform_plans[record_id].pseudonym
                member_key = f"patient:{pseudonym}" if pseudonym else content_anchor(record_id)
                village = row[village_col] if village_col is not None and village_col < len(row) else None
                district = row[district_col] if district_col is not None and district_col < len(row) else None
                _add_location_member(village, district, member_key)

        elif item["kind"] == "json":
            data = item["data"]
            json_arrays = record_arrays(data)
            if json_arrays:
                for array_key, array in json_arrays:
                    escaped_key = pointer_escape(array_key)
                    for i, record_item in enumerate(array):
                        locator = f"/{escaped_key}/{i}"
                        record_id = records_by_locator[locator].record_id
                        pseudonym = transform_plans[record_id].pseudonym
                        member_key = f"patient:{pseudonym}" if pseudonym else content_anchor(record_id)
                        village, district = find_village_and_district(record_item)
                        _add_location_member(village, district, member_key)
            else:
                record_id = records_by_locator["doc"].record_id
                pseudonym = transform_plans[record_id].pseudonym
                member_key = f"patient:{pseudonym}" if pseudonym else content_anchor(record_id)
                village, district = find_village_and_district(data)
                _add_location_member(village, district, member_key)

    village_group_size = {key: len(members) for key, members in village_members.items()}
    district_group_size = {key: len(members) for key, members in district_members.items()}

    min_group_size = int(POLICY.get("min_group_size", 5))
    age_band_years_for_plans = int(POLICY.get("age_band_years", 5))

    # One O10 plan per JSON profile (pseudonym, or else per-record when unlinked), taking
    # the MOST restrictive village_level seen across every record in that profile -- the
    # same "one profile, one compatible plan" rule _generalize_csv_rows applies to CSV.
    _restriction_rank = {"tehsil": 0, "district": 1, "suppress": 2}
    json_plan_by_profile: dict[str, object] = {}
    for item in pending:
        if item["kind"] != "json":
            continue
        records_by_locator = {
            record.locator: record for record in item["envelope"].records
        }
        data = item["data"]
        json_arrays = record_arrays(data)
        record_items: list[tuple[str, object]] = (
            [
                (f"/{pointer_escape(array_key)}/{i}", record_item)
                for array_key, array in json_arrays
                for i, record_item in enumerate(array)
            ]
            if json_arrays
            else [("doc", data)]
        )
        for locator, record_item in record_items:
            record_id = records_by_locator[locator].record_id
            pseudonym = transform_plans[record_id].pseudonym
            profile_key = pseudonym or f"unlinked-json:{record_id}"
            candidate_plan = _decide_json_profile_plan(
                pseudonym, record_item, village_group_size, district_group_size,
                min_group_size, age_band_years_for_plans,
            )
            current = json_plan_by_profile.get(profile_key)
            if (
                current is None
                or _restriction_rank[candidate_plan.village_level]
                > _restriction_rank[current.village_level]
            ):
                json_plan_by_profile[profile_key] = candidate_plan
    age_band_years = int(POLICY.get("age_band_years", 5))

    for item in pending:
        entry = item["entry"]
        out_rel = item["out_rel"]
        envelope = item["envelope"]
        records_by_locator = {
            record.locator: record for record in envelope.records
        }
        manifest_before = len(record_manifest)
        candidates_before = len(candidates)
        generalized_before = records_generalized
        identifiers_before = identifiers_detected

        try:
            if item["kind"] == "csv":
                table = item["table"]
                pids_by_row = {
                    i: transform_plans[records_by_locator[f"row:{i}"].record_id].pseudonym
                    for i in range(len(table.rows))
                }
                pids_by_row = embeddable_pseudonyms(
                    table.header, table.rows, pids_by_row, envelope.input_sha256
                )
                offsets_by_row = {
                    i: transform_plans[records_by_locator[f"row:{i}"].record_id].date_offset_days
                    for i in range(len(table.rows))
                }
                generalized_rows, transformations_by_row = _generalize_csv_rows(
                    table.header, table.rows, pids_by_row, village_hierarchy,
                    village_group_size, min_group_size, age_band_years,
                    district_group_size=district_group_size,
                )
                records_generalized += len(transformations_by_row)
                for i in range(len(table.rows)):
                    plan = transform_plans[records_by_locator[f"row:{i}"].record_id]
                    plan.pseudonym = pids_by_row[i]
                    row_transformations = transformations_by_row.get(i, [])
                    plan.field_transformations.extend(row_transformations)
                    if row_transformations:
                        mark_generalized(plan)
                record_ids_by_row = {
                    i: records_by_locator[f"row:{i}"].record_id for i in range(len(table.rows))
                }
                text_out, n = render_csv(
                    table.header, generalized_rows, table.delimiter, pids_by_row, offsets_by_row,
                    record_ids_by_row, envelope.input_sha256,
                )
                candidates.append(text_candidate(out_rel, text_out, envelope.detected_format))
                identifiers_detected += n
                for i in range(len(table.rows)):
                    record_manifest.append(
                        RecordManifestEntry(
                            file=f"sanitized/{out_rel}", loc=f"row:{i}",
                            patient=pids_by_row[i],
                            status="generalized" if i in transformations_by_row else None,
                        )
                    )

            elif item["kind"] == "json":
                data = item["data"]
                json_arrays = record_arrays(data)
                if json_arrays:
                    pids_by_locator: dict[str, str | None] = {}
                    offsets_by_locator: dict[str, int] = {}
                    generalized_data = dict(data)
                    for array_key, array in json_arrays:
                        escaped_key = pointer_escape(array_key)
                        generalized_array = []
                        for i, record_item in enumerate(array):
                            locator = f"/{escaped_key}/{i}"
                            record_id = records_by_locator[locator].record_id
                            plan = transform_plans[record_id]
                            # Plans were keyed before the embeddability check below.
                            profile_key = plan.pseudonym or f"unlinked-json:{record_id}"
                            pids_by_locator[locator] = (
                                plan.pseudonym
                                if can_embed_pseudonym(record_item, envelope.input_sha256, locator)
                                else None
                            )
                            plan.pseudonym = pids_by_locator[locator]
                            offsets_by_locator[locator] = plan.date_offset_days

                            village_level_plan = json_plan_by_profile[profile_key]
                            generalized_item, item_transformations = generalize_json_record(
                                record_item, village_level_plan, village_hierarchy
                            )
                            if item_transformations:
                                plan.field_transformations.extend(item_transformations)
                                mark_generalized(plan)
                                records_generalized += 1
                            generalized_array.append(generalized_item)

                            record_manifest.append(
                                RecordManifestEntry(
                                    file=f"sanitized/{out_rel}", loc=locator,
                                    patient=pids_by_locator[locator],
                                    status="generalized" if item_transformations else None,
                                )
                            )
                        generalized_data[array_key] = generalized_array
                    text_out, n = render_json_records(
                        generalized_data, pids_by_locator, offsets_by_locator,
                        {locator: record.record_id for locator, record in records_by_locator.items()},
                        envelope.input_sha256,
                    )
                else:
                    doc_record_id = records_by_locator["doc"].record_id
                    plan = transform_plans[doc_record_id]
                    # Plans were keyed before the embeddability check below.
                    profile_key = plan.pseudonym or f"unlinked-json:{doc_record_id}"
                    document_pseudonym = (
                        plan.pseudonym
                        if can_embed_pseudonym(data, envelope.input_sha256, "")
                        else None
                    )
                    plan.pseudonym = document_pseudonym

                    village_level_plan = json_plan_by_profile[profile_key]
                    generalized_data, doc_transformations = generalize_json_record(
                        data, village_level_plan, village_hierarchy
                    )
                    if doc_transformations:
                        plan.field_transformations.extend(doc_transformations)
                        mark_generalized(plan)
                        records_generalized += 1

                    text_out, n = render_json_doc(
                        generalized_data,
                        plan.date_offset_days,
                        document_pseudonym,
                        doc_record_id,
                        envelope.input_sha256,
                    )
                    record_manifest.append(
                        RecordManifestEntry(
                            file=f"sanitized/{out_rel}", loc="doc",
                            patient=document_pseudonym,
                            status="generalized" if doc_transformations else None,
                        )
                    )
                candidates.append(text_candidate(out_rel, text_out, envelope.detected_format))
                identifiers_detected += n

            elif item["kind"] == "fhir":
                data = item["data"]
                idx = item["fhir_index"]
                record_id = records_by_locator["doc"].record_id
                plan = transform_plans[record_id]
                pid = plan.pseudonym
                text_out, n = render_fhir_bundle(
                    data, idx, pid, date_offset_days=plan.date_offset_days, record_id=record_id,
                    age_band_years=age_band_years,
                )
                candidates.append(text_candidate(out_rel, text_out, "fhir"))
                identifiers_detected += n
                record_manifest.append(
                    RecordManifestEntry(file=f"sanitized/{out_rel}", loc="doc", patient=pid)
                )

            elif item["kind"] == "text":
                doc_record_id = records_by_locator["doc"].record_id
                plan = transform_plans[doc_record_id]
                document_pseudonym = plan.pseudonym
                text_out, n = render_text_document(
                    item["text"], document_pseudonym,
                    plan.date_offset_days, doc_record_id, age_band_years,
                )
                candidates.append(text_candidate(out_rel, text_out, "text"))
                identifiers_detected += n
                record_manifest.append(
                    RecordManifestEntry(
                        file=f"sanitized/{out_rel}", loc="doc",
                        patient=document_pseudonym,
                    )
                )
            else:
                raise IngestError("unsupported_pending_kind")

            envelope.terminal_status = "sanitized"
            exported_files.add(f"sanitized/{out_rel}")
            item["report_entry"] = FileReportEntry(
                input_sha256=entry.sha256, output=f"sanitized/{out_rel}", status="sanitized"
            )
            report.add_file(item["report_entry"])
            item["candidate_index"] = len(candidates) - 1

        except Exception as exc:  # noqa: BLE001 - one bad file must not abort the whole release
            # Roll back anything this file already queued, then quarantine it alone so
            # a single rendering failure cannot crash the run or leak a partial file.
            del record_manifest[manifest_before:]
            del candidates[candidates_before:]
            records_generalized = generalized_before
            identifiers_detected = identifiers_before
            for record in envelope.records:
                transform_plans[record.record_id].status = "quarantined"
            envelope.terminal_status = "quarantined"
            report.add_file(FileReportEntry(
                input_sha256=entry.sha256, output=None,
                status="quarantined", reason=safe_reason(exc),
            ))

    # ---- release gate (Danish's verifier): every candidate is checked before publication.
    # A leak gets one re-scrub; a file that still fails is quarantined alone (fail closed).
    gate = ReleaseGate(
        detection_engine(),
        allowed_tokens={p for p in pseudonym_map.values() if p},
        secret=keys.secret_text(),
    )
    gate.prepare()
    rejected: set[int] = set()
    for item in pending:
        index = item.get("candidate_index")
        if index is None:
            continue
        candidate = candidates[index]
        output_name = f"sanitized/{item['out_rel']}"
        claimed = tuple(sorted({
            e.patient for e in record_manifest if e.file == output_name and e.patient
        }))
        table = item.get("table")
        check = FileCandidate(
            text=candidate.content.decode("utf-8"),
            original_text=item.get("source_text"),
            fmt=candidate.format,
            pseudonyms=claimed,
            n_columns=len(table.header) if table is not None else None,
            n_rows=len(table.rows) if table is not None else None,
            delimiter=table.delimiter if table is not None else ",",
            order=detection_date_order(item["envelope"].input_sha256),
        )
        # The gate's rescrub is structure-aware (verify.release.rescrub_candidate): CSV/TSV
        # cell by cell with the header left alone, JSON/FHIR only while the result still
        # parses. The re-verification after a rescrub compares every CSV row's width with
        # the input, re-parses JSON and checks FHIR references, so a rescrub that damaged
        # structure (the merged-cell TSV bug found by Omkar) is quarantined, never published.
        try:
            verdict, fixed = gate.verify_and_fix(check)
        except Exception:  # noqa: BLE001 - a verifier crash must not release the file
            verdict, fixed = None, check
        if verdict is not None and verdict.passed:
            if fixed.text != check.text:
                candidates[index] = text_candidate(item["out_rel"], fixed.text, candidate.format)
            continue
        rejected.add(index)
        item["envelope"].terminal_status = "quarantined"
        for record in item["envelope"].records:
            transform_plans[record.record_id].status = "quarantined"
        exported_files.discard(output_name)
        record_manifest[:] = [e for e in record_manifest if e.file != output_name]
        item["report_entry"].output = None
        item["report_entry"].status = "quarantined"
        item["report_entry"].reason = "release_verifier_failed"
    candidates = [cand for i, cand in enumerate(candidates) if i not in rejected]

    if any(envelope.terminal_status is None for envelope in file_envelopes):
        raise IngestError("file_missing_terminal_status")
    n_sanitized_envelopes = sum(1 for e in file_envelopes if e.terminal_status == "sanitized")
    if len(candidates) != n_sanitized_envelopes:
        raise IngestError("candidate_file_count_mismatch")

    # Omkar-owned structural validation runs before publication. Danish's independent
    # PII/clinical verifier is inserted after this call and before publish_candidates.
    validate_candidate_structures(candidates)
    publish_candidates(sanitized_dir, candidates)
    write_records_jsonl(output_root, record_manifest, exported_files)

    n_records = len(record_manifest)
    n_linked = sum(1 for e in record_manifest if e.patient is not None)
    n_suppressed = sum(
        1 for plan in transform_plans.values() if plan.status == "suppressed"
    )
    n_quarantined_records = sum(
        1 for plan in transform_plans.values() if plan.status == "quarantined"
    )
    counts = report.counts(
        records_processed=n_records,
        records_linked=n_linked,
        records_generalized=records_generalized,
        records_suppressed=n_suppressed,
        identifiers_detected=identifiers_detected,
        records_quarantined=n_quarantined_records,
    )
    report.seconds = time.monotonic() - t0
    report.peak_rss_mb = peak_rss_mb()
    report.write(output_root, counts)

    print(
        f"files {counts.files_total} sanitized {counts.files_sanitized} "
        f"quarantined {counts.files_quarantined} records {counts.records_processed}"
    )
    return 0


def _entrypoint() -> int:
    try:
        return main()
    except Exception as exc:  # noqa: BLE001 - release boundary must sanitize all failures
        print(f"ERROR {safe_reason(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_entrypoint())
