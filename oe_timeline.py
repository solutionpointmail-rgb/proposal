"""
The Benefits Group — Open Enrollment Timeline generator.

One intake (renewal or new group) -> a colorful 3-page PDF and an editable Word file.

Usage (CLI):
    python oe_timeline.py intake.txt --out ./output
Usage (Render / Flask):
    from oe_timeline import build_plan, parse_intake, render_pdf, render_docx
    plan = build_plan(parse_intake(text_or_dict))
    pdf_bytes = render_pdf(plan); docx_bytes = render_docx(plan)

Intake text format (any missing date is filled with a suggested date and flagged):

    Renewal Timeline – ABC Company          (or "New Group Timeline – ABC Company")
    Effective date: 1/1/27
    Quotes expected: 11/1
    All quotes back: 11/16
    Plan decision: 11/18
    Build complete: 11/20
    OE starts: 11/23
    OE ends: 11/30
    Carrier submission: 12/2
    Milestones:
    - Benefit guide delivered: 11/20
    - Employee meeting: 11/23
    Short name: ABC                         (optional — used inside sentences)
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

# ──────────────────────────────────────────────────────────────────────────────
# 1. Intake + plan
# ──────────────────────────────────────────────────────────────────────────────

CORE_KEYS = ["quotes_expected", "quotes_back", "decision", "build",
             "oe_start", "oe_end", "submission"]

# Days before the effective date used when a date is not supplied.
# (Matches the True Cable 1/1 cadence: 11/1, 11/16, 11/18, 11/20, 11/23, 11/30, 12/2.)
DEFAULT_OFFSETS = {"quotes_expected": 61, "quotes_back": 46, "decision": 44,
                   "build": 42, "oe_start": 39, "oe_end": 32, "submission": 30}

LABEL_ALIASES = {
    "effective": ["effective date", "effective", "renewal effective date", "renewal date"],
    "quotes_expected": ["quotes expected", "renewal expected", "initial quotes", "renewal received",
                        "initial renewal", "quotes received"],
    "quotes_back": ["all quotes back", "quotes back", "marketing back", "final quotes"],
    "decision": ["plan decision", "final decision", "decision"],
    "build": ["build complete", "platform build", "build ready", "enrollment build", "build"],
    "oe_start": ["oe starts", "oe start", "open enrollment begins", "oe begins", "enrollment opens"],
    "oe_end": ["oe ends", "oe end", "open enrollment ends", "enrollment closes", "oe closes"],
    "submission": ["carrier submission", "submission", "elections submitted", "submit to carrier"],
    "short_name": ["short name", "nickname"],
    "client": ["client", "client name", "group", "company"],
    "type": ["type", "group type"],
}

SUGGESTED_MILESTONES = [  # (label, offset from key, owner) — offered when none are given
    ("Contribution strategy finalized", ("decision", 0), "Client"),
    ("Carrier implementation call", ("decision", 2), "TBG / Carrier"),
    ("Benefit guide & SBCs delivered", ("oe_start", -1), "TBG"),
    ("Employee meeting / enrollment kickoff", ("oe_start", 0), "TBG / Client"),
    ("Payroll deduction file to payroll", ("effective", -14), "Client"),
    ("ID cards in hand / portal access", ("effective", -7), "Carrier"),
]


@dataclass
class Plan:
    client: str
    short: str
    kind: str                      # "renewal" | "new"
    effective: date
    dates: dict                    # CORE_KEYS -> date
    milestones: list = field(default_factory=list)   # [(label, date, owner)]
    suggested: list = field(default_factory=list)    # keys that were auto-filled
    warnings: list = field(default_factory=list)

    @property
    def year(self):
        return self.effective.year

    @property
    def is_new(self):
        return self.kind == "new"


def _parse_date(s: str, anchor: date | None = None) -> date | None:
    s = s.strip().rstrip(".")
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})$", s)
    if not m:
        for fmt in ("%B %d", "%b %d", "%b. %d"):
            try:
                d = datetime.strptime(s, fmt)
                m = (d.month, d.day)
                break
            except ValueError:
                m = None
        if m is None:
            return None
        mo, dy = m
    else:
        mo, dy = int(m.group(1)), int(m.group(2))
    # Year-less date: the year that puts it within the year before (or a few weeks after) effective.
    if anchor is None:
        anchor = date.today()
    for yr in (anchor.year, anchor.year - 1, anchor.year + 1):
        try:
            d = date(yr, mo, dy)
        except ValueError:
            continue
        if timedelta(days=-60) <= (anchor - d) <= timedelta(days=330):
            return d
    return date(anchor.year, mo, dy)


def _match_key(label: str):
    l = label.lower().strip().strip("-•* ").rstrip(":")
    for key, names in LABEL_ALIASES.items():
        for n in names:
            if l == n or l.startswith(n):
                return key
    return None


def parse_intake(src) -> dict:
    """Accepts the short text format, a JSON string, or a dict. Returns a raw dict."""
    if isinstance(src, dict):
        return dict(src)
    s = src.strip()
    if s.startswith("{"):
        return json.loads(s)
    raw = {"milestones": []}
    lines = [ln.rstrip() for ln in s.splitlines() if ln.strip()]
    in_ms = False
    for i, ln in enumerate(lines):
        if i == 0 and ":" not in ln:
            m = re.match(r"^(.*?timeline)\s*[–—-]\s*(.+)$", ln, re.I)
            if m:
                raw["client"] = m.group(2).strip()
                raw["type"] = "new" if re.search(r"\bnew\b", m.group(1), re.I) else "renewal"
            else:
                raw["client"] = ln.strip()
            continue
        if re.match(r"^\s*(special\s+)?milestones?\s*:?\s*$", ln, re.I):
            in_ms = True
            continue
        if ":" in ln:
            label, val = ln.split(":", 1)
            key = None if in_ms and ln.lstrip().startswith(("-", "•", "*")) else _match_key(label)
            if key:
                raw[key] = val.strip()
                in_ms = False
            elif in_ms or ln.lstrip().startswith(("-", "•", "*")):
                parts = [p.strip() for p in val.split("|")]
                raw["milestones"].append({"label": label.strip().lstrip("-•* ").strip(),
                                          "date": parts[0],
                                          "owner": parts[1] if len(parts) > 1 else ""})
    return raw


def _short_name(client: str) -> str:
    words = re.sub(r"[,.]", " ", client).split()
    drop = {"inc", "llc", "llp", "lp", "pllc", "pc", "co", "corp", "corporation", "company",
            "holdings", "group", "the", "ltd", "incorporated", "enterprises", "services"}
    kept = [w for w in words if w.lower() not in drop]
    kept = kept[:2] if kept else words[:2]
    return " ".join(kept) or client


def _nth_weekday(yr, mo, wd, n):
    d = date(yr, mo, 1)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(yr, mo, wd):
    d = date(yr, mo + 1, 1) - timedelta(days=1) if mo < 12 else date(yr, 12, 31)
    return d - timedelta(days=(d.weekday() - wd) % 7)


def holidays(yr: int) -> dict:
    """Office-closure holidays that commonly derail enrollment work."""
    tg = _nth_weekday(yr, 11, 3, 4)
    return {date(yr, 1, 1): "New Year's Day", _last_weekday(yr, 5, 0): "Memorial Day",
            date(yr, 7, 4): "Independence Day", _nth_weekday(yr, 9, 0, 1): "Labor Day",
            tg: "Thanksgiving", tg + timedelta(days=1): "the day after Thanksgiving",
            date(yr, 12, 24): "Christmas Eve", date(yr, 12, 25): "Christmas Day",
            date(yr, 12, 31): "New Year's Eve"}


def _is_off(d: date) -> bool:
    return d.weekday() >= 5 or d in holidays(d.year)


def _weekday_back(d: date) -> date:
    while _is_off(d):
        d -= timedelta(days=1)
    return d


def _weekday_fwd(d: date) -> date:
    while _is_off(d):
        d += timedelta(days=1)
    return d


def _bizdays(a: date, b: date) -> int:
    n, d = 0, a
    while d <= b:
        if not _is_off(d):
            n += 1
        d += timedelta(days=1)
    return n


def build_plan(raw: dict, today: date | None = None) -> Plan:
    today = today or date.today()
    client = (raw.get("client") or "").strip()
    if not client:
        raise ValueError("Client name is required.")
    eff = raw.get("effective")
    eff = eff if isinstance(eff, date) else _parse_date(str(eff or ""), today + timedelta(days=200))
    if not eff:
        raise ValueError("Effective date is required (e.g. 1/1/27).")
    kind = "new" if str(raw.get("type", "renewal")).lower().startswith("new") else "renewal"
    short = (raw.get("short_name") or "").strip() or _short_name(client)

    dates, suggested = {}, []
    for k in CORE_KEYS:
        v = raw.get(k)
        d = v if isinstance(v, date) else _parse_date(str(v or ""), eff)
        if d is None:
            d = eff - timedelta(days=DEFAULT_OFFSETS[k])
            d = _weekday_fwd(d) if k == "oe_start" else _weekday_back(d)
            suggested.append(k)
        dates[k] = d

    # Keep suggested dates consistent with the dates that WERE supplied.
    gaps = {("quotes_expected", "quotes_back"): 7, ("quotes_back", "decision"): 2,
            ("decision", "build"): 2, ("build", "oe_start"): 1, ("oe_start", "oe_end"): 6,
            ("oe_end", "submission"): 2}
    def add_bd(d0, n):
        step = 1 if n >= 0 else -1
        d1 = d0
        for _ in range(abs(n)):
            d1 += timedelta(days=step)
            while _is_off(d1):
                d1 += timedelta(days=step)
        return d1
    for a, b in zip(CORE_KEYS, CORE_KEYS[1:]):          # forward pass
        if b in suggested and dates[b] < add_bd(dates[a], gaps[(a, b)]):
            dates[b] = add_bd(dates[a], gaps[(a, b)])
    for a, b in reversed(list(zip(CORE_KEYS, CORE_KEYS[1:]))):   # backward pass
        if a in suggested and b not in suggested and dates[a] > add_bd(dates[b], -gaps[(a, b)]):
            dates[a] = add_bd(dates[b], -gaps[(a, b)])

    ms = []
    for m in raw.get("milestones") or []:
        d = m.get("date")
        d = d if isinstance(d, date) else _parse_date(str(d or ""), eff)
        if d:
            ms.append((m.get("label", "").strip(), d, (m.get("owner") or "").strip()))
    if not ms and raw.get("suggest_milestones", True):
        ref = dict(dates, effective=eff)
        for label, (k, off), owner in SUGGESTED_MILESTONES:
            ms.append((label, _weekday_back(ref[k] + timedelta(days=off)), owner))
        suggested.append("milestones")
    ms.sort(key=lambda x: x[1])

    p = Plan(client=client, short=short, kind=kind, effective=eff, dates=dates,
             milestones=ms, suggested=suggested)
    p.warnings = validate(p, today)
    return p


def validate(p: Plan, today: date) -> list:
    w, d = [], p.dates
    seq = CORE_KEYS
    for a, b in zip(seq, seq[1:]):
        if d[b] < d[a]:
            w.append(f"{LABELS[b]} ({fmt_md(d[b])}) is before {LABELS[a]} ({fmt_md(d[a])}).")
    if d["submission"] >= p.effective:
        w.append("Carrier submission is on/after the effective date.")
    lead = (p.effective - d["submission"]).days
    if 0 < lead < 21:
        w.append(f"Only {lead} days between carrier submission and effective date — "
                 "tight for ID cards, eligibility loads and payroll.")
    oe_bd = _bizdays(d["oe_start"], d["oe_end"])
    hol = sorted({n for dd, n in {**holidays(d["oe_start"].year), **holidays(d["oe_end"].year)}.items()
                  if d["oe_start"] <= dd <= d["oe_end"]})
    if hol:
        w.append(f"The OE window includes {' and '.join(hol)} — only {oe_bd} working days. "
                 "Consider extending a day or two or opening earlier.")
    elif oe_bd < 5:
        w.append(f"Open enrollment is only {oe_bd} business days — consider at least 5.")
    if (d["decision"] - d["quotes_back"]).days < 2:
        w.append("Less than 2 days between final quotes and plan decision.")
    ql = (p.effective - d["quotes_expected"]).days
    if not p.is_new and ql < 60:
        w.append(f"Renewal expected only {ql} days before effective — carriers usually release "
                 "1/1 renewals 60–90 days out; push for an earlier release.")
    for k in CORE_KEYS:
        hn = holidays(d[k].year).get(d[k])
        if hn:
            w.append(f"{LABELS[k]} falls on {hn} ({fmt_md(d[k])}).")
        elif d[k].weekday() >= 5:
            w.append(f"{LABELS[k]} falls on a {d[k].strftime('%A')} ({fmt_md(d[k])}).")
    return w


# ──────────────────────────────────────────────────────────────────────────────
# 2. Content (shared by PDF and Word)
# ──────────────────────────────────────────────────────────────────────────────

LABELS = {"quotes_expected": "Quotes expected", "quotes_back": "All quotes back",
          "decision": "Plan decision", "build": "Build complete", "oe_start": "OE starts",
          "oe_end": "OE ends", "submission": "Carrier submission"}

PALETTE = {
    "navy": "#0E2A47", "ink": "#1E2B3A", "muted": "#5B6878", "line": "#D9E1EA",
    "mist": "#EEF3F8", "cream": "#FBF4E2", "white": "#FFFFFF",
    "gold": "#E9B949", "brand_blue": "#498DCB", "brand_green": "#85B440",
}
STEP_COLORS = ["#1F5A85", "#2A9493", "#E2AA3B", "#E5853A",
               "#62A462", "#D2524E", "#2367A3", "#0E2A47"]


def fmt_md(d: date) -> str:
    return f"{d.month}/{d.day}"


def fmt_mdy(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year}"


def fmt_mon(d: date) -> str:
    return d.strftime("%b").upper() + f" {d.day}"


def fmt_long(d: date) -> str:
    m = d.strftime("%B")
    return f"{m} {d.day}"


def fmt_abbr(d: date) -> str:
    m = d.strftime("%b")
    return (m if m == "May" else m + ".") + f" {d.day}"


def fmt_range(a: date, b: date) -> str:
    if a == b:
        return fmt_abbr(a)
    if a.month == b.month:
        return f"{fmt_abbr(a)}–{b.day}"
    return f"{fmt_abbr(a)} – {fmt_abbr(b)}"


def steps(p: Plan) -> list:
    """The eight timeline milestones: (date, title, body, chip, owner)."""
    d, s, eff = p.dates, p.short, p.effective
    if p.is_new:
        first = ("Initial quotes received",
                 "First round of market quotes back from the census. Begin the side-by-side "
                 "review and flag any underwriting needs.", "QUOTES", "Carriers / TBG")
    else:
        first = ("Expected renewal",
                 "Current carrier renewal expected. Once received, begin marketing and request "
                 "competitive quotes.", "RENEWAL", "Carrier / TBG")
    return [
        (d["quotes_expected"], *first[:3], first[3]),
        (d["quotes_back"], "Final quotes & analysis",
         "All quotes targeted back. Finalize the side-by-side analysis and recommendation "
         "package.", "ANALYZE", "TBG"),
        (d["decision"], "Plan decision",
         f"{s} selects plan(s), employer contribution strategy, and final benefit design.",
         "DECIDE", s),
        (d["build"], "Enrollment build complete",
         "Enrollment platform built with rates, plan rules and deductions; test link sent for "
         "approval.", "BUILD", "TBG"),
        (d["oe_start"], "Open enrollment opens",
         "Employees receive enrollment instructions, the benefit guide and SBCs, and begin "
         "elections.", "ENROLL", f"{s} employees"),
        (d["oe_end"], "Open enrollment closes",
         "Target close date. Begin the final audit for missing elections, waivers and "
         "dependent data.", "CLOSE", f"{s} employees"),
        (d["submission"], "Carrier submission",
         "Resolve final corrections and transmit completed elections and forms to the "
         "carrier(s).", "SUBMIT", "TBG"),
        (eff, "Coverage effective",
         f"{p.year} benefits become effective. ID cards and member portals live.",
         "GO LIVE", "Carrier"),
    ]


def goal_text(p: Plan) -> str:
    lead = (p.effective - p.dates["submission"]).days
    span = "a full month" if lead >= 28 else f"{lead} days"
    return (f"Complete carrier elections by {fmt_long(p.dates['submission'])}, leaving {span} for "
            "carrier processing, ID cards, payroll setup, and cleanup.")


def buffer_text(p: Plan) -> str:
    return (f"Submitting by {fmt_abbr(p.dates['submission'])} creates room for carrier review, "
            "eligibility cleanup, payroll reconciliation, ID cards, and first-invoice checks "
            f"before {fmt_md(p.effective)}.")


def checkpoints(p: Plan) -> list:
    """Six cards: (title, when, bullets)."""
    d, s, eff = p.dates, p.short, p.effective
    one = timedelta(days=1)
    if p.is_new:
        c1 = ("Pre-market data check", f"Before quotes are requested",
              ["Confirm a complete census: DOB, ZIP, coverage tier, salary and class for "
               "every eligible employee.",
               "Validate eligibility classes, waiting period, and minimum participation / "
               "contribution targets.",
               "Gather current plan summaries, renewal and recent bill for apples-to-apples "
               "comparison.",
               "Note COBRA participants, pending life events, and anyone on leave."])
    else:
        c1 = ("Pre-market data check", "Before final quote review",
              ["Confirm final employee/dependent census and eligibility classes.",
               "Validate current plans, contributions, waiting period, and effective-date "
               "rules.",
               "Identify known terminations, new hires, COBRA participants, or pending life "
               "events.",
               "Request claims / large-claimant data where available to support marketing."])
    c2 = ("Decision package", f"By {fmt_abbr(d['decision'])}",
          ["Approve carrier, plan design(s), and employer contribution strategy.",
           "Run the ACA affordability check on the lowest-cost employee-only option "
           "(applicable large employers).",
           "Confirm which plans are being replaced, retained, or mapped.",
           "Collect final rates, SBCs, benefit summaries, and any required enrollment forms."])
    if p.is_new:
        c2[2].insert(1, "Sign the employer application and confirm participation and "
                        "contribution requirements are met.")
    c3 = ("Enrollment build QA", fmt_range(d["decision"] + one, d["build"]),
          ["Test rates by tier and payroll frequency.",
           "Confirm dependent eligibility, plan mapping, waivers, and required questions.",
           "Load required notices (SBCs, annual notices) into the platform.",
           f"Have {s} test the employee experience before launch."])
    c4 = ("Employee communication & OE", fmt_range(d["oe_start"], d["oe_end"]),
          [f"Send enrollment instructions, deadlines, benefit guide, and support contacts on "
           f"{fmt_abbr(d['oe_start'])}.",
           f"Open enrollment runs {fmt_range(d['oe_start'], d['oe_end'])} — employees log in, "
           "review options, and make or change elections.",
           "Track non-responders and collect a waiver from every eligible employee who "
           "declines.",
           "Flag employees who need one-on-one help before the close date."])
    c5 = ("Post-enrollment audit", fmt_range(d["oe_end"] + one, d["submission"]),
          ["Reconcile enrollments, waivers, dependents, coverage tiers, and payroll "
           "deductions.",
           "Resolve evidence-of-insurability (EOI) and missing-data items where applicable.",
           "Submit clean carrier files/forms and retain confirmation of receipt."])
    if p.is_new:
        c5[2].append("Remit the binder / first-month premium and confirm the group is "
                     "approved before giving prior-carrier notice.")
    month = (d["submission"] + one).strftime("%B")
    when6 = month if (d["submission"] + one).month == (eff - one).month else \
        fmt_range(d["submission"] + one, eff)
    c6 = ("Pre-effective follow-through", when6,
          ["Confirm carrier implementation is complete and eligibility is loaded correctly.",
           "Send the payroll deduction file to payroll before the first "
           f"{p.year} check.",
           "Review ID card / member-access timing and communicate expectations to employees.",
           "Reconcile the first invoice and payroll deductions against final elections."])
    return [c1, c2, c3, c4, c5, c6]


def best_practice(p: Plan) -> str:
    return (f"Treat {fmt_abbr(p.dates['submission'])} as the hard carrier-submission target — "
            f"not the last possible day. The extra buffer is what protects a smooth "
            f"{fmt_long(p.effective)} launch.")


def checklist(p: Plan) -> list:
    """Page 3 compliance & don't-miss checklist: [(section, [items])]."""
    req = ("Required notices & documents", [
        "SBCs for every medical plan offered, delivered with enrollment materials",
        "Annual notices: CHIP, WHCRA, HIPAA special enrollment, privacy-notice availability",
        "Medicare Part D creditable-coverage notice to new enrollees (annual notice due Oct. 15)",
        "Section 125 / premium-only plan document reflects the new plans and contributions",
        "ERISA wrap / SPD updated; summary of material modifications for any changes",
        "COBRA general notice to newly covered employees and spouses",
    ])
    if p.is_new:
        mid = ("New group essentials", [
            "Signed employer application and carrier group forms",
            "Participation and employer-contribution minimums met, with valid waivers",
            "Binder / first-month premium payment remitted",
            "Prior carrier terminated to align with the new effective date — never before approval",
            "Wage & tax / payroll report and business documentation for underwriting",
            "Deductible credit, transition-of-care and Rx prior-authorization transfers",
        ])
    else:
        mid = ("Often-missed details", [
            "ACA affordability test on the lowest-cost employee-only plan (ALEs)",
            f"{p.year} HSA / FSA limits reflected; employer HSA funding schedule set",
            "EOI submitted for voluntary life / disability above guaranteed issue",
            "COBRA and state-continuation members carried into new-year elections",
            "Network and Rx disruption review if changing carriers",
            "Waivers on file for every eligible employee who declines coverage",
        ])
    post = ("After the effective date", [
        "ID cards received and member portals active (temporary IDs if needed)",
        "First invoice reconciled to enrollment and payroll deductions",
        "Enrollment confirmations and election records retained",
        "Year-end reporting on the calendar: ACA 1094/1095 (ALEs), Form 5500 (100+ participants)",
    ])
    return [req, mid, post]


