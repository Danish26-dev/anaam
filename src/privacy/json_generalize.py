"""O10: generalization for nested JSON records.

Extends the CSV-only generalization in main.py's `_generalize_csv_rows` to JSON records
(e.g. `registration/dhh_patients.json`'s `patients[].age` / `patients[].address.{village,
tehsil,district,pin}`). Reuses the SAME shared key-role table as CSV headers
(`core.header_roles.role_for_header`) so "age"/"village"/"tehsil"/"district"/"pin" are
recognized identically regardless of source format -- a renamed JSON key is caught the
same way a renamed CSV header is.

Walks the whole record recursively (not just top-level keys), because the practice data
nests quasi-identifiers under an `address` object. Only scalar string/int leaves whose KEY
matches a known role are touched; nothing else in the record is altered here.
"""
from __future__ import annotations

from core.header_roles import role_for_header
from core.interfaces import FieldTransformation
from .generalize import VillageHierarchy
from .profile_policy import ProfilePrivacyPlan, apply_plan_to_pin, apply_plan_to_village


def _coerce_age(value: object) -> int | None:
    if isinstance(value, bool):  # bool is an int subclass; never treat it as an age
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def collect_village_hierarchy_facts(
    value: object,
) -> list[tuple[str, str | None, str | None]]:
    """Find every (village, tehsil, district) triple reachable from one JSON value.

    Mirrors `main._learn_village_hierarchy` for CSV rows, applied to every dict found
    anywhere in the structure (the practice data keeps village/tehsil/district together
    under one `address` object, but a hidden dataset could put them at any depth).
    """
    facts: list[tuple[str, str | None, str | None]] = []
    if isinstance(value, dict):
        village = tehsil = district = None
        for key, child in value.items():
            if not isinstance(child, str):
                continue
            role = role_for_header(str(key))
            if role == "village" and child.strip():
                village = child
            elif role == "tehsil" and child.strip():
                tehsil = child
            elif role == "district" and child.strip():
                district = child
        if village:
            facts.append((village, tehsil, district))
        for child in value.values():
            facts.extend(collect_village_hierarchy_facts(child))
    elif isinstance(value, list):
        for item in value:
            facts.extend(collect_village_hierarchy_facts(item))
    return facts


def find_village_and_district(value: object) -> tuple[str | None, str | None]:
    """Return the first (village, district) pair found anywhere in one JSON record.

    Used only to build O10's group-size tables (how many profiles/anchors share a given
    village or district), mirroring what main.py already does for CSV rows via
    `core.header_roles.find_column`.
    """
    village: str | None = None
    district: str | None = None

    def walk(node: object) -> None:
        nonlocal village, district
        if village and district:
            return
        if isinstance(node, dict):
            for key, child in node.items():
                if not isinstance(child, str) or not child.strip():
                    continue
                role = role_for_header(str(key))
                if role == "village" and village is None:
                    village = child
                elif role == "district" and district is None:
                    district = child
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return village, district


def generalize_json_record(
    value: object,
    plan: ProfilePrivacyPlan,
    hierarchy: VillageHierarchy,
    path_prefix: str = "",
) -> tuple[object, list[FieldTransformation]]:
    """Return (generalized_copy, transformations). Does not mutate `value` in place."""
    transformations: list[FieldTransformation] = []

    def walk(node: object, prefix: str) -> object:
        if isinstance(node, dict):
            result: dict = {}
            for key, child in node.items():
                child_path = f"{prefix}/{key}" if prefix else str(key)
                role = role_for_header(str(key))

                if role == "age" and not isinstance(child, (dict, list)):
                    age = _coerce_age(child)
                    if age is not None:
                        from .profile_policy import apply_plan_to_age

                        new_value = apply_plan_to_age(plan, age)
                        transformations.append(
                            FieldTransformation(path=child_path, action="generalize", replacement=new_value)
                        )
                        result[key] = new_value
                        continue

                if role == "village" and isinstance(child, str) and child.strip():
                    new_value = apply_plan_to_village(plan, child.strip(), hierarchy)
                    transformations.append(
                        FieldTransformation(
                            path=child_path,
                            action="generalize" if new_value else "suppress",
                            replacement=new_value or "",
                        )
                    )
                    result[key] = new_value or ""
                    continue

                if role == "pin" and isinstance(child, str) and child.strip():
                    new_value = apply_plan_to_pin(plan, child.strip())
                    transformations.append(
                        FieldTransformation(
                            path=child_path,
                            action="generalize" if new_value else "suppress",
                            replacement=new_value,
                        )
                    )
                    result[key] = new_value
                    continue

                if role in ("tehsil", "district") and plan.village_level == "suppress" and (
                    isinstance(child, str) and child.strip()
                ):
                    transformations.append(
                        FieldTransformation(path=child_path, action="suppress", replacement="")
                    )
                    result[key] = ""
                    continue

                result[key] = walk(child, child_path)
            return result
        if isinstance(node, list):
            return [walk(item, f"{prefix}/{i}") for i, item in enumerate(node)]
        return node

    generalized = walk(value, path_prefix)
    return generalized, transformations
