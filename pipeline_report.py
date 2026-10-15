#!/usr/bin/env python3
"""
New Business Pipeline Check — report builder for The Benefits Group.

The routine decides WHAT the report says and writes it as JSON. This script owns HOW it looks,
so every run comes out identical in design. It writes three files from one JSON:

    <base>.html        the interactive page (same design as the approved artifact)
    <base>.pdf         a print-designed PDF (letter; the status grid gets a landscape page)
    <base>-email.html  a short HTML email body: tallies, today's three, the effective-date callout

Usage:
    python3 pipeline_report.py content.json "New Business Pipeline Check - 2026-10-15"
    python3 pipeline_report.py --example out_base      # build from pipeline_report_example.json

Needs reportlab (pip install --break-system-packages reportlab). Fonts (Source Serif 4, Public Sans,
IBM Plex Mono) are read from ./fonts next to this script, downloaded from the Render app if missing,
and replaced by built-in fonts if neither works — the PDF still builds.
See pipeline_report_example.json for the schema.
"""
import html
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_URL = "https://proposal-fgqm.onrender.com/tools/"

TIERS = [
    # key,  chip label,        section heading,              description
    ("crit", "Quiet & stuck", "Quiet and stuck", "8+ days without client contact, and the work isn't moving"),
    ("warn", "Blocked", "Blocked", "Waiting on census, waiting on carriers, or quotes not yet sent"),
    ("note", "Analysis gap", "Quotes in, analysis behind", "Quotes are saved, but the analysis is missing or out of date"),
    ("info", "Data cleanup", "Setup and data cleanup", "Missing setup, stage mismatches, and records to fix"),
    ("ok", "On track", "On track", "No blocking flags"),
]
TIER_KEYS = [t[0] for t in TIERS]

COLORS = {
    "paper": "#F4F6F5", "surface": "#FFFFFF", "ink": "#18232A", "muted": "#5B686E", "line": "#DCE2E0",
    "soft": "#EBEFEE", "accent": "#1E4F63", "accent_soft": "#E2ECEF",
    "crit": "#B03F2C", "crit_soft": "#F7E6E2", "warn": "#A8701B", "warn_soft": "#F6EEDF",
    "note": "#7A6D1E", "note_soft": "#F2EFDC", "info": "#5F6B71", "info_soft": "#E9ECEC",
    "ok": "#2B7350", "ok_soft": "#E1F0E7",
}


# ----------------------------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def inline_html(s):
    """Escape, then allow **bold** and `mono` — the only markup the routine may use."""
    t = esc(s)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<span class="mono">\1</span>', t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", t)
    return t


def first_name(who):
    w = (who or "").strip()
    if not w:
        return ""
    parts = w.split()
    return parts[0] if len(parts) == 1 or len(parts[0]) > 2 else w


def short_date(d):
    """'10/02/26' -> '10/02'."""
    m = re.match(r"^(\d{1,2}/\d{1,2})", d or "")
    return m.group(1) if m else (d or "")


def quiet_info(g, threshold):
    q = g.get("quiet")
    label = g.get("quiet_label")
    if q is None:
        return (label or "No contact found"), True
    bad = q >= threshold
    if not label:
        if q == 0:
            label = "Today"
        elif bad:
            label = f"{q} days quiet"
        else:
            label = f"{q} day" if q == 1 else f"{q} days"
    return label, bad


def last_contact_short(g, arrow=True):
    last = g.get("last")
    if not last:
        return "—"
    d = short_date(last.get("date"))
    who = first_name(last.get("who"))
    team = last.get("team") or ""
    if (last.get("dir") or "").upper().startswith("FROM"):
        return f"{d} ← {who}" if arrow else f"{d} from {who}"
    return (f"{d} → {who}" if arrow else f"{d} to {who}") + (f" ({team})" if team else "")


def meta_line(g):
    parts = []
    if g.get("effective"):
        parts.append(f"Eff {g['effective']}")
    if g.get("meta"):
        parts.append(g["meta"])
    elif not g.get("effective"):
        parts.append("No effective date")
    if g.get("status"):
        parts.append(g["status"])
    return " · ".join(parts)


def tally(data):
    counts = {k: 0 for k in TIER_KEYS}
    for g in data.get("groups", []):
        if g.get("sev") in counts:
            counts[g["sev"]] += 1
    return counts


def validate(data):
    problems = []
    for k in ("run", "groups"):
        if k not in data:
            problems.append(f"missing top-level '{k}'")
    for i, g in enumerate(data.get("groups", [])):
        if g.get("sev") not in TIER_KEYS:
            problems.append(f"group {i} ({g.get('name')}): sev must be one of {TIER_KEYS}")
        if not g.get("name"):
            problems.append(f"group {i}: missing name")
    if problems:
        raise SystemExit("content.json problems:\n  - " + "\n  - ".join(problems))