def key_dates(p: Plan) -> list:
    rows = [(dt, title, owner) for dt, title, _b, _c, owner in steps(p)]
    rows += [(dt, label, owner or "TBG / Client") for label, dt, owner in p.milestones]
    rows.sort(key=lambda r: r[0])
    return rows


def title_line(p: Plan) -> str:
    return (f"{p.year} Benefits Implementation & Open Enrollment Timeline" if p.is_new
            else f"{p.year} Benefits Renewal & Open Enrollment Timeline")


def file_stem(p: Plan) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "_", p.client).strip("_")
    return f"{name}_Open_Enrollment_Timeline_{p.year}"


# ──────────────────────────────────────────────────────────────────────────────
# 3. PDF (ReportLab — pure Python, runs on Render)
# ──────────────────────────────────────────────────────────────────────────────

def _fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [os.path.join(here, "fonts"), "./fonts", "/usr/share/fonts/truetype/poppins"]
    want = {"P-Light": "Poppins-Light.ttf", "P-Reg": "Poppins-Regular.ttf",
            "P-Med": "Poppins-Medium.ttf", "P-Bold": "Poppins-Bold.ttf"}
    try:
        for name, fn in want.items():
            path = next(os.path.join(d, fn) for d in dirs if os.path.exists(os.path.join(d, fn)))
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, path))
        return {"light": "P-Light", "reg": "P-Reg", "med": "P-Med", "bold": "P-Bold"}
    except StopIteration:
        return {"light": "Helvetica", "reg": "Helvetica", "med": "Helvetica-Bold",
                "bold": "Helvetica-Bold"}


