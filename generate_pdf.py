"""
generate_pdf.py — The Benefits Group · Premium Proposal v3
Landscape (11x8.5), dark navy + TBG green, clean card grid.
"""
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image as RLImage
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas as rc
from datetime import datetime
from proposal_data import (
    CLIENT, PRODUCER, CONTRIBUTIONS,
    MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS, DISCLAIMER_TEXT
)

# ── LOGO ──────────────────────────────────────────────────────────────────────
import os
LOGO_PATH = os.path.join(os.path.dirname(__file__), "tbg-logo.png")

# ── PAGE SIZE ─────────────────────────────────────────────────────────────────
PAGE = landscape(letter)   # 792 x 612
PW, PH = PAGE
MARGIN = 0.5 * inch
CONTENT_W = PW - 2 * MARGIN   # ~692 pt usable

# ── PALETTE ───────────────────────────────────────────────────────────────────
NAVY        = colors.HexColor("#0D1B2A")
NAVY_MID    = colors.HexColor("#1B2E45")
NAVY_LIGHT  = colors.HexColor("#243B55")
GREEN       = colors.HexColor("#4CAF7D")
GREEN_LIGHT = colors.HexColor("#EAF7F1")
GOLD        = colors.HexColor("#F0B429")
BLUE_ACC    = colors.HexColor("#63B3ED")
SLATE       = colors.HexColor("#4A5568")
SLATE_LT    = colors.HexColor("#718096")
SMOKE       = colors.HexColor("#F7F9FC")
RULE        = colors.HexColor("#E2E8F0")
WHITE       = colors.white
INK         = colors.HexColor("#1A202C")

# ── HELPERS ───────────────────────────────────────────────────────────────────
def money(v): return f"${v:,.2f}"

def p(text, size=9, color=INK, font="Helvetica", align=TA_LEFT,
      leading=None, after=0, before=0):
    return Paragraph(str(text), ParagraphStyle(
        "_", fontName=font, fontSize=size,
        textColor=color, leading=leading or size * 1.3,
        alignment=align, spaceAfter=after, spaceBefore=before,
        wordWrap='CJK'   # prevents overflow on long strings
    ))

def sp(h=6): return Spacer(1, h)

def hr(color=RULE, w=1):
    return HRFlowable(width="100%", thickness=w, color=color,
                      spaceAfter=0, spaceBefore=0)

def tbl(data, widths, styles=None):
    t = Table(data, colWidths=widths)
    base = [
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
    ]
    t.setStyle(TableStyle(base + (styles or [])))
    return t

# ── BRANDED CANVAS ────────────────────────────────────────────────────────────
class BrandedCanvas(rc.Canvas):
    def __init__(self, filename, **kw):
        kw.pop("pagesize", None)
        super().__init__(filename, pagesize=PAGE, **kw)
        self._pg = 0

    def showPage(self):
        self._pg += 1
        self._furniture()
        super().showPage()

    def save(self):
        self._pg += 1
        self._furniture()
        super().save()

    def _furniture(self):
        if self._pg == 1:           # cover — no header/footer
            return
        # Top bar
        self.setFillColor(NAVY)
        self.rect(0, PH - 0.38*inch, PW, 0.38*inch, fill=1, stroke=0)
        self.setFillColor(GREEN)
        self.rect(0, PH - 0.41*inch, PW, 0.03*inch, fill=1, stroke=0)
        # Logo in top bar (left side)
        if os.path.exists(LOGO_PATH):
            logo_h = 0.28 * inch
            logo_w = logo_h  # square logo
            self.drawImage(LOGO_PATH, MARGIN, PH - 0.37*inch,
                           width=logo_w, height=logo_h,
                           mask='auto', preserveAspectRatio=True)
        # Agency name next to logo
        self.setFillColor(WHITE)
        self.setFont("Helvetica-Bold", 8.5)
        self.drawString(MARGIN + 0.35*inch, PH - 0.25*inch, PRODUCER["agency"])
        self.setFont("Helvetica", 8.5)
        self.drawRightString(PW - MARGIN, PH - 0.25*inch, CLIENT["name"])
        # Footer
        self.setFillColor(SLATE_LT)
        self.setFont("Helvetica", 7)
        foot = (f"Effective Date: {CLIENT['effective_date']}  ·  "
                f"Quote ID: {CLIENT['quote_id']}  ·  "
                f"Prepared by {PRODUCER['agency']}")
        self.drawString(MARGIN, 0.22*inch, foot)
        self.drawRightString(PW - MARGIN, 0.22*inch, f"Page {self._pg}")
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(MARGIN, 0.36*inch, PW - MARGIN, 0.36*inch)


