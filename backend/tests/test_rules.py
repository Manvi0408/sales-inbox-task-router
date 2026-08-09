from datetime import date, datetime

from app.pipeline.rules import apply_rules
from app.pipeline.types import Classification


def _c(**kw):
    base = dict(category="enterprise_rfp", assignee_id="u_rohit", priority="medium",
                is_actionable=True, direction_of_intent="inbound_buyer")
    base.update(kw)
    return Classification(**base)


def _rx(s):
    return datetime.fromisoformat(s)


def test_r3_psu_beats_value():
    # PSU tender ₹6.5L (below threshold) must still go to Aarti (Example 3).
    c = _c(category="enterprise_rfp", assignee_id="u_rohit", deal_value_inr=650000,
           due_date=date(2026, 8, 3))
    out = apply_rules(c, signals={"psu": True}, received_at=_rx("2026-08-01T14:20:00+05:30"))
    assert out.assignee_id == "u_aarti"
    assert "R3_PSU" in out.rules_fired
    assert out.priority == "high"  # ~51h out
    assert "R1_DEADLINE_72H" in out.rules_fired


def test_r_value_above_threshold_to_aarti():
    c = _c(category="smb_enquiry", assignee_id="u_rohit", deal_value_inr=12000000)
    out = apply_rules(c, signals={}, received_at=_rx("2026-08-05T10:00:00+05:30"))
    assert out.assignee_id == "u_aarti"
    assert out.category == "enterprise_rfp"
    assert "R_VALUE" in out.rules_fired


def test_r_value_at_or_below_threshold_to_rohit():
    c = _c(category="smb_enquiry", assignee_id="u_aarti", deal_value_inr=800000)
    out = apply_rules(c, signals={}, received_at=_rx("2026-08-05T10:00:00+05:30"))
    assert out.assignee_id == "u_rohit"


def test_r_value_does_not_fire_for_marketing():
    # Sponsorship with a stated price stays with Meera (Example 4).
    c = _c(category="marketing", assignee_id="u_meera", deal_value_inr=400000,
           due_date=date(2026, 8, 3))
    out = apply_rules(c, signals={}, received_at=_rx("2026-08-02T16:45:00+05:30"))
    assert out.assignee_id == "u_meera"
    assert "R_VALUE" not in out.rules_fired
    assert out.priority == "high"


def test_invoice_nulls_deal_value():
    c = _c(category="finance", assignee_id="u_divya", deal_value_inr=118000)
    out = apply_rules(c, signals={"invoice": True}, received_at=_rx("2026-08-01T10:00:00+05:30"))
    assert out.deal_value_inr is None
    assert "R_INVOICE_NOT_DEAL" in out.rules_fired


def test_auto_reply_no_task():
    c = _c()
    out = apply_rules(c, signals={"auto_reply": True}, received_at=_rx("2026-08-03T08:00:00+05:30"))
    assert out.is_actionable is False
    assert out.skip_reason == "out_of_office"
    assert "R4_NO_TASK" in out.rules_fired


def test_outbound_spam_no_task():
    c = _c(direction_of_intent="outbound_seller")
    out = apply_rules(c, signals={"outbound_spam": True}, received_at=_rx("2026-08-01T10:00:00+05:30"))
    assert out.is_actionable is False
    assert out.skip_reason == "vendor_spam"


def test_deadline_far_out_stays_medium():
    c = _c(due_date=date(2026, 8, 12))
    out = apply_rules(c, signals={}, received_at=_rx("2026-08-01T09:00:00+05:30"))
    assert out.priority == "medium"
    assert "R1_DEADLINE_72H" not in out.rules_fired