# ----------------------------------------------------------------------------------------------
# HTML page (the approved artifact design)
# ----------------------------------------------------------------------------------------------
HTML_CSS = r"""
:root{
  --paper:#F4F6F5; --surface:#FFFFFF; --ink:#18232A; --muted:#5B686E; --line:#DCE2E0; --soft:#EBEFEE;
  --accent:#1E4F63; --accent-soft:#E2ECEF;
  --crit:#B03F2C; --crit-soft:#F7E6E2; --warn:#A8701B; --warn-soft:#F6EEDF;
  --note:#7A6D1E; --note-soft:#F2EFDC; --info:#5F6B71; --info-soft:#E9ECEC; --ok:#2B7350; --ok-soft:#E1F0E7;
  --f-display:"Source Serif 4", Georgia, "Times New Roman", serif;
  --f-body:"Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-mono:"IBM Plex Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#11181B; --surface:#182124; --ink:#E4EAE8; --muted:#97A4A8; --line:#2A3538; --soft:#1E282B;
  --accent:#86B9CB; --accent-soft:#1D3038;
  --crit:#E8806C; --crit-soft:#3A2420; --warn:#E3AB5C; --warn-soft:#382D1C;
  --note:#D3C36F; --note-soft:#33301C; --info:#A3AFB3; --info-soft:#232C2F; --ok:#73C69A; --ok-soft:#1B3328;
  color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#11181B; --surface:#182124; --ink:#E4EAE8; --muted:#97A4A8; --line:#2A3538; --soft:#1E282B;
  --accent:#86B9CB; --accent-soft:#1D3038;
  --crit:#E8806C; --crit-soft:#3A2420; --warn:#E3AB5C; --warn-soft:#382D1C;
  --note:#D3C36F; --note-soft:#33301C; --info:#A3AFB3; --info-soft:#232C2F; --ok:#73C69A; --ok-soft:#1B3328;
  color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--f-body);font-size:15px;line-height:1.55}
.wrap{max-width:1040px;margin:0 auto;padding-block:40px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;grid-template-columns:minmax(0,1fr);gap:44px}
h1,h2,h3{font-family:var(--f-display);font-weight:600;text-wrap:balance;margin:0;letter-spacing:-.005em}
h1{font-size:clamp(1.9rem,4.4vw,2.6rem);line-height:1.1}
h2{font-size:1.45rem;line-height:1.2}
h3{font-size:1.15rem;line-height:1.25}
.eyebrow{font-size:.72rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.mono{font-family:var(--f-mono);font-variant-numeric:tabular-nums}
p{margin:0}
header{display:grid;gap:14px;border-bottom:1px solid var(--line);padding-bottom:26px}
.runline{display:flex;flex-wrap:wrap;gap:6px 18px;color:var(--muted);font-size:.9rem}
.runline b{color:var(--ink);font-weight:600}
.gap{background:var(--crit-soft);color:var(--crit);border-radius:8px;padding:10px 14px;font-size:.9rem}
.today{display:grid;gap:16px}
.today-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.today-card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:18px;display:grid;gap:8px;align-content:start;min-width:0}
.today-card .rank{font-family:var(--f-mono);font-size:.78rem;color:var(--crit);font-weight:500}
.today-card p{font-size:.92rem;color:var(--muted)}
.callout{background:var(--accent-soft);border-radius:10px;padding:14px 18px;font-size:.93rem}
.callout b{color:var(--accent)}
.tally{display:flex;flex-wrap:wrap;gap:8px}
.chip{appearance:none;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:999px;padding:7px 14px 7px 11px;font:500 .86rem var(--f-body);display:inline-flex;align-items:center;gap:8px;cursor:pointer}
.chip:hover{border-color:var(--muted)}
.chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.chip[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.chip .n{font-family:var(--f-mono);font-size:.8rem;opacity:.8}
.dot{width:9px;height:9px;border-radius:2px;flex:none;background:var(--info);display:inline-block}
.s-crit .dot,.dot.crit{background:var(--crit)} .s-warn .dot,.dot.warn{background:var(--warn)}
.s-note .dot,.dot.note{background:var(--note)} .s-info .dot,.dot.info{background:var(--info)} .s-ok .dot,.dot.ok{background:var(--ok)}
.sev{display:grid;gap:4px}
.sev-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;padding-bottom:10px;border-bottom:2px solid var(--ink)}
.sev-head .dot{transform:translateY(-1px)}
.sev-head .desc{color:var(--muted);font-size:.9rem}
.item{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;padding:20px 0;border-bottom:1px solid var(--line)}
.item-head{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
.item-head h3{margin-right:4px}
.pill{font-size:.72rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;padding:3px 8px;border-radius:4px;background:var(--soft);color:var(--muted);white-space:nowrap}
.meta{font-size:.85rem;color:var(--muted)}
.quiet{margin-left:auto;font-family:var(--f-mono);font-size:.8rem;font-weight:500;padding:3px 9px;border-radius:4px;white-space:nowrap}
.quiet.bad{background:var(--crit-soft);color:var(--crit)} .quiet.okq{background:var(--ok-soft);color:var(--ok)}
.lastcomm{font-size:.95rem}
.lastcomm .dir{font-weight:700;letter-spacing:.02em}
.lastcomm .subj{color:var(--muted);font-style:italic}
.flags{margin:0;padding:0;list-style:none;display:grid;gap:5px;font-size:.92rem}
.flags li{display:grid;grid-template-columns:110px minmax(0,1fr);gap:12px}
.flags .k{font-size:.72rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding-top:3px}
.next{font-size:.92rem;background:var(--soft);border-radius:8px;padding:10px 14px}
.next b{font-weight:600;color:var(--accent)}
.carriers{display:inline-flex;flex-wrap:wrap;gap:5px;vertical-align:middle}
.car{font-family:var(--f-mono);font-size:.76rem;padding:1px 7px;border:1px solid var(--line);border-radius:4px;background:var(--surface);white-space:nowrap}
.car.open{border-color:var(--warn);color:var(--warn)}
.tablebox{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;min-width:900px;font-size:.86rem}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600;background:var(--soft);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td.num{font-family:var(--f-mono);font-variant-numeric:tabular-nums;white-space:nowrap}
td .g{display:flex;align-items:center;gap:8px;font-weight:600}
.y{color:var(--ok);font-weight:600} .n{color:var(--crit);font-weight:600} .p{color:var(--warn);font-weight:600}
td.q-bad{color:var(--crit);font-weight:600}
.outside{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 28px}
.outside div{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);font-size:.9rem;min-width:0}
.outside span:last-child{color:var(--muted);font-size:.84rem;text-align:right}
.notes{display:grid;gap:8px;font-size:.88rem;color:var(--muted);max-width:72ch}
.notes ul{margin:0;padding-left:18px;display:grid;gap:6px}
section>.intro,.sec-title .intro{color:var(--muted);font-size:.92rem;max-width:70ch;margin-top:6px}
.sec-title{display:grid;gap:4px;margin-bottom:14px}
@media (max-width:760px){
  .today-list{grid-template-columns:minmax(0,1fr)}
  .outside{grid-template-columns:minmax(0,1fr)}
  .flags li{grid-template-columns:minmax(0,1fr);gap:0}
  .quiet{margin-left:0}
}
@media (prefers-reduced-motion:no-preference){.chip{transition:background .15s,border-color .15s}}
@media print{.tally{display:none}.sev[hidden]{display:grid!important}}
"""

