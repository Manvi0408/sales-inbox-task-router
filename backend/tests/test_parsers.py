from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.pipeline.parsers import parse_deadline, parse_money

IST = ZoneInfo("Asia/Kolkata")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Indicative budget is Rs. 25 lakhs.", 2500000),
        ("Gold tier is ₹4,00,000 and includes a keynote", 400000),
        ("we need 25L worth", 2500000),
        ("INR 25L for the year", 2500000),
        ("Budget approx 1.2 cr allocated hai", 12000000),
        ("Estimated value: Rs. 6,50,000.", 650000),
        ("total is 2500000 rupees", 2500000),
        ("no money mentioned here at all", None),
        ("call us at 9am, 30-person team", None),
    ],
)
def test_parse_money(text, expected):
    assert parse_money(text) == expected


def _rx(s):
    return datetime.fromisoformat(s)


@pytest.mark.parametrize(
    "text,received,expected",
    [
        ("Proposals must reach us by 12th August 2026.", "2026-08-01T09:14:22+05:30", date(2026, 8, 12)),
        ("Last date for bid submission: 03-08-2026, 1700 hrs IST.", "2026-08-01T14:20:00+05:30", date(2026, 8, 3)),
        ("deadline is 2026-08-12", "2026-08-01T09:00:00+05:30", date(2026, 8, 12)),
        ("confirmation by tomorrow EOD", "2026-08-02T16:45:00+05:30", date(2026, 8, 3)),
        ("respond within 48 hours please", "2026-08-01T10:00:00+05:30", date(2026, 8, 3)),
        ("deadline advanced to 11th August", "2026-08-09T10:00:00+05:30", date(2026, 8, 11)),
        ("board review 20th ko hai", "2026-08-05T10:00:00+05:30", date(2026, 8, 20)),  # bare ordinal + cue
        ("can we get a demo sometime next week?", "2026-08-01T10:00:00+05:30", None),
        ("nothing urgent, soon is fine", "2026-08-01T10:00:00+05:30", None),
    ],
)
def test_parse_deadline(text, received, expected):
    assert parse_deadline(text, _rx(received)) == expected