def render_pdf(p: Plan, path: str | None = None) -> bytes:
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.platypus import Paragraph
    from reportlab.pdfgen import canvas

    F = _fonts()
    C = {k: HexColor(v) for k, v in PALETTE.items()}
    W, H = landscape(letter)
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=(W, H))
    cv.setTitle(f"{p.client} — {title_line(p)}")
    cv.setAuthor("The Benefits Group")
    cv.setSubject("Open enrollment timeline")

    def para(text, size, font, color, align=TA_LEFT, lead=None):
        return ParagraphStyle("x", fontName=font, fontSize=size, textColor=color,
                              alignment=align, leading=lead or size * 1.35)

    def draw_para(text, style, x, y_top, w):
        pr = Paragraph(text, style)
        _, h = pr.wrap(w, 1000)
        pr.drawOn(cv, x, y_top - h)
        return h

    def para_h(text, style, w):
        return Paragraph(text, style).wrap(w, 1000)[1]

    def header(title, sub, pill=None):
        cv.setFillColor(C["navy"])
        cv.rect(0, H - 78, W, 78, stroke=0, fill=1)
        # brand accent rule: blue + green
        cv.setFillColor(C["brand_blue"]); cv.rect(0, H - 82, W * 0.72, 4, stroke=0, fill=1)
        cv.setFillColor(C["brand_green"]); cv.rect(W * 0.72, H - 82, W * 0.28, 4, stroke=0, fill=1)
        cv.setFillColor(C["white"])
        size = 24
        while cv.stringWidth(title, F["bold"], size) > W - 300 and size > 15:
            size -= 1
        cv.setFont(F["bold"], size)
        cv.drawString(36, H - 42, title)
        cv.setFont(F["light"], 11.5)
        cv.setFillColor(HexColor("#C9D6E4"))
        cv.drawString(36, H - 62, sub)
        if pill:
            cv.setFont(F["bold"], 13)
            tw = cv.stringWidth(pill, F["bold"], 13)
            pw, ph = tw + 36, 34
            px, py = W - 36 - pw, H - 39 - ph / 2
            cv.setFillColor(C["gold"])
            cv.roundRect(px, py, pw, ph, 9, stroke=0, fill=1)
            cv.setFillColor(C["navy"])
            cv.drawCentredString(px + pw / 2, py + 11.5, pill)

    def footer(left, right):
        cv.setFont(F["reg"], 7.5)
        cv.setFillColor(C["muted"])
        cv.drawString(36, 20, left)
        cv.drawRightString(W - 36, 20, right)

    def chip(cx, y, text, color):
        cv.setFont(F["bold"], 6.3)
        tw = cv.stringWidth(text, F["bold"], 6.3)
        w, h = tw + 16, 12
        cv.setFillColor(color)
        cv.roundRect(cx - w / 2, y, w, h, 6, stroke=0, fill=1)
        cv.setFillColor(C["white"])
        cv.drawCentredString(cx, y + 3.6, text)

    def shadow_card(x, y, w, h, r=8):
        cv.setFillColor(Color(0.05, 0.16, 0.28, alpha=0.07))
        cv.roundRect(x + 1.2, y - 2, w, h, r, stroke=0, fill=1)
        cv.setFillColor(C["white"])
        cv.setStrokeColor(C["line"])
        cv.setLineWidth(0.7)
        cv.roundRect(x, y, w, h, r, stroke=1, fill=1)

    # ── Page 1: timeline ───────────────────────────────────────────────────
    eff_lbl = f"Effective {fmt_mdy(p.effective)}"
    header(p.client.upper(), title_line(p), eff_lbl)

    # goal bar
    cv.setFillColor(C["mist"])
    cv.roundRect(36, H - 122, W - 72, 28, 8, stroke=0, fill=1)
    cv.setFillColor(C["brand_blue"])
    cv.roundRect(36, H - 122, 5, 28, 2, stroke=0, fill=1)
    draw_para(f"<font name='{F['bold']}' color='#0E2A47'>Goal:</font>&nbsp;&nbsp;{goal_text(p)}",
              para("", 9, F["reg"], C["ink"]), 52, H - 101.5, W - 100)

    st = steps(p)
    axis_y = 318
    x0, x1 = 108, W - 108
    xs = [x0 + i * (x1 - x0) / 7 for i in range(8)]
    cw = 148
    title_st = para("", 9.6, F["bold"], C["ink"], TA_CENTER, 12)
    body_st = para("", 7.8, F["reg"], C["muted"], TA_CENTER, 10.4)
    # uniform card height
    inner = cw - 16
    need = max(para_h(t, title_st, inner) + para_h(b, body_st, inner) for _, t, b, _, _ in st)
    card_h = 24 + 8 + need + 6 + 12 + 10
    gap = 30

    # OE window band on the axis
    cv.setStrokeColor(C["line"]); cv.setLineWidth(5); cv.setLineCap(1)
    cv.line(x0 - 30, axis_y, x1 + 30, axis_y)
    cv.setStrokeColor(HexColor("#BFE0BF")); cv.setLineWidth(9)
    cv.line(xs[4], axis_y, xs[5], axis_y)
    oe_days = (p.dates["oe_end"] - p.dates["oe_start"]).days + 1
    cv.setFont(F["med"], 6.6); cv.setFillColor(HexColor("#3E7E3E"))
    lbl = f"OE WINDOW · {oe_days} DAYS"
    # place label under the band, left of bottom card stack
    cv.drawCentredString((xs[4] + xs[5]) / 2, axis_y + 10, lbl)

    for i, (dt, title, body, chiptxt, owner) in enumerate(st):
        col = HexColor(STEP_COLORS[i])
        x = xs[i]
        top = (i % 2 == 0)
        cy = axis_y + gap if top else axis_y - gap - card_h
        # connector
        cv.setStrokeColor(col); cv.setLineWidth(1.2); cv.setDash(2, 2)
        if top:
            cv.line(x, axis_y + 8, x, cy)
        else:
            cv.line(x, axis_y - 8, x, cy + card_h)
        cv.setDash()
        # dot
        cv.setFillColor(C["white"]); cv.setStrokeColor(col); cv.setLineWidth(2.4)
        cv.circle(x, axis_y, 7.5, stroke=1, fill=1)
        cv.setFillColor(col); cv.circle(x, axis_y, 3.6, stroke=0, fill=1)
        # card
        lx = x - cw / 2
        shadow_card(lx, cy, cw, card_h)
        # date tab (rounded top)
        cv.setFillColor(col)
        cv.roundRect(lx, cy + card_h - 24, cw, 24, 8, stroke=0, fill=1)
        cv.rect(lx, cy + card_h - 24, cw, 10, stroke=0, fill=1)
        cv.setFillColor(C["white"] if i not in (2,) else C["navy"])
        cv.setFont(F["bold"], 11)
        cv.drawCentredString(x, cy + card_h - 16.5, fmt_mon(dt))
        yy = cy + card_h - 24 - 8
        yy -= draw_para(title, title_st, lx + 8, yy, inner)
        yy -= 2
        draw_para(body, body_st, lx + 8, yy, inner)
        chip(x, cy + 9, chiptxt, col)

    # also-on-the-calendar strip (special milestones)
    strip_y = 128
    if p.milestones:
        cv.setFont(F["bold"], 7.2); cv.setFillColor(C["navy"])
        cv.drawString(36, strip_y + 6, "ALSO ON THE")
        cv.drawString(36, strip_y - 4, "CALENDAR")
        sx0 = 36 + cv.stringWidth("ALSO ON THE", F["bold"], 7.2) + 14
        sx = sx0
        for label, dt, _o in p.milestones:
            t = f"{fmt_md(dt)}  {label}"
            cv.setFont(F["reg"], 7.2)
            tw = cv.stringWidth(t, F["reg"], 7.2) + 18
            if sx + tw > W - 36:
                if strip_y < 120:
                    break
                strip_y -= 22
                sx = sx0
            cv.setFillColor(C["white"]); cv.setStrokeColor(C["line"]); cv.setLineWidth(0.7)
            cv.roundRect(sx, strip_y, tw, 18, 9, stroke=1, fill=1)
            cv.setFillColor(C["brand_blue"]); cv.circle(sx + 8, strip_y + 9, 2.2, stroke=0, fill=1)
            cv.setFillColor(C["ink"])
            cv.setFont(F["bold"], 7.2); cv.drawString(sx + 13, strip_y + 6.3, fmt_md(dt))
            dw = cv.stringWidth(fmt_md(dt), F["bold"], 7.2)
            cv.setFont(F["reg"], 7.2); cv.drawString(sx + 13 + dw + 4, strip_y + 6.3, label)
            sx += tw + 6

    # buffer bar
    cv.setFillColor(C["cream"])
    cv.roundRect(36, 44, W - 72, 44, 8, stroke=0, fill=1)
    cv.setFillColor(C["gold"]); cv.roundRect(36, 44, 5, 44, 2, stroke=0, fill=1)
    cv.setFont(F["bold"], 9); cv.setFillColor(C["navy"])
    cv.drawString(54, 62.5, "Built-in buffer")
    draw_para(buffer_text(p), para("", 8.8, F["reg"], C["ink"]), 140, 72, W - 190)
    footer("The Benefits Group  |  thebenefits.group", f"{'Implementation' if p.is_new else 'Renewal'} Planning Timeline  ·  Page 1 of 3")
    cv.showPage()

    # ── Page 2: checkpoints ────────────────────────────────────────────────
    header("RECOMMENDED RENEWAL CHECKPOINTS" if not p.is_new else "RECOMMENDED IMPLEMENTATION CHECKPOINTS",
           f"A few items worth confirming so nothing gets lost between plan selection and "
           f"{fmt_md(p.effective)}.")
    cps = checkpoints(p)
    cols = [STEP_COLORS[0], STEP_COLORS[2], STEP_COLORS[3], STEP_COLORS[4], STEP_COLORS[5],
            STEP_COLORS[7]]
    gx, gw = 36, (W - 72 - 2 * 16) / 3
    ch_top = H - 104
    row_h = 196
    gw_in = gw - 36
    bsize = 8.3
    while bsize > 7.0:
        bullet_st = para("", bsize, F["reg"], C["ink"], TA_LEFT, bsize * 1.35)
        need = max(sum(para_h(b, bullet_st, gw_in) + 4.5 for b in bl) for _t, _w, bl in cps)
        if need + 62 <= row_h:
            break
        bsize -= 0.2
    for k, (title, when, bullets) in enumerate(cps):
        r, c = divmod(k, 3)
        x = gx + c * (gw + 16)
        ytop = ch_top - r * (row_h + 14)
        col = HexColor(cols[k])
        shadow_card(x, ytop - row_h, gw, row_h)
        cv.setFillColor(col)
        cv.roundRect(x, ytop - 28, gw, 28, 8, stroke=0, fill=1)
        cv.rect(x, ytop - 28, gw, 10, stroke=0, fill=1)
        cv.setFillColor(C["navy"] if k == 1 else C["white"])
        cv.setFont(F["bold"], 9.6)
        cv.drawString(x + 12, ytop - 18.5, f"{k + 1}.  {title}")
        cv.setFont(F["bold"], 7.6); cv.setFillColor(col if k != 1 else HexColor("#B4841F"))
        cv.drawString(x + 12, ytop - 44, when)
        yy = ytop - 54
        for b in bullets:
            cv.setFillColor(col)
            cv.circle(x + 15, yy - 5.2, 1.9, stroke=0, fill=1)
            yy -= draw_para(b, bullet_st, x + 23, yy, gw - 36) + 4.5
    # best practice bar
    cv.setFillColor(C["navy"])
    cv.roundRect(36, 40, W - 72, 46, 9, stroke=0, fill=1)
    cv.setFont(F["bold"], 9); cv.setFillColor(C["gold"])
    cv.drawString(54, 59.5, "BEST PRACTICE")
    draw_para(best_practice(p), para("", 9, F["reg"], C["white"]), 148, 70, W - 200)
    footer("The Benefits Group  |  thebenefits.group",
           f"Prepared for {p.client}  |  {fmt_mdy(p.effective)} {'Implementation' if p.is_new else 'Renewal'}  ·  Page 2 of 3")
    cv.showPage()

    # ── Page 3: key dates + don't-miss checklist ──────────────────────────
    header("KEY DATES & COMPLIANCE CHECKLIST",
           "Every date in one place, plus the notices and details that are easiest to miss.")
    # left: key dates table
    tx, ty, tw = 36, H - 104, 300
    cv.setFont(F["bold"], 10); cv.setFillColor(C["navy"])
    cv.drawString(tx, ty - 4, "Key dates at a glance")
    rows = key_dates(p)
    yy = ty - 22
    cv.setFont(F["bold"], 6.8); cv.setFillColor(C["muted"])
    cv.drawString(tx + 8, yy, "DATE"); cv.drawString(tx + 62, yy, "MILESTONE")
    cv.drawRightString(tx + tw - 8, yy, "OWNER")
    yy -= 6
    rh = min(22, (yy - 50) / max(len(rows), 1))
    core_titles = {s_[1]: STEP_COLORS[i] for i, s_ in enumerate(st)}
    for n, (dt, title, owner) in enumerate(rows):
        if n % 2 == 0:
            cv.setFillColor(C["mist"])
            cv.roundRect(tx, yy - rh, tw, rh, 4, stroke=0, fill=1)
        mid = yy - rh / 2 - 3
        colhex = core_titles.get(title)
        cv.setFillColor(HexColor(colhex) if colhex else C["white"])
        cv.setStrokeColor(HexColor(colhex) if colhex else C["brand_blue"]); cv.setLineWidth(1.2)
        cv.circle(tx + 10, mid + 3, 3, stroke=1, fill=1)
        cv.setFont(F["bold"], 8); cv.setFillColor(C["ink"])
        cv.drawString(tx + 20, mid, f"{dt.strftime('%a')} {fmt_md(dt)}")
        cv.setFont(F["med"] if colhex else F["reg"], 8)
        cv.drawString(tx + 62, mid, title)
        cv.setFont(F["reg"], 7); cv.setFillColor(C["muted"])
        cv.drawRightString(tx + tw - 8, mid, owner)
        yy -= rh
    # right: checklist
    rx, rw = tx + tw + 24, W - 36 - (tx + tw + 24)
    sec_cols = [C["brand_blue"], HexColor(STEP_COLORS[3]), C["brand_green"]]
    item_st = para("", 8.5, F["reg"], C["ink"], TA_LEFT, 11.4)
    yy = ty
    for si, (sec, items) in enumerate(checklist(p)):
        cv.setFillColor(sec_cols[si])
        cv.roundRect(rx, yy - 16, 4, 14, 2, stroke=0, fill=1)
        cv.setFont(F["bold"], 9.5); cv.setFillColor(C["navy"])
        cv.drawString(rx + 11, yy - 12.5, sec)
        yy -= 24
        half = (rw - 14) / 2
        colx = [rx, rx + half + 14]
        ys = [yy, yy]
        for ii, it in enumerate(items):
            cidx = 0 if ii < (len(items) + 1) // 2 else 1
            x = colx[cidx]
            cv.setStrokeColor(sec_cols[si]); cv.setLineWidth(1); cv.setFillColor(C["white"])
            cv.roundRect(x, ys[cidx] - 9, 8, 8, 1.5, stroke=1, fill=1)
            ys[cidx] -= draw_para(it, item_st, x + 14, ys[cidx], half - 16) + 7
        yy = min(ys) - 16
    cv.setFont(F["light"], 6.8); cv.setFillColor(C["muted"])
    draw_para("Checklist items are general reminders; applicability depends on group size, "
              "funding and plan design. The Benefits Group does not provide legal or tax advice.",
              para("", 6.8, F["light"], C["muted"]), rx, 62, rw)
    footer("The Benefits Group  |  thebenefits.group",
           f"Prepared for {p.client}  |  {fmt_mdy(p.effective)} {'Implementation' if p.is_new else 'Renewal'}  ·  Page 3 of 3")
    cv.showPage()
    cv.save()
    data = buf.getvalue()
    if path:
        with open(path, "wb") as f:
            f.write(data)
    return data


