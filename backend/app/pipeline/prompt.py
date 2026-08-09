"""Prompt construction for Stage 4. Roster + the four rules + all twelve §6
worked examples as few-shot cases. Stage-3 hints are passed as hard facts."""
from __future__ import annotations

import json

from ..roster import TEAM

SYSTEM_INSTRUCTION = """You are the classifier for a B2B company's sales@ inbox.
You route each incoming email to exactly one owner, or decide it needs no task.
You are precise, you never invent facts, and you prefer the triage queue over a
confident wrong guess.

TEAM ROSTER (route to exactly one user_id):
{roster}

ROUTING RULES (business-written; incomplete and slightly contradictory on purpose):
- RFPs, RFIs, tenders, inbound deals ABOVE ₹10,00,000 -> u_aarti (enterprise_rfp).
- Product enquiries, demo requests, deals AT OR BELOW ₹10,00,000 -> u_rohit (smb_enquiry).
- Webinars, event/conference sponsorships, content collaborations, PR/media -> u_meera (marketing).
- Reseller, channel partner, technology integration proposals -> u_karan (alliances).
- Invoices, POs, payment reminders, GST, vendor billing -> u_divya (finance).
- Anything genuinely ambiguous or that doesn't cleanly fit -> u_triage (triage).

ADDITIONAL RULES:
1. A stated deadline within 72h of received_at => priority "high".
2. A reply on an existing thread updates the existing task (handled by the system, not you).
3. Government/PSU tenders ALWAYS go to Aarti, regardless of deal value.
4. Do NOT create tasks for out-of-office auto-replies, newsletters, or unsolicited vendor spam.

CRITICAL JUDGEMENT:
- direction_of_intent is decisive. "inbound_buyer" = they want to buy from us / need our help.
  "outbound_seller" = they are selling their services TO us (SEO, marketing agencies, lead-gen).
  "informational" = newsletters, notices, auto-replies. Outbound_seller marketing spam that uses
  words like "webinar", "content", "PR" is NOT marketing work -> it gets no task.
- Money in an email does not make it a Sales deal. A sponsorship price is Marketing. An invoice
  amount is Finance and is NOT a deal_value_inr.
- When two different owners each have a legitimate claim on the same email, return u_triage with
  confidence below 0.55 and state BOTH asks in the description. Never pick one and drop the other.
- company_name is null unless a company is actually named in the text. Do NOT infer it from the
  email domain unless the domain unambiguously IS the company name.
- The system has already parsed money and the deadline deterministically and passes them to you as
  facts. Do NOT override deal_value_inr or due_date — copy the provided values through.

OUTPUT: return ONLY a JSON object with EXACTLY these keys, all required:
  "is_actionable" (bool), "skip_reason" (string or null), "category" (enum),
  "assignee_id" (enum), "priority" (high|medium|low), "company_name" (string or null),
  "deal_value_inr" (integer or null), "due_date" (YYYY-MM-DD or null),
  "confidence" (float 0-1), "direction_of_intent" (inbound_buyer|outbound_seller|informational),
  "reasoning" (ONE sentence explaining the route — never leave this empty),
  "title" (short task title), "description" (one or two sentences).
"""


