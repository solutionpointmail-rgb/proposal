# Analyze Quotes — routine (button + daily sweep)

Status as of Oct 12, 2026: **working end to end, both modes, with direct write to Dropbox and
GitHub Pages.** The Cowork daily task is paused; this routine is now the only thing running
quote analysis.

## The routine

- Name: **TBG Analyze Quotes**
- ID: `trig_01FPR6uiUGsiLm1aSW1eLVmz`
- Fire URL: `https://api.anthropic.com/v1/claude_code/routines/trig_01FPR6uiUGsiLm1aSW1eLVmz/fire`
- Model: **Opus** — set it explicitly; the source task inherited the default and skipped steps.
- Triggers: **API** (the dashboard button) **and Schedule, daily 7:05 AM CT**.
- Connectors: Asana, Dropbox, **Google Drive**, Microsoft 365, Zapier. Drive matters — comparisons
  are filed in "TBG Carrier Comparisons".
- Environment: Default, with `proposal-fgqm.onrender.com` on the allowed-domains list and a
  network secret supplying `X-TBG-Secret` for that host.

## One prompt, two modes

The RUN SCOPE block at the top decides by payload:

- **Client named in the payload** → that client only, in whichever pipeline it belongs to. Bypasses
  the DEDUPE CHECK V2 five-day cooldown (the button is pressed because something arrived today).
  Other protections still apply: no second copy of a current analysis, never re-flag a client under
  CLIENT RESOLUTIONS. Skips the combined exception email; posts the Asana comment instead.
- **Empty payload** → the full daily sweep across both pipelines, every cooldown in force,
  including the exception email.

The Zap's filter guarantees the dashboard never sends an empty payload, so the two modes can't be
confused.

## The Zap — "TBG — Run Analyze Quotes now"

1. **Catch Hook**: `https://hooks.zapier.com/hooks/catch/5928257/41u4fte/`
2. **Filter by Zapier**: one rule only — `Querystring Group` → **(Text) Exists**. A second
   "does not contain" rule with an empty value blocks everything; that mistake cost a test cycle.
3. **POST** to the fire URL, `text` = `Run for this client only: <group>`, with this routine's own
   token in `Authorization: Bearer` (the Send for Quotes token does not work here), plus
   `anthropic-beta: experimental-cc-routine-2026-04-01` and `anthropic-version: 2023-06-01`.

## Email format

Step 9 now carries a locked output format, approved from the Oct 11 report: title line, an
"Automated daily check" lead with the day's headline in bold, navy `#1F3864` headings, NEW BUSINESS
(HOT LEADS) before RENEWALS, a three-column Client / Still outstanding / Note table for waiting
clients, bullets for the other buckets, renewal dates in parentheses. The instructions say not to
redesign it — consistency between runs beats improvement.

## Proven runs

- **Intocast (Oct 11, scoped):** looked only at Intocast and correctly declined to rebuild — client
  staying with UHC Level Funded, 9/28 draft newer than every quote file.
- **Oct 12 (scheduled sweep):** built the GunnCo Pump & Control comparison, **saved the .docx into
  Dropbox itself** via `/save-file`, and **published the selector page live** via `/push-selector`.
  Both manual steps are now gone. Long runs are normal: the orchestrator fans status checks out to
  background agents and heartbeats while a draft builds, which looks like a loop but isn't.

## Cowork tasks

Paused Oct 12 (not deleted, so history and settings survive):

- `hot-leads-and-renewals-quote-status` — replaced by this routine's 7:05 schedule
- `tbg-send-for-quotes-autorun` — replaced by the TBG Send for Quotes routine's weekday schedule

**Still running:** `tbg-send-quotes-emails`, weekdays 8:22 AM CT, which actually sends the carrier
emails from quotes@benefits.place. It has no routine counterpart — do not pause it.
