import type { EmailInput } from "../types";

// Seeded RNG so "Generate 250 samples" is reproducible within a session.
function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const ENT_COMPANIES = ["Meridian Steel", "Halcyon Retail", "Orbit Manufacturing", "Nimbus Textiles", "Apex Cement", "Vega Pharma", "Cobalt Motors"];
const SMB_COMPANIES = ["Railyard Logistics", "Bluepeak Studios", "Kettle & Co", "Finch Analytics", "Pace Fitness", "Loop Grocers"];
const PSU = ["Bharat Heavy Electricals Limited", "ONGC", "NTPC", "SAIL", "GAIL", "Indian Railways", "BEL"];
const PSU_DOMAINS = ["bhel.in", "ongc.gov.in", "ntpc.co.in", "sail.nic.in"];
const PARTNERS = ["Zenith Cloud Partners", "MEA Systems", "Northstar Integrators", "Kylo Channel Co"];
const VENDORS = ["RankBoost", "LeadGorilla", "PixelPigeon Media", "GrowthHackr"];
const FIRST = ["Suresh", "Ankit", "Nandita", "Farhan", "Imran", "Priya", "Rohan", "Meera", "Vikram", "Sana", "Rakesh", "Divya"];
const LAST = ["Kulkarni", "Bose", "Reddy", "Qureshi", "Sheikh", "Nair", "Gupta", "Iyer", "Singh", "Khan", "Rao"];

type Kind = "ent_rfp" | "smb" | "psu" | "marketing" | "finance" | "alliances" | "hinglish" | "triage" | "autoreply" | "newsletter" | "spam";

// ~75% signal, ~25% noise (autoreply/newsletter/spam).
const WEIGHTS: [Kind, number][] = [
  ["ent_rfp", 14], ["smb", 16], ["psu", 7], ["marketing", 10], ["finance", 10],
  ["alliances", 8], ["hinglish", 6], ["triage", 4],
  ["autoreply", 9], ["newsletter", 8], ["spam", 8],
];

function pick<T>(r: () => number, arr: T[]): T {
  return arr[Math.floor(r() * arr.length)];
}
function pad(n: number, w = 5) {
  return String(n).padStart(w, "0");
}
function isoIST(day: number, hour: number, min: number): string {
  const d = 1 + (day % 12);
  return `2026-08-${String(d).padStart(2, "0")}T${String(hour).padStart(2, "0")}:${String(min).padStart(2, "0")}:00+05:30`;
}

function weightedKind(r: () => number): Kind {
  const total = WEIGHTS.reduce((s, [, w]) => s + w, 0);
  let x = r() * total;
  for (const [k, w] of WEIGHTS) {
    if (x < w) return k;
    x -= w;
  }
  return "smb";
}

