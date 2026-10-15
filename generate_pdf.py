"""
generate_pdf.py — The Benefits Group · Client Proposal v4 (2026-10-15)

Landscape letter. Laid out after the Benefitter proposal Will likes, in TBG's own brand:
  1. Cover — client, effective date, presenter / prepared-for / employees, coverage counts
  2. Contents
  3. Employer profile — employer, employees and tiers, producer, underwriting
  4. Coverage pages — up to four plan cards per page, every benefit the quote states,
     rows aligned across cards, composite rates with census tier counts, employer/employee split
  5. Disclaimers — general, illustrative (when any plan is), summary, carrier-specific

Illustrative quotes (illustrative / IMQs / apps required) are labelled four ways: an amber
ribbon and diagonal watermark on the card, an amber callout on the coverage page, a count on
the cover, and their own disclaimer paragraph.

What each card shows is defined once in proposal_fields.py and shared with generate_excel.py.
"""
import math
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

import proposal_fields as F

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(HERE, "tbg-logo.png")
TOOLS_URL = "https://proposal-fgqm.onrender.com/tools/"

PAGE = landscape(letter)
PW, PH = PAGE
MARGIN = 0.5 * inch
CONTENT_W = PW - 2 * MARGIN
TOP_M = 0.78 * inch
BOT_M = 0.55 * inch
FRAME_H = PH - TOP_M - BOT_M

# ── PALETTE ───────────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#0D1B2A")
NAVY_2 = colors.HexColor("#1B2E45")
INK = colors.HexColor("#1A202C")
SLATE = colors.HexColor("#4A5568")
MUTED = colors.HexColor("#718096")
RULE = colors.HexColor("#D9E1EA")
GREEN = colors.HexColor("#3E9B6C")
GREEN_TINT = colors.HexColor("#EDF6F1")
GREEN_SOFT = colors.HexColor("#DCEFE4")
GOLD = colors.HexColor("#D69E2E")
BLUE = colors.HexColor("#3B82B8")
AMBER = colors.HexColor("#B45309")
AMBER_BG = colors.HexColor("#FEF3C7")
AMBER_LINE = colors.HexColor("#F59E0B")
WHITE = colors.white
LINE_COLORS = {"medical": GREEN, "dental": GOLD, "vision": BLUE}
LINE_TINTS = {"medical": colors.HexColor("#EDF6F1"), "dental": colors.HexColor("#FBF4E4"),
              "vision": colors.HexColor("#EAF2F9")}
LINE_TITLES = {"medical": "Medical Coverage", "dental": "Dental Coverage", "vision": "Vision Coverage"}

# ── FONTS ─────────────────────────────────────────────────────────────────────
FONT = {"display": "Helvetica-Bold", "body": "Helvetica", "semi": "Helvetica-Bold",
        "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique"}
_FONT_FILES = {"TBGSerif": "SourceSerif4_600SemiBold.ttf", "TBGSans": "PublicSans_400Regular.ttf",
               "TBGSans-Italic": "PublicSans_400Regular_Italic.ttf",
               "TBGSans-Semi": "PublicSans_600SemiBold.ttf", "TBGSans-Bold": "PublicSans_700Bold.ttf"}


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    paths = {}
    for name, fname in _FONT_FILES.items():
        p = os.path.join(HERE, "fonts", fname)
        if not os.path.exists(p):
            try:
                import urllib.request
                cache = os.path.join(os.path.expanduser("~"), ".cache", "tbg-fonts")
                os.makedirs(cache, exist_ok=True)
                p = os.path.join(cache, fname)
                if not os.path.exists(p):
                    urllib.request.urlretrieve(TOOLS_URL + "fonts/" + fname, p)
            except Exception:
                return
        paths[name] = p
    try:
        for name, p in paths.items():
            pdfmetrics.registerFont(TTFont(name, p))
    except Exception:
        return
    from reportlab.lib.fonts import addMapping
    addMapping("TBGSans", 0, 0, "TBGSans")
    addMapping("TBGSans", 1, 0, "TBGSans-Bold")
    addMapping("TBGSans", 0, 1, "TBGSans-Italic")
    addMapping("TBGSans", 1, 1, "TBGSans-Bold")
    FONT.update({"display": "TBGSerif", "body": "TBGSans", "semi": "TBGSans-Semi",
                 "bold": "TBGSans-Bold", "italic": "TBGSans-Italic"})


# ── HELPERS ───────────────────────────────────────────────────────────────────
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def P(text, size=8, color=INK, font="body", align=TA_LEFT, leading=None, after=0, before=0):
    return Paragraph(text, ParagraphStyle(
        "_", fontName=FONT.get(font, font), fontSize=size, textColor=color,
        leading=leading or size * 1.25, alignment=align, spaceAfter=after, spaceBefore=before))


