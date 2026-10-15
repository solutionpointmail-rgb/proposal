"""
generate_excel.py — The Benefits Group proposal workbook (v2, 2026-10-15)

Same look as before (teal headers, banded rows, one sheet per coverage line), but every benefit
row now comes from proposal_fields.py, the same definition the PDF uses, so the workbook carries
the full plan detail instead of a few medical keys and "See SBC". Illustrative plans get an
amber ILLUSTRATIVE status cell and their own disclaimer.
"""
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import proposal_fields as F

TEAL = "FF2E8B8B"
LIGHT_TEAL = "FFE0F4F4"
WHITE = "FFFFFFFF"
ORANGE = "FFFF6B35"
LIGHT_GRAY = "FFF5F5F5"
NAVY = "FF0D1B2A"
AMBER = "FFB45309"
AMBER_BG = "FFFEF3C7"
SECTION = "FFEAF0F4"
TAB = {"medical": "2E8B8B", "dental": "FF6B35", "vision": "5B8DB8"}
TITLE = {"medical": "Medical Coverage", "dental": "Dental Coverage", "vision": "Vision Coverage"}


def _set(ws, row, col, value, bold=False, size=10, color="FF000000", fill=None, halign="left",
         wrap=True, border=False, italic=False):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="Arial", bold=bold, italic=italic, size=size, color=color)
    cell.alignment = Alignment(horizontal=halign, vertical="center", wrap_text=wrap)
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    if border:
        s = Side(style="thin", color="FFB0B0B0")
        cell.border = Border(left=s, right=s, top=s, bottom=s)
    return cell


def _included(plans):
    return [p for p in plans if p.get("include", True)]


# ── INTRO ─────────────────────────────────────────────────────────────────────
def build_intro(wb):
    ws = wb.create_sheet("Intro")
    ws.sheet_properties.tabColor = "2E8B8B"
    for col, w in (("A", 2), ("B", 34), ("C", 2), ("D", 30), ("E", 2), ("F", 34)):
        ws.column_dimensions[col].width = w
    _set(ws, 2, 2, CLIENT["name"], bold=True, size=16, color=TEAL)
    addr = ", ".join(x for x in (CLIENT.get("address"), CLIENT.get("city_state_zip"),
                                 f"County: {CLIENT['county']}" if CLIENT.get("county") else "") if x)
    if addr:
        _set(ws, 3, 2, addr)
    _set(ws, 5, 2, "Prepared by: " + PRODUCER.get("agency", "The Benefits Group"), bold=True)
    _set(ws, 6, 2, f"Effective date: {CLIENT.get('effective_date_mmddyyyy') or CLIENT.get('effective_date', '')}")
    if CLIENT.get("sic_code"):
        _set(ws, 7, 2, f"SIC code: {CLIENT['sic_code']}")
    if CLIENT.get("quote_id") not in (None, "", "TBD"):
        _set(ws, 8, 2, f"Quote ID: {CLIENT['quote_id']}")

    r = 5
    for label, key in (("Total employees", "total_employees"), ("Eligible employees", "eligible_employees"),
                       ("Enrolling employees", "enrolling_employees"), ("Waiving employees", "waiving_employees"),
                       ("Total enrolling members", "total_members")):
        if CLIENT.get(key) not in (None, ""):
            _set(ws, r, 4, f"{label}: {CLIENT[key]}", bold=(key == "enrolling_employees"))
            r += 1
    tc = F.tier_counts(CLIENT, "medical")
    if any(v is not None for v in tc.values()):
        _set(ws, r, 4, "Enrolling by tier: " + " · ".join(f"{k.upper()} {tc[k]}" for k, _ in F.TIERS
                                                          if tc[k] is not None))

    _set(ws, 5, 6, "Employer Contribution", bold=True, size=11)
    for i, line in enumerate(("medical", "dental", "vision")):
        _set(ws, 6 + i, 6, f"{line.title()}: {F.contribution_text(CONTRIBUTIONS, line)}")

    allp = _included(MEDICAL_PLANS) + _included(DENTAL_PLANS) + _included(VISION_PLANS)
    n_ill = sum(1 for p in allp if F.is_illustrative(p))
    if n_ill:
        _set(ws, 11, 2, f"ILLUSTRATIVE QUOTES: {n_ill} plan{'s' if n_ill != 1 else ''} in this proposal "
                        "are illustrative and subject to underwriting (see the Disclaimers sheet).",
             bold=True, color=AMBER, fill=AMBER_BG)
        ws.merge_cells(start_row=11, start_column=2, end_row=11, end_column=6)
        ws.row_dimensions[11].height = 30
    return ws


