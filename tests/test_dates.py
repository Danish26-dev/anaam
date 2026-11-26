import datetime as dt

import pytest

from src import contracts as c
from src.detection.dates import detect_dates_and_ages, find_dates, infer_order


def spans(text, order=None):
    return {(text[s.start:s.end], s.category) for s in detect_dates_and_ages(text, order)}


@pytest.mark.parametrize("text,surface,expected", [
    ("Date of Admission: 15-05-2026", "15-05-2026", dt.date(2026, 5, 15)),
    ("2026-04-21T17:15:00+05:30", "2026-04-21T17:15:00+05:30", dt.date(2026, 4, 21)),
    ("[30/05/26, 9:32 pm] Kamal Bhaiya:", "30/05/26", dt.date(2026, 5, 30)),
    ("Visit on 3 March 2026 at OPD", "3 March 2026", dt.date(2026, 3, 3)),
    ("भर्ती की तारीख: 11-09-2026", "11-09-2026", dt.date(2026, 9, 11)),
])
def test_dates_parse(text, surface, expected):
    found = {text[s:e]: d for s, e, d, _ in find_dates(text, "dmy")}
    assert found[surface] == expected


def test_month_first_order_and_fallback():
    assert find_dates("01/13/2026 22:00", "dmy")[0][2] == dt.date(2026, 1, 13)
    assert find_dates("02/06/2026", "mdy")[0][2] == dt.date(2026, 2, 6)
    assert infer_order(["04/20/1979", "11/24/2025"]) == "mdy"
    assert infer_order(["25-04-1980"]) == "dmy"


def test_dob_label():
    assert ("25-04-1980", c.DOB) in spans("DOB: 25-04-1980")
    assert ("1983-03-24", c.DOB) in spans('"dob": "1983-03-24"')
    assert ("15-05-2026", c.DATE) in spans("Date of Admission: 15-05-2026")


def test_day_month_without_year():
    assert ("5 September", c.DATE) in spans("Visit: 5 September\nTreated for")
    assert not spans("Dose 1 may be repeated")


@pytest.mark.parametrize("text", [
    "BP 117/82", "Tab 1-0-1 x 5 days", "range 12.0-16.0", "IP/26/00574", "SNJ/26/052715",
    "OPD/26/02/00085", "90-6549-3147-0151", "4000-11000", "DHH2026-018208",
])
def test_non_dates(text):
    assert not [s for s in detect_dates_and_ages(text) if s.category in (c.DATE, c.DOB)]


@pytest.mark.parametrize("text,age", [
    ("Name: Padmini Reddy   Age: 48/F   Reg No", "48"),
    ("Age/Sex: 46 Yrs/M", "46"),
    ("Report of Asha ji  48 Y / F", "48"),
    ("आयु: 65 वर्ष / महिला", "65"),
    ("65/F", "65"),
    ("a 47-year-old woman", "47"),
])
def test_ages(text, age):
    assert (age, c.AGE) in spans(text)


@pytest.mark.parametrize("text", [
    "K/C/O DM2 x 12 yrs", "H/O TB 10 yrs back, completed ATT", "BP 168/92", "Bed 12",
])
def test_not_ages(text):
    assert not [s for s in detect_dates_and_ages(text) if s.category == c.AGE]