# ──────────────────────────────────────────────────────────────────────────────
# 4. Word (python-docx — editable, same content)
# ──────────────────────────────────────────────────────────────────────────────

def render_docx(p: Plan, path: str | None = None) -> bytes:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, Inches, RGBColor, Emu

    def rgb(h):
        h = h.lstrip("#")
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Inches(11), Inches(8.5)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Inches(0.55))
    sec.top_margin, sec.bottom_margin = Inches(0.45), Inches(0.5)
    usable = 11 - 1.1

    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    st.font.size = Pt(10)
    st.font.color.rgb = rgb(PALETTE["ink"])
    st.paragraph_format.space_after = Pt(0)
    st.paragraph_format.space_before = Pt(0)

    # footer
    fp = sec.footer.paragraphs[0]
    fp.text = ""
    r = fp.add_run(f"The Benefits Group  |  thebenefits.group        Prepared for {p.client}  |  "
                   f"{fmt_mdy(p.effective)} {'Implementation' if p.is_new else 'Renewal'}")
    r.font.size = Pt(8); r.font.color.rgb = rgb(PALETTE["muted"])

    def shade(cell, hexcol):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hexcol.lstrip("#"))
        tcPr.append(shd)

    def cell_margins(cell, top=80, bottom=80, left=120, right=120):
        tcPr = cell._tc.get_or_add_tcPr()
        mar = OxmlElement("w:tcMar")
        for k, v in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
            e = OxmlElement(f"w:{k}"); e.set(qn("w:w"), str(v)); e.set(qn("w:type"), "dxa")
            mar.append(e)
        tcPr.append(mar)

    def borders(table, color="D9E1EA", inside=True, size=4):
        tblPr = table._tbl.tblPr
        b = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{edge}")
            if edge.startswith("inside") and not inside:
                e.set(qn("w:val"), "nil")
            else:
                e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(size))
                e.set(qn("w:color"), color)
            b.append(e)
        tblPr.append(b)

    def no_borders(table):
        tblPr = table._tbl.tblPr
        b = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{edge}"); e.set(qn("w:val"), "nil"); b.append(e)
        tblPr.append(b)

    def widths(table, inches):
        table.autofit = False
        tblPr = table._tbl.tblPr
        lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
        for row in table.rows:
            for c, w in zip(row.cells, inches):
                c.width = Inches(w)
        grid = table._tbl.tblGrid
        for gc, w in zip(grid.findall(qn("w:gridCol")), inches):
            gc.set(qn("w:w"), str(int(w * 1440)))

    def write(cell_or_par, text, size=10, bold=False, color=None, align=None, italic=False,
              space_after=0, first=True):
        if hasattr(cell_or_par, "paragraphs"):
            par = cell_or_par.paragraphs[0] if first else cell_or_par.add_paragraph()
        else:
            par = cell_or_par
        run = par.add_run(text)
        run.font.size = Pt(size); run.bold = bold; run.italic = italic
        if color:
            run.font.color.rgb = rgb(color)
        if align:
            par.alignment = align
        par.paragraph_format.space_after = Pt(space_after)
        return par

    def bullet(cell, text, color, size=9):
        par = cell.add_paragraph()
        par.paragraph_format.left_indent = Inches(0.16)
        par.paragraph_format.first_line_indent = Inches(-0.16)
        par.paragraph_format.space_after = Pt(3)
        r1 = par.add_run("■  "); r1.font.size = Pt(6); r1.font.color.rgb = rgb(color)
        r2 = par.add_run(text); r2.font.size = Pt(size)
        return par

    def page_header(title, sub, pill=None):
        t = doc.add_table(rows=1, cols=2)
        no_borders(t)
        widths(t, [usable - 2.2, 2.2])
        a, b = t.rows[0].cells
        for c in (a, b):
            shade(c, PALETTE["navy"]); cell_margins(c, 160, 160, 220, 220)
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        write(a, title, 22, True, "FFFFFF")
        write(a, sub, 11, False, "C9D6E4", first=False)
        if pill:
            write(b, pill, 13, True, PALETTE["gold"], WD_ALIGN_PARAGRAPH.RIGHT)
        # brand rule
        rule = doc.add_paragraph()
        pPr = rule._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr"); bot = OxmlElement("w:bottom")
        bot.set(qn("w:val"), "single"); bot.set(qn("w:sz"), "24")
        bot.set(qn("w:color"), PALETTE["brand_blue"].lstrip("#")); bdr.append(bot); pPr.append(bdr)
        rule.paragraph_format.space_after = Pt(8)

    def callout(label, text, fill, edge, label_color, text_color):
        t = doc.add_table(rows=1, cols=1)
        borders(t, edge.lstrip("#"), size=12)
        widths(t, [usable])
        c = t.rows[0].cells[0]
        shade(c, fill); cell_margins(c, 110, 110, 200, 200)
        par = c.paragraphs[0]
        r1 = par.add_run(label + "   "); r1.bold = True; r1.font.size = Pt(10)
        r1.font.color.rgb = rgb(label_color)
        r2 = par.add_run(text); r2.font.size = Pt(10); r2.font.color.rgb = rgb(text_color)
        return t

    def spacer(pts=8):
        sp = doc.add_paragraph(); sp.paragraph_format.space_after = Pt(0)
        sp.paragraph_format.line_spacing = Pt(pts)

    # Page 1 ─ timeline
    page_header(p.client.upper(), title_line(p), f"Effective {fmt_mdy(p.effective)}")
    callout("Goal:", goal_text(p), PALETTE["mist"], PALETTE["brand_blue"], PALETTE["navy"],
            PALETTE["ink"])
    spacer(10)
    st_ = steps(p)
    colw = [1.15, 1.0, 6.25, 1.5]
    t = doc.add_table(rows=1 + len(st_), cols=4)
    borders(t, "D9E1EA", inside=True)
    widths(t, colw)
    hdr = t.rows[0].cells
    for c, txt in zip(hdr, ["DATE", "PHASE", "MILESTONE  ·  WHAT HAPPENS", "OWNER"]):
        shade(c, PALETTE["mist"]); cell_margins(c, 60, 60, 120, 120)
        write(c, txt, 8, True, PALETTE["muted"])
    for i, (dt, title, body, chiptxt, owner) in enumerate(st_):
        row = t.rows[i + 1].cells
        col = STEP_COLORS[i]
        for c in row:
            cell_margins(c, 70, 70, 120, 120)
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        shade(row[0], col)
        write(row[0], fmt_mon(dt), 12, True, PALETTE["navy"] if i == 2 else "FFFFFF",
              WD_ALIGN_PARAGRAPH.CENTER)
        write(row[1], chiptxt, 8.5, True, col)
        par = row[2].paragraphs[0]
        r1 = par.add_run(title + "  "); r1.bold = True; r1.font.size = Pt(10.5)
        r2 = par.add_run(body); r2.font.size = Pt(9); r2.font.color.rgb = rgb(PALETTE["muted"])
        write(row[3], owner, 9, False, PALETTE["ink"])
    spacer(10)
    if p.milestones:
        par = doc.add_paragraph()
        r = par.add_run("ALSO ON THE CALENDAR   "); r.bold = True; r.font.size = Pt(8.5)
        r.font.color.rgb = rgb(PALETTE["navy"])
        r = par.add_run("   ·   ".join(f"{fmt_md(d)} {l}" for l, d, _ in p.milestones))
        r.font.size = Pt(8.5)
        spacer(8)
    callout("Built-in buffer:", buffer_text(p), PALETTE["cream"], PALETTE["gold"],
            PALETTE["navy"], PALETTE["ink"])

    # Page 2 ─ checkpoints
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    page_header("RECOMMENDED IMPLEMENTATION CHECKPOINTS" if p.is_new
                else "RECOMMENDED RENEWAL CHECKPOINTS",
                f"A few items worth confirming so nothing gets lost between plan selection and "
                f"{fmt_md(p.effective)}.")
    cps = checkpoints(p)
    cols = [STEP_COLORS[0], STEP_COLORS[2], STEP_COLORS[3], STEP_COLORS[4], STEP_COLORS[5],
            STEP_COLORS[7]]
    gap = 0.18
    cw = (usable - 2 * gap) / 3
    t = doc.add_table(rows=5, cols=5)
    no_borders(t)
    widths(t, [cw, gap, cw, gap, cw])
    for k, (title, when, bullets) in enumerate(cps):
        r0 = 0 if k < 3 else 3
        ci = (k % 3) * 2
        hc, bc = t.rows[r0].cells[ci], t.rows[r0 + 1].cells[ci]
        shade(hc, cols[k]); cell_margins(hc, 90, 90, 140, 140)
        write(hc, f"{k + 1}.  {title}", 10.5, True, PALETTE["navy"] if k == 1 else "FFFFFF")
        cell_margins(bc, 90, 120, 140, 140)
        tcPr = bc._tc.get_or_add_tcPr()
        b = OxmlElement("w:tcBorders")
        for edge in ("left", "bottom", "right"):
            e = OxmlElement(f"w:{edge}"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4")
            e.set(qn("w:color"), "D9E1EA"); b.append(e)
        tcPr.append(b)
        write(bc, when, 9, True, "B4841F" if k == 1 else cols[k], space_after=3)
        for bl in bullets:
            bullet(bc, bl, cols[k], 9)
    spacer(6)
    callout("BEST PRACTICE:", best_practice(p), PALETTE["navy"], PALETTE["navy"],
            PALETTE["gold"], "FFFFFF")

    # Page 3 ─ key dates + checklist
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    page_header("KEY DATES & COMPLIANCE CHECKLIST",
                "Every date in one place, plus the notices and details that are easiest to miss.")
    outer = doc.add_table(rows=1, cols=3)
    no_borders(outer)
    lw, g = 4.0, 0.3
    widths(outer, [lw, g, usable - lw - g])
    L, _, R = outer.rows[0].cells
    write(L, "Key dates at a glance", 12, True, PALETTE["navy"], space_after=4)
    rows = key_dates(p)
    kt = L.add_table(rows=1 + len(rows), cols=3)
    borders(kt, "D9E1EA", inside=True)
    widths(kt, [0.95, 2.0, 1.05])
    for c, txt in zip(kt.rows[0].cells, ["DATE", "MILESTONE", "OWNER"]):
        shade(c, PALETTE["mist"]); cell_margins(c, 40, 40, 90, 90)
        write(c, txt, 7.5, True, PALETTE["muted"])
    core = {s_[1]: STEP_COLORS[i] for i, s_ in enumerate(st_)}
    for n, (dt, title, owner) in enumerate(rows):
        cs = kt.rows[n + 1].cells
        for c in cs:
            cell_margins(c, 40, 40, 90, 90)
        colhex = core.get(title)
        write(cs[0], f"{dt.strftime('%a')} {fmt_md(dt)}", 9, True,
              colhex if colhex else PALETTE["ink"])
        write(cs[1], title, 9, bool(colhex))
        write(cs[2], owner, 8, False, PALETTE["muted"])
    sec_cols = [PALETTE["brand_blue"], STEP_COLORS[3], PALETTE["brand_green"]]
    first = True
    for si, (sec_title, items) in enumerate(checklist(p)):
        par = R.paragraphs[0] if first else R.add_paragraph()
        first = False
        par.paragraph_format.space_before = Pt(0 if si == 0 else 8)
        par.paragraph_format.space_after = Pt(3)
        r = par.add_run("▌ "); r.font.color.rgb = rgb(sec_cols[si]); r.font.size = Pt(12)
        r = par.add_run(sec_title); r.bold = True; r.font.size = Pt(11.5)
        r.font.color.rgb = rgb(PALETTE["navy"])
        for it in items:
            q = R.add_paragraph()
            q.paragraph_format.left_indent = Inches(0.22)
            q.paragraph_format.first_line_indent = Inches(-0.22)
            q.paragraph_format.space_after = Pt(2.5)
            r = q.add_run("☐  "); r.font.size = Pt(10); r.font.color.rgb = rgb(sec_cols[si])
            r = q.add_run(it); r.font.size = Pt(9)
    q = R.add_paragraph()
    q.paragraph_format.space_before = Pt(8)
    r = q.add_run("Checklist items are general reminders; applicability depends on group size, "
                  "funding and plan design. The Benefits Group does not provide legal or tax "
                  "advice.")
    r.italic = True; r.font.size = Pt(7.5); r.font.color.rgb = rgb(PALETTE["muted"])

    doc.core_properties.author = "The Benefits Group"
    doc.core_properties.title = f"{p.client} — {title_line(p)}"
    out = io.BytesIO()
    doc.save(out)
    data = out.getvalue()
    if path:
        with open(path, "wb") as f:
            f.write(data)
    return data


# ──────────────────────────────────────────────────────────────────────────────
# 5. CLI
# ──────────────────────────────────────────────────────────────────────────────

def summary(p: Plan) -> str:
    lines = [f"{'New Group' if p.is_new else 'Renewal'} Timeline – {p.client}",
             f"Effective date: {fmt_md(p.effective)}/{str(p.year)[2:]}"]
    for k in CORE_KEYS:
        flag = "   ← suggested, please confirm" if k in p.suggested else ""
        lines.append(f"{LABELS[k]}: {fmt_md(p.dates[k])}{flag}")
    if p.milestones:
        lines.append("Milestones:" + ("   ← suggested set, please confirm"
                                      if "milestones" in p.suggested else ""))
        for l, d, o in p.milestones:
            lines.append(f"- {l}: {fmt_md(d)}" + (f" | {o}" if o else ""))
    if p.warnings:
        lines.append("\nHeads-up:")
        lines += [f"  • {w}" for w in p.warnings]
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("intake")
    ap.add_argument("--out", default=".")
    ap.add_argument("--today", default=None)
    a = ap.parse_args()
    with open(a.intake, encoding="utf-8") as fh:
        raw = parse_intake(fh.read())
    today = datetime.strptime(a.today, "%Y-%m-%d").date() if a.today else None
    plan = build_plan(raw, today)
    os.makedirs(a.out, exist_ok=True)
    stem = file_stem(plan)
    render_pdf(plan, os.path.join(a.out, stem + ".pdf"))
    render_docx(plan, os.path.join(a.out, stem + ".docx"))
    print(summary(plan))
    print(f"\nWrote {stem}.pdf and {stem}.docx to {a.out}")