# ── COVER PAGE ────────────────────────────────────────────────────────────────
def build_cover(story):
    # Logo for cover — sized generously
    logo_h = 0.85 * inch
    logo_w = logo_h  # square
    if os.path.exists(LOGO_PATH):
        logo_img = RLImage(LOGO_PATH, width=logo_w, height=logo_h)
        logo_img.hAlign = 'LEFT'
    else:
        logo_img = p("", size=1)

    # Full-width hero — logo on left, headline text on right
    hero_left = tbl([
        [logo_img],
        [p(PRODUCER["agency"], size=9, color=WHITE,
           font="Helvetica-Bold", after=0)],
        [p(PRODUCER["sub_agency"], size=7.5,
           color=colors.HexColor("#A0AEC0"), after=0)],
    ], [1.4*inch], [
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
    ])

    hero_right = tbl([
        [p("HEALTHCARE & BENEFITS PROPOSAL",
           size=7, color=GREEN, font="Helvetica-Bold", after=6)],
        [p(CLIENT["name"], size=24, color=WHITE,
           font="Helvetica-Bold", leading=28, after=6)],
        [p(f"{CLIENT['address']}  ·  {CLIENT['city_state_zip']}",
           size=9, color=colors.HexColor("#A0AEC0"), after=3)],
        [p(f"Effective Date: {CLIENT['effective_date']}",
           size=9, color=colors.HexColor("#A0AEC0"), after=0)],
    ], [CONTENT_W - 1.6*inch], [
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
    ])

    hero = tbl([[hero_left, hero_right]],
               [1.5*inch, CONTENT_W - 1.5*inch], [
        ("BACKGROUND",    (0,0),(-1,-1), NAVY),
        ("TOPPADDING",    (0,0),(-1,-1), 20),
        ("BOTTOMPADDING", (0,0),(-1,-1), 20),
        ("LEFTPADDING",   (0,0),(-1,-1), 20),
        ("RIGHTPADDING",  (0,0),(-1,-1), 20),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LINEAFTER",     (0,0),(0,-1),  0.5, colors.HexColor("#1B2E45")),
    ])
    accent_line = tbl([[""]], [CONTENT_W], [
        ("BACKGROUND",    (0,0),(-1,-1), GREEN),
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ])
    story.append(sp(-0.35*inch))
    story.append(hero)
    story.append(accent_line)
    story.append(sp(20))

    # Three info columns
    def info_col(hdr, lines):
        rows = [[p(hdr, size=6.5, color=GREEN, font="Helvetica-Bold", after=5)]]
        for ln in lines:
            rows.append([p(ln, size=8.5, color=SLATE, after=2)])
        return tbl(rows, [2.15*inch], [
            ("TOPPADDING",    (0,0),(-1,-1), 0),
            ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ])

    info = tbl([[
        info_col("PRESENTED BY", [
            PRODUCER["agency"], PRODUCER["sub_agency"],
            PRODUCER["phone"],  PRODUCER["email"],
        ]),
        info_col("PREPARED FOR", [
            CLIENT["name"], CLIENT["address"],
            CLIENT["city_state_zip"],
            f"SIC: {CLIENT['sic_code']}  ·  Quote ID: {CLIENT['quote_id']}",
        ]),
        info_col("EMPLOYEE SUMMARY", [
            f"{CLIENT['total_employees']} total employees",
            f"{CLIENT['eligible_employees']} eligible",
            f"{CLIENT['enrolling_employees']} enrolling",
            f"County: {CLIENT['county']}",
        ]),
    ]], [2.3*inch, 2.5*inch, 2.3*inch], [
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 14),
        ("LINEAFTER",     (0,0),(1,-1),  0.5, RULE),
        ("LEFTPADDING",   (1,0),(2,-1),  14),
    ])
    story.append(info)
    story.append(sp(18))
    story.append(hr(GREEN, 1.5))
    story.append(sp(14))

    # Contributions row
    story.append(p("EMPLOYER CONTRIBUTIONS", size=6.5,
                    color=GREEN, font="Helvetica-Bold", after=8))

    contrib = tbl([[
        p("Medical", size=8.5, color=SLATE_LT),
        p(f"EE {CONTRIBUTIONS['medical_ee']}  ·  Dep {CONTRIBUTIONS['medical_dep']}",
          size=8.5, color=INK, font="Helvetica-Bold"),
        p("Dental", size=8.5, color=SLATE_LT),
        p(f"EE {CONTRIBUTIONS['dental_ee']}  ·  Dep {CONTRIBUTIONS['dental_dep']}",
          size=8.5, color=INK, font="Helvetica-Bold"),
        p("Vision", size=8.5, color=SLATE_LT),
        p(f"EE {CONTRIBUTIONS['vision_ee']}  ·  Dep {CONTRIBUTIONS['vision_dep']}",
          size=8.5, color=INK, font="Helvetica-Bold"),
        p("Life", size=8.5, color=SLATE_LT),
        p(CONTRIBUTIONS["life"], size=8.5, color=INK, font="Helvetica-Bold"),
    ]], [0.65*inch, 1.3*inch, 0.6*inch, 1.3*inch,
         0.6*inch,  1.3*inch, 0.45*inch, 1.2*inch], [
        ("BACKGROUND",    (0,0),(-1,-1), SMOKE),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 9),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LINEAFTER",     (1,0),(1,-1),  0.5, RULE),
        ("LINEAFTER",     (3,0),(3,-1),  0.5, RULE),
        ("LINEAFTER",     (5,0),(5,-1),  0.5, RULE),
    ])
    story.append(contrib)
    story.append(sp(18))
    story.append(hr(GREEN, 1.5))
    story.append(sp(14))

    # Coverage count tiles
    story.append(p("PLANS INCLUDED IN THIS PROPOSAL", size=6.5,
                    color=GREEN, font="Helvetica-Bold", after=10))

    med_n = len([x for x in MEDICAL_PLANS if x.get("include")])
    den_n = len([x for x in DENTAL_PLANS  if x.get("include")])
    vis_n = len([x for x in VISION_PLANS  if x.get("include")])

    def tile(n, line1, line2, acc):
        inner = tbl([
            [p(str(n),  size=30, color=acc, font="Helvetica-Bold", align=TA_CENTER)],
            [p(line1,   size=8,  color=WHITE, font="Helvetica-Bold", align=TA_CENTER)],
            [p(line2,   size=7,  color=colors.HexColor("#A0AEC0"), align=TA_CENTER)],
        ], [2.1*inch], [
            ("BACKGROUND",    (0,0),(-1,-1), NAVY_MID),
            ("TOPPADDING",    (0,0),(-1,-1), 12),
            ("BOTTOMPADDING", (0,0),(-1,-1), 12),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("RIGHTPADDING",  (0,0),(-1,-1), 6),
            ("LINEABOVE",     (0,0),(-1,0),  3, acc),
        ])
        return inner

    tiles = tbl([[
        tile(med_n, "MEDICAL PLANS",  "Cigna · PHCS/RBP", GREEN),
        tile(den_n, "DENTAL PLANS",   "Beam · MetLife",   GOLD),
        tile(vis_n, "VISION PLANS",   "Beam VSP · Guardian", BLUE_ACC),
    ]], [2.3*inch, 2.3*inch, 2.3*inch], [
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
    ])
    story.append(tiles)
    story.append(sp(20))
    story.append(p(
        f"Downloaded {datetime.today().strftime('%B %d, %Y')}  ·  "
        "Rates are for informational purposes and subject to carrier approval.",
        size=7, color=SLATE_LT, align=TA_CENTER))
    story.append(PageBreak())


