"""O10 integration point: applies a ProfilePrivacyPlan to a record's generalizable fields.

This module is the seam between Omkar's privacy policy (generalize.py / profile_policy.py)
and Danish's field classification (D5, src/detection/field_classifier.py). It does NOT
hardcode which CSV column is "age" or "village" -- that would silently break on hidden
datasets with renamed headers (the brief explicitly calls out "Patient's Name",
"Gram/Mohalla" as expected renames). Instead it consumes a `role_hint` already attached
to a FieldNode (set by Danish's classifier once it exists, or by a quick heuristic in the
meantime) and only generalizes fields whose role_hint matches a known quasi-identifier
role: "age", "village", "pin".

Until Danish's classifier lands, `heuristic_role_hint()` below provides a conservative,
header-name-only fallback so this path is exercisable end-to-end; it is intentionally
narrow (exact, case-insensitive header matches only) so it never over-reaches into
guessing on ambiguous columns -- that guessing is explicitly D5's job, not O10's.
"""
from __future__ import annotations

from core.header_roles import role_for_header
from core.interfaces import FieldNode
from .generalize import VillageHierarchy, age_band
from .profile_policy import ProfilePrivacyPlan, apply_plan_to_pin, apply_plan_to_village


def heuristic_role_hint(path: str) -> str | None:
    """Narrow, exact-match fallback until Danish's field classifier supplies role_hint
    directly on FieldNode. `path` is expected in the "col:<Header>" form used by the CSV
    adapter. Delegates to the single shared header-role table in core.header_roles so
    this stays in sync with csv_writer.py and main.py's column lookups.
    """
    if not path.startswith("col:"):
        return None
    header = path[4:]
    role = role_for_header(header)
    return role if role in ("age", "village", "pin") else None


def generalize_field_value(
    field: FieldNode, plan: ProfilePrivacyPlan, hierarchy: VillageHierarchy
) -> tuple[str | None, bool]:
    """Returns (new_value_or_None_to_suppress, was_changed).

    role_hint is read from field.role_hint if set, else derived via heuristic_role_hint.
    Fields with no recognized role are returned unchanged.
    """
    role = field.role_hint or heuristic_role_hint(field.path)
    value = field.value

    if role == "age" and isinstance(value, str) and value.strip().isdigit():
        return age_band(int(value.strip()), band_years=plan.age_band_years), True

    if role == "village" and isinstance(value, str) and value.strip():
        # apply_plan_to_village itself returns None both for an unknown mapping AND for
        # plan.village_level == "suppress" (the O10 last-resort case): either way the
        # truthful thing to do is drop the value rather than guess or leak a rare combo.
        generalized = apply_plan_to_village(plan, value.strip(), hierarchy)
        return generalized, True

    if role == "pin" and isinstance(value, str) and value.strip():
        new_pin = apply_plan_to_pin(plan, value.strip())
        return (new_pin or None), True

    return (value if isinstance(value, str) else None), False