def T(data, widths, style=None, heights=None, **kw):
    t = Table(data, colWidths=widths, rowHeights=heights, **kw)
    base = [("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP")]
    t.setStyle(TableStyle(base + (style or [])))
    return t


def eff_long():
    return CLIENT.get("effective_date") or "TBD"


def included(plans):
    return [p for p in plans if p.get("include", True)]


# ── PAGE FURNITURE ────────────────────────────────────────────────────────────
def _interior(canv, doc):
    canv.saveState()
    # Header
    canv.setFillColor(NAVY)
    canv.setFont(FONT["semi"], 8.5)
    canv.drawString(MARGIN, PH - 0.42 * inch,
                    f"{CLIENT['name']}  ·  Proposal  ·  Effective {eff_long()}")
    x = PW - MARGIN
    canv.setFont(FONT["semi"], 8.5)
    w = canv.stringWidth("The Benefits Group", FONT["semi"], 8.5)
    canv.drawRightString(x, PH - 0.42 * inch, "The Benefits Group")
    if os.path.exists(LOGO_PATH):
        canv.drawImage(LOGO_PATH, x - w - 22, PH - 0.49 * inch, width=17, height=17,
                       mask="auto", preserveAspectRatio=True)
    canv.setStrokeColor(GREEN)
    canv.setLineWidth(1.2)
    canv.line(MARGIN, PH - 0.55 * inch, PW - MARGIN, PH - 0.55 * inch)
    # Footer
    canv.setFillColor(MUTED)
    canv.setFont(FONT["body"], 7)
    canv.drawString(MARGIN, 0.3 * inch,
                    f"Prepared {datetime.today().strftime('%B %d, %Y').replace(' 0', ' ')}  ·  "
                    f"{PRODUCER.get('agency', 'The Benefits Group')}  ·  {PRODUCER.get('phone', '')}  ·  "
                    f"{PRODUCER.get('email', '')}")
    canv.setFillColor(NAVY)
    canv.circle(PW - MARGIN - 7, 0.33 * inch, 8, stroke=0, fill=1)
    canv.setFillColor(WHITE)
    canv.setFont(FONT["bold"], 7)
    canv.drawCentredString(PW - MARGIN - 7, 0.305 * inch, str(doc.page))
    canv.restoreState()


def _glyph(canv, kind, cx, cy, s, color=WHITE):
    """Simple white pictograms drawn with primitives (no icon fonts on the server)."""
    canv.saveState()
    canv.setFillColor(color)
    canv.setStrokeColor(color)
    if kind == "medical":
        canv.rect(cx - s * 0.12, cy - s * 0.38, s * 0.24, s * 0.76, stroke=0, fill=1)
        canv.rect(cx - s * 0.38, cy - s * 0.12, s * 0.76, s * 0.24, stroke=0, fill=1)
    elif kind == "dental":
        p = canv.beginPath()
        p.moveTo(cx - s * 0.32, cy + s * 0.18)
        p.curveTo(cx - s * 0.36, cy + s * 0.42, cx - s * 0.12, cy + s * 0.44, cx, cy + s * 0.32)
        p.curveTo(cx + s * 0.12, cy + s * 0.44, cx + s * 0.36, cy + s * 0.42, cx + s * 0.32, cy + s * 0.18)
        p.curveTo(cx + s * 0.30, cy - s * 0.02, cx + s * 0.24, cy - s * 0.12, cx + s * 0.20, cy - s * 0.38)
        p.curveTo(cx + s * 0.16, cy - s * 0.46, cx + s * 0.08, cy - s * 0.42, cx + s * 0.06, cy - s * 0.30)
        p.curveTo(cx + s * 0.04, cy - s * 0.18, cx - s * 0.04, cy - s * 0.18, cx - s * 0.06, cy - s * 0.30)
        p.curveTo(cx - s * 0.08, cy - s * 0.42, cx - s * 0.16, cy - s * 0.46, cx - s * 0.20, cy - s * 0.38)
        p.curveTo(cx - s * 0.24, cy - s * 0.12, cx - s * 0.30, cy - s * 0.02, cx - s * 0.32, cy + s * 0.18)
        p.close()
        canv.drawPath(p, stroke=0, fill=1)
    elif kind == "vision":
        canv.setLineWidth(s * 0.07)
        p = canv.beginPath()
        p.moveTo(cx - s * 0.42, cy)
        p.curveTo(cx - s * 0.2, cy + s * 0.32, cx + s * 0.2, cy + s * 0.32, cx + s * 0.42, cy)
        p.curveTo(cx + s * 0.2, cy - s * 0.32, cx - s * 0.2, cy - s * 0.32, cx - s * 0.42, cy)
        canv.drawPath(p, stroke=1, fill=0)
        canv.circle(cx, cy, s * 0.13, stroke=0, fill=1)
    elif kind == "building":
        canv.rect(cx - s * 0.26, cy - s * 0.34, s * 0.52, s * 0.62, stroke=0, fill=1)
        canv.setFillColor(colors.HexColor("#5B7590"))
        for dx in (-0.14, 0.04):
            for dy in (0.08, -0.1):
                canv.rect(cx + s * dx, cy + s * dy, s * 0.1, s * 0.1, stroke=0, fill=1)
        canv.rect(cx - s * 0.06, cy - s * 0.34, s * 0.12, s * 0.16, stroke=0, fill=1)
    elif kind == "people":
        for dx, r in ((-0.24, 0.85), (0.24, 0.85), (0, 1.0)):
            canv.circle(cx + s * dx, cy + s * 0.14 * r, s * 0.1 * r, stroke=0, fill=1)
            canv.roundRect(cx + s * dx - s * 0.13 * r, cy - s * 0.3, s * 0.26 * r, s * 0.3 * r,
                           s * 0.08, stroke=0, fill=1)
    canv.restoreState()