# ── COVERAGE SHEETS ───────────────────────────────────────────────────────────
def build_line(wb, line, plans):
    ws = wb.create_sheet(TITLE[line].split()[0])
    ws.sheet_properties.tabColor = TAB[line]
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 30
    c0 = 3
    for i in range(len(plans)):
        ws.column_dimensions[get_column_letter(c0 + i)].width = 30

    _set(ws, 1, 2, TITLE[line], bold=True, size=14, color=TEAL)
    _set(ws, 1, c0, "Employer contribution: " + F.contribution_text(CONTRIBUTIONS, line), size=9)

    # Plan header block
    r = 3
    header_rows = [
        ("", lambda i, p: str(i + 1), dict(bold=True, size=11, fill=TEAL, color=WHITE)),
        ("Carrier", lambda i, p: F.clean(p.get("carrier")), dict(bold=True, fill=LIGHT_TEAL)),
        ("Plan", lambda i, p: F.display_name(p), dict(bold=True, size=9, fill=LIGHT_TEAL)),
        ("Plan type · funding", lambda i, p: " · ".join(x for x in (F.clean(p.get("plan_type")),
                                                                    F.clean(p.get("funding"))) if x),
         dict(size=9, fill=LIGHT_TEAL)),
    ]
    for label, fn, kw in header_rows:
        if label:
            _set(ws, r, 2, label, bold=True, fill=LIGHT_TEAL, border=True)
        for i, p in enumerate(plans):
            _set(ws, r, c0 + i, fn(i, p), halign="center", border=True, **kw)
        r += 1
    _set(ws, r, 2, "Quote status", bold=True, fill=LIGHT_TEAL, border=True)
    for i, p in enumerate(plans):
        if F.is_illustrative(p):
            _set(ws, r, c0 + i, "ILLUSTRATIVE — subject to underwriting", bold=True, color=AMBER,
                 fill=AMBER_BG, halign="center", border=True)
        else:
            _set(ws, r, c0 + i, F.quote_label(p), fill=LIGHT_TEAL, halign="center", border=True, size=9)
    r += 2

    # Benefits
    band = 0
    for spec in F.visible_rows(line, plans):
        if spec[0] == "section":
            _set(ws, r, 2, spec[1], bold=True, fill=TEAL, color=WHITE)
            for i in range(len(plans)):
                _set(ws, r, c0 + i, "", fill=TEAL)
            band = 0
        else:
            bg = LIGHT_GRAY if band % 2 == 0 else WHITE
            _set(ws, r, 2, spec[1], fill=bg, border=True)
            for i, p in enumerate(plans):
                _set(ws, r, c0 + i, F.row_value(p, spec) or F.MISSING, fill=bg, halign="center", border=True)
            band += 1
        r += 1

    # Costs
    r += 1
    _set(ws, r, 2, "Monthly Composite Rates", bold=True, fill=TEAL, color=WHITE)
    for i in range(len(plans)):
        _set(ws, r, c0 + i, "", fill=TEAL)
    r += 1
    cs = [F.costs(p, line, CLIENT, CONTRIBUTIONS) for p in plans]
    for j, (k, lab) in enumerate(F.TIERS):
        bg = LIGHT_TEAL if j % 2 == 0 else WHITE
        n = cs[0]["counts"][k] if plans else None
        _set(ws, r, 2, f"{lab} ({n})" if cs and cs[0]["have_counts"] else lab, fill=bg, border=True)
        for i, c in enumerate(cs):
            _set(ws, r, c0 + i, c["rates"][k], fill=bg, halign="right", border=True).number_format = '"$"#,##0.00'
        r += 1
    r += 1
    rows = [("Employer cost", "employer", LIGHT_TEAL), ("Employee cost", "employee", WHITE),
            ("Monthly premium", "premium", ORANGE)]
    for label, key, bg in rows:
        _set(ws, r, 2, label, bold=True, fill=bg, border=True, color=WHITE if bg == ORANGE else "FF000000")
        for i, c in enumerate(cs):
            v = c[key]
            empty = "Contribution TBD" if key == "employer" else F.MISSING
            cell = _set(ws, r, c0 + i, v if v is not None else empty, bold=True, fill=bg,
                        halign="right", border=True, color=WHITE if bg == ORANGE else "FF000000")
            if v is not None:
                cell.number_format = '"$"#,##0.00'
        r += 1
    _set(ws, r, 2, "Annual premium", bold=True, fill=LIGHT_GRAY, border=True)
    for i, c in enumerate(cs):
        cell = _set(ws, r, c0 + i, round(c["premium"] * 12, 2) if c["premium"] is not None else F.MISSING,
                    bold=True, fill=LIGHT_GRAY, halign="right", border=True)
        cell.number_format = '"$"#,##0.00'
    r += 2

    # Notes
    _set(ws, r, 2, "Notes", bold=True, fill=LIGHT_TEAL, border=True)
    longest = 0
    for i, (p, c) in enumerate(zip(plans, cs)):
        parts = [F.clean(p.get("quote_status_note")) if F.is_illustrative(p) else "",
                 F.clean(p.get("notes")), c["note"]]
        txt = " ".join(x for x in parts if x)
        longest = max(longest, len(txt))
        _set(ws, r, c0 + i, txt, size=9, italic=True, border=True)
    ws.row_dimensions[r].height = max(15, min(160, 13 * (longest // 32 + 1)))
    ws.freeze_panes = ws.cell(row=3, column=c0)
    return ws


def build_disclaimers(wb, plans):
    ws = wb.create_sheet("Disclaimers")
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 120
    _set(ws, 1, 2, "Disclaimers", bold=True, size=14, color=TEAL)
    r = 3
    for para in F.disclaimers(plans):
        ill = para.startswith("Plans marked ILLUSTRATIVE")
        _set(ws, r, 2, para, size=9, bold=ill, color=AMBER if ill else "FF000000",
             fill=AMBER_BG if ill else None)
        ws.row_dimensions[r].height = max(30, 14 * (len(para) // 140 + 1))
        r += 1
    return ws


# ── MAIN ──────────────────────────────────────────────────────────────────────
def generate_excel(output_path=None):
    import proposal_data as _pd
    global CLIENT, CONTRIBUTIONS, MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS, PRODUCER
    CLIENT = _pd.CLIENT
    CONTRIBUTIONS = _pd.CONTRIBUTIONS
    MEDICAL_PLANS = _pd.MEDICAL_PLANS
    DENTAL_PLANS = _pd.DENTAL_PLANS
    VISION_PLANS = _pd.VISION_PLANS
    PRODUCER = dict(getattr(_pd, "PRODUCER", {}) or {})
    PRODUCER.setdefault("agency", "The Benefits Group")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    build_intro(wb)
    allp = []
    for line, plans in (("medical", MEDICAL_PLANS), ("dental", DENTAL_PLANS), ("vision", VISION_PLANS)):
        inc = _included(plans)
        if inc:
            build_line(wb, line, inc)
            allp += inc
    build_disclaimers(wb, allp)

    if output_path is None:
        safe = CLIENT["name"].replace(" ", "_").replace("/", "-")
        output_path = f"Proposal_{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(output_path)
    print(f"✅ Excel saved → {output_path}")
    return output_path


if __name__ == "__main__":
    generate_excel()