def _fewshot() -> str:
    """The twelve §6 examples, compacted to input->expected+why."""
    cases = [
        ("Meridian Steel invites proposals for an enterprise DMS covering 4 plants and ~1,200 users. Indicative budget is Rs. 25 lakhs. Proposals must reach us by 12th August 2026. (received 2026-08-01)",
         {"assignee_id": "u_aarti", "category": "enterprise_rfp", "priority": "medium", "company_name": "Meridian Steel", "direction_of_intent": "inbound_buyer", "is_actionable": True},
         "₹25L > ₹10L threshold -> Aarti; deadline 11 days out -> medium."),
        ("Hi, we're a 30-person logistics startup in Pune... can we get a demo sometime next week? Nothing urgent. — Ankit Bose, Founder, Railyard Logistics",
         {"assignee_id": "u_rohit", "category": "smb_enquiry", "priority": "low", "company_name": "Railyard Logistics", "direction_of_intent": "inbound_buyer", "is_actionable": True},
         "Small company demo, no value -> Rohit; 'sometime next week' is not a deadline; 'nothing urgent' -> low."),
        ("Tender Notice No. BHEL/PROC/2026/0847. Bharat Heavy Electricals Limited invites bids for supply of analytics software licences. Estimated value: Rs. 6,50,000. Last date for bid submission: 03-08-2026, 1700 hrs IST. (received 2026-08-01 14:20)",
         {"assignee_id": "u_aarti", "category": "enterprise_rfp", "priority": "high", "company_name": "Bharat Heavy Electricals Limited", "direction_of_intent": "inbound_buyer", "is_actionable": True},
         "PSU tender -> Aarti even though ₹6.5L is below threshold (Rule 3 beats value); deadline ~51h -> high."),
        ("We're finalising sponsors for the India SaaS Summit in Bengaluru. Gold tier is ₹4,00,000 and includes a keynote slot. We need confirmation by tomorrow EOD as we're going to print. — Nandita Reddy, Sponsorship Lead (received 2026-08-02 16:45)",
         {"assignee_id": "u_meera", "category": "marketing", "priority": "high", "company_name": "India SaaS Summit", "direction_of_intent": "inbound_buyer", "is_actionable": True},
         "Event sponsorship -> Meera not Sales despite the money; 'tomorrow EOD' within 72h -> high."),
        ("Please find attached invoice INV-2026-0331 for Rs. 1,18,000 (incl. 18% GST) against PO-88214. Kindly process — payment terms were Net 30 and this is now 12 days overdue. Also, our GSTIN has changed.",
         {"assignee_id": "u_divya", "category": "finance", "priority": "high", "company_name": "Vantage Cloud Services", "direction_of_intent": "informational", "is_actionable": True},
         "Invoice -> Divya; ₹1,18,000 is an invoice amount not a deal value (deal_value null); overdue -> high."),
        ("We're a Salesforce implementation partner across MEA with 40+ enterprise clients. We'd like to explore reselling your platform in the region, or a technical integration at minimum. Who handles partnerships?",
         {"assignee_id": "u_karan", "category": "alliances", "priority": "medium", "company_name": "Zenith Cloud Partners", "direction_of_intent": "inbound_buyer", "is_actionable": True},
         "Reseller/channel language -> Karan; it mentions clients/revenue but is not a deal."),
        ("I am out of office until 14th August with limited access to email. For urgent matters please contact my colleague at raghav@northbridge.in. — Sent from Outlook",
         {"is_actionable": False, "skip_reason": "out_of_office", "direction_of_intent": "informational"},
         "Auto-reply -> no task (Rule 4). A triage task here would be spurious."),
        ("Hi, I noticed your website isn't ranking on page 1 for key terms. We've helped 200+ SaaS companies 3x their organic traffic. We do content marketing, PR outreach, and webinar promotion. Free audit attached — interested in a quick 15 min call?",
         {"is_actionable": False, "skip_reason": "vendor_spam", "direction_of_intent": "outbound_seller"},
         "Every marketing keyword but they are selling TO us -> no task; direction of intent is decisive."),
        ("The B2B Growth Weekly — Issue #212. In this edition: why PLG is stalling, 5 pricing experiments that worked, and a teardown of Figma's onboarding. [Unsubscribe]",
         {"is_actionable": False, "skip_reason": "newsletter", "direction_of_intent": "informational"},
         "Newsletter -> no task (Rule 4)."),
        ("Correction to our earlier note — the board has approved an increased budget of Rs. 32 lakhs, and the submission deadline is advanced to 11th August. (reply on thread th_0091, received 2026-08-09)",
         {"assignee_id": "u_aarti", "category": "enterprise_rfp", "priority": "high", "direction_of_intent": "inbound_buyer", "is_actionable": True},
         "Reply on an existing thread -> the system updates the task; ₹32L, deadline ~48h -> high; ignore quoted text."),
        ("Hi — we met at your booth in Mumbai. Two things: (1) we'd like to evaluate your platform for our 800-person org, budget TBD but likely significant, and (2) our CMO wants to co-host a webinar with your team in September. — Farhan Qureshi, VP Strategy, Halcyon Retail",
         {"assignee_id": "u_triage", "category": "triage", "priority": "medium", "company_name": "Halcyon Retail", "confidence": 0.42, "direction_of_intent": "inbound_buyer", "is_actionable": True},
         "Two asks owned by two people and budget TBD -> u_triage, low confidence, both asks in description."),
        ("Bhai, humko aapka product chahiye for our dealer network. Around 150 users honge. Budget approx 1.2 cr allocated hai for this FY. Kab connect kar sakte hain? Thoda jaldi, board review 20th ko hai. (received 2026-08-05)",
         {"assignee_id": "u_aarti", "category": "enterprise_rfp", "priority": "medium", "company_name": None, "direction_of_intent": "inbound_buyer", "is_actionable": True},
         "'1.2 cr' = 1,20,00,000 -> Aarti; 20th is 15 days out -> medium; no company named -> null."),
    ]
    blocks = []
    for i, (body, expected, why) in enumerate(cases, 1):
        blocks.append(
            f"Example {i}\nEMAIL: {body}\nEXPECTED: {json.dumps(expected, ensure_ascii=False)}\nWHY: {why}"
        )
    return "\n\n".join(blocks)


def system_instruction() -> str:
    roster_lines = "\n".join(
        f"- {m['user_id']} ({m['name']}, {m['department']}): {m['scope']}" for m in TEAM
    )
    return SYSTEM_INSTRUCTION.format(roster=roster_lines) + "\n\nWORKED EXAMPLES:\n" + _fewshot()


def build_user_prompt(*, subject: str, cleaned_body: str, received_at: str, signals: dict,
                      money, due, is_reply: bool) -> str:
    facts = {
        "parsed_deal_value_inr": money,
        "parsed_due_date": due.isoformat() if due else None,
        "is_reply": is_reply,
        "signals": {
            "psu_or_government": signals.get("psu", False),
            "auto_reply": signals.get("auto_reply", False),
            "newsletter": signals.get("newsletter", False),
            "looks_outbound_spam": signals.get("outbound_spam", False),
            "invoice_or_po": signals.get("invoice", False),
        },
    }
    return (
        f"SUBJECT: {subject}\n"
        f"RECEIVED_AT: {received_at}\n"
        f"DETERMINISTIC_FACTS (treat as ground truth, do not override money/date): "
        f"{json.dumps(facts, ensure_ascii=False)}\n\n"
        f"EMAIL BODY (quoted/forwarded text already removed):\n{cleaned_body}\n\n"
        "Classify this email now. Return ONLY the JSON object."
    )