# ── SECTION HEADER BAR ────────────────────────────────────────────────────────
def sec_bar(title, contrib_str, accent):
    return tbl([[
        p(title, size=13, color=WHITE, font="Helvetica-Bold"),
        p(contrib_str, size=8, color=accent,
          font="Helvetica-Bold", align=TA_RIGHT),
    ]], [CONTENT_W * 0.55, CONTENT_W * 0.45], [
        ("BACKGROUND",    (0,0),(-1,-1), NAVY),
        ("TOPPADDING",    (0,0),(-1,-1), 9),
        ("BOTTOMPADDING", (0,0),(-1,-1), 9),
        ("LEFTPADDING",   (0,0),(0,-1),  12),
        ("RIGHTPADDING",  (-1,0),(-1,-1),12),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LINEABOVE",     (0,0),(-1,0),  3, accent),
    ])


# ── PLAN CARD ────────────────────────────────────────────────────────────────
# In landscape we fit 4 cards across; card width calculated from usable width
N_COLS   = 4
GAP      = 0.12 * inch
CARD_W   = (CONTENT_W - GAP * (N_COLS - 1)) / N_COLS   # ~161 pt each

def plan_card(plan, rank, accent, ctype):
    rows = []

    # ── Header: coloured rank box + carrier name ──────────────────────────
    hdr = tbl([[
        p(f"#{rank}", size=9, color=WHITE, font="Helvetica-Bold", align=TA_CENTER),
        p(plan["carrier"], size=8.5, color=WHITE, font="Helvetica-Bold"),
    ]], [0.30*inch, CARD_W - 0.30*inch], [
        ("BACKGROUND",    (0,0),(0,-1),  accent),
        ("BACKGROUND",    (1,0),(1,-1),  NAVY),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(0,-1),  0),
        ("LEFTPADDING",   (1,0),(1,-1),  7),
        ("RIGHTPADDING",  (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LINEABOVE",     (0,0),(-1,0),  2, accent),
    ])
    rows.append([hdr])

    # Plan type badge strip
    badge_txt = f"{plan.get('plan_type','PPO')}  ·  {plan.get('funding','')}"
    badge = tbl([[p(badge_txt, size=6.5, color=colors.HexColor("#A0AEC0"))]],
                [CARD_W], [
        ("BACKGROUND",    (0,0),(-1,-1), NAVY_LIGHT),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 7),
    ])
    rows.append([badge])

    # Plan name strip
    name = tbl([[p(plan["plan_name"], size=6.5,
                    color=colors.HexColor("#CBD5E0"), leading=8.5)]],
               [CARD_W], [
        ("BACKGROUND",    (0,0),(-1,-1), NAVY_MID),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 7),
        ("RIGHTPADDING",  (0,0),(-1,-1), 5),
    ])
    rows.append([name])

    # Premium block
    prem = tbl([
        [p("TOTAL MONTHLY COST", size=6, color=SLATE_LT,
           font="Helvetica-Bold", align=TA_CENTER)],
        [p(money(plan["monthly_premium"]), size=18, color=accent,
           font="Helvetica-Bold", align=TA_CENTER, leading=22)],
        [p(plan.get("quote_type",""), size=6, color=SLATE_LT, align=TA_CENTER)],
    ], [CARD_W], [
        ("BACKGROUND",    (0,0),(-1,-1), SMOKE),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
    ])
    rows.append([prem])

    # Benefit rows helper
    LW = CARD_W * 0.55
    VW = CARD_W * 0.45

    def brow(lbl, val, i):
        bg = GREEN_LIGHT if i % 2 == 0 else WHITE
        return tbl([[
            p(lbl, size=7, color=SLATE),
            p(str(val), size=7, color=INK, font="Helvetica-Bold", align=TA_RIGHT),
        ]], [LW, VW], [
            ("BACKGROUND",    (0,0),(-1,-1), bg),
            ("TOPPADDING",    (0,0),(-1,-1), 2.5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2.5),
            ("LEFTPADDING",   (0,0),(0,-1),  6),
            ("RIGHTPADDING",  (-1,0),(-1,-1),5),
            ("LINEBELOW",     (0,0),(-1,-1), 0.3, RULE),
        ])

    if ctype == "medical":
        benefits = [
            ("Ded (In) Ind",   plan["deductible_in_ind"]),
            ("Ded (In) Fam",   plan["deductible_in_fam"]),
            ("OOP Max Ind",    plan["oop_in_ind"]),
            ("OOP Max Fam",    plan["oop_in_fam"]),
            ("Coinsurance",    plan["coinsurance_in"]),
            ("Doctor Visit",   plan["doctor_visit"]),
            ("Specialist",     plan["specialist"]),
            ("Urgent Care",    plan["urgent_care"]),
            ("ER",             plan["er"]),
            ("Hospital",       plan["hospital"]),
            ("Rx",             plan["rx"]),
            ("HSA",            "Yes" if plan.get("hsa_eligible") else "No"),
        ]
    elif ctype == "dental":
        benefits = [
            ("Ded Ind",        plan["deductible_in_ind"]),
            ("Ded Fam",        plan["deductible_in_fam"]),
            ("Annual Max",     plan["annual_max_in"]),
            ("Preventive",     plan["preventive"]),
            ("Basic",          plan["basic"]),
            ("Major",          plan["major"]),
            ("Endodontics",    plan["endodontics"]),
            ("Periodontics",   plan["periodontics"]),
            ("Implants",       plan["implants"]),
            ("Ortho Max",      plan["ortho_max"]),
        ]
    else:  # vision
        benefits = [
            ("Exam",           plan["exam_frequency"]),
            ("Lenses",         plan["lenses_frequency"]),
            ("Frames",         plan["frames_frequency"]),
            ("Contact Lens",   plan["contacts_frequency"]),
        ]

    for i, (lbl, val) in enumerate(benefits):
        rows.append([brow(lbl, val, i)])

    # Monthly rates header
    rates_hdr = tbl([[p("MONTHLY RATES", size=6.5, color=WHITE,
                          font="Helvetica-Bold")]],
                    [CARD_W], [
        ("BACKGROUND",    (0,0),(-1,-1), NAVY_MID),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 7),
    ])
    rows.append([rates_hdr])

    ee = CLIENT["tier_ee"]
    for i, (lbl, val) in enumerate([
        (f"EE Only ({ee})",  money(plan["rate_ee"])),
        ("EE + Spouse",      money(plan["rate_es"])),
        ("EE + Children",    money(plan["rate_ec"])),
        ("EE + Family",      money(plan["rate_ef"])),
        ("Employer Cost",    money(plan["employer_cost"])),
        ("Employee Cost",    money(plan["employee_cost"])),
    ]):
        rows.append([brow(lbl, val, i)])

    # Total premium footer
    foot = tbl([[
        p("Monthly Premium", size=7.5, color=WHITE, font="Helvetica-Bold"),
        p(money(plan["monthly_premium"]), size=9, color=WHITE,
          font="Helvetica-Bold", align=TA_RIGHT),
    ]], [LW, VW], [
        ("BACKGROUND",    (0,0),(-1,-1), accent),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(0,-1),  7),
        ("RIGHTPADDING",  (-1,0),(-1,-1),6),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ])
    rows.append([foot])

    # Outer card box
    card = tbl(rows, [CARD_W], [
        ("BOX",           (0,0),(-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
    ])
    return card


# ── CARD GRID ────────────────────────────────────────────────────────────────
def card_grid(cards):
    """Lay out cards in rows of N_COLS with GAP columns between."""
    col_widths = []
    for i in range(N_COLS):
        col_widths.append(CARD_W)
        if i < N_COLS - 1:
            col_widths.append(GAP)

    rows = []
    chunk = []
    for card in cards:
        chunk.append(card)
        if len(chunk) == N_COLS:
            rows.append(chunk)
            chunk = []
    if chunk:
        while len(chunk) < N_COLS:
            chunk.append("")
        rows.append(chunk)

    # Interleave gap cells
    spaced = []
    for row in rows:
        nr = []
        for i, cell in enumerate(row):
            nr.append(cell)
            if i < N_COLS - 1:
                nr.append("")
        spaced.append(nr)

    t = Table(spaced, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
    ]))
    return t


