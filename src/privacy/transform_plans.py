"""Build and update the live per-record TransformPlan map."""
from __future__ import annotations

from core.interfaces import (
    ClusterAssignment,
    FieldTransformation,
    RecordEnvelope,
    ResolvedSpan,
    TransformPlan,
)


def build_transform_plans(
    records: list[RecordEnvelope],
    assignments: list[ClusterAssignment],
    pseudonyms: dict[str, str | None],
    date_offsets: dict[str, int],
    resolved_spans: dict[str, list[ResolvedSpan]] | None = None,
    field_transformations: dict[str, list[FieldTransformation]] | None = None,
) -> dict[str, TransformPlan]:
    """Create one complete plan per record, even when it remains unlinked."""
    resolved_spans = resolved_spans or {}
    field_transformations = field_transformations or {}
    assignment_ids = {assignment.record_id for assignment in assignments}
    record_ids = {record.record_id for record in records}
    if assignment_ids != record_ids:
        raise ValueError("transform_plan_assignment_mismatch")

    return {
        record.record_id: TransformPlan(
            record_id=record.record_id,
            pseudonym=pseudonyms.get(record.record_id),
            date_offset_days=date_offsets[record.record_id],
            resolved_spans=list(resolved_spans.get(record.record_id, [])),
            field_transformations=list(field_transformations.get(record.record_id, [])),
            status="sanitized",
        )
        for record in records
    }


def mark_generalized(plan: TransformPlan) -> None:
    if plan.status == "sanitized":
        plan.status = "generalized"


def suppress(plan: TransformPlan) -> None:
    plan.status = "suppressed"
    plan.pseudonym = None
