from app.pipeline.detectors import (
    is_auto_reply,
    is_invoice,
    is_newsletter,
    is_psu,
    looks_outbound_spam,
)
from app.pipeline.normalize import clean_body


def test_psu_detection():
    assert is_psu("Tender Notice No. BHEL/PROC/2026/0847. Bharat Heavy Electricals Limited invites bids")
    assert is_psu("query from procurement", from_email="tenders@ongc.gov.in")
    assert not is_psu("We're a small startup in Pune looking for a demo")
    # short abbreviations must not match inside ordinary words (regression)
    assert not is_psu("Farhan Qureshi, VP Strategy, Halcyon Retail", from_email="farhan@halcyonretail.com")
    assert not is_psu("please find the label and table attached")


def test_auto_reply_detection():
    assert is_auto_reply("Out of Office", "I am out of office until 14th August. Sent from Outlook")
    assert not is_auto_reply("RFP", "Please find attached our proposal")


def test_newsletter_detection():
    assert is_newsletter("B2B Growth Weekly", "In this edition ... [Unsubscribe]")
    assert is_newsletter("Issue #212", "the latest digest")
    assert not is_newsletter("Demo request", "can we get a demo next week")


def test_outbound_spam_detection():
    assert looks_outbound_spam(
        "I noticed your website isn't ranking. We've helped 200+ SaaS companies. Free audit attached."
    )
    assert not looks_outbound_spam("We'd like to evaluate your platform for our org")


def test_invoice_detection():
    assert is_invoice("Please find attached invoice INV-2026-0331 against PO-88214, Net 30")
    assert not is_invoice("We want a demo of your product")


def test_clean_body_strips_quotes():
    raw = (
        "Correction — increased budget of Rs. 32 lakhs, deadline 11th August.\n"
        "On Mon, 1 Aug 2026, Suresh wrote:\n> original budget Rs. 25 lakhs\n> please review"
    )
    cleaned = clean_body(raw)
    assert "32 lakhs" in cleaned
    assert "25 lakhs" not in cleaned  # quoted text removed


def test_clean_body_strips_html():
    assert "Hello" in clean_body("<p>Hello</p><br><b>world</b>")
