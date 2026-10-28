"""
proposal_fields.py — one definition of what a proposal shows, shared by generate_pdf.py,
generate_excel.py and app.py (added 2026-10-15).

Why this file exists: the plan cards used to read a handful of medical keys and printed
"See SBC" for everything else, so dental and vision cards were mostly "See SBC". The fields
below are the full schema the Analyze Quotes routine now writes into the selector page
(SELECTOR SCHEMA v2). Both generators read the same rows from here, so the PDF and the Excel
can never disagree about which benefits a plan shows.

Rules the generators follow:
  * A value that is missing, blank or the legacy placeholder "See SBC" is treated as not stated.
  * A row is shown when at least one included plan in that coverage line has a value; a plan
    that lacks it shows "See SBC" (Will prefers that to a dash).
  * A plan is ILLUSTRATIVE when it says so (illustrative: true, or quote_status / name / notes
    mention illustrative, IMQs, health questionnaires, apps required, indicative, not sellable).
    Illustrative plans are labelled on the card, on the cover, in the Excel and in the disclaimers.
"""
import re

MISSING = "See SBC"   # final fallback when the quote does not state a value (Will, 2026-10-15)

# ── ROW SPECS ─────────────────────────────────────────────────────────────────
# ("section", title) starts a group; ("row", label, key) is one value; ("pair", label, k1, k2)
# prints "k1 / k2" (Ind / Fam). A key may be a tuple of fallbacks (new name first, legacy after).

MEDICAL_ROWS = [
    ("section", "Plan"),
    ("row",  "Network",               "network"),
    ("row",  "HSA eligible",          "hsa_eligible"),
    ("section", "Deductible"),
    ("pair", "In-network Ind / Fam",  "deductible_in_ind", "deductible_in_fam"),
    ("pair", "Out-of-network Ind / Fam", "deductible_out_ind", "deductible_out_fam"),
    ("section", "Out-of-Pocket Max"),
    ("pair", "In-network Ind / Fam",  "oop_in_ind", "oop_in_fam"),
    ("pair", "Out-of-network Ind / Fam", "oop_out_ind", "oop_out_fam"),
    ("section", "Coinsurance"),
    ("row",  "In-network",            "coinsurance_in"),
    ("row",  "Out-of-network",        "coinsurance_out"),
    ("section", "Office & Facility"),
    ("row",  "Preventive care",       "preventive"),
    ("row",  "Doctor visit",          "doctor_visit"),
    ("row",  "Virtual visit",         "virtual_visit"),
    ("row",  "Specialist visit",      "specialist"),
    ("row",  "X-ray / lab",           "xray_lab"),
    ("row",  "Imaging (CT/MRI/PET)",  "imaging"),
    ("row",  "Urgent care",           "urgent_care"),
    ("row",  "Emergency room",        "er"),
    ("row",  "Hospital stay",         "hospital"),
    ("row",  "Outpatient surgery",    "outpatient_surgery"),
    ("section", "Prescription Drugs"),
    ("row",  "Rx tiers",              "rx"),
    ("row",  "Rx deductible",         "rx_deductible"),
]

DENTAL_ROWS = [
    ("section", "Plan"),
    ("row",  "Network",               "network"),
    ("section", "Deductible & Maximum"),
    ("pair", "Deductible in Ind / Fam", "deductible_in_ind", "deductible_in_fam"),
    ("pair", "Deductible out Ind / Fam", "deductible_out_ind", "deductible_out_fam"),
    ("row",  "Waived for preventive", "deductible_waived_preventive"),
    ("row",  "Annual max (in)",       "annual_max_in"),
    ("row",  "Annual max (out)",      "annual_max_out"),
    ("row",  "Max rollover",          "rollover"),
    ("section", "Covered Services"),
    ("row",  "Preventive",            "preventive"),
    ("row",  "Basic",                 "basic"),
    ("row",  "Major",                 "major"),
    ("row",  "Endodontics",           "endodontics"),
    ("row",  "Periodontics",          "periodontics"),
    ("row",  "Oral surgery",          "oral_surgery"),
    ("row",  "Implants",              "implants"),
    ("section", "Orthodontia"),
    ("row",  "Coverage",              "ortho"),
    ("row",  "Lifetime maximum",      "ortho_max"),
    ("row",  "Age limit",             "ortho_age"),
    ("section", "Plan Rules"),
    ("row",  "Waiting periods",       "waiting_periods"),
    ("row",  "Out-of-network pays",   "oon_reimbursement"),
]

