"""O9 regression tests: date syntax preservation, interval preservation, keying."""
from __future__ import annotations

import datetime as dt
import unittest

import tests.conftest_path  # noqa: F401  (adds src/ to sys.path)

from privacy.date_shift import (
    build_date_offset_map,
    shift_date,
    shift_date_string,
    shift_days_for_key,
)


class ShiftDateStringTests(unittest.TestCase):
    def test_dmy_preserves_syntax_and_four_digit_year(self):
        self.assertEqual(shift_date_string("30/06/2025", 10, "dmy"), "10/07/2025")

    def test_dmy_short_year_stays_two_digits(self):
        self.assertEqual(shift_date_string("30/05/26", 10, "dmy"), "09/06/26")

    def test_mdy_declared_hint_is_respected(self):
        # 12/31 would be invalid as DMY; only the MDY hint makes this parseable.
        self.assertEqual(shift_date_string("12/31/2026", 1, "mdy"), "01/01/2027")

    def test_auto_hint_rejects_ambiguous_date(self):
        # Both components <= 12: genuinely ambiguous between DMY and MDY, must not guess.
        self.assertIsNone(shift_date_string("04/05/2026", 10, "auto"))

    def test_auto_hint_accepts_unambiguous_date(self):
        self.assertEqual(shift_date_string("25/02/2026", 1, "auto"), "26/02/2026")

    def test_iso_date_preserves_syntax(self):
        self.assertEqual(shift_date_string("2026-02-04", 7, "dmy"), "2026-02-11")

    def test_iso_datetime_preserves_time_and_timezone_suffix(self):
        self.assertEqual(
            shift_date_string("2026-02-04T18:15:00+05:30", 8),
            "2026-02-12T18:15:00+05:30",
        )

    def test_unparseable_value_returns_none_rather_than_guessing(self):
        self.assertIsNone(shift_date_string("not a date", 10))

    def test_malformed_numeric_date_returns_none(self):
        # Day 32 is not a valid DMY date; must fail closed, not raise or wrap around.
        self.assertIsNone(shift_date_string("32/01/2026", 5, "dmy"))


class ShiftDateIntervalTests(unittest.TestCase):
    def test_interval_between_two_shifted_dates_is_preserved(self):
        admission = shift_date_string("04/02/2026", 180, "dmy")
        discharge = shift_date_string("12/02/2026", 180, "dmy")
        admission_date = dt.datetime.strptime(admission, "%d/%m/%Y").date()
        discharge_date = dt.datetime.strptime(discharge, "%d/%m/%Y").date()
        self.assertEqual((discharge_date - admission_date).days, 8)

    def test_shift_date_overflow_returns_none_not_original(self):
        huge_offset = 10**9  # far beyond dt.date's representable range
        self.assertIsNone(shift_date(dt.date(2026, 1, 1), huge_offset))


class KeyedOffsetTests(unittest.TestCase):
    def test_offset_is_deterministic_for_same_key(self):
        key = b"a" * 32
        self.assertEqual(
            shift_days_for_key(key, "PT00001", 180),
            shift_days_for_key(key, "PT00001", 180),
        )

    def test_offset_differs_across_identity_keys(self):
        # Offsets are drawn from a bounded range (+/- max_days), so any single pair of
        # identities can coincidentally collide. Assert that offsets are not ALL equal
        # across many identities instead of comparing just one arbitrary pair.
        key = b"a" * 32
        offsets = {shift_days_for_key(key, f"PT{i:05d}", 180) for i in range(50)}
        self.assertGreater(len(offsets), 1)

    def test_offset_differs_across_secrets(self):
        self.assertNotEqual(
            shift_days_for_key(b"a" * 32, "PT00001", 180),
            shift_days_for_key(b"b" * 32, "PT00001", 180),
        )

    def test_offset_is_never_zero(self):
        key = b"c" * 32
        for identity in (f"PT{i:05d}" for i in range(200)):
            self.assertNotEqual(shift_days_for_key(key, identity, 180), 0)

    def test_max_days_must_be_positive(self):
        with self.assertRaises(ValueError):
            shift_days_for_key(b"a" * 32, "PT00001", 0)


class BuildDateOffsetMapTests(unittest.TestCase):
    def test_linked_cluster_members_share_one_offset(self):
        from core.interfaces import ClusterAssignment
        from core.record_ids import make_record_id

        record_a = make_record_id("sha", "file1.csv", "row:0")
        record_b = make_record_id("sha", "file2.csv", "row:0")
        assignments = [
            ClusterAssignment(record_id=record_a, cluster_key=record_a, decision="MUST_LINK", evidence_codes=[]),
            ClusterAssignment(record_id=record_b, cluster_key=record_a, decision="MUST_LINK", evidence_codes=[]),
        ]
        offsets = build_date_offset_map(b"k" * 32, assignments, max_days=180)
        self.assertEqual(offsets[record_a], offsets[record_b])

    def test_unlinked_records_get_independent_offsets(self):
        from core.interfaces import ClusterAssignment
        from core.record_ids import make_record_id

        record_a = make_record_id("sha1", "file1.csv", "row:0")
        record_b = make_record_id("sha2", "file2.csv", "row:0")
        assignments = [
            ClusterAssignment(record_id=record_a, cluster_key=None, decision="UNRESOLVED", evidence_codes=[]),
            ClusterAssignment(record_id=record_b, cluster_key=None, decision="UNRESOLVED", evidence_codes=[]),
        ]
        offsets = build_date_offset_map(b"k" * 32, assignments, max_days=180)
        self.assertNotEqual(offsets[record_a], offsets[record_b])

    def test_duplicate_file_offset_matches_original_content_anchor(self):
        """Two distinct input paths with identical file content and locator must get the
        same unlinked-record offset, since content_anchor() ignores the path component.
        """
        from core.interfaces import ClusterAssignment
        from core.record_ids import make_record_id

        same_sha = "deadbeef" * 8
        record_original = make_record_id(same_sha, "a/original.csv", "row:0")
        record_duplicate = make_record_id(same_sha, "b/duplicate_copy.csv", "row:0")
        assignments = [
            ClusterAssignment(record_id=record_original, cluster_key=None, decision="UNRESOLVED", evidence_codes=[]),
            ClusterAssignment(record_id=record_duplicate, cluster_key=None, decision="UNRESOLVED", evidence_codes=[]),
        ]
        offsets = build_date_offset_map(b"k" * 32, assignments, max_days=180)
        self.assertEqual(offsets[record_original], offsets[record_duplicate])


if __name__ == "__main__":
    unittest.main()
