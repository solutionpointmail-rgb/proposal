# New Business Pipeline Check — Routine Instructions

> Public copy: two client email addresses are masked here. The full text lives in the AI AUTOMATION DASHBOARD project (claude/new-business-pipeline-check.md) and in the live routine.

**Owner:** Will Brown, The Benefits Group
**Purpose:** Each run reviews every active new-business group across four systems: Odoo, Dropbox, Asana, and Outlook. It then produces an exception report showing who has gone quiet, who is stuck, and why.
**Mode:** Read-only in Odoo, Dropbox client folders, Asana, and Outlook mail. Never create, move, rename, complete, or delete anything there. The only things this routine writes are the report itself (filed in the Pipeline Reports folder, Section 6B) and one report email to Will, Alex, and Lindsey (Section 6C).
**Calibrated:** 10/15/2026, against live data. Delivery (PDF, filing, email, Action Center button) added 10/15/2026.

---

## RUN SCOPE — READ FIRST

This routine runs two ways. Both do the full check across every in-scope group; there is no single-group mode.
- **Scheduled:** 7:45 AM Central, weekdays. "Requested" in the run notes and the email is "scheduled 7:45 AM run".
- **On demand:** the "Run now" button on the TBG Action Center (Zapier → this routine's API trigger). The routine-fire-payload block then says it came from the Action Center. "Requested" is "on demand from the Action Center".
If a payload names a group, still run the whole check.

---

## 0. Configuration (edit here, not in the steps)

| Setting | Value |
|---|---|
| Odoo pipeline stages in scope | `QUALIFIED - WAITING ON INFO` (id 2), `QUOTING` (id 9), `QUOTED/PRESENTED` (id 3), plus any stage named `DECIDING` if one is added later |
| Odoo stages excluded | `NEW`, `WON`, `OPPORTUNITY LOST`, and every `RENEWAL*` stage (renewals come in phase 2) |
| Odoo record type | `type == "opportunity"` only. **Ignore all `type == "lead"` records**, including AI voice-agent call intakes. |
| Quiet threshold | **8 days.** Flag a group when its last client email is 8 or more days ago, counting both inbound and outbound. |
| Lingering threshold | `QUOTED/PRESENTED` with no client email in 8+ days, or more than 14 days since `date_last_stage_update` |
| Carrier wait threshold | Flag a carrier still outstanding 7+ days after its Send for Quotes subtask was completed |
| Email lookback | 60 days |
| Dropbox Hot Leads root | `ns:11769612001//2.  HOT LEADS` (two spaces after "2.") |
| Dropbox Cold Leads root | `ns:11769612001//3.  WARM+COOL+COLD LEADS/4.  COLD LEADS` |
| Asana workspace | benefits.place |
| Team email domains | `benefits.place`, `solutionpointconsulting.com`. These are internal and never count as client contact. |
| Report title | `New Business Pipeline Check` |
| Report generator | `pipeline_report.py` + `pipeline_report_example.json` (schema and worked example). In the repository checkout (solutionpointmail-rgb/proposal); if missing, download both from `https://proposal-fgqm.onrender.com/tools/pipeline_report.py` and `https://proposal-fgqm.onrender.com/tools/pipeline_report_example.json`. |
| Report folder (Dropbox, as /save-file sees it) | `/Solutionpoint Groups/Pipeline Reports/` (shows in Dropbox as `/William Brown/Solutionpoint Groups/Pipeline Reports/`) |
| Report file names | `New Business Pipeline Check - YYYY-MM-DD.pdf` and `.html` (the run's date, Central). A second run the same day overwrites that day's files. |
| Report email | To will@benefits.place, alex@benefits.place, lindsey@benefits.place, with the PDF attached (Section 6C) |
| Report artifact (optional) | https://claude.ai/artifact/XLR9jw6RqJE9CzL9D7mMce. Publish the HTML here only if the `Artifact` tool exists in this run (Section 6D). Never create a new artifact. |

---

## 1. Pull the pipeline from Odoo

**Tool:** Zapier MCP → `execute_zapier_read_action`, `selected_api: OdooCLIAPI`, `action: lead`, `params: {}`. The connection is `will@benefits.place @ the-benefits-group.odoo.com`.

- The response is large, often 400k+ characters. When it truncates, read the saved copy and parse it with code rather than skimming it.
- **The feed returns only the 100 most recent records.** Older open opportunities can fall off it, which is why Step 1b exists.
- Filter on `type == "opportunity"`, `active == true`, and `stage_id[1]` in the in-scope list.
- Capture these fields for each group:
  - `id`, `name`, `partner_name`, `contact_name`, `email_from`, `email_domain_criterion`
  - `stage_id[1]`, `date_last_stage_update`, `date_deadline` (used as the effective date when filled)
  - `description` (strip the HTML to get the notes)
- Clean the display name: strip suffixes such as "- Need Census", "- Katie & Kerri", "- Laurie Guzman", "- AOR", and trailing dates like "01/01".
- De-duplicate by email domain and keep the record in the most advanced stage.
- For free-mail addresses (gmail, yahoo, etc.), match on the full address instead of the domain.

### 1b. Safety net: catch groups the Odoo feed missed
- List the direct child folders of Hot Leads (Step 2).
- List the **active (non-archived)** Asana projects whose name contains `Quoting` (Step 4).
- Any group in either list but missing from the in-scope Odoo set goes in the report section **"Active work not in Odoo pipeline."** Show the stage Odoo has for it, or "not found in feed."
- Skip these Asana projects: `The Benefits Group (Internal Benefits)` and any project with `Renewal` in the name.

---

## 2. Dropbox: confirm the Hot Leads folder

**Tools:** `mcp__Dropbox__list_folder` and `mcp__Dropbox__search`. Always use `ns:` paths or `id:` values, never display paths.

1. List the direct children of Hot Leads with `recursive=false`, paging through every cursor.
   - Ignore the utility folders: `1AAA - LEESA CALL LIST…`, `2AAA-Typeform Census Response…`, `3AAA - New Group Dropbox Folders Template`.
2. Match each Odoo group to a folder:
   - First by normalized name: lowercase, with punctuation, "Inc", "LLC", "PLLC", and "Co" stripped.
   - Then by distinctive word overlap. Known alias: Kirby Gate Living → `Kirby Gate LLC`.
3. If there is no folder in Hot Leads, search Dropbox for the name.
   - Found in Cold Leads → flag **STAGE MISMATCH** ("Odoo shows QUALIFIED but the folder is in Cold Leads").
   - Not found anywhere → flag **NO DROPBOX FOLDER**.

---

## 3. Dropbox: check what exists inside the group folder

The standard layout comes from the New Group Dropbox Folders Template:

```
<GROUP>/Quoting/1. Census
<GROUP>/Quoting/2. Quotes        ← carrier subfolders inside (e.g. "Great American - DTQ", "UHCLF - UW")
<GROUP>/Quoting/3. Proposal
<GROUP>/Quoting/4. Current Plan Info
```

List each subfolder recursively. Count files and record the newest `last_modified` date.

| Check | Rule |
|---|---|
| **Census on file** | `1. Census` has at least one `.xlsx`, `.xls`, `.csv`, or `.pdf`. A census file name containing "NEEDS INFO", "Missing", or "need" means the census is incomplete. |
| **Quotes saved** | `2. Quotes` holds at least one PDF or `.xlsx` inside carrier subfolders. Report the carrier subfolder names with their status suffix: DTQ, NOT COMP, UW, NEED IMQs, waiting, after APPS. An empty carrier subfolder means that quote has not been saved. |
| **Carrier analysis run** | `3. Proposal` contains `* Carrier Comparison*.docx/.pdf`, `*_Medical_Analysis*.docx/.pdf`, or `Proposal <Group>*.pdf` |
| **Selector page built** | `3. Proposal` contains a lowercase slug `.html` such as `<groupslug>-<mon><yyyy>[-vN].html` (example: `mccallwealthadvisors-nov2026.html`). Report the newest version. |
| **Misfiled check** | Flag any file in this group's folder whose name contains a different group's name. Seen 10/15: Ocean Health Beam quotes inside Anderson; `greenandlittle-renewal-oct2026.html` inside Arise. |

Info Sheet `.md`/`.docx` files, logos, and video files are normal and do not count as analysis.

---

## 4. Asana: quoting project status

**Find the project:** use `search_objects` with `resource_type: project`, `query: "Quoting"`, `count: 100`, `opt_fields: name,archived,created_at,modified_at`. Keep the non-archived projects named `<Group> Quoting MM/DD/YYYY`. The date in the name is the effective date.

**Pull every task with its subtasks:** one `get_tasks` call per project, run in parallel:
```
opt_fields: name,completed,completed_at,assignee.name,due_on,
            subtasks.name,subtasks.completed,subtasks.completed_at
limit: 100
```

**Pull comments in one batched call:** `get_task_stories` for every Send for Quotes task id plus every Save Census task id, with `resource_subtype: comment_added`, `sort_ascending: false`, `limit: 3`, `opt_fields: created_at,created_by.name,text`.

**Match tasks by name prefix** after trimming spaces and ignoring case. The team renames tasks to show status, for example "Send for Quotes - need census".

| Template task (prefix) | Meaning |
|---|---|
| `Save Census` | Census received and saved. A suffix such as "need census", "missing information", or "waiting on updated" means a census problem. |
| `Send for Quotes` | Its subtasks are the carriers the request went to. A complete subtask means sent; an open one means not sent yet. |
| `Save Quotes in DB` | **This is the "quotes received" log.** Each subtask is a carrier whose response came back: a quote, DTQ, NOT COMP, or NA. |
| `Save Quotes in Benefitter` | Secondary log. Use it only to break ties. |
| `Schedule Group Benefits Review` | Complete means the GBR meeting is scheduled. |

> ✅ Confirmed by Will on 10/15: the template has **no "Quotes Received" task.** Received quotes are logged as carrier subtasks under **Save Quotes in DB**. If a "Quotes Received" task is added to the template later, check it first and treat open subtasks as outstanding carriers.

**Derived statuses:**

- **Quotes not sent:** the Send for Quotes task is open and has open carrier subtasks. List the open carriers.
  - Ignore subtasks whose name starts with or contains "NA", "merged", or "DTQ" (pre-declined).
- **Waiting on carrier X:** a carrier subtask under Send for Quotes is complete, but no subtask under Save Quotes in DB mentions that carrier.
  - Match carriers by normalized keyword: UHCLF/UHC, Arlo, Simpara/Level, Angle, Edison, Great American/GA, Aetna/Cason/AFA, Cigna, One Health, Gravie, ABA, CBC Triad, Crumdale, Beam, Imagine360, Principal, Nationwide, Optimyl.
  - Report each outstanding carrier with days since its send subtask was completed.
- **Waiting on census:** true when any of these holds:
  - (a) a Send for Quotes or Save Census task or subtask name contains "census" together with need, missing, waiting, or updated, and the task is open
  - (b) one of the last 3 comments on those tasks mentions census and is newer than the newest census file in Dropbox
  - (c) `1. Census` is empty

  Quote the comment date and author, for example: "Waiting on census — Lindsey 10/10: 'census is missing first and last names.'"
- **Unanswered team question:** the newest comment on Send for Quotes is a question (ends with "?") from a teammate and has no later comment. Example from 10/15: ZLD, Lindsey 10/06, "should I resend these with the new census?"
- **Asana vs. Dropbox drift:** Dropbox holds carrier quote files for a carrier that has no Save Quotes in DB subtask. Flag it as "Quotes saved in Dropbox but not logged in Asana."
- **No quoting project:** no active quoting project matches the group.

---

## 5. Outlook: last client communication

**Tool:** `mcp__Microsoft_365__outlook_email_search`. This covers Will's mailbox only.

For each group, run these searches with `afterDateTime` set to 60 days ago (ISO 8601, `Z`):
1. **Inbound:** `sender: "<client domain>"`, or the full address for free-mail clients, with `limit: 10`.
2. **Outbound:** `recipient: "<each known client address>"`, `limit: 10`. This also catches teammates' emails when Will was cc'd.
3. **Fallback:** `query: "\"<distinctive company name>\""`. This finds contacts Odoo does not have. On 10/15 it found Max Echuz ([client email — in the live routine only]) for Kirby Gate and Ryan Haskins for Studio 1.

**Rules:**
- Count only messages **FROM a client address** or **SENT TO a client address.**
- Exclude carrier, vendor, and internal-only emails, plus Will's automation summaries: "TBG Send for Quotes", "Carrier Quote Status", "TBG Daily New-Business Automation", and "We've Received Your Intake Respones" when it is only the automated confirmation.
- Will's own sent items can show the sender as `/O=EXCHANGELABS/…/CN=…-WBROWN`. Treat that as Will. Also treat `will@benefits.place` and `quotes@benefits.place` as Will.
- Result sorting is unreliable with `recipient`/`query` searches, so always pick the maximum date yourself.
- `recipients` is null in search results. If you need to confirm who an email went to, open it with `read_resource`.
- **Search only Will's mailbox.** Alex always copies Will, so his client emails show up there.
- `quotes@benefits.place` and teammates' mailboxes are not shared with this account; tested 10/15, they return FORBIDDEN. Do not try them.
- Calls and meetings found in Fireflies may be shown as context, but they do not reset the quiet clock. Only emails do.

**Output format, required:**
> "Last communication was **SENT TO** Katie Dowdell (OakPoint) by Will on **10/15/26** — *RE: OakPoint – Benefit Detail Requests*"
> "Last communication was **FROM** Michelle Lubbert (ZLD) to Alex on **10/14/26** — *RE: We've Received Your Intake…*"

Show days since contact. Flag the group when that number is 8 or more.

---

## 6. Build and deliver the report

The look is owned by `pipeline_report.py`, so every run is identical in design. Your job is the
CONTENT: decide each group's severity, flags, and next step, and write it as JSON in the shape of
`pipeline_report_example.json`. Never hand-write the HTML or PDF, never restyle them, and never edit
the script.

**Environment (do not rediscover):**
- `pip install --break-system-packages reportlab` if `import reportlab` fails.
- The script reads its fonts from `./fonts`, or downloads them from the Render app; if neither works it
  falls back to built-in fonts and still builds. A font fallback is not a failure.
- Render cold-starts. If a call to proposal-fgqm.onrender.com times out or returns 502/503, wait 30
  seconds and retry once.
- Never base64 a file into a tool-call parameter. Files go local → `curl --data-binary` only.

### 6A. Write content.json

Follow `pipeline_report_example.json` exactly (its `_schema_notes` explain every field). The content
rules below decide what goes in it.

**Report layout** (the script renders this order; you supply the data):
1. **Header** (`run`): run timestamp in CT as `label` (e.g. "Thu 10/15/26 · 9:55 AM CT"), `date`
   (YYYY-MM-DD), `groups_in_scope`, `quiet_days` (8), `sources`, and `gaps`: one line per system that
   failed or was incomplete (an empty list when all four answered).
2. **Today's three** (`today`): the three most urgent groups, ranked by effective-date proximity × days
   quiet × blockers, each with a short `rank` label ("13 days quiet", "census blocking") and a 1–2
   sentence `reason`.
3. **Effective-date callout** (`callout`): groups effective within the next 30 days, as `lead` + `text`.
   Use `null` when there are none.
4. **Severity tallies**: computed by the script from each group's `sev`.
5. **Exception entries** (`groups`), each with: `name`, Odoo `stage`, `effective`, `sev`, `status`
   (the tier in words, e.g. "Waiting on carriers"), `quiet` (whole days; `null` if no client email in
   60 days), `last` (the last communication: `dir` SENT TO or FROM, `who`, `team`, `date` MM/DD/YY,
   `subject`), labeled `flags` (Quotes / Outstanding / Not sent / Census / Analysis / Selector / Drift /
   Data / Open question / Context / Misfiled / Setup / Status / Sensitive / Ready), one `next` step, and
   its `grid` row. The script prints the required "Last communication was FROM/SENT TO … on MM/DD/YY ·
   subject" line from `last`.
6. **Full status grid**: built from each group's `grid` (Section B).
7. **Active work not in the Odoo pipeline** (`outside`, Section C).
8. **Run notes** (`notes`, Section D).

Map the severity tiers in the list below onto `sev` like this:
- `crit` (Quiet & stuck): tiers 1–2
- `warn` (Blocked): tiers 3–5
- `note` (Analysis gap): tiers 6–7
- `info` (Data cleanup): tier 8
- `ok` (On track): no flags, or minor flags only

When a tier has no groups, `empty_tier_notes` may hold one line saying why (e.g. "Nothing in this tier
today. OakPoint moved to Blocked: 13 carriers are still outstanding.").

#### Section A — Needs attention today (exceptions)
List each group once, sorted by severity and then by days since contact. Give each one a single-sentence diagnosis followed by its specific flags. Severity order:

1. **🔴 Gone quiet AND stuck:** 8+ days without contact, plus quotes not sent, census outstanding, or carriers outstanding
2. **🔴 Lingering in decision:** QUOTED/PRESENTED with 8+ days of silence. Name what was sent and when (selector page, comparison).
3. **🟠 Waiting on census:** quote the latest census comment and the census file status
4. **🟠 Waiting on carriers:** list each carrier with days outstanding
5. **🟠 Quotes not sent:** list the open carriers and the Send for Quotes due date
6. **🟡 Quotes in, no analysis:** quotes are saved but there is no Carrier Comparison or Medical Analysis
7. **🟡 Analysis done, no selector page**
8. **⚪ Setup and data gaps:** no Dropbox folder, folder in Cold Leads, no Asana project, Odoo stage mismatch, misfiled files, Asana/Dropbox drift, unanswered team questions, Odoo contact differs from the active email contact

Example line:
> **Beyond Expectations** — QUOTING · Eff 11/01 · *Quiet 9 days.* Last communication was SENT TO Karen Reid by Will on 10/06/26. 11 of 14 carriers not yet logged in Asana; quotes saved in Dropbox for Angle, Gravie, One Health. No carrier analysis yet. Census task still "waiting on updated/clarity."

#### Section B — Full status grid
One row per in-scope group, with these columns:
- Group
- Odoo stage
- Effective date
- Last contact (date · FROM/SENT TO · who)
- Days quiet
- Census ✓/✗
- Quotes sent (x/y)
- Quotes received (x/y)
- Outstanding carriers
- Analysis ✓/✗
- Selector ✓/✗ (+ file)
- Dropbox folder ✓/✗
- Asana project ✓/✗

#### Section C — Active work not in Odoo pipeline
List each group found in Hot Leads or active Asana quoting projects that is not in the in-scope Odoo set. Give its Odoo stage, or "not in feed."

#### Section D — Run notes
- Run timestamp in Central time
- Record counts per system
- Anything that failed or was truncated
- The "last visible communication" caveat
- Whether this run was scheduled or on demand from the Action Center

**Grid values:** census, analysis, selector, folder, and asana use `y`, `n`, or a short amber word
(`partial`, `stale`, `cold`, `archived`); add a note after a colon when useful (`y:nov2026`). Sent,
received, and outstanding are short text (`6/6`, `2/14`, `12`, `—`).

**Markup:** text fields may use `**bold**`, `*italic*`, and backticks for file names. Nothing else. Spell "Benefits" correctly throughout, and never write "Solutionpoint Consulting" in the report.

### 6B. Build, check, and file

1. Build: `python3 pipeline_report.py content.json "New Business Pipeline Check - YYYY-MM-DD"`
   This writes the `.pdf`, `.html`, and `-email.html` side by side and prints a JSON summary.
2. CHECK IT before filing. Render the PDF pages (`pdftoppm -r 60 -png`) and look at every page:
   nothing overflows or overlaps, no section heading sits alone at the bottom of a page, the grid page
   is complete, and the tally counts match the groups. Run `pdftotext` on the PDF and confirm no SSN,
   tax ID, date of birth, or member ID appears anywhere (look for 9-digit runs and the patterns
   NN-NNNNNNN and NNN-NN-NNNN). Fix content.json and rebuild if anything is wrong.
3. File the PDF and the HTML (not the -email.html) with Render's /save-file:

       curl -sS --max-time 120 -X POST https://proposal-fgqm.onrender.com/save-file \
         -H "X-Dropbox-Path: /Solutionpoint Groups/Pipeline Reports/New Business Pipeline Check - YYYY-MM-DD.pdf" \
         --data-binary @"New Business Pipeline Check - YYYY-MM-DD.pdf"

   (the same for the .html). No auth header: the environment's network secret adds it. A JSON response
   with "status":"success" means it is filed; keep the PDF's `link` (a Dropbox shared link) for the
   email. Anything else, including 401, is a failed save: say so in the email and carry on.
4. The Action Center's "Open latest report" link reads the newest report in that folder by itself, so
   filing is all it needs.

### 6C. Email the report — every run, no exceptions

Send ONE email through the Zapier Microsoft Outlook connector (`execute_zapier_write_action`,
selected_api `MicrosoftOutlookCLIAPI`, action `send_email`) from Will's normal Outlook connection, NOT
quotes@benefits.place (that account is for carrier email only):

    recipients: ["will@benefits.place", "alex@benefits.place", "lindsey@benefits.place"]
    subject:    "New Business Pipeline Check — <Mon DD> — <N> need attention"
                (N = groups not On track; write "all on track" when N is 0, and "Problem" when two or
                more systems failed)
    bodyFormat: "HTML"
    body:       the contents of "New Business Pipeline Check - YYYY-MM-DD-email.html" exactly as
                built, followed by one line: "Requested: <scheduled 7:45 AM run | on demand from the
                Action Center>. Filed to Dropbox: Pipeline Reports/New Business Pipeline Check -
                YYYY-MM-DD.pdf" (or "Dropbox filing failed: <reason>").
    file:       [the PDF's shared link from the /save-file response, with "dl=0" changed to "dl=1"
                (or "?dl=1" appended)]

After sending, confirm the tool result lists the PDF as an attachment. If the save failed, or the
result shows no attachment, the email still goes out with the HTML body plus the line "The PDF could
not be attached this run; open the latest report from the Action Center." Never say the PDF is
attached unless the result shows it.

The email goes only to those three addresses. Never send it, or anything else, to a client or carrier.

### 6D. Optional: refresh the artifact

Only if an `Artifact` tool exists in this run: read the artifact in Section 0 first (action read), then
publish the new `.html` to that same `url`. If the tool is not available, skip this step without
comment; the PDF, the Dropbox copy, and the Action Center link are the record.

### 6E. Notification (3–6 lines)

Finish with a PushNotification (wrap it in <routine_summary> tags; the first sentence is the headline):
the number of groups reviewed and the counts by severity, the top 3 groups that need action today with
a one-line reason each, and whether the email went out.

---

## 7. Guardrails
- **Read-only** in Odoo, Asana, Outlook mail, and every client folder in Dropbox. The only writes are
  the two report files in the Pipeline Reports folder (Section 6B) and the one report email to Will,
  Alex, and Lindsey (Section 6C). Never email a client or carrier, edit Asana, move Dropbox files, or
  change Odoo during this routine.
- **Never reproduce sensitive identifiers** in the report: SSNs, tax IDs, DOBs, or member IDs found in comments or files. If you see one in an Asana comment, add a ⚪ flag ("sensitive identifier in an Asana comment — remove") without repeating the value.
- When a match between systems is uncertain, list it under ⚪ as "Possible match — confirm" rather than guessing.
- If a system fails (auth error or timeout), finish the report with the others and state the gap at the top.
- Do not re-flag groups Will has told you to stop tracking. Keep a "Snoozed" list here:
  - *(none yet)*

---

## 8. Known data notes (as of 10/15/2026)
- Odoo has duplicate opportunities and leads for Funtown Splashtown (4), Johnson McGinnis (2), RM Consulting / Ryan Myers (2), and Edit Rentals (2).
- Copper Partners II and Ballard Products are QUALIFIED in Odoo, but their folders are in Cold Leads. Copper's Asana project was archived 10/12.
- Funtown Splashtown and Studio 1 Catering have no Dropbox folder and no Asana quoting project.
- The Kirby Gate Odoo contact is [client email — in the live routine only], but the active contact is Max Echuz ([client email — in the live routine only]).
- Phase 2: add the RENEWAL, RENEWAL QUOTED/DECIDING stages and the Renewals folder tree.