VISION_ROWS = [
    # Labels say COPAY or ALLOWANCE outright (Will, 2026-10-16): "$20" for an exam is what the member
    # pays; "$150" for frames is what the plan pays toward them. Same-looking numbers, opposite meaning.
    ("section", "Plan"),
    ("row",  "Network",               "network"),
    ("section", "Copays (member pays)"),
    ("row",  "Eye exam copay",        ("exam_copay",)),
    ("row",  "Materials copay",       "materials_copay"),
    ("row",  "Lenses copay",          "lenses"),
    ("section", "Allowances (plan pays up to)"),
    ("row",  "Frame allowance",       "frame_allowance"),
    ("row",  "Contact lens allowance", "contacts_allowance"),
    ("row",  "LASIK",                 "lasik"),
    ("section", "Frequency"),
    ("row",  "Exam",                  "exam_frequency"),
    ("row",  "Lenses",                "lenses_frequency"),
    ("row",  "Frames",                "frames_frequency"),
    ("row",  "Contacts",              "contacts_frequency"),
    ("section", "Out of Network"),
    ("row",  "Reimbursement",         "oon_reimbursement"),
]

ROWS = {"medical": MEDICAL_ROWS, "dental": DENTAL_ROWS, "vision": VISION_ROWS}

TIERS = [("ee", "Employee only"), ("es", "Employee & spouse"),
         ("ec", "Employee & children"), ("ef", "Employee & family")]


# ── VALUES ────────────────────────────────────────────────────────────────────
_PLACEHOLDER = re.compile(r"^\s*(see\s*sbc|tbd|n/?a\s*-?\s*see.*|none\s*stated|unknown|/)\s*$", re.I)


def clean(v):
    """A display string, or '' when the value is missing / a placeholder."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (int, float)):
        return f"{v:,.2f}" if isinstance(v, float) and not float(v).is_integer() else f"{v:,}"
    s = str(v).strip()
    if not s or _PLACEHOLDER.match(s):
        return ""
    if s.lower() in ("true", "false"):
        return "Yes" if s.lower() == "true" else "No"
    return s


def get(plan, key):
    keys = key if isinstance(key, tuple) else (key,)
    for k in keys:
        s = clean(plan.get(k))
        if s:
            return s
    return ""


def row_value(plan, spec):
    kind = spec[0]
    if kind == "row":
        return get(plan, spec[2])
    if kind == "pair":
        a, b = get(plan, spec[2]), get(plan, spec[3])
        if a and b:
            return a if a == b and a.lower().startswith(("not covered", "n/a", "none")) else f"{a} / {b}"
        return a or b
    return ""


def visible_rows(line, plans):
    """Row specs worth printing for this coverage line: sections are kept only when they hold
    at least one row that some plan fills in."""
    out, pending = [], None
    for spec in ROWS[line]:
        if spec[0] == "section":
            pending = spec
            continue
        if any(row_value(p, spec) for p in plans):
            if pending:
                out.append(pending)
                pending = None
            out.append(spec)
    return out


def num(v):
    """'$1,234.50' / 1234.5 -> 1234.5 ; anything unparseable -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d[\d,]*\.?\d*", str(v))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def money(v, blank=MISSING):
    n = num(v)
    return f"${n:,.2f}" if n is not None else blank