HTML_JS = r"""
(function(){
  var chips=[].slice.call(document.querySelectorAll('.chip'));
  var secs=[].slice.call(document.querySelectorAll('.sev'));
  function apply(f){
    chips.forEach(function(c){c.setAttribute('aria-pressed',String(c.dataset.f===f));});
    secs.forEach(function(s){s.hidden=!(f==='all'||s.dataset.sev===f);});
  }
  chips.forEach(function(c){c.addEventListener('click',function(){apply(c.dataset.f);});});
})();
"""


def grid_cell_html(v, num=False):
    v = "" if v is None else str(v)
    low = v.lower()
    if low == "y" or low.startswith("y:"):
        extra = v.split(":", 1)[1].strip() if ":" in v else ""
        return f'<td class="y">✓{(" " + esc(extra)) if extra else ""}</td>'
    if low == "n":
        return '<td class="n">✗</td>'
    if v in ("", "-", "—"):
        return '<td class="num">—</td>'
    if num:
        return f'<td class="num">{esc(v)}</td>'
    return f'<td class="p">{esc(v)}</td>'


def flag_value_html(f):
    if f.get("carriers"):
        cars = "".join(
            f'<span class="car{" open" if c.get("open", True) else ""}">{esc(c.get("name"))}'
            f'{(" " + esc(c["days"])) if c.get("days") else ""}</span>'
            for c in f["carriers"])
        lead = f'{inline_html(f["text"])} ' if f.get("text") else ""
        return f'<span>{lead}<span class="carriers">{cars}</span></span>'
    return f"<span>{inline_html(f.get('text'))}</span>"