def _cover(canv, doc):
    canv.saveState()
    # Soft brand shapes (top wave, bottom triangles)
    canv.setFillColor(GREEN_TINT)
    p = canv.beginPath()
    p.moveTo(0, PH)
    p.lineTo(PW, PH)
    p.lineTo(PW, PH - 150)
    p.curveTo(PW * 0.72, PH - 95, PW * 0.42, PH - 250, 0, PH - 175)
    p.close()
    canv.drawPath(p, stroke=0, fill=1)
    canv.setFillColor(colors.HexColor("#F1F5F9"))
    p = canv.beginPath()
    p.moveTo(0, 0)
    p.lineTo(0, 170)
    p.lineTo(PW * 0.62, 0)
    p.close()
    canv.drawPath(p, stroke=0, fill=1)
    canv.setFillColor(colors.HexColor("#E3EEF6"))
    p = canv.beginPath()
    p.moveTo(PW, 0)
    p.lineTo(PW, 190)
    p.lineTo(PW * 0.58, 0)
    p.close()
    canv.drawPath(p, stroke=0, fill=1)

    # Title block
    x0 = 0.75 * inch
    canv.setFillColor(NAVY)
    name = CLIENT["name"]
    size = 30
    while canv.stringWidth(name, FONT["display"], size) > PW * 0.66 and size > 18:
        size -= 1
    canv.setFont(FONT["display"], size)
    canv.drawString(x0, PH - 0.95 * inch, name)
    canv.setFillColor(SLATE)
    canv.setFont(FONT["body"], 14)
    canv.drawString(x0, PH - 0.95 * inch - 26, "a healthcare & benefits proposal")
    canv.setFont(FONT["body"], 9.5)
    canv.drawString(x0, PH - 0.95 * inch - 44, f"Proposal effective date: {eff_long()}")
    if os.path.exists(LOGO_PATH):
        canv.drawImage(LOGO_PATH, PW - 0.75 * inch - 62, PH - 1.25 * inch, width=62, height=62,
                       mask="auto", preserveAspectRatio=True)

    # Three columns
    cy = PH - 3.05 * inch
    cols = [PW * 0.2, PW * 0.5, PW * 0.8]
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.8)
    for xs in (PW * 0.35, PW * 0.65):
        canv.line(xs, cy - 120, xs, cy + 28)
    icons = [("logo", colors.HexColor("#E6F0FA")), ("building", colors.HexColor("#C9D6E2")),
             ("people", colors.HexColor("#FBE3CF"))]
    for (kind, bg), cx in zip(icons, cols):
        canv.setFillColor(bg)
        canv.circle(cx, cy, 24, stroke=0, fill=1)
        if kind == "logo" and os.path.exists(LOGO_PATH):
            canv.drawImage(LOGO_PATH, cx - 17, cy - 17, width=34, height=34, mask="auto",
                           preserveAspectRatio=True)
        elif kind == "building":
            _glyph(canv, "building", cx, cy, 34, NAVY_2)
        elif kind == "people":
            _glyph(canv, "people", cx, cy, 36, colors.HexColor("#C2410C"))

    def column(cx, caption, headline, lines):
        y = cy - 44
        canv.setFillColor(MUTED)
        canv.setFont(FONT["body"], 8)
        canv.drawCentredString(cx, y, caption)
        y -= 18
        canv.setFillColor(NAVY)
        hs = 13
        while canv.stringWidth(headline, FONT["bold"], hs) > PW * 0.28 and hs > 9:
            hs -= 0.5
        canv.setFont(FONT["bold"], hs)
        canv.drawCentredString(cx, y, headline)
        y -= 15
        canv.setFillColor(SLATE)
        for ln, bold in lines:
            if not ln:
                continue
            canv.setFont(FONT["semi"] if bold else FONT["body"], 8.5)
            canv.drawCentredString(cx, y, ln)
            y -= 11.5

    column(cols[0], "Presenter", PRODUCER.get("agency", "The Benefits Group"),
           [(PRODUCER.get("name", ""), True), (PRODUCER.get("phone", ""), False),
            (PRODUCER.get("email", ""), False)])
    column(cols[1], "Prepared for", CLIENT["name"],
           [(CLIENT.get("address", ""), False), (CLIENT.get("city_state_zip", ""), False),
            (f"County: {CLIENT['county']}" if CLIENT.get("county") else "", False),
            (f"SIC code: {CLIENT['sic_code']}" if CLIENT.get("sic_code") else "", False)])
    tot = CLIENT.get("total_employees")
    column(cols[2], "Employee information",
           f"{tot} Total employees" if tot not in (None, "") else "Employee information",
           [(f"{CLIENT['eligible_employees']} eligible employees" if CLIENT.get("eligible_employees") not in (None, "") else "", False),
            (f"{CLIENT['enrolling_employees']} enrolling employees" if CLIENT.get("enrolling_employees") not in (None, "") else "", True),
            (f"{CLIENT['total_members']} total enrolling members" if CLIENT.get("total_members") else "", False)])

    # Coverage tiles
    lines = [(k, included(v)) for k, v in (("medical", MEDICAL_PLANS), ("dental", DENTAL_PLANS),
                                           ("vision", VISION_PLANS))]
    lines = [(k, v) for k, v in lines if v]
    if lines:
        gap = PW / (len(lines) + 1)
        ty = 1.75 * inch
        for i, (k, plans) in enumerate(lines):
            cx = gap * (i + 1)
            canv.setFillColor(LINE_COLORS[k])
            canv.roundRect(cx - 22, ty, 44, 44, 9, stroke=0, fill=1)
            _glyph(canv, k, cx, ty + 22, 30)
            canv.setFillColor(SLATE)
            canv.setFont(FONT["body"], 8.5)
            canv.drawCentredString(cx, ty - 14, LINE_TITLES[k])
            canv.setFillColor(NAVY)
            canv.setFont(FONT["bold"], 9)
            n = len(plans)
            canv.drawCentredString(cx, ty - 27, f"{n} Recommended Plan{'s' if n != 1 else ''}")
            ni = sum(1 for p in plans if F.is_illustrative(p))
            if ni:
                label = f"{ni} illustrative — subject to underwriting"
                w = canv.stringWidth(label, FONT["bold"], 7) + 14
                canv.setFillColor(AMBER_BG)
                canv.setStrokeColor(AMBER_LINE)
                canv.setLineWidth(0.6)
                canv.roundRect(cx - w / 2, ty - 46, w, 13, 6.5, stroke=1, fill=1)
                canv.setFillColor(AMBER)
                canv.setFont(FONT["bold"], 7)
                canv.drawCentredString(cx, ty - 42, label)

    canv.setFillColor(MUTED)
    canv.setFont(FONT["body"], 7.5)
    canv.drawRightString(PW - 0.75 * inch, 0.4 * inch,
                         f"Prepared {datetime.today().strftime('%B %d, %Y').replace(' 0', ' ')}")
    canv.restoreState()