# ── MAIN ─────────────────────────────────────────────────────────────────────
def generate_pdf(output_path=None):
    # Re-read from proposal_data at call time so app.py injections are picked up
    import proposal_data as _pd
    global CLIENT, CONTRIBUTIONS, MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS, DISCLAIMER_TEXT, PRODUCER
    CLIENT        = _pd.CLIENT
    CONTRIBUTIONS = _pd.CONTRIBUTIONS
    MEDICAL_PLANS = _pd.MEDICAL_PLANS
    DENTAL_PLANS  = _pd.DENTAL_PLANS
    VISION_PLANS  = _pd.VISION_PLANS
    DISCLAIMER_TEXT = getattr(_pd, 'DISCLAIMER_TEXT', '')
    PRODUCER      = getattr(_pd, 'PRODUCER', {})

    if output_path is None:
        safe      = CLIENT["name"].replace(" ","_").replace("/","-")
        eff       = CLIENT["effective_date_mmddyyyy"].replace("/","")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/mnt/user-data/outputs/Proposal_{safe}_{eff}_v{timestamp}.pdf"

    doc = SimpleDocTemplate(
        output_path, pagesize=PAGE,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.55*inch, bottomMargin=0.5*inch,
        title=f"{CLIENT['name']} — Benefits Proposal",
        author=PRODUCER["agency"],
    )

    story = []
    build_cover(story)

    # Medical
    med = [x for x in MEDICAL_PLANS if x.get("include")]
    if med:
        contrib = (f"Employer contribution — "
                   f"EE {CONTRIBUTIONS['medical_ee']} · Dep {CONTRIBUTIONS['medical_dep']}")
        story.append(sec_bar("Medical Coverage", contrib, GREEN))
        story.append(sp(10))
        story.append(card_grid([plan_card(x, i+1, GREEN, "medical")
                                 for i, x in enumerate(med)]))
        story.append(PageBreak())

    # Dental
    den = [x for x in DENTAL_PLANS if x.get("include")]
    if den:
        contrib = (f"Employer contribution — "
                   f"EE {CONTRIBUTIONS['dental_ee']} · Dep {CONTRIBUTIONS['dental_dep']}")
        story.append(sec_bar("Dental Coverage", contrib, GOLD))
        story.append(sp(10))
        story.append(card_grid([plan_card(x, i+1, GOLD, "dental")
                                 for i, x in enumerate(den)]))
        story.append(PageBreak())

    # Vision
    vis = [x for x in VISION_PLANS if x.get("include")]
    if vis:
        contrib = (f"Employer contribution — "
                   f"EE {CONTRIBUTIONS['vision_ee']} · Dep {CONTRIBUTIONS['vision_dep']}")
        story.append(sec_bar("Vision Coverage", contrib, BLUE_ACC))
        story.append(sp(10))
        story.append(card_grid([plan_card(x, i+1, BLUE_ACC, "vision")
                                 for i, x in enumerate(vis)]))
        story.append(PageBreak())

    # Disclaimers
    story.append(p("Disclaimers", size=13, color=NAVY,
                    font="Helvetica-Bold", after=10))
    story.append(hr(GREEN, 1.5))
    story.append(sp(8))
    story.append(p(DISCLAIMER_TEXT, size=7.5, color=SLATE_LT, leading=11))

    doc.build(story, canvasmaker=BrandedCanvas)
    print(f"✅ PDF saved → {output_path}")
    return output_path

if __name__ == "__main__":
    generate_pdf()