# ── ILLUSTRATIVE ──────────────────────────────────────────────────────────────
_ILLUS = re.compile(r"illustrat|\bimqs?\b|health questionnaire|medical questionnaire|need(s)? apps|"
                    r"requires? apps|apps required|health apps|medical apps|\bmuw\b|indicative|not sellable|"
                    r"subject to (medical )?underwriting and imq",
                    re.I)


_NOT_ILLUS = re.compile(r"\b(no|without|not requir\w*|not needed)\b[^.;]{0,25}\b(imqs?|questionnaires?|apps)\b|"
                        r"\b(imqs?|questionnaires?|apps)\b[^.;]{0,15}\bnot (required|needed)\b", re.I)


def is_illustrative(plan):
    """True when the plan is flagged illustrative OR its own text says IMQs / health apps / illustrative.
    A text signal wins over an explicit false, so a quote whose note says "IMQs required to get
    competitive" is never shown as final (Will, 2026-10-28). "No IMQs required" does not count."""
    flag = plan.get("illustrative")
    if flag is True or (isinstance(flag, str) and flag.strip().lower() in ("true", "yes", "1")):
        return True
    hay = " ".join(str(plan.get(k) or "") for k in
                   ("quote_status", "quote_type", "quote_status_note", "plan_name", "carrier", "notes"))
    hay = _NOT_ILLUS.sub(" ", hay)
    return bool(_ILLUS.search(hay))


def quote_label(plan):
    if is_illustrative(plan):
        return "Illustrative quote — subject to underwriting"
    s = clean(plan.get("quote_status") or plan.get("quote_type"))
    if not s:
        return "Quoted rates"
    s = re.split(r"[(;]", s)[0].strip()
    if s.lower() in ("underwritten", "quoted", "final"):
        return "Underwritten quote" if s.lower() == "underwritten" else "Quoted rates"
    return s


def display_name(plan):
    """Plan name without '(illustrative, subject to IMQs)'-style tails — the card says it louder."""
    name = clean(plan.get("plan_name"))
    return re.sub(r"\s*[\(\[][^\)\]]*(illustrat|imq|underwrit)[^\)\]]*[\)\]]\s*", " ", name, flags=re.I).strip()


# ── COSTS ─────────────────────────────────────────────────────────────────────
def contribution(value):
    """'50%' -> ('pct', 0.5); '$250' -> ('flat', 250); 'TBD' / '' -> (None, None)."""
    s = clean(value)
    if not s:
        return None, None
    if "%" in s:
        n = num(s)
        return ("pct", n / 100.0) if n is not None else (None, None)
    if "$" in s:
        n = num(s)
        return ("flat", n) if n is not None else (None, None)
    n = num(s)
    if n is not None and 0 <= n <= 100:
        return "pct", n / 100.0
    return None, None


def tier_counts(client, line):
    by_line = client.get("tier_counts_by_line") or {}
    src = by_line.get(line) or client.get("tier_counts") or {}
    out = {}
    for k, _ in TIERS:
        n = num(src.get(k, client.get(f"tier_{k}")))
        out[k] = int(n) if n is not None else None
    return out