def build_html(data):
    run = data["run"]
    threshold = int(run.get("quiet_days", 8))
    counts = tally(data)
    total = len(data.get("groups", []))
    title = data.get("title") or "New Business Pipeline Check"
    out = []
    a = out.append
    a('<!doctype html><html lang="en"><head><meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">')
    a(f"<title>{esc(title)}</title>")
    a('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    a('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&family=Public+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">')
    a(f"<style>{HTML_CSS}</style></head><body><div class=\"wrap\">")

    # Header
    sources = run.get("sources") or ["Odoo", "Dropbox", "Asana", "Outlook"]
    a('<header><div class="eyebrow">The Benefits Group · New Business</div>')
    a(f"<h1>{esc(title)}</h1><div class=\"runline\">")
    a(f'<span>Run <b class="mono">{esc(run.get("label"))}</b></span>')
    a(f'<span><b>{esc(run.get("groups_in_scope", total))}</b> groups in scope</span>')
    a(f'<span>Quiet line <b>{threshold} days</b></span>')
    a(f'<span>Sources: {esc(" · ".join(sources))}</span></div>')
    for gap in run.get("gaps") or []:
        a(f'<p class="gap"><b>Gap:</b> {inline_html(gap)}</p>')
    a("</header>")

    # Today's three
    today = data.get("today") or []
    if today:
        a('<section class="today"><div class="sec-title"><div class="eyebrow">Act on these first</div><h2>Today\'s three</h2></div><div class="today-list">')
        for i, t in enumerate(today[:3], 1):
            a(f'<div class="today-card"><span class="rank">{i:02d} · {esc(t.get("rank"))}</span>'
              f'<h3>{esc(t.get("group"))}</h3><p>{inline_html(t.get("reason"))}</p></div>')
        a("</div>")
        co = data.get("callout")
        if co and (co.get("lead") or co.get("text")):
            a(f'<p class="callout"><b>{inline_html(co.get("lead"))}</b> {inline_html(co.get("text"))}</p>')
        a("</section>")

    # Tally chips
    a('<section><div class="sec-title"><div class="eyebrow">Needs attention</div><h2>Exceptions by severity</h2></div>')
    a('<div class="tally" role="group" aria-label="Filter by severity">')
    a(f'<button class="chip" data-f="all" aria-pressed="true">All <span class="n">{total}</span></button>')
    for key, chip, _h, _d in TIERS:
        a(f'<button class="chip s-{key}" data-f="{key}" aria-pressed="false"><span class="dot"></span>{esc(chip)} <span class="n">{counts[key]}</span></button>')
    a("</div></section>")

    # Severity sections
    empty_notes = data.get("empty_tier_notes") or {}
    for key, _chip, heading, desc in TIERS:
        groups = [g for g in data.get("groups", []) if g.get("sev") == key]
        a(f'<section class="sev" data-sev="{key}"><div class="sev-head"><span class="dot {key}"></span><h2>{esc(heading)}</h2><span class="desc">{esc(desc)}</span></div>')
        if not groups:
            a(f'<article class="item"><p class="meta">{inline_html(empty_notes.get(key) or "Nothing in this tier today.")}</p></article>')
        for g in groups:
            ql, bad = quiet_info(g, threshold)
            a('<article class="item"><div class="item-head">')
            a(f'<h3>{esc(g.get("name"))}</h3><span class="pill">{esc(g.get("stage"))}</span>')
            a(f'<span class="meta">{esc(meta_line(g))}</span><span class="quiet {"bad" if bad else "okq"}">{esc(ql)}</span></div>')
            last = g.get("last")
            if last:
                d = (last.get("dir") or "").upper()
                if d.startswith("FROM"):
                    who = f'{esc(last.get("who"))} to {esc(last.get("team"))}' if last.get("team") else esc(last.get("who"))
                    a(f'<p class="lastcomm">Last communication was <span class="dir">FROM</span> {who} on <b class="mono">{esc(last.get("date"))}</b>')
                else:
                    by = f' by {esc(last.get("team"))}' if last.get("team") else ""
                    a(f'<p class="lastcomm">Last communication was <span class="dir">SENT TO</span> {esc(last.get("who"))}{by} on <b class="mono">{esc(last.get("date"))}</b>')
                if last.get("subject"):
                    a(f' · <span class="subj">{esc(last["subject"])}</span>')
                a("</p>")
            else:
                a('<p class="lastcomm">No client email found in the last 60 days.</p>')
            flags = g.get("flags") or []
            if flags:
                a('<ul class="flags">')
                for f in flags:
                    a(f'<li><span class="k">{esc(f.get("k"))}</span>{flag_value_html(f)}</li>')
                a("</ul>")
            if g.get("next"):
                a(f'<p class="next"><b>Next step:</b> {inline_html(g["next"])}</p>')
            a("</article>")
        a("</section>")

    # Grid
    a('<section><div class="sec-title"><div class="eyebrow">Every group</div><h2>Full status grid</h2></div><div class="tablebox"><table>')
    a("<thead><tr><th>Group</th><th>Odoo stage</th><th>Eff</th><th>Last contact</th><th>Quiet</th><th>Census</th><th>Sent</th><th>Received</th><th>Outstanding</th><th>Analysis</th><th>Selector</th><th>Folder</th><th>Asana</th></tr></thead><tbody>")
    for key in TIER_KEYS:
        for g in [x for x in data.get("groups", []) if x.get("sev") == key]:
            gr = g.get("grid") or {}
            q = g.get("quiet")
            qcls = "num q-bad" if (q is not None and q >= threshold) else "num"
            a("<tr>")
            a(f'<td><span class="g"><span class="dot {key}"></span>{esc(g.get("name"))}</span></td>')
            a(f'<td>{esc(gr.get("stage") or g.get("stage"))}</td>')
            a(f'<td class="num">{esc(gr.get("eff") or short_date(g.get("effective")) or "—")}</td>')
            a(f'<td class="num">{esc(last_contact_short(g))}</td>')
            a(f'<td class="{qcls}">{esc("—" if q is None else q)}</td>')
            a(grid_cell_html(gr.get("census")))
            a(grid_cell_html(gr.get("sent"), num=True))
            a(grid_cell_html(gr.get("received"), num=True))
            a(grid_cell_html(gr.get("outstanding"), num=True))
            a(grid_cell_html(gr.get("analysis")))
            a(grid_cell_html(gr.get("selector")))
            a(grid_cell_html(gr.get("folder")))
            a(grid_cell_html(gr.get("asana")))
            a("</tr>")
    a("</tbody></table></div>")
    a('<p class="intro">→ sent to the client · ← from the client. "Received" counts carriers logged under Save Quotes in DB, including DTQ and not-competitive responses. "Drift" means a response is saved in Dropbox but not logged in Asana.</p></section>')

    # Outside the pipeline
    outside = data.get("outside") or []
    a('<section><div class="sec-title"><div class="eyebrow">Outside this report\'s stages</div><h2>Active work not in the Odoo pipeline</h2>')
    a('<p class="intro">These groups have a Hot Leads folder or an active Asana quoting project, but aren\'t in Qualified, Quoting, or Quoted/Presented in Odoo. Move them in Odoo, or archive the work.</p></div>')
    if outside:
        a('<div class="outside">')
        for o in outside:
            a(f'<div><span>{esc(o.get("name"))}</span><span>{esc(o.get("status"))}</span></div>')
        a("</div>")
    else:
        a('<p class="meta">None today.</p>')
    a("</section>")

    # Notes
    a('<section class="notes"><div class="eyebrow">Run notes</div><ul>')
    for n in data.get("notes") or []:
        a(f"<li>{inline_html(n)}</li>")
    a("</ul></section></div>")
    a(f"<script>{HTML_JS}</script></body></html>")
    return "\n".join(out)


# ----------------------------------------------------------------------------------------------
# Email body (short; the PDF is attached)
# ----------------------------------------------------------------------------------------------
def build_email(data, report_note=None):
    run = data["run"]
    counts = tally(data)
    total = len(data.get("groups", []))
    c = COLORS
    font = "font-family:Arial,Helvetica,sans-serif;"
    rows = []
    a = rows.append
    a(f'<div style="{font}font-size:14px;line-height:1.5;color:{c["ink"]};max-width:640px">')
    a(f'<div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:{c["muted"]}">The Benefits Group · New Business</div>')
    a(f'<div style="font-family:Georgia,serif;font-size:22px;font-weight:bold;margin:2px 0 4px">{esc(data.get("title") or "New Business Pipeline Check")}</div>')
    a(f'<div style="color:{c["muted"]};font-size:13px;margin-bottom:14px">Run {esc(run.get("label"))} · {esc(run.get("groups_in_scope", total))} groups in scope · quiet line {esc(run.get("quiet_days", 8))} days</div>')
    for gap in run.get("gaps") or []:
        a(f'<div style="background:{c["crit_soft"]};color:{c["crit"]};padding:8px 12px;border-radius:6px;margin-bottom:12px;font-size:13px"><b>Gap:</b> {inline_html(gap)}</div>')
    chips = []
    for key, chip, _h, _d in TIERS:
        chips.append(f'<td style="padding:6px 10px;border:1px solid {c["line"]};border-radius:999px;white-space:nowrap;font-size:13px">'
                     f'<span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:{c[key]};margin-right:6px"></span>'
                     f'{esc(chip)} <b>{counts[key]}</b></td><td style="width:6px"></td>')
    a(f'<table role="presentation" cellspacing="0" cellpadding="0" style="margin-bottom:16px"><tr>{"".join(chips)}</tr></table>')
    today = data.get("today") or []
    if today:
        a('<div style="font-weight:bold;font-size:15px;margin:4px 0 6px">Today\'s three</div>')
        for i, t in enumerate(today[:3], 1):
            a(f'<div style="border-left:3px solid {c["crit"]};padding:4px 0 4px 12px;margin-bottom:10px">'
              f'<div><b>{i}. {esc(t.get("group"))}</b> <span style="color:{c["crit"]};font-size:12px">· {esc(t.get("rank"))}</span></div>'
              f'<div style="color:{c["muted"]};font-size:13px">{inline_html(t.get("reason"))}</div></div>')
    co = data.get("callout")
    if co and (co.get("lead") or co.get("text")):
        a(f'<div style="background:{c["accent_soft"]};padding:10px 14px;border-radius:8px;font-size:13px;margin:8px 0 14px">'
          f'<b style="color:{c["accent"]}">{inline_html(co.get("lead"))}</b> {inline_html(co.get("text"))}</div>')
    a(f'<div style="font-size:13px;color:{c["muted"]}">{inline_html(report_note or "The full report — every exception, the status grid, and the run notes — is attached as a PDF.")}</div>')
    a("</div>")
    return "\n".join(rows)


# ----------------------------------------------------------------------------------------------
# PDF (reportlab)
# ----------------------------------------------------------------------------------------------
FONT_FILES = {
    "TBGSerif": "SourceSerif4_600SemiBold.ttf",
    "TBGSans": "PublicSans_400Regular.ttf",
    "TBGSans-Italic": "PublicSans_400Regular_Italic.ttf",
    "TBGSans-Semi": "PublicSans_600SemiBold.ttf",
    "TBGSans-Bold": "PublicSans_700Bold.ttf",
    "TBGMono": "IBMPlexMono-Regular.ttf",
    "TBGMono-Medium": "IBMPlexMono-Medium.ttf",
}


def _font_path(fname):
    local = os.path.join(HERE, "fonts", fname)
    if os.path.exists(local):
        return local
    cache = os.path.join(os.path.expanduser("~"), ".cache", "tbg-fonts")
    os.makedirs(cache, exist_ok=True)
    cached = os.path.join(cache, fname)
    if os.path.exists(cached) and os.path.getsize(cached) > 1000:
        return cached
    try:
        urllib.request.urlretrieve(TOOLS_URL + "fonts/" + fname, cached)
        if os.path.getsize(cached) > 1000:
            return cached
    except Exception:
        pass
    return None


def register_fonts():
    """Returns a dict of role -> font name. Falls back to built-in fonts if the TTFs are unavailable."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    ok = True
    for name, fname in FONT_FILES.items():
        p = _font_path(fname)
        if not p:
            ok = False
            break
        try:
            pdfmetrics.registerFont(TTFont(name, p))
        except Exception:
            ok = False
            break
    if ok:
        addMapping("TBGSans", 0, 0, "TBGSans")
        addMapping("TBGSans", 1, 0, "TBGSans-Bold")
        addMapping("TBGSans", 0, 1, "TBGSans-Italic")
        addMapping("TBGSans", 1, 1, "TBGSans-Bold")
        return {"display": "TBGSerif", "body": "TBGSans", "italic": "TBGSans-Italic", "semi": "TBGSans-Semi",
                "bold": "TBGSans-Bold", "mono": "TBGMono", "mono_med": "TBGMono-Medium", "unicode": True}
    return {"display": "Times-Bold", "body": "Helvetica", "italic": "Helvetica-Oblique", "semi": "Helvetica-Bold",
            "bold": "Helvetica-Bold", "mono": "Courier", "mono_med": "Courier-Bold", "unicode": False}


def build_pdf(data, out_path):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
                                    TableStyle, KeepTogether, NextPageTemplate, PageBreak, CondPageBreak, Image)

    F = register_fonts()
    C = {k: colors.HexColor(v) for k, v in COLORS.items()}
    run = data["run"]
    threshold = int(run.get("quiet_days", 8))
    counts = tally(data)
    total = len(data.get("groups", []))
    title = data.get("title") or "New Business Pipeline Check"

    def clean(s):
        s = "" if s is None else str(s)
        # Drop emoji and other symbols no font here carries.
        s = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️]", "", s)
        if not F["unicode"]:
            s = s.replace("→", "to").replace("←", "from").replace("✓", "Y").replace("✗", "N")
            s = s.encode("cp1252", "ignore").decode("cp1252")
        return s

    def P(s):
        """Escape and convert **bold** / `mono` for reportlab paragraphs."""
        t = html.escape(clean(s), quote=False)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"`(.+?)`", lambda m: f'<font face="{F["mono"]}">{m.group(1)}</font>', t)
        t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", lambda m: f'<font face="{F["italic"]}">{m.group(1)}</font>', t)
        return t

    def mono(s):
        return f'<font face="{F["mono"]}">{html.escape(clean(s), quote=False)}</font>'

    st = {
        "eyebrow": ParagraphStyle("eyebrow", fontName=F["semi"], fontSize=7.2, leading=9, textColor=C["muted"]),
        "h1": ParagraphStyle("h1", fontName=F["display"], fontSize=25, leading=29, textColor=C["ink"]),
        "h2": ParagraphStyle("h2", fontName=F["display"], fontSize=15, leading=19, textColor=C["ink"]),
        "h3": ParagraphStyle("h3", fontName=F["display"], fontSize=12, leading=15, textColor=C["ink"]),
        "body": ParagraphStyle("body", fontName=F["body"], fontSize=9, leading=12.6, textColor=C["ink"]),
        "muted": ParagraphStyle("muted", fontName=F["body"], fontSize=8.6, leading=12, textColor=C["muted"]),
        "small": ParagraphStyle("small", fontName=F["body"], fontSize=7.8, leading=10.4, textColor=C["muted"]),
        "k": ParagraphStyle("k", fontName=F["semi"], fontSize=6.6, leading=11, textColor=C["muted"]),
        "rank": ParagraphStyle("rank", fontName=F["mono_med"], fontSize=7.6, leading=10, textColor=C["crit"]),
        "cell": ParagraphStyle("cell", fontName=F["body"], fontSize=7.4, leading=9.4, textColor=C["ink"]),
        "cellb": ParagraphStyle("cellb", fontName=F["semi"], fontSize=7.4, leading=9.4, textColor=C["ink"]),
        "th": ParagraphStyle("th", fontName=F["semi"], fontSize=6.3, leading=8, textColor=C["muted"]),
    }

    def eyebrow(s):
        return Paragraph(clean(s).upper(), st["eyebrow"])

    def spaced(s):
        return s

    logo_path = os.path.join(HERE, "tbg-logo.png")
    if not os.path.exists(logo_path):
        try:
            cache = os.path.join(os.path.expanduser("~"), ".cache", "tbg-fonts", "tbg-logo.png")
            if not os.path.exists(cache):
                urllib.request.urlretrieve(TOOLS_URL + "tbg-logo.png", cache)
            logo_path = cache
        except Exception:
            logo_path = None

    PW, PH = letter
    LW, LH = landscape(letter)
    M = 0.6 * inch

    def decorate(canvas, doc, pw, ph):
        canvas.saveState()
        canvas.setFillColor(C["paper"])
        canvas.rect(0, 0, pw, ph, stroke=0, fill=1)
        # Accent rule across the top
        canvas.setFillColor(C["accent"])
        canvas.rect(0, ph - 5, pw, 5, stroke=0, fill=1)
        # Footer
        canvas.setStrokeColor(C["line"])
        canvas.setLineWidth(0.6)
        canvas.line(M, 0.5 * inch, pw - M, 0.5 * inch)
        canvas.setFont(F["body"], 7)
        canvas.setFillColor(C["muted"])
        canvas.drawString(M, 0.36 * inch, clean(f"The Benefits Group · {title} · Run {run.get('label', '')}"))
        canvas.drawRightString(pw - M, 0.36 * inch, f"Page {doc.page}")
        canvas.setFont(F["italic"], 6.6)
        canvas.drawCentredString(pw / 2, 0.22 * inch, "Internal — contains client contact details. Do not forward outside The Benefits Group.")
        canvas.restoreState()

    doc = BaseDocTemplate(out_path, pagesize=letter, leftMargin=M, rightMargin=M, topMargin=0.62 * inch,
                          bottomMargin=0.72 * inch, title=title, author="The Benefits Group",
                          subject="New business pipeline exception report")
    fp = Frame(M, 0.72 * inch, PW - 2 * M, PH - 0.62 * inch - 0.72 * inch, id="p", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    fl = Frame(M, 0.72 * inch, LW - 2 * M, LH - 0.62 * inch - 0.72 * inch, id="l", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="portrait", frames=[fp], pagesize=letter, onPage=lambda c, d: decorate(c, d, PW, PH)),
        PageTemplate(id="landscape", frames=[fl], pagesize=landscape(letter), onPage=lambda c, d: decorate(c, d, LW, LH)),
    ])
    W = PW - 2 * M
    story = []

    # ---- Header ----
    head_left = [eyebrow("The Benefits Group · New Business"), Spacer(1, 4), Paragraph(P(title), st["h1"]), Spacer(1, 6)]
    sources = run.get("sources") or ["Odoo", "Dropbox", "Asana", "Outlook"]
    runline = (f'Run <font face="{F["mono_med"]}" color="{COLORS["ink"]}">{html.escape(clean(run.get("label", "")))}</font>'
               f'&nbsp;&nbsp;·&nbsp;&nbsp;<font color="{COLORS["ink"]}"><b>{esc(run.get("groups_in_scope", total))}</b></font> groups in scope'
               f'&nbsp;&nbsp;·&nbsp;&nbsp;Quiet line <font color="{COLORS["ink"]}"><b>{threshold} days</b></font>'
               f'&nbsp;&nbsp;·&nbsp;&nbsp;Sources: {html.escape(clean(" · ".join(sources)))}')
    head_left.append(Paragraph(runline, st["muted"]))
    if logo_path:
        logo = Image(logo_path, width=0.78 * inch, height=0.78 * inch)
        ht = Table([[head_left, logo]], colWidths=[W - 0.9 * inch, 0.9 * inch])
        ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        story.append(ht)
    else:
        story.extend(head_left)
    story.append(Spacer(1, 10))
    rule = Table([[""]], colWidths=[W], rowHeights=[0.1])
    rule.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.8, C["line"])]))
    story.append(rule)
    story.append(Spacer(1, 10))
    for gap in run.get("gaps") or []:
        gt = Table([[Paragraph(f'<b>Gap:</b> {P(gap)}', ParagraphStyle("gap", parent=st["body"], textColor=C["crit"]))]], colWidths=[W])
        gt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C["crit_soft"]), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story.extend([gt, Spacer(1, 8)])

    # ---- Tally strip ----
    cells, widths = [], []
    cw = W / 6
    cells.append(Paragraph(f'<font face="{F["mono_med"]}" size="15">{total}</font><br/><font size="7" color="{COLORS["muted"]}">GROUPS REVIEWED</font>', st["body"]))
    for key, chip, _h, _d in TIERS:
        cells.append(Paragraph(f'<font face="{F["mono_med"]}" size="15" color="{COLORS[key]}">{counts[key]}</font><br/><font size="7" color="{COLORS["muted"]}">{esc(chip.upper())}</font>', st["body"]))
    tt = Table([cells], colWidths=[cw] * 6)
    ts = [("BACKGROUND", (0, 0), (-1, -1), C["surface"]), ("BOX", (0, 0), (-1, -1), 0.6, C["line"]),
          ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i, (key, *_r) in enumerate(TIERS, start=1):
        ts.append(("LINEBEFORE", (i, 0), (i, 0), 0.6, C["line"]))
        ts.append(("LINEABOVE", (i, 0), (i, 0), 2.2, C[key]))
    tt.setStyle(TableStyle(ts))
    story.extend([tt, Spacer(1, 16)])

    # ---- Today's three ----
    today = (data.get("today") or [])[:3]
    if today:
        story.extend([eyebrow("Act on these first"), Spacer(1, 2), Paragraph("Today’s three" if F["unicode"] else "Today's three", st["h2"]), Spacer(1, 8)])
        cardw = (W - 2 * 8) / 3
        cards = []
        for i, t in enumerate(today, 1):
            cards.append([Paragraph(f"{i:02d} · {html.escape(clean(t.get('rank')), quote=False)}", st["rank"]), Spacer(1, 3),
                          Paragraph(P(t.get("group")), st["h3"]), Spacer(1, 4), Paragraph(P(t.get("reason")), st["muted"])])
        while len(cards) < 3:
            cards.append("")
        row = []
        for i, cdata in enumerate(cards):
            row.append(cdata)
            if i < 2:
                row.append("")
        ct = Table([row], colWidths=[cardw, 8, cardw, 8, cardw])
        cts = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
               ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 11)]
        for col in (0, 2, 4):
            if cards[col // 2]:
                cts += [("BACKGROUND", (col, 0), (col, 0), C["surface"]), ("BOX", (col, 0), (col, 0), 0.6, C["line"]),
                        ("LINEABOVE", (col, 0), (col, 0), 2.4, C["crit"])]
        for col in (1, 3):
            cts += [("LEFTPADDING", (col, 0), (col, 0), 0), ("RIGHTPADDING", (col, 0), (col, 0), 0)]
        ct.setStyle(TableStyle(cts))
        story.extend([ct, Spacer(1, 10)])
        co = data.get("callout")
        if co and (co.get("lead") or co.get("text")):
            cot = Table([[Paragraph(f'<font color="{COLORS["accent"]}"><b>{P(co.get("lead"))}</b></font> {P(co.get("text"))}', st["body"])]], colWidths=[W])
            cot.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C["accent_soft"]), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
            story.append(cot)
        story.append(Spacer(1, 18))

    # ---- Severity sections ----
    empty_notes = data.get("empty_tier_notes") or {}
    KW = 0.95 * inch

    def carriers_par(f):
        bits = []
        for c in f.get("carriers") or []:
            col = COLORS["warn"] if c.get("open", True) else COLORS["muted"]
            label = clean(c.get("name")) + ((" " + clean(c.get("days"))) if c.get("days") else "")
            bits.append(f'<font face="{F["mono"]}" color="{col}">{html.escape(label, quote=False)}</font>')
        lead = (P(f["text"]) + "  ") if f.get("text") else ""
        return Paragraph(lead + '<font color="#B7C0BD">  |  </font>'.join(bits), st["body"])

    def group_block(g, key):
        ql, bad = quiet_info(g, threshold)
        qcol = COLORS["crit"] if bad else COLORS["ok"]
        qbg = C["crit_soft"] if bad else C["ok_soft"]
        name = Paragraph(P(g.get("name")), st["h3"])
        stage = Paragraph(f'<font face="{F["semi"]}" size="6.6" color="{COLORS["muted"]}">{html.escape(clean(g.get("stage", "")).upper(), quote=False)}</font>'
                          f'&nbsp;&nbsp;<font size="7.8" color="{COLORS["muted"]}">{html.escape(clean(meta_line(g)), quote=False)}</font>', st["body"])
        from reportlab.pdfbase.pdfmetrics import stringWidth
        bw = stringWidth(clean(ql), F["mono_med"], 7.6) + 14
        badge = Table([[Paragraph(f'<font face="{F["mono_med"]}" size="7.6" color="{qcol}">{html.escape(clean(ql), quote=False)}</font>', st["body"])]], colWidths=[bw])
        badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), qbg), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        head = Table([[[name, Spacer(1, 2), stage], badge]], colWidths=[W - 1.25 * inch, 1.25 * inch])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                                  ("RIGHTPADDING", (1, 0), (1, 0), 0),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                  ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        parts = [head, Spacer(1, 5)]
        last = g.get("last")
        if last:
            d = (last.get("dir") or "").upper()
            if d.startswith("FROM"):
                lc = f'Last communication was <b>FROM</b> {P(last.get("who"))}' + (f' to {P(last.get("team"))}' if last.get("team") else "")
            else:
                lc = f'Last communication was <b>SENT TO</b> {P(last.get("who"))}' + (f' by {P(last.get("team"))}' if last.get("team") else "")
            lc += f' on {mono(last.get("date"))}'
            if last.get("subject"):
                lc += f' · <font face="{F["italic"]}" color="{COLORS["muted"]}">{P(last["subject"])}</font>'
        else:
            lc = "No client email found in the last 60 days."
        parts += [Paragraph(lc, st["body"]), Spacer(1, 5)]
        flags = g.get("flags") or []
        if flags:
            rows = []
            for f in flags:
                val = carriers_par(f) if f.get("carriers") else Paragraph(P(f.get("text")), st["body"])
                rows.append([Paragraph(clean(f.get("k", "")).upper(), st["k"]), val])
            ft = Table(rows, colWidths=[KW, W - KW])
            ft.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2)]))
            parts += [ft, Spacer(1, 6)]
        if g.get("next"):
            nt = Table([[Paragraph(f'<font color="{COLORS["accent"]}"><b>Next step:</b></font> {P(g["next"])}', st["body"])]], colWidths=[W])
            nt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C["soft"]), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            parts.append(nt)
        parts.append(Spacer(1, 9))
        sep = Table([[""]], colWidths=[W], rowHeights=[0.1])
        sep.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, C["line"])]))
        parts += [sep, Spacer(1, 10)]
        return parts

    def hw(text):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        return min(W * 0.6, stringWidth(clean(text), F["display"], 15) + 34)

    for key, _chip, heading, desc in TIERS:
        groups = [g for g in data.get("groups", []) if g.get("sev") == key]
        if not groups and key == "ok":
            continue
        sh = Table([[Paragraph(f'<font color="{COLORS[key]}">■</font>&nbsp; {P(heading)}', st["h2"]),
                     Paragraph(P(desc), st["muted"])]], colWidths=[hw(heading), W - hw(heading)])
        sh.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LINEBELOW", (0, 0), (-1, -1), 1.4, C["ink"]),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
        if not groups:
            story.append(KeepTogether([sh, Spacer(1, 10), Paragraph(P(empty_notes.get(key) or "Nothing in this tier today."), st["muted"]), Spacer(1, 16)]))
            continue
        for i, g in enumerate(groups):
            parts = group_block(g, key)
            story.append(KeepTogether(([sh, Spacer(1, 10)] if i == 0 else []) + parts))
        story.append(Spacer(1, 6))

    # ---- Grid (landscape) ----
    story += [NextPageTemplate("landscape"), PageBreak()]
    GW = LW - 2 * M
    story += [eyebrow("Every group"), Spacer(1, 2), Paragraph("Full status grid", st["h2"]), Spacer(1, 8)]
    hdr = ["Group", "Odoo stage", "Eff", "Last contact", "Quiet", "Census", "Sent", "Received", "Outstanding", "Analysis", "Selector", "Folder", "Asana"]
    widths = [1.43, 1.1, 0.48, 1.45, 0.45, 0.58, 0.5, 0.62, 0.86, 0.62, 0.66, 0.5, 0.55]
    scale = GW / (sum(widths) * inch)
    widths = [w * inch * scale for w in widths]

    def gcell(v, num=False):
        v = "" if v is None else str(v)
        low = v.lower()
        if low == "y" or low.startswith("y:"):
            extra = v.split(":", 1)[1].strip() if ":" in v else ""
            tick = "✓" if F["unicode"] else "Y"
            return Paragraph(f'<font face="{F["mono_med"]}" color="{COLORS["ok"]}">{tick}</font>' +
                             (f' <font color="{COLORS["ok"]}">{html.escape(clean(extra), quote=False)}</font>' if extra else ""), st["cell"])
        if low == "n":
            return Paragraph(f'<font face="{F["bold"]}" color="{COLORS["crit"]}">×</font>' if F["unicode"] else f'<font color="{COLORS["crit"]}"><b>N</b></font>', st["cell"])
        if v in ("", "-", "—"):
            return Paragraph(f'<font color="{COLORS["muted"]}">—</font>', st["cell"])
        if num:
            return Paragraph(mono(v), st["cell"])
        return Paragraph(f'<font color="{COLORS["warn"]}"><b>{html.escape(clean(v), quote=False)}</b></font>', st["cell"])

    rows = [[Paragraph(h.upper(), st["th"]) for h in hdr]]
    row_keys = []
    for key in TIER_KEYS:
        for g in [x for x in data.get("groups", []) if x.get("sev") == key]:
            gr = g.get("grid") or {}
            q = g.get("quiet")
            qtxt = "—" if q is None else str(q)
            qpar = Paragraph(f'<font face="{F["mono_med"]}" color="{COLORS["crit"] if (q is not None and q >= threshold) else COLORS["ink"]}">{qtxt}</font>', st["cell"])
            rows.append([
                Paragraph(f'<font color="{COLORS[key]}">■</font> {P(g.get("name"))}', st["cellb"]),
                Paragraph(P(gr.get("stage") or g.get("stage")), st["cell"]),
                Paragraph(mono(gr.get("eff") or short_date(g.get("effective")) or "—"), st["cell"]),
                Paragraph(mono(last_contact_short(g, arrow=F["unicode"])), st["cell"]),
                qpar,
                gcell(gr.get("census")), gcell(gr.get("sent"), True), gcell(gr.get("received"), True),
                gcell(gr.get("outstanding"), True), gcell(gr.get("analysis")), gcell(gr.get("selector")),
                gcell(gr.get("folder")), gcell(gr.get("asana")),
            ])
            row_keys.append(key)
    gt = Table(rows, colWidths=widths, repeatRows=1)
    gts = [("BACKGROUND", (0, 0), (-1, 0), C["soft"]), ("BOX", (0, 0), (-1, -1), 0.6, C["line"]),
           ("LINEBELOW", (0, 0), (-1, -1), 0.4, C["line"]), ("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
           ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5)]
    for i in range(1, len(rows)):
        gts.append(("BACKGROUND", (0, i), (-1, i), C["surface"] if i % 2 else colors.HexColor("#FAFBFB")))
    gt.setStyle(TableStyle(gts))
    story += [gt, Spacer(1, 6),
              Paragraph(P("“Last contact”: to = sent to the client, from = from the client. “Received” counts carriers logged under Save Quotes in DB, including DTQ and not-competitive responses. “Drift” means a response is saved in Dropbox but not logged in Asana."
                          if F["unicode"] else
                          "Last contact: to = sent to the client, from = from the client. Received counts carriers logged under Save Quotes in DB, including DTQ and not-competitive responses. Drift means a response is saved in Dropbox but not logged in Asana."), st["small"])]

    # ---- Outside pipeline + notes (back to portrait) ----
    story += [NextPageTemplate("portrait"), PageBreak()]
    story += [eyebrow("Outside this report’s stages" if F["unicode"] else "Outside this report's stages"), Spacer(1, 2),
              Paragraph("Active work not in the Odoo pipeline", st["h2"]), Spacer(1, 4),
              Paragraph("These groups have a Hot Leads folder or an active Asana quoting project, but aren't in Qualified, Quoting, or Quoted/Presented in Odoo. Move them in Odoo, or archive the work.", st["muted"]),
              Spacer(1, 8)]
    outside = data.get("outside") or []
    if outside:
        half = (len(outside) + 1) // 2
        colA, colB = outside[:half], outside[half:]
        orows = []
        for i in range(half):
            a1 = colA[i]
            b1 = colB[i] if i < len(colB) else None
            orows.append([Paragraph(P(a1.get("name")), st["body"]), Paragraph(P(a1.get("status")), st["small"]), "",
                          Paragraph(P(b1.get("name")), st["body"]) if b1 else "", Paragraph(P(b1.get("status")), st["small"]) if b1 else ""])
        cwid = (W - 0.3 * inch) / 2
        ot = Table(orows, colWidths=[cwid * 0.5, cwid * 0.5, 0.3 * inch, cwid * 0.5, cwid * 0.5])
        ot.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (1, -1), 0.4, C["line"]),
                                ("LINEBELOW", (3, 0), (4, len(colB) - 1 if colB else 0), 0.4, C["line"]),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story.append(ot)
    else:
        story.append(Paragraph("None today.", st["muted"]))
    story += [Spacer(1, 22), eyebrow("Run notes"), Spacer(1, 6)]
    for n in data.get("notes") or []:
        story.append(Paragraph(P(n), ParagraphStyle("note", parent=st["muted"], leftIndent=10, bulletIndent=0, spaceAfter=3), bulletText="•"))

    doc.build(story)


# ----------------------------------------------------------------------------------------------
def main(argv):
    if len(argv) >= 2 and argv[1] == "--example":
        src = os.path.join(HERE, "pipeline_report_example.json")
        base = argv[2] if len(argv) > 2 else "pipeline_report_example"
    elif len(argv) >= 3:
        src, base = argv[1], argv[2]
    else:
        print(__doc__)
        return 2
    base = re.sub(r"\.(pdf|html)$", "", base)
    with open(src, encoding="utf-8") as fh:
        data = json.load(fh)
    validate(data)
    with open(base + ".html", "w", encoding="utf-8") as fh:
        fh.write(build_html(data))
    with open(base + "-email.html", "w", encoding="utf-8") as fh:
        fh.write(build_email(data))
    build_pdf(data, base + ".pdf")
    print(json.dumps({"html": base + ".html", "pdf": base + ".pdf", "email": base + "-email.html",
                      "groups": len(data.get("groups", [])), "tally": tally(data)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
