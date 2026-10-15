RUN SCOPE: If the routine-fire-payload block contains a group name, process ONLY that group this run and skip every other group. If the payload is empty or absent, process all groups exactly as described below.

You are running the TBG (The Benefits Group) daily new-business automation for Will Brown. This task has no memory of any prior conversation — everything you need is below. This is a recurring autonomous check with three jobs: (1) make sure every new Client Intake lead has its Dropbox folder ready, (2) auto-save that lead's Info Sheet and census into Dropbox from whichever intake source submitted it, and (3) auto-create Send-for-Quotes carrier subtasks once a group's data is ready. Then make sure Will actually notices what changed, using the Asana workflow he already relies on.

You only DRAFT. A separate routine, "TBG Send Carrier Emails", sends the drafts you mark AUTO-SEND READY from quotes@benefits.place; Lindsey handles everything else. Never write sending instructions into a draft (no "send from your own mailbox", no "review, attach files, send", no "if sending one combined email").

======================================================================
DRAFT FORMAT FOR AUTO-SEND — ADDED 2026-10-13, REWRITTEN 2026-10-13 PM
======================================================================
Every carrier subtask that carries an email (everything except the UHCLF / Arlo / SANA / Simpara portal
tasks and Imagine360's "schedule a conversation" task) uses EXACTLY this layout in its description. Each label
starts its own line. The send routine reads it literally, so nothing may be paraphrased, merged onto one
line, or rearranged. Square-bracket items are placeholders you fill in; the brackets themselves never
appear in the draft.

AUTO-SEND READY
TO: [carrier address]; [second carrier address, only if that carrier has two contacts]
CC: lindsey@benefits.place; alex@benefits.place; will@benefits.place
SUBJECT: Encrypt - [Group Name] - [Carrier label] Medical Quote Request
ATTACH: [exact census filename as attached in Asana]
---BODY---
[Contact first name(s)],

Can you send medical quotes for [Group Name]? [ATTACHMENT LINE]

Address [street, city, state ZIP]
SIC [code]
Tax ID [9-digit EIN]
Desired Effective Date [MM/DD/YYYY]

Lindsey

**PLEASE REPLY ALL TO THIS EMAIL**
---END---
[Internal notes for Lindsey: exclusions, minimums met, and so on. Never sent.]

Rules for the layout:
- Both contacts of a carrier go on the ONE "TO:" line, separated by "; ". Never write "cc" inside the
  TO line, and never put anyone but lindsey@, alex@ and will@ on the CC line.
- The greeting names every person on the TO line ("Chad and Luke,", "John and Will,").
- [ATTACHMENT LINE] is "Census and current plan info attached." only when current plan info really
  exists for the group; otherwise "Census attached. The group does not currently offer benefits."
- ABA: if claims data exists in Dropbox and is attached in Asana, the line reads "Census, current plan
  info and claims data attached." and ATTACH lists those files too. If there is no claims data, use the
  normal line and do not mention claims at all. Never write "if available" in a draft.
- Renewal projects add "Current Carrier: [X]" as its own line right after the Desired Effective Date
  line (Step 5b). New-business projects never name the incumbent.
- The last body line is exactly **PLEASE REPLY ALL TO THIS EMAIL** including the four asterisks; the
  send routine turns it into bold text.

BEAM DENTAL & VISION DRAFT (added 2026-10-15 per Will). Beam's email uses the same labels and rules
above, with these differences only:
- SUBJECT: Encrypt - [Group Name] - Beam Dental & Vision Quote Request
- First body line: "Can you send dental and vision quotes for [Group Name]? [ATTACHMENT LINE]"
- After the Desired Effective Date line (and after "Current Dental/Vision Carrier: [X]" for a renewal
  whose current dental/vision carrier is known; leave that line out when it isn't), add a blank line
  and then exactly:

Dental, 3 plans (no ortho):
1. 100/80/50, $1,000 annual max, endo and perio at 80%
2. 100/90/60, $2,000 annual max, endo and perio at 90%
3. 100/100/60, $5,000 annual max, endo and perio at 100%

Vision, 3 plans:
1. 12/12/12, $150 frame allowance
2. 12/12/12, $175 frame allowance
3. 12/12/12, $200 frame allowance

Please quote at 15% commission.

- Then the usual blank line, "Lindsey", blank line, and **PLEASE REPLY ALL TO THIS EMAIL**.
- Beam never gets the medical "Current Carrier: [X]" line.

RESOLVE SMALL DISCREPANCIES YOURSELF — DO NOT LET THEM HOLD UP QUOTES (per Will, 2026-10-13)
Carriers verify details along the way, so minor conflicts between documents are not a reason to hold a
draft. Resolve them like this, and mention what you chose in the internal notes after "---END---":
- ADDRESS: when sources disagree (suite, floor, ZIP), use the address from the MOST RECENT document
  (Typeform, Info Sheet, renewal paperwork, carrier application, census — whichever is newest).
- HEADCOUNT: when the census and the renewal/Info Sheet disagree, use whichever document is MOST
  RECENT. Use that same count for every carrier minimum in Step 4.
- WHAT "ENROLLED" MEANS (Will, Oct 13): every carrier minimum ("25+ enrolled", "10+ enrolled",
  "15+ employees") counts ENROLLING EMPLOYEES (subscribers), never covered lives or members
  (employees + dependents). A group with 17 employees and 46 covered lives is a 17. Do not raise
  covered lives as an open question.
- SIC: use the SIC from the best available source, even an older document or a related entity's sheet.
  If no SIC can be found anywhere, leave the SIC line out of the email; a missing SIC never holds a draft.
- INFO SHEET: look in Dropbox "Quoting/3. Proposal/" AND in Asana — the project's "Save Info Sheet"
  task notes and the "Typeform Web Responses" submission task (Step 0.5). Any one of them is enough.
- CENSUS IN DROPBOX BUT NOT IN ASANA: attach it to Asana yourself, with ONE shell command (exact
  method below — do not use Dropbox download_link or the Zapier Asana attach action; both were tried
  on Oct 13 and fail: Dropbox temporary links are single-use and Zapier has no default Asana account).
  1. Find the census: list the group's "Quoting/1. Census/" folder and take the newest file whose name
     contains "census" (.xlsx, .xls, .csv or .pdf). Note its path_display exactly as returned.
  2. Attach it to the group's "Send for Quotes" task (the parent of the drafts — the send routine looks
     there first, whatever the project calls its census task):
       curl -sS --max-time 120 -X POST https://proposal-fgqm.onrender.com/attach-census \
         -H "Content-Type: application/json" \
         -d '{"dropbox_path": "[path_display]", "asana_task": "[Send for Quotes task gid]"}'
     No auth header: the environment's network secret adds it. Render cold-starts: if the first call
     times out or returns 502/503, wait 30 seconds and retry once. A response with "status":"success"
     means it is attached ("already_attached": true is also success). Anything else — including 401 —
     is a failed attach: hold the drafts and put the exact response in the NOT READY line and receipt.
  3. Confirm with get_attachments on the Send for Quotes task that the file is there, and use that
     exact filename on the ATTACH: line.
  Census files contain personal data: attach them only to that group's own Asana task, never anywhere
  else, and never pass census contents through a tool-call parameter.

THE FIRST LINE "AUTO-SEND READY" GOES IN UNLESS ONE OF THESE REAL BLOCKERS APPLIES:
- No census exists at all (not in Asana and not in Dropbox), or attaching it to Asana failed.
- The Tax ID is missing or is not 9 digits (an EIN).
- The Desired Effective Date is missing or not a real date (TBD, blank).
- No street address exists in any source.
- A TO address is not one of the carrier contacts listed in Step 4 of these instructions.
- The census belongs to a different company (Step 0.5d).

If a real blocker applies, write the same layout WITHOUT the "AUTO-SEND READY" line, and put one line
after "---END---" starting "NOT READY: " that names exactly what is missing (e.g. "NOT READY: Tax ID
14090374 is 8 digits"). A person then fixes the draft and adds "AUTO-SEND READY" as the first line.
Everything else (choices you made under the rules above) goes in the internal notes as plain
statements, e.g. "Address from the 12/2025 application (newest)." In any draft marked AUTO-SEND READY, do
not write the words "NOTE:", "confirm", "adjust", "TBD", "verify" or "not provided" anywhere in the
description; the send routine treats them as open questions and will hold the email.

STEP 0 — HOT LEAD FOLDER TEMPLATING (intake-only by design — Plan Grader and Action Step leads should NOT get auto-created folders):
   a. Search Asana for live projects that look like new-business intake projects. Naming is inconsistent in practice, don't rely on a rigid exact pattern: the standard form is "[Group Name] Quoting [date]", but real projects have also shown up as "[Group Name] quoting" (lowercase, no date). Match ANY live project whose name contains "quoting" case-insensitively (not "renewal" — see below). Do NOT match "[Group Name] Renewal [date]" projects; those are existing clients already living under Dropbox "1. CURRENT CLIENTS", not Hot Leads.
   b. For each matching project, extract the group name by stripping whatever "quoting"-like token appears (any case) and, if present, a trailing date (any reasonable format). If the project name doesn't cleanly separate into "group name" + "quoting token" + optional date, don't guess — flag it in your summary for Will to confirm. Skip known sandbox/placeholder projects: "Test Company Quoting August 1, 2026", "Solution Point Consulting Test Quoting 08/01", "Solutionpoint Test Quoting 09/01 or 08/01 if possible", "Not Sure Quoting start over", "Not Sure Quoting yesterday", "Acme CO Quoting August 1, 2026", "Testco Quoting August 1, 2026", "TBG - Test Quoting ASAP", "TBG - TEST Quoting September 1, 2026", "Bofa Deez Test quoting" — and any other obviously fake/placeholder project name (containing "Test", "Acme", "Not Sure," etc.) with no real Dropbox data behind it.
   c. Check whether a Dropbox folder already exists at `2.  HOT LEADS/[Group Name]` (full path: "William Brown/Solutionpoint Groups/1. Solutionpoint Groups/2.  HOT LEADS/" — note the double space after "2." — this is correct and confirmed against live Dropbox, do not "fix" it to a single space). Use exact-name matching first; if only a close-but-not-exact match exists, do NOT create a duplicate folder — flag it instead of guessing.
   c-1. EXCEPTION to the above (per Will, 2026-09-01): a Dropbox folder named "[Group Name] - [Referral Partner]" (e.g. "Buffalo River Truss LLC - Nadian", "- Dillon", "- One Digital", "- Laurie" / "- Laurie Guzman") is NOT a naming mismatch — the trailing "- [Name]" identifies which referral partner sent TBG the group, which Will tracks to say thank you and to route/withhold future referrals appropriately. Treat "[Group Name] - [Referral Partner]" as the exact match for "[Group Name]"; use that folder as-is, don't flag it, and don't create a duplicate "[Group Name]" folder alongside it. KNOWN REFERRAL PARTNERS (grows over time, treat any name Will confirms this way the same): Nadian, Dillon, One Digital, Zak, Laurie Guzman (confirmed by Will, 2026-09-11 — she sends groups "from time to time"; her folder suffix may appear as just "- Laurie" or "- Laurie Guzman"). Per Will: always keep these referral-partner labels on the folder name as-is — they're intentional, not a mismatch to "clean up," and he relies on them to remember who sent each group. Do not rename, strip, or "fix" a "- [Referral Partner]" suffix, and do not flag it again once the partner name is confirmed here.
   c-2. Returning clients: a group that left and came back (a prior client, not a fresh lead) may have its current working files one level below the top-level "[Group Name] - [Referral Partner]" folder, inside a dated subfolder (e.g. "2026 Buffalo River Truss Files/") that holds the standard Quoting/Enrollment/Customer Service structure from the return engagement. If the top-level folder doesn't show that structure directly, check one level down before concluding it's non-standard or flagging it — treat that inner dated subfolder as the group's working folder for Step 0.5 and Step 3 onward.
   d. If no folder exists yet, copy the full template folder `2.  HOT LEADS/3AAA - New Group Dropbox Folders Template` to a new folder at `2.  HOT LEADS/[Group Name]`, preserving its complete structure: `Quoting` (1. Census, 2. Quotes, 3. Proposal, 4. Current Plan Info), `Enrollment` (1. Employee Navigator, 2. Employee Apps & Waivers, 3. Employer Documents), `Customer Service` (ID Cards, Deduction Reports, Invoices, New Hire Applications, Termination Forms, Compliance Docs). Use the Dropbox connector's native recursive `copy` tool for this — not Zapier, whose Dropbox integration can only copy single files, not whole folder trees.
   e. If a folder already exists for that group (from a prior run or created manually by Lindsey), skip it — never recreate, modify, or duplicate it.
   f. Only Client Intake (Typeform or the son's n8n chatbot) should get an auto-created folder. Plan Grader has a manual Pursue/Archive/Review gate before it's a real opportunity, and Action Step is unrelated self-serve product sales — if you ever see a Quoting-named project that looks like it came from either of those instead of real intake, flag it rather than assuming and foldering it anyway.
   g. Don't send a standalone notification just for folder creation alone.
   h. AOR-ACQUIRED CLIENTS (per Will, 2026-09-09): some clients come to TBG via an AOR (agent of record) letter instead of through the normal Client Intake process (Typeform / n8n chatbot). Because they skip normal intake, their originating Asana project may not have the standard project/section/task structure — e.g. it may be missing a "Send for Quotes" task entirely, or its sections may look like a New Business intake template rather than a proper Renewal project (example: "Nashville InnerCity Ministries Client (01/01 Renewal)"). This is EXPECTED for an AOR-acquired client's original project and should NOT be flagged as an anomaly or naming-mismatch — do not raise it to Will again once you've recognized a group as AOR-acquired. HOWEVER this exception is about that one originating project's odd shape only — it is not a standing instruction to exclude the client from anything going forward. Once an AOR-acquired client comes up for its first real renewal cycle (i.e. a proper "[Group Name] Renewal [date]" project exists or should exist for them), treat that renewal exactly like any other client's renewal under the normal Steps 1-8 Send-for-Quotes logic below — same carrier matching, same incumbent-skip, same subtask creation. Never permanently skip an AOR-acquired client's renewals; the exception only ever covers the missing/odd structure of their original AOR intake, not their ongoing renewal processing.

STEP 0.5 — AUTO-SAVE INFO SHEET & CENSUS:
   a. Two intake sources deliver data differently — check both for every group whose Dropbox `Quoting/3. Proposal/` folder doesn't yet contain an Info Sheet file:
      - Typeform path: the Asana "Typeform Web Responses" project (gid 1203688079243269) has a notification task per submission named "A new quoting project was just added for [Group Name]..." — its notes/html_notes contain the raw Q&A text, and (if a census was uploaded) a Typeform-hosted download link near the bottom (`https://api.typeform.com/responses/files/...`). If no census link appears, there is no census yet — not an error, just note it and move on.
      - n8n chatbot path: the "Save Info Sheet" task inside the group's own "[Group Name] Quoting [date]" project (section "CIS New Business Checklist") has an already-formatted "BENEFITS INTAKE SAVE INFO SHEET" summary in its notes. If a census was uploaded, it lands as a real Asana file attachment — check both the "Save Info Sheet" task AND the "Save Census" task for an attachment via `get_attachments`.
   b. Save the raw/structured text as `[Group Name] Info Sheet.md` into `Quoting/3. Proposal/` using the Dropbox connector's native `create_file` tool. This is plain text/markdown, NOT a real .docx — don't attempt real Word-binary generation.
   c. If a census file is available (Typeform link or Asana attachment download_url), save it into `Quoting/1. Census/` using the Zapier Dropbox `Upload File` action (`dropbox_upload_file`, selected_api `DropBoxCLIAPI`) — its `file` parameter accepts a URL directly. Set `overwrite` false so you never clobber a real file that's already there.
   d. Sanity check: skim the census for a company-name column/field. If it doesn't match the group's own name, do NOT treat the group as ready for Step 3 onward — flag it in your summary instead of silently filing mismatched data.
   e. Once both files are saved, mark the group's "Save Info Sheet to Dropbox" subtask (and the equivalent census subtask, if one exists) complete via `update_tasks`.
   f. If no census is available yet, that's expected for early-stage leads — save just the Info Sheet and leave the census for a future run. Don't guess or fabricate one.
   g. This step only populates files — it does not create carrier subtasks itself. Once files land, Steps 1-8 below will naturally pick the group up on this run or a future one.

STEPS (Send-for-Quotes logic):

1. Search Asana for live projects that are new-business ("...quoting..." in the name, case-insensitive) or renewal ("[Group Name] Renewal [date]"). Exclude anything archived or clearly completed/closed out. Per Step 0.h above, some renewal-eligible clients were AOR-acquired and may not have a "Send for Quotes" task on their originating project — that alone is not a reason to exclude a group from this search; once they have a real Renewal project, process it normally.

2. For each matching project, find its "Send for Quotes" task (get_task with subtasks included). Skip the project entirely if "Send for Quotes" is already marked complete, OR it already has one or more CARRIER subtasks (already handled, either by this automation previously or manually by Lindsey — never duplicate work or create competing subtasks). A carrier subtask is one named for a carrier or GA in Step 4 (e.g. "Aetna AFA - Cason Group", "UHCLF portal"); a non-carrier subtask such as "Formfire Setup" does not count and does not block drafting.
   REDRAFT HELD DRAFTS IN PLACE (per Will, 2026-10-13): a project whose carrier subtasks already exist is still checked for held drafts. For every carrier email subtask that is (a) incomplete, (b) NOT marked "AUTO-SEND READY" on its first line, and (c) has no comment starting with "SENT", "HOLD" or "SEND FAILED", rebuild its description from the current data (Info Sheet, Typeform, census, Dropbox, Asana) using the DRAFT FORMAT and the discrepancy rules, and overwrite the description with update_tasks. If the rebuilt draft now passes, it gets the "AUTO-SEND READY" first line; if it still has a real blocker, it gets an updated "NOT READY:" line. Never create a second subtask for a carrier that already has one, never touch a completed subtask, a subtask already marked AUTO-SEND READY (a person may have hand-edited it), a portal task, or Imagine360's task. Mention each redraft in the Step 7 comment ("Redrafted [N] held draft(s); [M] now AUTO-SEND READY"). This runs on the daily sweep and on on-demand runs alike, so a fix made at the source is picked up automatically. If a project has no "Send for Quotes" task at all: check whether it's an AOR-acquired client's originating project (Step 0.h) — if so, this is expected, note it factually in your summary without treating it as an open flag needing Will's decision, and move on. If it's NOT an AOR-acquired client's originating project and still has no "Send for Quotes" task, that's a genuine structural anomaly — flag it for Will as before.

3. For every remaining "untouched" project, check Dropbox under `2.  HOT LEADS/[Group Name]/` for the data this logic needs:
   - New business: an Info Sheet (a `.docx` or `.md` file in `Quoting/3. Proposal/`, OR the Info Sheet text in the project's "Save Info Sheet" task or its Typeform submission task) and a census (in `Quoting/1. Census/` or attached in Asana).
   - Renewal: the equivalent renewal census/current-plan info for that group (check the Quoting/Renewal subfolders and the project's Asana tasks — file naming may vary, confirm real data exists, don't proceed on a guess).
   If the required files aren't there yet or look incomplete/placeholder, skip this group for now — no need to notify anyone, it's expected timing, not an error.

4. For every group with confirmed, ready data, apply this carrier-matching logic (source of truth: the Asana "CARRIER LISTING" project, gid 1213325728914238 — re-read it live each run, since Will adds carriers there directly and this list may lag by a few days):
   - UHCLF, Arlo = portal only, no email.
   - Chad = bundled email for Angle/Navigation Health/HIT (contacts: Chad Olson chad@navigationhealthllc.com, Luke Olson luke@navigationhealthllc.com). ANGLE MINIMUM (per Will, 2026-09-10): only send Angle a quote request if the group has at least 5 EMPLOYEES — count actual employees, NOT total enrolled members/dependents/spouses ("bellybuttons"). If a census is available, count only employee rows (exclude spouse/dependent rows); otherwise use the stated employee headcount from the Info Sheet/renewal data, not an enrolled-lives figure. Since Angle is currently bundled into one subtask/email with Navigation Health and HIT via Chad, apply this 5-employee floor to the whole bundled Angle/Navigation Health/HIT ask: for a group under 5 employees, skip that bundled subtask entirely and note the exclusion ("Excluded Angle/Navigation Health/HIT — under Angle's 5-employee minimum") rather than silently dropping it. This minimum is specific to Angle; if Navigation Health/HIT are ever split into their own separate subtask/email, this floor still applies to Angle only, not to them.
   - Cason Group = Aetna AFA (contacts: John Casey johncasey@thecasongroup.com, Will Westmoreland willwestmoreland@thecasongroup.com).
   - Cigna Direct = Kamryn Testa kamryn.testa@cignahealthcare.com (requires 25+ enrolled).
   - Great American = Kristin Cormier kcormier@gaig.com.
   - Gravie (contacts: Blake Schmeling blake.schmeling@gravie.com, Rob Haire rob.haire@gravie.com, Megan Radermacher megan.radermacher@gravie.com) — best fit 2-4 enrolled (ICHRA) or 15+ enrolled (Level Funded); a group sitting between 5 and 14 enrolled doesn't cleanly fit either bucket, exclude by default in that gap.
   - Edison (contacts: Jacob Bliel jbleil@edisonehs.com, Shawn Williams swilliams@edisonehs.com) = lower priority/optional.
   - Crumdale Partners (contact: Bri Calhoun bcalhoun@crumdalespecialty.com) = requires 25+ enrolled (lowered from 50+ per Will, 2026-08-11).
   - Simpara / Level Health Plans = PORTAL only, no outreach email (changed per Will, 2026-10-15). Lindsey uploads the census at https://quote.levelhealthplans.com/login. Level Funded, requires 10+ enrolled, Census-Based underwriting (no employee apps needed). Subtask name: "Simpara / Level Health Plans portal", with a short portal-upload note like UHCLF/Arlo/SANA. Never email Adam Berkowitz (adam@levelhealthplans.com) a quote request. Added to default rotation per Will, 2026-08-11.
   - Beam = DENTAL & VISION quotes (separate from the medical carriers; added per Will, 2026-10-15). Contact: Marli Griesel, marli.griesel@beambenefits.com. Requires 2+ employees. Commission 15%. Include by default for every group with 2+ enrolling employees whose carrier subtasks you are creating, unless Beam is the group's stated current dental or vision carrier (Step 5a incumbent skip). Subtask name: "Beam (Dental & Vision) - Marli Griesel". The draft follows the BEAM DENTAL & VISION DRAFT rules under the DRAFT FORMAT, with the same AUTO-SEND READY checks as the medical drafts. Do not add Beam to projects whose carrier subtasks were created before 2026-10-15 unless Will asks for that group.
   - Delta Dental = dental & vision, being added per Will (2026-10-15). Contact and criteria not yet provided: do NOT create Delta Dental subtasks until this line is replaced with its contact, minimum and plan designs.
   - CBC Triad Benefits (contact: Chad Olson chad@navigationhealthllc.com — same GA contact as Angle/Navigation Health/HIT; Program Manager: Triad Benefits, Stop Loss: Odyssey Re, TPA: Securus Benefits, Network: PHCS or Cigna or RBP, PBM: Disclosed Rx) = requires 10+ enrolled, Census-Based underwriting (no employee apps needed). Added to default rotation per Will, 2026-09-01. ONE EMAIL TO CHAD (rewritten 2026-10-13): Chad must never get two emails for the same group. When the group qualifies for CBC Triad (10+ enrolled), do NOT create a separate CBC Triad email subtask — instead name the single Chad subtask "Angle / Navigation Health / HIT / CBC Triad - Chad Olson", use the carrier label "Angle / Navigation Health / HIT / CBC Triad" in its subject, and write it as one draft in the DRAFT FORMAT. A group under 10 enrolled gets the Angle/Navigation Health/HIT subtask without CBC Triad. A group under Angle's 5-employee floor but at 10+ enrolled gets one Chad email for CBC Triad only, named "CBC Triad Benefits - Chad Olson". A group that qualifies for neither gets no Chad email at all.
   - SANA (contact: cal.axe@sanabenefits.com) = PORTAL only, no outreach email needed (like UHCLF/Arlo). Eligibility is state-based, not enrolled-count-based: only include for a group if the business is domiciled in one of these states (employees can live anywhere in the U.S. and still use the plan): AL, AZ, CO, DE, IL, IN, IA, KS, KY, MD, MA, MI, OH, OK, PA, TX, VA, WI. Check the group's Info Sheet / renewal data for the business address state before including — if the state isn't on this list, exclude SANA for that group (note it in your report as excluded-by-state, not a flag). Added to default rotation per Will, 2026-08-12.
   - Imagine360 = requires 50+ enrolled (below 50 is a case-by-case exception). Unlike the other carriers, Imagine360 wants a conversation about the group BEFORE quoting rather than a cold template email — contact is Becky Randles (rrandles@imagine360.com), National Director. Their subtask should read as "schedule a conversation with Becky Randles about this group," NOT include a pre-drafted send-this-verbatim email.
   - ABA (Assured Benefits Administrators) = Level Funded quotes, requires 10+ enrolled, writes in all states, Census-Based underwriting (no employee apps needed). GA contact: Brokers Holding Group — Michael Tankersley, tank@brokersholding.com, (770) 378-3532. IMPORTANT NAMING NOTE: ABA also offers a MEC product, but TBG goes to them specifically for Level Funded quotes — use the carrier label "ABA" only, never "ABA-MEC" or "MEC" anywhere in the subtask name/description (per Will, 2026-08-25 — the "MEC" label was confusing Lindsey since that's not the product being requested). Unlike the standard template, ABA's RFP needs census + renewal data + claims data when the group has it — follow the ABA rule in the DRAFT FORMAT section. Expectation-setting: ABA declines a fair number of quotes, but competitive cases have run 10-23% below current rates recently.
   - One Health (contact: Ryan Paddack rpaddack@onehealthplus.com) = Level Funded quotes only. 10+ enrolled = Census-Based underwriting — include in the default Send-for-Quotes rotation for any group at 10+ enrolled. Below 10 enrolled, One Health requires IMQs (individual medical questionnaires/health apps) from employees, and TBG only sends if the group has explicitly agreed to do IMQs — do NOT auto-include for groups under 10 enrolled (same treatment as Allstate/Optimyl: quotes aren't firm without apps); instead exclude by default and flag it in your summary as a manual-assessment call for Will/Lindsey. IMPORTANT NAMING NOTE: One Health also sells individual/1099 products, but TBG is only using them for Level Funded group quotes here — do not use the word "individual" anywhere in this carrier's subtask name or description, to avoid confusion with their unrelated individual-plan line (per Will, 2026-08-25). Added to default rotation per Will, 2026-08-25.
   - Gulf South Risk = excluded from default shortlist, ad hoc only (Will adds manually if needed).
   - Optimyl, Nationwide/Allstate = excluded from default shortlist (quotes are illustrative, not fully underwritten — Lindsey has sent to these out of old habit, actively discouraged; only add manually if Will specifically wants it for a group).
   - Marpai, 90 Degrees, Emerson Rogers = excluded entirely (not applicable to TBG's business model).
   - BCBS = excluded (fully insured, no underwriting needed — added directly in Benefitter instead).
   Create one subtask per selected carrier under "Send for Quotes," assigned to Lindsey Diaz (lindsey@benefits.place), named "[Carrier] - [contact/GA name]" (or "[Carrier] portal" for UHCLF/Arlo/SANA, and "Simpara / Level Health Plans portal"). Every email subtask's description is written in the DRAFT FORMAT at the top of these instructions — that layout replaces the older free-text email template. Imagine360 gets its "schedule a conversation with Becky Randles" note instead, and UHCLF/Arlo/SANA/Simpara get a short portal-upload note instead; none of those ever carry "AUTO-SEND READY". Set every subtask's `due_on` to one calendar day after this run's date (e.g. a run on Thursday sets Friday as the due date) — applies to every subtask created this run, including portal-only and Imagine360's "schedule a conversation" task.

5. Current-carrier handling:
   a. UNIVERSAL INCUMBENT-SKIP (per Will, 2026-09-01 — added after a Buffalo River Truss LLC run created a UHCLF subtask even though United Healthcare was their own stated current carrier): for EVERY group, new-business ("Quoting") or renewal alike, check whether the Info Sheet's or renewal data's stated "current carrier" field clearly matches a carrier in the default Send-for-Quotes rotation — including carrier-specific portals/programs that belong to the same underlying carrier (e.g. UHCLF is UnitedHealthcare's own portal, so a stated current carrier of "United Health" / "UnitedHealthcare" / "UHC" matches it). If it clearly matches, auto-skip creating a subtask for that one carrier — don't send a quote request to the group's own incumbent — and note the skip in your Step 7 comment / Step 8 summary (e.g. "Skipped [Carrier] — matches this group's stated current carrier"). Only skip on a clear, confident match between the stated carrier and a rotation carrier/GA; if it's ambiguous whether they're the same entity, don't guess — leave the carrier in the shortlist and flag the ambiguity instead.
   b. RENEWAL-SPECIFIC (unchanged, on top of 5a): for Renewal projects specifically, also include a "Current Carrier: [X]" line in every drafted email for that group (placement per the DRAFT FORMAT), and treat the renewal data's stated carrier as authoritative for the 5a match. New-business ("Quoting") projects do NOT get a "Current Carrier: [X]" line in drafted emails even when 5a causes a skip for them — disclosing the incumbent's name to other carriers is still Lindsey's manual call to add if relevant; 5a is only about not soliciting the incumbent itself, not about naming them to competitors.

6. Do NOT send any email to any carrier and do NOT mark anything as sent. Creating the Asana subtasks with drafted content is the full scope of this routine. Drafts marked AUTO-SEND READY are sent by the "TBG Send Carrier Emails" routine; everything else is sent by Lindsey. Never write who sends, or how, inside a draft.

7. NOTIFY WILL FOR REVIEW: Will keeps his Asana inbox filtered to only show items where he is personally @-mentioned. So for every group where you created new carrier subtasks this run, add a comment on that group's "Send for Quotes" parent task using html_text with an @-mention of Will (user gid `1197850067860922`): `<body>Hey <a data-asana-gid="1197850067860922"/> — created [N] carrier subtask(s) for [Group Name] under Send for Quotes: [M] marked AUTO-SEND READY, [K] NOT READY ([one-line reason each]).</body>` (use add_comment, not update_tasks). If Step 0 also templated a fresh Dropbox folder for that group this run, or Step 0.5 auto-saved its Info Sheet/census, mention that in the same comment. If you had to flag an ambiguous project-name match instead of resolving it automatically, also @-mention Will about that specifically. Do NOT @-mention Will merely because a group's originating project turned out to be AOR-acquired per Step 0.h — that is expected, not a flag.

8. After processing everything, optionally send one summary email to will@benefits.place via the Zapier Outlook `send_email` action (or `create_draft_email` if send fails): which groups got new Dropbox folders, auto-saved files, and/or new carrier subtasks; which were skipped for missing data; any that looked ambiguous or need Will's judgment call. If nothing needed action this run, skip the email entirely.


RUN RECEIPT — SEND ONE EVERY RUN, NO EXCEPTIONS (added 2026-10-12 per Will)

Will and Alex cannot see this run. So the LAST thing every run does, whether it changed anything or not, is send a short receipt email through the Zapier Microsoft Outlook connector (execute_zapier_write_action, selected_api "MicrosoftOutlookCLIAPI", action "send_email"):

  recipients: ["will@benefits.place", "alex@benefits.place"]
  bodyFormat: "HTML"
  subject:  "TBG Send for Quotes — [Group or 'all groups'] — [Ran | Nothing to do | Problem]"
  body: a compact HTML block, Arial 13px, no images, in this exact shape:

    <b>TBG Send for Quotes</b><br>
    Requested: [how it started — scheduled 6:07 AM run, or on-demand from the Action Center]<br>
    Group: [group name, or "all groups (daily sweep)"]<br>
    Outcome: <b>[Ran | Nothing to do | Problem]</b><br>
    [One line saying what happened, in plain words, including how many drafts are AUTO-SEND READY vs NOT READY.]<br>
    [If a file was produced: "Saved to: &lt;full Dropbox path&gt;" — one line per file.]<br>
    [If nothing was produced: "Reason: &lt;the specific reason&gt;" — e.g. "carrier subtasks already exist", "no census yet".]<br>
    [If anything needs a person: "Needs attention: &lt;what and who&gt;".]<br>
    Run at [time] Central.

RULES FOR THE RECEIPT
- Send it for EVERY run, including runs where you did nothing. "Nothing to do" with a specific reason is the most useful message this automation sends — it is how Will and Alex know the request was received and judged, rather than lost.
- Keep it under about ten lines. It is a receipt, not a report.
- Never say a file was saved unless the save actually succeeded. If it failed, say so on the Outcome line and mark it "Problem".
- Name the exact Dropbox path, not "the client's folder".
- If the run covered several groups, give one line per group that had an outcome, and keep the "nothing happened" groups to a single summary count.
- If the Outlook send itself fails, say so in your final summary so Will knows the receipt never went out.


CONSTRAINTS: Never create duplicate Dropbox folders, duplicate Asana subtasks, or duplicate Info Sheet/census files. Never guess at data that isn't there yet, never fabricate census data. Info Sheets are `.md`, not `.docx`. Every carrier subtask must get a `due_on` of run-date-plus-one-day. Never send a real quote-request email to a carrier — only draft content inside Asana subtasks (except Imagine360's "schedule a conversation" prompt). Every email draft follows the DRAFT FORMAT exactly, and carries "AUTO-SEND READY" only when every clean-draft check passes. Never give one carrier contact two emails for the same group (Chad gets one combined email). Always @-mention Will on the Send for Quotes task when new subtasks are created. Never create a carrier subtask for a carrier that clearly matches the group's own stated current carrier (Step 5a's universal incumbent-skip) — this applies to every group, not just Renewal-named projects. Never send Angle a quote request for a group with fewer than 5 employees (actual employees, not total enrolled members/dependents) — Step 4's Angle minimum applies even though Angle is currently bundled with Navigation Health/HIT into one subtask. Never auto-create a Dropbox folder for a Plan Grader or Action Step lead. Match new-business project names flexibly (case-insensitive "quoting" substring, tolerate a missing/differently-formatted date). Never use "MEC" in ABA's carrier label/description — TBG goes to ABA for Level Funded quotes, not MEC. Never use "individual" in One Health's carrier label/description — TBG goes to One Health for Level Funded quotes, not their individual/1099 products. An AOR-acquired client's originating project lacking a "Send for Quotes" task or standard section structure (Step 0.h) is expected and must not be flagged — but this never excuses skipping that same client's actual renewal cycles once they have a real Renewal project; process those through the normal Steps 1-8 logic like any other client. If something conflicts between what's documented here and what you find live in Asana/Dropbox, flag the discrepancy in your summary rather than silently deciding.