def costs(plan, line, client, contributions):
    """Everything the rate block needs. Counts come from the census tier counts; when they are
    known the premium is rebuilt from them (Benefitter-style) and checked against the carrier's
    own total."""
    counts = tier_counts(client, line)
    rates = {k: num(plan.get(f"rate_{k}")) for k, _ in TIERS}
    carrier_total = num(plan.get("monthly_premium"))
    have_counts = all(c is not None for c in counts.values()) and sum(counts.values()) > 0
    note = ""
    premium = carrier_total
    if have_counts and all(rates[k] is not None or counts[k] == 0 for k, _ in TIERS):
        calc = sum((rates[k] or 0) * counts[k] for k, _ in TIERS)
        if carrier_total is None:
            premium = calc
        elif abs(calc - carrier_total) > 1.0:
            note = (f"The carrier's quoted total of ${carrier_total:,.2f} uses its own tier mix; "
                    f"at this census the monthly total is ${calc:,.2f}.")
            premium = calc
        else:
            premium = carrier_total   # within rounding: print the carrier's own total

    er = ee = None
    mode_ee, val_ee = contribution(contributions.get(f"{line}_ee"))
    mode_dep, val_dep = contribution(contributions.get(f"{line}_dep"))
    if premium is not None and have_counts and mode_ee and rates["ee"] is not None:
        employees = sum(counts.values())
        base = rates["ee"]
        per_ee = base * val_ee if mode_ee == "pct" else min(val_ee, base)
        dep_total = sum(((rates[k] or base) - base) * counts[k] for k, _ in TIERS if k != "ee")
        if mode_dep == "pct":
            dep_er = dep_total * val_dep
        elif mode_dep == "flat":
            dep_er = min(val_dep * sum(counts[k] for k, _ in TIERS if k != "ee"), dep_total)
        else:
            dep_er = 0.0
        er = round(per_ee * employees + dep_er, 2)
        ee = round(premium - er, 2)
    return {"counts": counts, "rates": rates, "premium": premium, "carrier_total": carrier_total,
            "employer": er, "employee": ee, "note": note, "have_counts": have_counts}


def contribution_text(contributions, line):
    a, b = clean(contributions.get(f"{line}_ee")), clean(contributions.get(f"{line}_dep"))
    if not a and not b:
        return "Employer contribution to be determined"
    return f"Employees {a or 'TBD'} / Dependents {b or 'TBD'}"


# ── DISCLAIMERS ───────────────────────────────────────────────────────────────
GENERAL_DISCLAIMER = (
    "The above rates and benefits are for general information and discussion purposes only and are not "
    "valid unless approved by the carrier. This rate quote is not an offer or a guarantee of coverage. The "
    "rates quoted apply to the plan design selected. Actual costs will vary based on factors such as the "
    "case characteristics of the group and the employees and dependents to be insured, the plan selected "
    "and the start date. Rates are determined by the carrier and are not final until the group is enrolled "
    "with the carrier. This group should not, under any circumstances, cancel its existing coverage unless "
    "and until coverage is offered by the carrier and final rates have been accepted by, and initial "
    "premium paid by, the group."
)

RATE_CONDITIONS = (
    "Quotes are based on the census provided and are dependent upon final enrollment. Rates may change "
    "if enrollment changes by more than 10%."
)

ILLUSTRATIVE_DISCLAIMER = (
    "Plans marked ILLUSTRATIVE are illustrative quotes only. Their rates are estimates, not final rates, and "
    "are subject to the carrier's medical underwriting, which may require every enrolling employee to "
    "complete an individual medical questionnaire (IMQ). After underwriting, the carrier may change the "
    "rates or decline to offer coverage."
)

SUMMARY_DISCLAIMER = (
    "Benefits shown are a summary. The carrier's Summary of Benefits and Coverage and plan documents "
    "govern. \"See SBC\" means the carrier's quote did not state that benefit; see the carrier's "
    "Summary of Benefits and Coverage."
)

CARRIER_DISCLAIMERS = {
    "beam": "Beam: dental and vision insurance products underwritten by National Guardian Life Insurance "
            "Company (NGL), Madison, WI, marketed by Beam Insurance Services LLC.",
}


def disclaimers(plans):
    out = [GENERAL_DISCLAIMER, RATE_CONDITIONS]
    if any(is_illustrative(p) for p in plans):
        out.append(ILLUSTRATIVE_DISCLAIMER)
    out.append(SUMMARY_DISCLAIMER)
    carriers = " ".join((p.get("carrier") or "").lower() for p in plans)
    for key, text in CARRIER_DISCLAIMERS.items():
        if key in carriers:
            out.append(text)
    return out