function body(kind: Kind, r: () => number, company: string, person: string): { subject: string; body: string; email: string } {
  const domain = company.toLowerCase().replace(/[^a-z]/g, "") + ".co.in";
  const email = `${person.split(" ")[0].toLowerCase()}@${domain}`;
  switch (kind) {
    case "ent_rfp": {
      const lk = pick(r, [15, 20, 25, 30, 45]);
      const dd = pick(r, ["12th August 2026", "20th August 2026", "2026-08-25", "5th September 2026"]);
      return { subject: `RFP - Enterprise platform for ${company}`, email,
        body: `Dear Team,\n\n${company} invites proposals for an enterprise deployment covering multiple sites and ~${100 + Math.floor(r() * 1500)} users. Indicative budget is Rs. ${lk} lakhs. Proposals must reach us by ${dd}.\n\nRegards,\n${person}\n${company}` };
    }
    case "smb":
      return { subject: "Quick demo request", email,
        body: `Hi, we're a ${10 + Math.floor(r() * 40)}-person team at ${company}. Can we get a demo ${pick(r, ["sometime next week", "this month", "soon"])}? ${pick(r, ["Nothing urgent.", "Keen to move fast."])}\n\n— ${person}, ${company}` };
    case "psu": {
      const psu = pick(r, PSU);
      const val = pick(r, [650000, 850000, 1200000, 450000]);
      return { subject: `Tender Notice No. ${psu.split(" ")[0].toUpperCase()}/PROC/2026/${pad(Math.floor(r() * 9999), 4)}`, email: `eproc@${pick(r, PSU_DOMAINS)}`,
        body: `${psu} invites bids for supply of software licences. Estimated value: Rs. ${val.toLocaleString("en-IN")}. Last date for bid submission: 03-08-2026, 1700 hrs IST. EMD as per tender document. e-procurement portal only.` };
    }
    case "marketing": {
      const val = pick(r, [300000, 400000, 250000, 500000]);
      return { subject: "Sponsorship confirmation needed", email,
        body: `We're finalising sponsors for the ${pick(r, ["India SaaS Summit", "DevConf Bengaluru", "GrowthX Mumbai"])}. Gold tier is ₹${val.toLocaleString("en-IN")} and includes a keynote slot. We need confirmation by ${pick(r, ["tomorrow EOD", "Friday", "next Monday"])}.\n\n— ${person}, Sponsorship Lead` };
    }
    case "finance":
      return { subject: `Invoice INV-2026-${pad(Math.floor(r() * 9999), 4)}`, email,
        body: `Please find attached invoice INV-2026-${pad(Math.floor(r() * 9999), 4)} for Rs. ${(50000 + Math.floor(r() * 200000)).toLocaleString("en-IN")} (incl. 18% GST) against PO-${pad(Math.floor(r() * 99999))}. Kindly process — payment terms were Net 30 and this is now ${Math.floor(r() * 20)} days overdue.\n\n${company} Accounts` };
    case "alliances":
      return { subject: "Partnership / reselling proposal", email,
        body: `We're an implementation partner with ${20 + Math.floor(r() * 60)}+ enterprise clients. We'd like to explore reselling your platform or a technical integration. Who handles partnerships?\n\n— ${person}, ${company}` };
    case "hinglish": {
      const cr = pick(r, ["1.2 cr", "80 lakhs", "1.5 cr", "60L"]);
      return { subject: "Product for our network", email,
        body: `Bhai, humko aapka product chahiye for our dealer network. Around ${100 + Math.floor(r() * 200)} users honge. Budget approx ${cr} allocated hai for this FY. Kab connect kar sakte hain? Thoda jaldi, board review ${pick(r, ["20th", "25th", "15th"])} ko hai.` };
    }
    case "triage":
      return { subject: "Great meeting you at the booth", email,
        body: `Hi — we met at your booth. Two things: (1) we'd like to evaluate your platform for our ${500 + Math.floor(r() * 500)}-person org, budget TBD but likely significant, and (2) our CMO wants to co-host a webinar. Can you loop in the right people?\n\n— ${person}, VP Strategy, ${company}` };
    case "autoreply":
      return { subject: "Out of Office", email,
        body: `I am out of office until ${pick(r, ["14th August", "next Monday", "the 20th"])} with limited access to email. For urgent matters please contact my colleague.\n\n— Sent from Outlook` };
    case "newsletter":
      return { subject: `The B2B Growth Weekly — Issue #${100 + Math.floor(r() * 200)}`, email: "newsletter@b2bgrowth.email",
        body: `In this edition: why PLG is stalling, ${Math.floor(r() * 9)} pricing experiments that worked, and a product teardown. You're receiving this because you subscribed. [Unsubscribe] · View in browser` };
    case "spam": {
      const v = pick(r, VENDORS);
      return { subject: "Your website isn't ranking on page 1", email: `hello@${v.toLowerCase()}.io`,
        body: `Hi, I noticed your website isn't ranking on page 1 for key terms. We've helped 200+ SaaS companies 3x their organic traffic. We do content marketing, PR outreach, and webinar promotion. Free audit attached — interested in a quick 15 min call?` };
    }
  }
}

export function generateSamples(count = 250, seed = 42): EmailInput[] {
  const r = mulberry32(seed);
  const emails: EmailInput[] = [];
  let n = 0;
  let thread = 0;
  while (emails.length < count) {
    const kind = weightedKind(r);
    const person = `${pick(r, FIRST)} ${pick(r, LAST)}`;
    const company =
      kind === "smb" ? pick(r, SMB_COMPANIES) :
      kind === "alliances" ? pick(r, PARTNERS) :
      pick(r, ENT_COMPANIES);
    const b = body(kind, r, company, person);
    thread += 1;
    const tid = `th_${pad(thread)}`;
    const day = n % 12;
    emails.push({
      email_id: `em_${pad(n)}`,
      thread_id: tid,
      message_index: 0,
      from_name: kind === "autoreply" || kind === "newsletter" ? "—" : person,
      from_email: b.email,
      to: "sales@company.com",
      subject: b.subject,
      body: b.body,
      received_at: isoIST(day, 9 + Math.floor(r() * 9), Math.floor(r() * 60)),
      attachments: kind === "ent_rfp" || kind === "psu" || kind === "finance" ? ["doc.pdf"] : [],
      is_reply: false,
    });
    n += 1;

    // ~12% of actionable threads get a follow-up reply (multi-message thread).
    if (emails.length < count && (kind === "ent_rfp" || kind === "smb") && r() < 0.12) {
      emails.push({
        email_id: `em_${pad(n)}`,
        thread_id: tid,
        message_index: 1,
        from_name: person,
        from_email: b.email,
        to: "sales@company.com",
        subject: `RE: ${b.subject}`,
        body: `Quick update — the budget is now Rs. ${pick(r, [32, 40, 18])} lakhs and we'd like to close by ${pick(r, ["11th August", "this Friday", "the 15th"])}.\n\nOn earlier date, ${person} wrote:\n> ${b.body.slice(0, 60)}...`,
        received_at: isoIST(day + 2, 10, 0),
        attachments: [],
        is_reply: true,
      });
      n += 1;
    }
  }
  return emails.slice(0, count);
}
