"""Exact, case-sensitive enums from §5.2. These strings are graded mechanically."""
from __future__ import annotations

from enum import Enum


class AssigneeId(str, Enum):
    u_aarti = "u_aarti"
    u_rohit = "u_rohit"
    u_meera = "u_meera"
    u_karan = "u_karan"
    u_divya = "u_divya"
    u_triage = "u_triage"


class Category(str, Enum):
    enterprise_rfp = "enterprise_rfp"
    smb_enquiry = "smb_enquiry"
    marketing = "marketing"
    alliances = "alliances"
    finance = "finance"
    triage = "triage"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Decision(str, Enum):
    created = "created"
    updated = "updated"
    skipped = "skipped"
    error = "error"


class SkipReason(str, Enum):
    out_of_office = "out_of_office"
    newsletter = "newsletter"
    vendor_spam = "vendor_spam"
    no_actionable_content = "no_actionable_content"


class DirectionOfIntent(str, Enum):
    inbound_buyer = "inbound_buyer"
    outbound_seller = "outbound_seller"
    informational = "informational"


ASSIGNEE_VALUES = [e.value for e in AssigneeId]
CATEGORY_VALUES = [e.value for e in Category]
PRIORITY_VALUES = [e.value for e in Priority]

# Maps the enum field name -> allowed list, for the invalid_enum_value error body.
ENUM_ALLOWED: dict[str, list[str]] = {
    "assignee_id": ASSIGNEE_VALUES,
    "category": CATEGORY_VALUES,
    "priority": PRIORITY_VALUES,
}