# ── PAGE TITLE ────────────────────────────────────────────────────────────────
def page_title(title, right_label="", right_value="", accent=GREEN, kind=None):
    left = T([[IconBadge(kind, accent) if kind else "", P(title, 15, NAVY, "display")]],
             [26 if kind else 0, CONTENT_W * 0.6 - (26 if kind else 0)],
             [("VALIGN", (0, 0), (-1, -1), "MIDDLE")])
    right = T([[P(right_label, 7.5, MUTED, align=TA_RIGHT)],
               [P(right_value, 9, NAVY, "bold", align=TA_RIGHT)]], [CONTENT_W * 0.4])
    return T([[left, right]], [CONTENT_W * 0.6, CONTENT_W * 0.4],
             [("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])


class IconBadge(Flowable):
    def __init__(self, kind, color, size=19):
        super().__init__()
        self.kind, self.color, self.size = kind, color, size

    def wrap(self, *a):
        return self.size, self.size

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.circle(self.size / 2, self.size / 2, self.size / 2, stroke=0, fill=1)
        if self.kind in ("medical", "dental", "vision"):
            _glyph(c, self.kind, self.size / 2, self.size / 2, self.size * 0.72)
        else:
            c.setFillColor(WHITE)
            c.setFont(FONT["bold"], self.size * 0.6)
            c.drawCentredString(self.size / 2, self.size * 0.29, "i")


# ── CONTENTS + PROFILE ────────────────────────────────────────────────────────
def contents(story, entries):
    story.append(P("Table of Contents", 16, GREEN, "display", after=14))
    rows = []
    for title, page in entries:
        rows.append([P(title, 9.5, INK), P(str(page), 9.5, INK, align=TA_RIGHT)])
    t = T(rows, [CONTENT_W - 40, 40],
          [("LINEBELOW", (0, 0), (-1, -1), 0.6, RULE), ("TOPPADDING", (0, 0), (-1, -1), 6),
           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])
    story.append(t)
    story.append(PageBreak())


def _field(label, value, w):
    return T([[P(label, 8.5, NAVY, "bold")], [P(esc(value) if value not in (None, "") else F.MISSING, 8, SLATE)]],
             [w - 14], [("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE), ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
                        ("TOPPADDING", (0, 1), (-1, 1), 3)])


def _field_grid(title, fields, width, cols=3):
    cw = width / cols
    rows, row = [], []
    for lbl, val in fields:
        row.append(_field(lbl, val, cw))
        if len(row) == cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row + [""] * (cols - len(row)))
    grid = T(rows, [cw] * cols, [("BOTTOMPADDING", (0, 0), (-1, -1), 10)])
    return T([[P(title, 11.5, NAVY, "display", after=6)], [grid]], [width])


def employer_profile(story):
    story.append(page_title("Employer Profile", kind="info", accent=NAVY))
    story.append(Spacer(1, 6))
    half = CONTENT_W / 2 - 12
    tc = F.tier_counts(CLIENT, "medical")
    tiers = "  \u00b7  ".join(f"{k.upper()} {tc[k]}" for k, _ in F.TIERS if tc[k] is not None)
    employer = [("State", CLIENT.get("state")), ("Zip code", CLIENT.get("zip")), ("County", CLIENT.get("county")),
                ("Address", ", ".join(x for x in (CLIENT.get("address"), CLIENT.get("city_state_zip")) if x)),
                ("SIC code", CLIENT.get("sic_code")), ("Effective date", eff_long())]
    if CLIENT.get("quote_id") not in (None, "", "TBD"):
        employer.append(("Quote ID", CLIENT.get("quote_id")))
    if CLIENT.get("primary_contact"):
        employer.append(("Primary contact", CLIENT.get("primary_contact")))
    producer = [("Writing producer", PRODUCER.get("name")), ("Agency", PRODUCER.get("agency")),
                ("Phone", PRODUCER.get("phone")), ("Email", PRODUCER.get("email"))]
    employees = [("Total employees", CLIENT.get("total_employees")),
                 ("Eligible employees", CLIENT.get("eligible_employees")),
                 ("Enrolling employees", CLIENT.get("enrolling_employees")),
                 ("Waiving employees", CLIENT.get("waiving_employees")),
                 ("Total enrolling members", CLIENT.get("total_members")),
                 ("Enrolling by coverage tier", tiers)]
    allp = included(MEDICAL_PLANS) + included(DENTAL_PLANS) + included(VISION_PLANS)
    n_ill = sum(1 for p in allp if F.is_illustrative(p))
    status = (f"{len(allp) - n_ill} quoted, {n_ill} illustrative (subject to underwriting)" if n_ill
              else f"{len(allp)} quoted plans")
    funding = sorted({F.clean(p.get('funding')) for p in included(MEDICAL_PLANS) if F.clean(p.get('funding'))})
    under = [("Underwriting effective date", eff_long()), ("Quote status", status),
             ("Medical funding", ", ".join(funding)),
             ("Medical contribution", F.contribution_text(CONTRIBUTIONS, "medical")),
             ("Dental contribution", F.contribution_text(CONTRIBUTIONS, "dental")),
             ("Vision contribution", F.contribution_text(CONTRIBUTIONS, "vision"))]
    if CLIENT.get("rate_guarantee"):
        under.insert(2, ("Rate guarantee", CLIENT["rate_guarantee"]))
    left = T([[_field_grid("Employer Information", employer, half)], [Spacer(1, 10)],
              [_field_grid("Employee Information", employees, half)]], [half])
    right = T([[_field_grid("Producer Information", producer, half, cols=2)], [Spacer(1, 10)],
               [_field_grid("Underwriting Information", under, half, cols=2)]], [half])
    story.append(T([[left, "", right]], [half, 24, half]))
    story.append(PageBreak())


# ── PLAN CARDS ────────────────────────────────────────────────────────────────
N_COLS = 4
GAP = 0.14 * inch
CARD_W = (CONTENT_W - GAP * (N_COLS - 1)) / N_COLS
LW = CARD_W * 0.5
VW = CARD_W - LW
PAD_X = 6


class Watermarked(Flowable):
    """Draws the card, then a faint diagonal ILLUSTRATIVE across its body."""

    def __init__(self, inner, text="ILLUSTRATIVE"):
        super().__init__()
        self.inner, self.text = inner, text

    def wrap(self, aw, ah):
        self.w, self.h = self.inner.wrap(aw, ah)
        return self.w, self.h

    def draw(self):
        self.inner.drawOn(self.canv, 0, 0)
        c = self.canv
        c.saveState()
        c.setFillColor(AMBER_LINE)
        c.setFillAlpha(0.13)
        c.translate(self.w / 2, self.h * 0.48)
        c.rotate(62)
        size = 34
        c.setFont(FONT["bold"], size)
        c.drawCentredString(0, -size / 3, self.text)
        c.restoreState()


NOTE_CAP = 240


def _slot_cells(plan, line, specs, s, rank, any_ill, notes_off=False):
    """Each card is a list of slots: (kind, left, right). kind sets the styling."""
    accent = LINE_COLORS[line]
    ill = F.is_illustrative(plan)
    slots = []
    if any_ill:
        if ill:
            slots.append(("ribbon", P("ILLUSTRATIVE QUOTE · SUBJECT TO UNDERWRITING", 6.4 * s, WHITE, "bold",
                                      align=TA_CENTER), None))
        else:
            slots.append(("ribbon_blank", P("&nbsp;", 6.4 * s), None))
    head = (f"<font name='{FONT['bold']}' color='#FFFFFF' backColor='{accent.hexval().replace('0x', '#')}'>"
            f"&nbsp;{rank}&nbsp;</font>&nbsp;&nbsp;{esc(F.clean(plan.get('carrier')) or 'Carrier')}")
    slots.append(("head", P(head, 9.2 * s, NAVY, "bold", leading=11.5 * s), None))
    slots.append(("name", P(esc(F.display_name(plan)), 7.2 * s, SLATE, leading=8.8 * s), None))
    c = F.costs(plan, line, CLIENT, CONTRIBUTIONS)
    slots.append(("premium", P(F.money(c["premium"]), 17 * s, NAVY, "display", align=TA_CENTER,
                               leading=19 * s), None))
    slots.append(("premium_lbl", P("Total Monthly Cost", 7.2 * s, NAVY, "semi", align=TA_CENTER), None))
    qcolor, qfont = (AMBER, "bold") if ill else (MUTED, "body")
    slots.append(("status", P(esc(F.quote_label(plan)), 6.8 * s, qcolor, qfont, align=TA_CENTER), None))
    chips = " · ".join(esc(x) for x in (F.clean(plan.get("plan_type")), F.clean(plan.get("funding"))) if x)
    slots.append(("chips", P(chips or "&nbsp;", 6.6 * s, GREEN if line == "medical" else SLATE, "semi",
                             align=TA_CENTER), None))
    for spec in specs:
        if spec[0] == "section":
            slots.append(("section", P(esc(spec[1]), 6.3 * s, MUTED, "semi"), None))
        else:
            v = F.row_value(plan, spec)
            slots.append(("row", P(esc(spec[1]), 6.6 * s, SLATE),
                          P(esc(v) if v else F.MISSING, 6.6 * s, INK, "bold", align=TA_RIGHT)))
    slots.append(("section", P("Monthly Composite Rates", 6.3 * s, MUTED, "semi"), None))
    for k, lab in F.TIERS:
        n = c["counts"][k]
        lbl = f"{lab} ({n})" if c["have_counts"] else lab
        slots.append(("row", P(esc(lbl), 6.6 * s, SLATE), P(F.money(c["rates"][k]), 6.6 * s, INK, "bold",
                                                            align=TA_RIGHT)))
    if c["employer"] is not None:
        slots.append(("rowgap", P("Employer cost", 6.6 * s, SLATE),
                      P(F.money(c["employer"]), 6.6 * s, INK, "bold", align=TA_RIGHT)))
        slots.append(("row", P("Employee cost", 6.6 * s, SLATE),
                      P(F.money(c["employee"]), 6.6 * s, INK, "bold", align=TA_RIGHT)))
    else:
        slots.append(("rowgap", P("Employer / employee split", 6.6 * s, SLATE),
                      P("Contribution TBD", 6.6 * s, MUTED, align=TA_RIGHT)))
    slots.append(("total", P("Monthly Premium", 7.4 * s, WHITE, "bold"),
                  P(F.money(c["premium"]), 8.6 * s, WHITE, "bold", align=TA_RIGHT)))
    annual = c["premium"] * 12 if c["premium"] is not None else None
    slots.append(("annual", P("Annual premium", 6.6 * s, SLATE),
                  P(F.money(annual), 6.6 * s, INK, "semi", align=TA_RIGHT)))
    notes = " ".join(x for x in (F.clean(plan.get("notes")), c["note"]) if x)
    if ill and F.clean(plan.get("quote_status_note")):
        notes = (F.clean(plan.get("quote_status_note")) + " " + notes).strip()
    if len(notes) > NOTE_CAP:   # the full text is in the Excel; the card keeps a readable footnote
        notes = notes[:NOTE_CAP].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"
    if notes_off:
        notes = ""
    slots.append(("notes", P(esc(notes) if notes else "&nbsp;", 6 * s, SLATE, "italic", leading=7.6 * s), None))
    return slots


_VPAD = {"ribbon": 3, "ribbon_blank": 3, "head": 6, "name": 1.5, "premium": 4, "premium_lbl": 0.5,
         "status": 1.5, "chips": 4, "section": 3, "row": 1.8, "rowgap": 1.8, "total": 4, "annual": 2.5,
         "notes": 3}


def _slot_h(slot, s):
    kind, left, right = slot
    lw = CARD_W - 2 * PAD_X if right is None else LW - 2 * PAD_X
    h = left.wrap(lw, 1000)[1]
    if right is not None:
        h = max(h, right.wrap(VW - 2 * PAD_X, 1000)[1])
    return h + 2 * _VPAD[kind] * s


def build_cards(plans, line, specs, scale, start_rank, notes_off=False):
    any_ill = any(F.is_illustrative(p) for p in plans)
    all_slots = [_slot_cells(p, line, specs, scale, start_rank + i, any_ill, notes_off)
                 for i, p in enumerate(plans)]
    n = len(all_slots[0])
    heights = [max(_slot_h(sl[i], scale) for sl in all_slots) for i in range(n)]
    tint = LINE_TINTS[line]
    accent = LINE_COLORS[line]
    cards = []
    for p, slots in zip(plans, all_slots):
        data, style = [], []
        body_start = None
        for i, (kind, left, right) in enumerate(slots):
            vp = _VPAD[kind] * scale
            if right is None:
                data.append([left, ""])
                style.append(("SPAN", (0, i), (1, i)))
            else:
                data.append([left, right])
            style += [("TOPPADDING", (0, i), (-1, i), vp), ("BOTTOMPADDING", (0, i), (-1, i), vp)]
            if kind == "ribbon":
                style.append(("BACKGROUND", (0, i), (-1, i), AMBER))
            if kind in ("section", "row", "rowgap") and body_start is None:
                body_start = i
            if kind in ("section", "row", "rowgap", "annual"):
                style.append(("BACKGROUND", (0, i), (-1, i), tint))
            if kind == "section":
                style.append(("LINEABOVE", (0, i), (-1, i), 0.5, colors.HexColor("#C9D6CF")))
            if kind == "rowgap":
                style.append(("LINEABOVE", (0, i), (-1, i), 0.5, colors.HexColor("#C9D6CF")))
            if kind == "total":
                style.append(("BACKGROUND", (0, i), (-1, i), NAVY))
            if kind == "chips":
                style.append(("BOTTOMPADDING", (0, i), (-1, i), vp + 2))
        style += [("LEFTPADDING", (0, 0), (-1, -1), PAD_X), ("RIGHTPADDING", (0, 0), (-1, -1), PAD_X),
                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("BOX", (0, 0), (-1, -2), 0.7, colors.HexColor("#C5D0DB")),
                  ("LINEABOVE", (0, 0), (-1, 0), 2.2, AMBER if F.is_illustrative(p) else accent)]
        t = Table(data, colWidths=[LW, VW], rowHeights=heights)
        t.setStyle(TableStyle(style))
        cards.append(Watermarked(t) if F.is_illustrative(p) else t)
    return cards, sum(heights)


def card_grid(cards):
    row = []
    for i in range(N_COLS):
        row.append(cards[i] if i < len(cards) else "")
        if i < N_COLS - 1:
            row.append("")
    widths = []
    for i in range(N_COLS):
        widths.append(CARD_W)
        if i < N_COLS - 1:
            widths.append(GAP)
    return T([row], widths)


def illustrative_callout(n):
    b = FONT["bold"]
    subject = "The plan" if n == 1 else f"The {n} plans"
    verb = "is" if n == 1 else "are"
    txt = (f"<font name='{b}'>Illustrative quotes.</font> {subject} marked "
           f"<font name='{b}'>ILLUSTRATIVE</font> {verb} not final. Rates are subject to the carrier's "
           "medical underwriting, which may require each enrolling employee to complete a health "
           "questionnaire (IMQ), and may change or be declined after underwriting.")
    return T([[P(txt, 7.6, colors.HexColor("#7C2D12"), leading=9.8)]], [CONTENT_W],
             [("BACKGROUND", (0, 0), (-1, -1), AMBER_BG), ("LINEBEFORE", (0, 0), (0, -1), 3, AMBER_LINE),
              ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
              ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)])


def coverage_pages(story, line, plans):
    specs = F.visible_rows(line, plans)
    chunks = [plans[i:i + N_COLS] for i in range(0, len(plans), N_COLS)]
    for ci, chunk in enumerate(chunks):
        title = LINE_TITLES[line] + (" (continued)" if ci else "")
        block = [page_title(title, f"{line.title()} employer contribution",
                            F.contribution_text(CONTRIBUTIONS, line), LINE_COLORS[line], kind=line)]
        n_ill = sum(1 for p in chunk if F.is_illustrative(p))
        # The page frame keeps 6pt padding top and bottom, so 12pt less than FRAME_H is usable.
        avail = FRAME_H - 12 - block[0].wrap(CONTENT_W, FRAME_H)[1] - 6
        if n_ill:
            co = illustrative_callout(n_ill)
            block += [co, Spacer(1, 6)]
            avail -= co.wrap(CONTENT_W, 100)[1] + 6
        # Shrink type until the cards fit one page; as a last resort drop the card footnotes
        # (they are always in the Excel). Never let a page of cards spill onto a second page.
        scale, notes_off = 1.0, False
        while True:
            cards, h = build_cards(chunk, line, specs, scale, ci * N_COLS + 1, notes_off)
            if h <= avail:
                break
            if scale > (0.6 if notes_off else 0.72):
                scale -= 0.03
            elif not notes_off:
                notes_off, scale = True, 0.9
            else:
                break
        block.append(card_grid(cards))
        story.append(KeepTogether(block))
        story.append(PageBreak())


# ── MAIN ─────────────────────────────────────────────────────────────────────
def generate_pdf(output_path=None):
    import proposal_data as _pd
    global CLIENT, CONTRIBUTIONS, MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS, PRODUCER
    CLIENT = _pd.CLIENT
    CONTRIBUTIONS = _pd.CONTRIBUTIONS
    MEDICAL_PLANS = _pd.MEDICAL_PLANS
    DENTAL_PLANS = _pd.DENTAL_PLANS
    VISION_PLANS = _pd.VISION_PLANS
    PRODUCER = dict(getattr(_pd, "PRODUCER", {}) or {})
    PRODUCER.setdefault("agency", "The Benefits Group")
    PRODUCER.pop("sub_agency", None)   # client-facing brand is The Benefits Group only
    _register_fonts()

    if output_path is None:
        safe = CLIENT["name"].replace(" ", "_").replace("/", "-")
        output_path = f"Proposal_{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    lines = [(k, included(v)) for k, v in (("medical", MEDICAL_PLANS), ("dental", DENTAL_PLANS),
                                           ("vision", VISION_PLANS))]
    lines = [(k, v) for k, v in lines if v]

    # Contents: cover 1, contents 2, profile 3, then one page per four plans per line.
    entries, page = [("Employer Profile", 3)], 4
    for k, plans in lines:
        entries.append((LINE_TITLES[k] + " — Card View", page))
        page += math.ceil(len(plans) / N_COLS)
    entries.append(("Disclaimers", page))

    doc = SimpleDocTemplate(output_path, pagesize=PAGE, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=TOP_M, bottomMargin=BOT_M,
                            title=f"{CLIENT['name']} — Benefits Proposal",
                            author=PRODUCER.get("agency", "The Benefits Group"))
    story = [Spacer(1, 1), PageBreak()]
    contents(story, entries)
    employer_profile(story)
    for k, plans in lines:
        coverage_pages(story, k, plans)
    story.append(page_title("Disclaimers", kind="info", accent=NAVY))
    story.append(Spacer(1, 8))
    allp = [p for _, v in lines for p in v]
    for para in F.disclaimers(allp):
        bold = para.startswith("Plans marked ILLUSTRATIVE")
        story.append(P(esc(para), 8.2, colors.HexColor("#7C2D12") if bold else SLATE,
                       "semi" if bold else "body", leading=11.5, after=8))
    doc.build(story, onFirstPage=_cover, onLaterPages=_interior)
    print(f"✅ PDF saved → {output_path}")
    return output_path


if __name__ == "__main__":
    generate_pdf()
