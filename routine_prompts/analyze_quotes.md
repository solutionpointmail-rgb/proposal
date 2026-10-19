RUN SCOPE — READ FIRST, THIS OVERRIDES ANYTHING BELOW:

This routine runs in two modes, decided by the routine-fire-payload block.

A. PAYLOAD NAMES A CLIENT — an on-demand run, started by someone pressing the button because new information arrived today.
   1. Process ONLY that client, in whichever pipeline it belongs to (Hot Leads / new business, or Renewals). Skip every other client in both pipelines without listing them.
   2. Bypass the DEDUPE CHECK V2 five-day cooldown for this client. The other protections still apply: do not build a second copy of an analysis that is already up to date, and never re-flag a client listed under CLIENT RESOLUTIONS.
   3. Do NOT send the combined Hot Leads / Renewals exception email — that belongs to the scheduled sweep. Post the normal Asana comment, @-mentioning BOTH Will (gid 1197850067860922) and Alex Sejas (gid 1207730690627632). The RUN RECEIPT email below still goes out, as it does for every run.

B. PAYLOAD IS EMPTY OR ABSENT — the scheduled daily sweep. Run the full check across both pipelines exactly as described below, including the exception email, with every dedupe rule and cooldown in force.

Everything below describes the full daily check. Mode A applies it to one client; mode B applies it to all of them.

You are running a recurring daily check for William Brown (Will) at The Benefits Group, an employee benefits brokerage. This task has no memory of any prior conversation — everything you need is below.

GOAL: Run TWO parallel pipelines and report on both in one combined run:
- PART A — NEW BUSINESS (HOT LEADS): for every active client in the "Hot Leads" pipeline, determine whether ALL carriers that were sent a quote request have actually responded (quoted or declined) in Dropbox.
- PART B — RENEWALS: for every current client with an active Renewal project due in the near term, determine the same thing.
In both parts: if all required carriers have responded, and no up-to-date draft exists yet, build a full carrier comparison analysis (same format as prior manual analyses) and save it as a DRAFT for Will to review — never send it anywhere, never treat it as final. Afterward, send Will, Alex and Lindsey ONE combined internal exception-report email summarizing which clients (across both pipelines) are stuck waiting on a carrier, which got a new draft, and which need a manual look — but only on days something is actually outstanding, and clearly label which section each client belongs to (Hot Leads / New Business vs Renewals).

STEP 1 — Connect folders
Request access to (or confirm existing access to) these folders via the cowork directory tool if not already connected:
- The Hot Leads root: "...Dropbox\William Brown\Solutionpoint Groups\1. Solutionpoint Groups\2.  HOT LEADS" (note the double space before HOT LEADS)
- The Current Clients root (used for Renewals): "...Dropbox\William Brown\Solutionpoint Groups\1. Solutionpoint Groups\1. CURRENT CLIENTS" — this folder has hundreds of client subfolders, so never list it wholesale; always reach a specific client folder by name once you know it from Asana (see PART B below).
- The logo folder: "...Dropbox\William Brown\SolutionPoint\Logos\The Benefits Group Logo\The Benefits Group Logo\Logo" — use "The Benefits Group_Logo.png" from here for branding.
If the folder picker doesn't default to these exact paths, ask Will once to confirm/select them, then proceed.

KNOWN ENVIRONMENT LIMITATIONS — read this once, don't rediscover it every run:
- SAVING FILES TO DROPBOX — the Dropbox connector cannot upload binary files (.docx, .pdf, .xlsx), but TBG's own Render app can, and the routine environment is allowed to reach it. To file any binary deliverable, POST it from the shell:
  curl -sS --max-time 120 -X POST https://proposal-fgqm.onrender.com/save-file -H "X-Dropbox-Path: <full Dropbox path including the filename>" --data-binary @"<local file path>"
  There is NO auth header to add — the environment's network secret attaches it automatically. Dropbox paths start with "/Solutionpoint Groups/1. Solutionpoint Groups/...". A JSON response containing "status":"success" means the file is filed; treat anything else as a failure, say so plainly in the report, and fall back to delivering the file in the run with SendUserFile plus the path it belongs in. Always send the file with --data-binary from the shell — never read it into the conversation, and never base64 it into a tool-call parameter. Still deliver a copy to Will in the run as well, so he has it without opening Dropbox.
- LARGE QUOTE FILES — READ THEM THROUGH RENDER (added 2026-10-16). The Dropbox connector's fetch only
  extracts text from files up to 5 MB. Carrier proposals often run larger — One Health's proposal PDFs
  (about 5.5 MB) are the usual case, and a skipped proposal is why The Arise Group's One Health cards came
  out with only a deductible and rates. Whenever fetch fails, returns nothing useful, or the file is over
  5 MB, get the text from Render instead:
    curl -sS --max-time 180 -X POST https://proposal-fgqm.onrender.com/dropbox-text \
      -H "Content-Type: application/json" \
      -d '{"path": "<the file's Dropbox path, as the connector shows it>"}' -o quote.json
  (no auth header; the environment's network secret adds it). The JSON has "text" with "===== page N ====="
  markers, plus "pages" and "truncated" (pass "max_chars" to raise the 300,000 limit). If "note" says the
  file is scanned images — or a page you need (a benefit grid) comes back empty — read those pages as
  images instead (added 2026-10-19; One Health's benefit grid on Harrison Audio, pages 8-9, is scanned):
    curl -sS --max-time 180 -X POST https://proposal-fgqm.onrender.com/dropbox-page-image \
      -H "Content-Type: application/json" -d '{"path": "<pdf path>", "page": 8, "scale": 2}' -o p8.png
  then open p8.png with the Read tool and transcribe the values. The response header X-Page-Count gives
  the page count. Never leave a plan's OOP, coinsurance, copays or Rx blank because a page was scanned. Never call it on a census file — it refuses them anyway.
  Never write "could not be read" into a plan's notes when this route exists: use it first.
- The GitHub push endpoint (https://proposal-fgqm.onrender.com/push-to-github, used in the selector-page steps) is blocked by this sandbox's network egress policy — POSTs to it will not succeed. This is also a confirmed, permanent limitation. Do NOT retry it or spend cycles testing it. Go straight to the fallback every time: save the HTML selector page to Dropbox (this part works fine, since HTML is a plain-text file Dropbox CAN create) and add the "⚠️ Selector page generation failed — upload manually to GitHub" warning to the Asana task description immediately, without first attempting the push.
- Dropbox binary DOWNLOADS are also blocked (dropboxusercontent.com / www.dropbox.com are outside this sandbox's egress allowlist), so you cannot pull the logo PNG down to embed in the .docx. Do NOT retry this. Use a text wordmark — "THE BENEFITS GROUP" in navy (#1F3864) caps at the top of the cover page and in the running header. This matches the approved reference document (TennGreen v4), so it is correct output, not a degraded fallback.
- OVERWRITING — /save-file overwrites by default, so a corrected draft or selector page replaces the old one instead of piling up as -v2, -v3, -v5. Pass the header "X-Overwrite: false" only when both copies genuinely need to be kept. The Dropbox connector's own create_file still cannot overwrite (it returns ALREADY_EXISTS), so use /save-file for anything that may already exist.
- HTML files (the selector page) upload to Dropbox just fine via the text-file creation tool — only true binary formats are blocked. Don't conflate the two.
- The "1. CURRENT CLIENTS" Dropbox root (used for Renewals) contains hundreds of client folders. Never enumerate it in full — always locate a specific client's folder by searching/matching on the client name you already derived from Asana (PART B, Step B2), e.g. via a targeted Dropbox search or a direct list_folder on the guessed exact path.
- Never pass a file's contents as base64 inside a tool-call parameter. Long base64 strings get truncated or corrupted, which is what made the old Google Drive filing fail silently. Files move one way only: written locally, then sent to Dropbox with curl --data-binary via /save-file, where the bytes never pass through a tool call.
  - IMPORTANT ADDENDUM (2026-09-22): even a small (<30KB) file's base64 upload can come out corrupted from a one-shot manual retype (this has actually happened — a Cornerstone-sized chunk got spliced into an Intocast-sized upload once). ALWAYS verify immediately after every Drive create_file call: compare the `fileSize` the API returns against the local file's actual byte size (e.g. from `wc -c` or the file listing you already have). If they don't match, delete the corrupted file from Drive right away and retry ONCE with a fresh, careful read of the source file immediately before the retry call (don't reuse anything from the failed attempt). If the retry also mismatches, stop — don't loop — and report that file as "not filed to Drive, delivered via chat only."

======================================================================
DEDUPE CHECK — ADDED 2026-09-11 PER WILL'S REQUEST, REWRITTEN 2026-10-12 — READ BEFORE STEPS A5/B5

Will flagged (2026-09-11) that this routine rebuilt the same carrier comparison DRAFT for the
same client on consecutive days, burning usage for no reason. The original cause was that the
routine could not write its own drafts into Dropbox, so the next run never found them. That is
fixed: the routine now files every draft into Dropbox itself through /save-file.

So the "already current?" check reads Dropbox, which is now reliably populated:

- Look in the client's "Quoting/3. Proposal" folder for a draft matching this client
  ("[Client] Carrier Comparison*.docx" for New Business, "[Client] Renewal Carrier Comparison*.docx"
  for a Renewal), plus the broader CAUSE 1 fuzzy match described in DEDUPE CHECK V2 below.
- If such a file exists AND its modified time is newer than the most-recently-modified file among
  all matched carrier response folders and the current-plan document, treat the client as
  "Already current" — do NOT rebuild and do NOT re-deliver.
- Record the bucket as "Already current (filed [date])" with the Dropbox path, so Will can see at
  a glance which draft the decision was based on.

There is no Drive copy to check any more. Any client whose only draft predates 2026-10-12 may have
its file in Drive rather than Dropbox; treat a missing Dropbox draft as "no draft" and build one.

DEDUPE CHECK V2 — ADDED 2026-09-22 PER WILL'S REQUEST — READ THIS BEFORE STEPS A5/B5 TOO
======================================================================
Even with the V1 Drive-based dedupe check above, Will found real duplicates piling up for several clients (Ideal Millwork, Porterfield, Intocast, TN Men's Health/MMM, and others) — investigated on 2026-09-22 and traced to TWO separate, compounding causes. Both are fixed by the rules below. Neither rule ever blocks a build the client genuinely needs; they only stop rebuilds that aren't actually warranted.

CAUSE 1 — Filename-matching is too narrow, so the routine doesn't recognize its own past work.
Some earlier runs (before this naming convention was locked in) saved analysis files under different names — e.g. "[Client]_Renewal_Analysis.docx", "[Client]_Medical_Analysis.docx", or other ad hoc titles — instead of the standard "[Client] Carrier Comparison DRAFT.docx" / "[Client] Renewal Carrier Comparison DRAFT.docx" pattern. The V1 dedupe check above only matches the standard pattern, so it walks right past these older files, concludes no draft exists, and builds a brand-new one under the standard name — leaving the old file sitting there unused forever and creating a duplicate.
FIX: when doing the Drive and Dropbox "already current?" checks in Step A5/B5, do a broader match, not just the exact standard filename. For the client you're checking, treat ANY file (in Drive's "TBG Carrier Comparisons" folder or in Dropbox's "[Client]/Quoting/3. Proposal" folder) whose name contains the client's name (fuzzy-matched the same way you fuzzy-match client names elsewhere — ignore LLC/Inc/punctuation/spacing) AND contains "Carrier Comparison" (case-insensitive) as a CANDIDATE existing draft. Files named "...Renewal Analysis" or "...Benefits Analysis" are client-facing documents (built by the TBG Client Quote Summary routine, or by hand). They are NOT comparisons: never treat them as an existing draft and never let them block a rebuild (changed 2026-10-13), regardless of exact naming. Use whichever candidate is newest. Apply the same "is it newer than the latest source data?" currency test to that file as you would to a standard-named one. If it's current, skip the rebuild and note in the report which (non-standard) filename you matched against, and suggest Will rename it to the standard pattern next time he's in there — but do not rename it yourself and do not delete anything.

CAUSE 2 — No cooldown, so any incidental new file triggers a full rebuild.
The currency test ("is there a file in this client's folders newer than the last draft?") fires on ANY new file landing anywhere in scope — including things that aren't actually new carrier data: a stray forwarded email, a census correction, enrollment paperwork, a duplicate carrier-portal export with a new internal reference number but identical figures, etc. Each of these was silently triggering a same-day-quality full rebuild, which is wasted effort when nothing about the actual comparison changed. This is also why selector HTML pages for a few clients (Porterfield, Intocast) had climbed to v5–v8 in a matter of weeks.
FIX: add a 5-calendar-day cooldown per client per pipeline. Before rebuilding a client's analysis in Step A6/B6, check the creation/modified date of the most recent existing draft for that client (standard-named or matched via the CAUSE 1 fuzzy match above, whichever is newer, across both Drive and Dropbox). If that draft is less than 5 calendar days old, do NOT rebuild automatically — bucket the client as "Already current (cooldown — refreshed <date>, next eligible <date+5>)" instead, EVEN IF a newer file has landed in the client's Dropbox folder since. The one exception that overrides the cooldown and always allows an immediate rebuild: a REQUIRED carrier that was previously missing (i.e., was in the "Waiting on carrier(s)" bucket in a prior run) has now actually responded — a change in carrier-response completeness is a real, meaningful trigger and is never held back by the cooldown. Two other things are never subject to this cooldown either: (a) a client with no existing draft at all yet (first build is never delayed), and (b) any analysis run because Will asked for it directly in chat, off-cycle — an explicit request always takes priority and always runs fresh regardless of how recently the routine last touched that client.
Record which clients were skipped purely due to the cooldown (as opposed to skipped because they're genuinely current with no new carrier activity) so Will can tell the difference at a glance.

======================================================================
CLIENT RESOLUTIONS — ADDED 2026-09-28 PER WILL'S FEEDBACK — READ BEFORE BUCKETING ANY CLIENT
======================================================================
On 2026-09-28 Will reviewed the 2026-09-27 exception report and flagged that several clients it listed as "Waiting on a Carrier" or "Needs a Manual Look" were actually already resolved — the client decided to renew with their CURRENT/incumbent carrier instead of continuing to shop competing quotes, so there is nothing left to wait on and no carrier comparison draft is needed (there's nothing to compare once the decision not to shop further has been made).

GENERAL RULE (applies to every future run, not just the clients named below): a client renewing with its current/incumbent carrier — confirmed via an Asana comment, task status, or note saying things like "moving forward with current carrier," "renewed," "staying with [incumbent]," "enrolling" with the incumbent, or similar — is RESOLVED, not outstanding. Do NOT bucket a resolved client as "Waiting on a Carrier" (missing quotes from other carriers no longer matter — they were never going to be used) or "Needs a Manual Look" (an incomplete or contradictory-looking carrier subtask list stops being a problem once the client has already decided not to shop further). Do NOT attempt to build a carrier comparison draft for a resolved client — there is nothing to compare. Simply drop the client from the exception report entirely once resolved (same treatment as a "not in progress" client in Step 8), unless something NEW and carrier-shopping-relevant shows up for them later (e.g. Will reopens shopping for a future renewal cycle), in which case treat that as a fresh cycle under the normal Part A/B rules.
Before defaulting a client to WAITING or SKIP because its carrier data looks incomplete or contradictory, check Asana for a comment or task/subtask note indicating a decision to renew with the incumbent — an incomplete-looking checklist is often just because shopping was abandoned partway through once the renewal decision was made, not because carriers haven't responded yet. A "dental only" note on a client (like Camp Bow Wow, Southeastern Technology Automation) means the medical Send-for-Quotes carrier list genuinely does not apply to that client — don't treat the empty/thin medical carrier data as a gap needing a manual look.

KNOWN RESOLVED CLIENTS (as of 2026-09-28, per Will directly — do not re-flag any of these unless Will says shopping has reopened for them):
- Keystone Business Solutions LLC (Renewal) — was flagged "waiting on Edison." Resolved: moving forward with current carrier renewal.
- Quatracor dba Complete Health Partners (Renewal) — resolved: in enrollment with current carrier renewal.
- Camp Bow Wow (Renewal) — dental only; already renewed.
- Gen X HR Solutions (Renewal) — resolved: enrolling, moving forward with current carrier renewal.
- PW Consulting LLC (Renewal) — resolved: moving forward with current carrier renewal.
- Nashville InnerCity Ministries (Renewal) — resolved: moving forward with current carrier renewal.
- Southeastern Technology Automation, LLC (Renewal) — dental only; resolved, moving forward with current carrier renewal.
- Syndicate Investments (Renewal) — resolved: moving forward with current carrier renewal.
- Nashville Opera (Renewal) — resolved: moving forward with current carrier renewal.
These 9 should no longer appear in either the "Waiting on a Carrier" or "Needs a Manual Look" buckets in future runs. If Will later says any of these clients is shopping again, remove that specific client from this resolved list and evaluate it fresh under the normal Part B rules.

======================================================================
FILING EVERY DELIVERABLE — DROPBOX IS THE ONE PLACE (REWRITTEN 2026-10-12)

Google Drive filing is RETIRED. It existed only because this environment could not write
binary files to Dropbox. It can now, through TBG's Render app, so Dropbox is both the system
of record and the routine's own memory of what it has already built. Do NOT create Drive
folders, do NOT upload anything to Drive, and do NOT put Drive links in the report. (Why it
was dropped: Drive uploads had to be passed as inline base64, which silently failed for files
over roughly 30KB. Between 2026-09-30 and 2026-10-12 every dated Drive folder was created
empty — the drafts never arrived, while the report implied they had.)

For every deliverable, every run:

1. Build the file locally as usual.
2. Save it to Dropbox with the /save-file call from KNOWN ENVIRONMENT LIMITATIONS above, into
   the client's own "Quoting/3. Proposal/" folder — "2.  HOT LEADS/[Client]/..." for new
   business, "1. CURRENT CLIENTS/[Client]/..." for a renewal.
3. VERIFY. A JSON response containing "status":"success" means it is filed; the response also
   carries the Dropbox path and a share link. Anything else is a failure: say so plainly in the
   report, name the file, and fall back to delivering it with SendUserFile plus the path it
   belongs in. Never imply a file was filed when the call did not succeed.
4. Report the Dropbox path (and the share link when you have one) in the Asana comment and in
   the exception email. That path is what a person opens — there is no second location to
   mention.
5. Also deliver the .docx (and a PDF render if you made one) to Will in the run with
   SendUserFile, so he has a copy without opening Dropbox.

DOCUMENT DEPTH STANDARD — THE "TENNGREEN STANDARD" (BOTH PIPELINES)
======================================================================
Will's approved reference document is "TennGreen Land Conservancy Carrier Comparison
DRAFT v4" (8 pages, 10 carriers). Every comparison you build — New Business or
Renewal — must match that depth. Thin, one-line-per-carrier output is a failure of
the task even when the numbers are right. Concretely:

EXECUTIVE SUMMARY must state, in prose, all of:
- What the Asana "Send for Quotes" checklist showed (e.g. "10 carrier requests sent,
  all marked complete") — so Will can see the RFP was fully worked.
- Which carrier documents this draft reflects, with their dates, and — on a rebuild —
  what specifically postdates the prior draft and triggered the refresh.
- Outstanding carriers, explicitly, including "None" when nothing is outstanding, and
  naming any "asking for apps" carrier as an intentional exclusion rather than a gap.
Then the tables/sections: "Carriers Quoted" (Carrier / Status / Funding Type /
Network / TPA or Stop-Loss / # Plan Options), plus separately-headed "Declined to
Quote", "Not Competitive — Reference Only", and "Optional / Non-Required Item"
sections. Never merge those categories into one list.

BENCHMARK TABLES: group by deductible tier (Tier A/B/C/D style), each tier its own
labeled table, richest to leanest. Columns: Carrier, Plan Name, Deductible (Ind/Fam),
OOP Max (Ind/Fam), Coinsurance, PCP/Specialist, Rx if available, Monthly EE-Only, and
Monthly Group Total. State explicitly where a tier is not an exact deductible match.
Where a current/incumbent renewal exists, it gets its own clearly labeled baseline row.

CARRIER NOTES & HIGHLIGHTS — the section most likely to come out thin. Every carrier
gets its own light-blue shaded banner with a navy (#1F3864) left-accent border, the
carrier name and network in bold navy, and THREE TO FIVE substantive bullets. Pull
these from the actual quote documents, not from generic knowledge. Cover as many as
the source supports:
- Quote/proposal ID, document date, and revision lineage ("revised 08/10/2026 — the
  most recent on file; supersedes the 06/12 version").
- Number of plan designs offered and the deductible range they span.
- Funding structure, TPA, stop-loss carrier, and stop-loss/aggregate limits.
- Direct comparability commentary against the other carriers at matched tiers
  ("runs meaningfully higher than Angle at every matched tier").
- Contract terms (12/24-month), surplus-return provisions, commission percentage,
  and per-employee admin fees, where the document states them.
- The census the carrier actually underwrote against, and a warning when that census
  is stale or differs from the current roster.
A carrier note that says only "quoted three plans, level funded" is not acceptable —
go back to the source PDF and get the specifics.

RECOMMENDATION: short, but must name the recommended option, the runner-up, and the
concrete reason (cost delta at a matched tier, network fit, or funding risk), and
stay framed as a draft steer for Will to confirm.

======================================================================
FILE DELIVERY PROTOCOL — MANDATORY, APPLIES TO EVERY DELIVERABLE IN BOTH PIPELINES
======================================================================
This exists because a previous run silently failed to deliver 9 finished carrier
comparisons: subagents built them correctly but left them in their own private
scratch directories, reported "sent to Will," and the orchestrator repeated that
claim without checking. Will saw nothing. Never let that happen again.

1. ONE SHARED OUTPUT DIRECTORY. Every finished deliverable (.docx and its .pdf
   render) MUST be written to, or copied into, /mnt/user-data/outputs/ . Create it
   if it does not exist (mkdir -p). A file that exists only in a subagent's
   scratch/working directory does NOT count as produced. If you delegate document
   building to subagents, instruct each one explicitly to copy its finished files
   into /mnt/user-data/outputs/ as its final action, and to report back the exact
   absolute paths it wrote.

2. THE ORCHESTRATOR DELIVERS, NOT THE SUBAGENT. Do not rely on a subagent's
   SendUserFile call and do not treat a subagent's word as proof of delivery. After
   all subagents finish, the orchestrator itself must:
   a. Run `ls -la /mnt/user-data/outputs/` and confirm, file by file, that every
      client you believe got a draft actually has BOTH a .docx and a .pdf there,
      each non-zero in size (a .docx under ~8KB is almost certainly an empty shell
      — investigate before shipping it).
   b. Generate any missing .pdf render itself:
      `soffice --headless --convert-to pdf --outdir <dir> "<file>.docx"`
      (libreoffice IS available in this environment.)
   c. Call SendUserFile itself on the verified files, batched by pipeline, with a
      caption naming the exact Dropbox path each one belongs in.

3. NEVER CLAIM UNVERIFIED DELIVERY. Do not write "sent to Will," "delivered," or
   any equivalent — in the exception email, the Asana task, the push notification,
   or your final summary — for any file you have not personally confirmed exists on
   disk and personally passed to SendUserFile. If a draft was built but could not be
   delivered, say exactly that instead, and say where it is.

4. RECONCILE BEFORE REPORTING. Immediately before sending the exception email,
   compare your "New draft generated today" bucket against the verified contents of
   /mnt/user-data/outputs/. The counts must match. If they do not, fix the gap
   first; if you cannot, the email must name the specific clients whose drafts are
   missing and why, rather than quietly listing them as done.

======================================================================
PART A — NEW BUSINESS (HOT LEADS)
======================================================================

STEP A2 — Identify client folders
List the immediate subfolders of the Hot Leads root. A folder is a real CLIENT folder only if it contains a "Quoting" subfolder with a "2. Quotes" subfolder inside it (this filters out loose template files, call lists, and other non-client items sitting at the root). For each client folder found, note its name (e.g., "Tyler Investments LLC"). Keep this full list handy — the report covers every client checked, not just the ones that got a new draft.

STEP A3 — Match to Asana and get the carrier send-list
Using the Asana connector, find the project whose name best fuzzy-matches "<client folder name> Quoting ..." (ignore suffixes like LLC/Inc/Incorporated and date strings when matching). ALWAYS IGNORE archived Asana projects — never match to, or even consider, a project that is archived; filter those out before doing any fuzzy-matching or ambiguity check. If two or more candidate projects fuzzy-match the client name and only one of them is not archived, that's not ambiguous — just use the non-archived one automatically. Only treat it as genuinely ambiguous if there are two or more competing candidates that are BOTH still active/non-archived. Within the matched project, find the task named "Send for Quotes" (it lives in a "CIS New Business Checklist" section) and pull its subtasks.
- EXCLUDE any subtask whose name starts with "ignore" (case-insensitive) — these are stale duplicates and should always be filtered out, for every client.
- EXCLUDE any subtask from the "must be matched to proceed" requirement in Step A4 if its name or notes mention requiring apps/applications from employees — phrases like "asking for apps", "requires apps", "require apps", "portal - asking for apps" (case-insensitive). These are carriers (e.g. UHCLF) that require employees to complete health questionnaires/applications for buy-in, which often doesn't happen and shouldn't hold up the analysis for everyone else. Treat this the same as an "ignore" item for readiness purposes: don't wait on it. IMPORTANT NUANCE: unlike "ignore" subtasks (which are excluded from the carrier list entirely, everywhere), an "asking for apps" carrier should still be excluded from the Step A4 blocking check, but if a Dropbox response folder for it DOES exist by the time you check, still pull it into the analysis normally like any other carrier.
- Among the remaining subtasks (after both exclusions above), the ones with completed = true are the carriers that were actually SENT a quote request and are REQUIRED to have a response before this client is ready. Subtasks with completed = false have not been sent yet — this client is not ready regardless of anything else.
- If the Asana project match is ambiguous (can't confidently find it, or there are competing/duplicate "Send for Quotes" tasks, or the carrier subtask list is clearly messy/inconsistent), skip this client for both the draft-building steps below AND note it in the report as "Skipped — needs a look" with a one-line reason.

STEP A4 — Match sent carriers to Dropbox response folders
Look at the client's "[Client]/Quoting/2. Quotes" folder. Each immediate subfolder there represents one carrier's response (received quote OR a decline). For each REQUIRED sent carrier subtask from Step A3 (i.e. excluding "ignore" items and excluding "asking for apps" items), check whether a response folder exists whose name contains a matching keyword (e.g., subtask "Aetna - Cason" matches folder "Aetna"; subtask "Cigna Direct - Kamryn" matches a folder containing "Cigna"; subtask "NHP - Chad" matches folder "NHP"). This must be a real per-carrier match, not just a count comparison — a folder count that happens to match the sent count is not sufficient on its own if the actual carriers don't line up.
IMPORTANT: a response folder with "DTQ" in its name (declined to quote) will very often contain few or NO files at all — maybe just a screenshot of the decline email, or nothing — because the carrier didn't provide a quote to save. That is expected and normal by definition (they declined, so there's nothing to attach), not a sign of messy or incomplete data. Do NOT flag a DTQ-named folder as ambiguous, "needs a look", or an unconfirmed response just because it's sparse or empty — its existence alone is what confirms the decline was received and logged; folder existence satisfies the match. Reserve "sparse/empty folder" suspicion for folders that are NOT named DTQ (or NOT COMP) — an unexpectedly empty folder for a carrier that was supposedly quoted (no DTQ/NOT COMP marker in the name) is the real signal worth flagging for a manual look, since there's no quote data to extract from it in Step A6.
- If EVERY required sent carrier has a matching response folder, this client is READY for analysis (an "asking for apps" carrier like UHCLF being absent does NOT block readiness).
- If any REQUIRED sent carrier has no matching folder yet, SKIP this client today (still waiting on that carrier) — do nothing further for it, but record the client name and the specific missing carrier name(s) (drop personal names, e.g. "Aetna" not "Aetna - Cason") for the "Waiting on carrier(s)" bucket.
- Separately, also check whether any "asking for apps" carrier DOES have a matching response folder despite not being required — if so, include it in the analysis normally in Step A6.

STEP A4B — Pull the current/incumbent carrier's renewal quote (always attempt, for every client that isn't skipped in A4)
Separate from the RFP-shopped carriers in "2. Quotes", also look for the incumbent carrier's current-plan/renewal quote — this is never required for readiness, but should always be pulled in when available, because it's the one data point that's still there even when every shopped carrier declines:
- PRIMARY location: "[Client]/Quoting/4. Current Plan Info" — a standard sibling folder to "1. Census", "2. Quotes", and "3. Proposal" inside every client's Quoting folder. Look for the most recent renewal letter/renewal package document(s) there (e.g., "[Carrier] Renewal Letter.pdf", "[Client] Renewal.pdf", "[Client] - Renewal Package.pdf") and use the most recently modified one if there are several.
- FALLBACK: if "4. Current Plan Info" has nothing usable, check inside "[Client]/Quoting/2. Quotes" for a subfolder whose name contains "Renewal" (as opposed to a shopped-carrier name) and use that instead.
- If neither location has anything usable, proceed without it — this is optional enrichment, not a blocker, and never causes a client to be skipped.
This matters most exactly when every shopped carrier in "2. Quotes" is DTQ/NOT COMP: in that case the current/renewal quote may be the ONLY real data available, and it must still go into the comparison doc and selector page rather than leaving Will with an empty comparison (this was the AH Supplies / Guardian Management case — confirmed with Will on 2026-08-30).

STEP A5 — Check if a draft is already up to date
FIRST, run the DEDUPE CHECK V1 described above against this client's Dropbox "Quoting/3. Proposal" folder, AND the DEDUPE CHECK V2 fuzzy-filename-match and 5-day-cooldown rules, AND the CLIENT RESOLUTIONS section above — if any of these finds a current match, the cooldown is still active, or the client is a known/newly-confirmed resolution (renewing with current carrier), stop here and record "Already current (filed <date>)", "Already current (cooldown — refreshed <date>, next eligible <date+5>)", or drop the client from the report entirely (per CLIENT RESOLUTIONS), as appropriate.
Otherwise, look in "[Client]/Quoting/3. Proposal" for an existing file matching a pattern like "[Client] Carrier Comparison*.docx" (NOT the "Renewal Carrier Comparison" pattern used in Part B — those are separate documents and must never be confused with each other, even if the same client somehow appears in both pipelines in the same run) — and also the CAUSE 1 fuzzy match from DEDUPE CHECK V2 (any file containing the client name plus "Carrier Comparison", "Renewal Analysis", or "Medical Analysis"). If one exists AND its last-modified time is newer than the most recently modified file across all matched response folders in Step A4 AND the current/renewal document(s) found in Step A4B, this client's draft is already current — skip it, do not regenerate, and record it in the "Already current" bucket. (A newer renewal letter landing in "4. Current Plan Info" — or its "2. Quotes" fallback — since the last draft is enough on its own to make the draft stale, even if the shopped-carrier folders haven't changed — UNLESS the 5-day cooldown from DEDUPE CHECK V2 is still active and the missing-carrier exception doesn't apply, in which case the cooldown wins and no rebuild happens.)
Otherwise (no draft yet in either Drive or Dropbox, or newer files have landed since the last draft AND the cooldown has expired or doesn't apply), proceed to Step A6.

STEP A6 — Build the analysis (for each ready, out-of-date client)
Read the actual quote documents (PDFs/xlsx, including the carrier's benefit summaries and SBCs that sit in the same folder) inside each matched response subfolder in "2. Quotes" (including any "asking for apps" carrier that happens to have responded) and extract EVERY field in the SELECTOR SCHEMA v2 field list in Step A7B — medical, dental and vision alike — not just deductible, OOP, coinsurance and copays. The comparison tables still show the benchmark columns below, but the full extraction is what the client proposal is built from: anything not extracted here prints as "See SBC" on the proposal (Will, 2026-10-15: "ALL of the information is already in the quotes"). Also record whether each quote is ILLUSTRATIVE (see Step A7B). Monthly premium by tier for all four tiers. Multiply by the actual census tier counts for that client (found in "1. Census" or within the quotes themselves) to get fully-loaded group monthly cost. Apply these rules, established and confirmed by Will:
- CBC Triad quotes every plan design on two networks (CIGNA and PHCS/RBP). Treat each network as its own plan, labeled "(CIGNA)" / "(PHCS/RBP)", in the benchmark tables, the selector and the proposal — see the CBC TRIAD rule in Step A7B.
- Any response folder with "DTQ" in its name means that carrier declined to quote — EXCLUDE it entirely from benchmarking tables (it had no quote to compare).
- Any response folder with "NOT COMP" in its name means the broker flagged it as NOT COMPETITIVE (not "not comparable") — include it in the doc but clearly labeled as not competitive / reference-only, excluded from the primary recommendation.
- If a current/incumbent renewal quote was found in Step A4B, extract the same benchmark fields from it (deductible, OOP max, coinsurance, copays, premium by tier) and include it as a distinct "Current Plan / Renewal" entry, labeled with the incumbent carrier's actual name (e.g., "Beam Benefits — Current Plan Renewal") — do not fold it into the shopped-carrier benchmarking table as if it were a competing RFP response; give it its own clearly-labeled row/column so it's obviously the baseline, not one of the quotes Will requested. This entry always appears in the Executive Summary and benchmark table(s) when found — most importantly on a client where every shopped carrier is DTQ, where it may be the only real numbers in the whole document.
- Never name an individual carrier rep/agent in the client-facing document (e.g., a subtask like "Cigna Direct - Kamryn" or "Aetna - Cason" should appear only as "Cigna Direct" or "Aetna" in the doc — drop personal names entirely).
- When carriers don't offer identical deductibles, group by the closest matching deductible tier (e.g., ~$2,000, ~$3,500) across carriers and say explicitly when it's not an exact match rather than forcing false apples-to-apples comparisons.
- Brand the document as "The Benefits Group" throughout (cover page, header, "Prepared by" line) — never "SolutionPoint Consulting," which is the internal legal entity name, not the client-facing brand.
- Use the docx skill to build the file. Visual style: Arial font, navy (#1F3864) headings, each carrier's notes/highlights subsection gets a light-blue shaded banner with a navy left-accent border (not a plain heading) — reference style established in "Tyler Investments Carrier Comparison" doc. Cover page includes the full-color logo pulled from the connected logo folder; a small version of the same logo goes in the running header of interior pages, next to "[Client Name] — Carrier Comparison".
- Structure: cover page (title, client name, effective date, census size, "Prepared by: William Brown, The Benefits Group", date) → Executive Summary (with a "carriers quoted" table including funding type/network/TPA/# plan options, and explicitly listing any declined-to-quote or not-competitive carriers, noting any "asking for apps" carrier that is still outstanding as an intentionally-excluded/optional item, not a gap, and — when found in Step A4B — a labeled "Current Plan / Renewal" baseline row) → benchmark comparison table(s) by deductible tier (with the current/renewal plan's figures included as its own labeled row/column wherever it fits a tier, so it's easy to see how each shopped carrier compares to what the client has today) → a "Carrier Notes & Highlights" section with the colored banner per carrier (include one for the current/renewal plan too, when found) → a short Recommendation section.
- Clearly label the file as a draft — e.g. filename "[Client Name] Carrier Comparison DRAFT.docx", and include a line near the top of the doc itself noting it was auto-generated and needs Will's review before anything goes to the client.
Record each client that got a new/updated draft here, plus its Dropbox path, for the "New draft generated today" bucket.

STEP A7 — Save, do not distribute
Save the finished .docx into "[Client]/Quoting/3. Proposal/" using the /save-file call from the KNOWN ENVIRONMENT LIMITATIONS section above, and report the path it landed in. Also use SendUserFile to deliver the .docx (and a PDF render, if you generated one) to Will in this run so he has a copy without opening Dropbox. If /save-file fails, say so plainly and tell him the exact Dropbox path the delivered file belongs in. Do NOT email it, message it to anyone else, upload it anywhere else, or treat it as final. Do NOT notify the client. This is a draft for Will to review and manually place in Dropbox on his own time.

STEP A7B — Generate & Push GitHub Selector Page
Run AFTER the carrier comparison .docx has been saved to Dropbox for a client. Run for EVERY client that completes quote analysis in this session (either pipeline — see Step B7B for the Renewal-specific naming note).

1. Build the plan data structure. From the plans already extracted during quote analysis, build three arrays:
- `medical_plans` — all viable medical plans (exclude DTQ, NOT COMP, Need Apps)
- `dental_plans` — all viable dental plans (exclude DTQ, NOT COMP, Need Apps)
- `vision_plans` — all viable vision plans (exclude DTQ, NOT COMP, Need Apps)
("Need Apps" here means a carrier that gave NO rates until apps are in. A carrier that DID give rates
but needs IMQs/apps before they are final — e.g. a "Great American need IMQ" folder with a proposal
PDF in it — is included, with "illustrative": true.)

If a current/incumbent renewal quote was found in Step A4B, add it as an additional entry in the relevant array (medical_plans/dental_plans/vision_plans) with "carrier" set to the incumbent carrier's name plus " (Current Plan Renewal)" (e.g. "Beam Benefits (Current Plan Renewal)"), so it shows up in the selector page alongside any alternative quotes for direct comparison. Do this even when it ends up being the ONLY entry in that array (e.g., every shopped carrier DTQ'd) — an array with just the current/renewal entry is far more useful to Will than an empty one, and is exactly the AH Supplies / Guardian Management scenario this was added to fix.

SELECTOR SCHEMA v2 (2026-10-15). The plan objects ARE the client proposal: Render builds the PDF
and Excel straight from them, field for field. Every field below that the carrier's quote, benefit
summary or SBC states must be filled in. Before this schema, plan objects carried only ~8 medical
keys, so dental and vision cards printed "See SBC" on every line.

Value rules:
- Write values the way a client reads them, short: "$2,000", "20%", "$35", "20% after deductible",
  "100%, no deductible", "Not covered", "Per DMO copay schedule", "Every 12 months".
- Use "" ONLY when no document in the carrier's folder states it; the proposal then prints "See SBC"
  as the final fallback. Don't write "See SBC", "TBD" or "N/A" yourself — go to the SBC / benefit
  summary and get the value first.
- Out-of-network on an in-network-only plan (EPO, DMO, INO): "Not covered".
- Numbers for rates and premium (591.81, not "$591.81").
- notes: one or two client-appropriate sentences (accrual basis, network rule, wellness perks,
  participation requirement). NEVER commission, PEPM fees, admin/stop-loss/claims-fund splits,
  broker of record, or anything about individual employees.

Every plan (all three lines):
  carrier, plan_name, plan_type, funding, network,
  illustrative            true | false  (see ILLUSTRATIVE below)
  quote_status            "Illustrative" | "Underwritten" | "Quoted"
  quote_status_note       for illustrative quotes, the carrier's own condition in one sentence,
                          e.g. "Great American requires health questionnaires (IMQs) before rates are final."
  rate_ee, rate_es, rate_ec, rate_ef, monthly_premium   (monthly_premium = the carrier's group total)
  rate_guarantee, notes, include: true

Medical adds:
  hsa_eligible (true/false),
  deductible_in_ind, deductible_in_fam, deductible_out_ind, deductible_out_fam,
  oop_in_ind, oop_in_fam, oop_out_ind, oop_out_fam, coinsurance_in, coinsurance_out,
  preventive, doctor_visit, virtual_visit, specialist, xray_lab, imaging, urgent_care, er,
  hospital, outpatient_surgery, rx (all tiers, "$10 / $35 / $75 / $250"), rx_deductible

Dental adds:
  deductible_in_ind, deductible_in_fam, deductible_out_ind, deductible_out_fam,
  deductible_waived_preventive, annual_max_in, annual_max_out, rollover,
  preventive, basic, major, endodontics, periodontics, oral_surgery, implants,
  ortho ("50%" / "Not covered" / "Child only, 50%"), ortho_max, ortho_age,
  waiting_periods, oon_reimbursement ("90th percentile UCR", "MAC")

Vision adds (copays are what the MEMBER pays; allowances are what the PLAN pays toward frames or
contacts — keep them in the right fields, the proposal labels them "copay" and "allowance"):
  exam_copay, materials_copay, lenses (lens copay), frame_allowance, contacts_allowance, lasik,
  exam_frequency, lenses_frequency, frames_frequency, contacts_frequency, oon_reimbursement

Carrier-name nomenclature maps like this (use judgment for others): "PCP / Primary care / Office
visit" -> doctor_visit; "Telehealth / Virtual" -> virtual_visit; "Advanced imaging / CT, MRI, PET"
-> imaging; "Diagnostic lab & x-ray" -> xray_lab; "Inpatient" -> hospital; "Outpatient surgery /
ASC" -> outpatient_surgery; "Type A / Class I / Diagnostic & preventive" -> preventive; "Type B /
Class II" -> basic; "Type C / Class III" -> major; "Calendar-year max / Annual benefit max" ->
annual_max_in; "Frame allowance / retail frames" -> frame_allowance; "Elective contacts" ->
contacts_allowance.

ONE HEALTH (Will, 2026-10-16: One Health quotes were not carrying over). One Health sends a rate grid
(designs like "$1,000 Classic", "$3,500 HSA") plus a proposal PDF that holds the benefit summary for
each design — deductible, OOP max, coinsurance, copays, ER, urgent care, Rx. The rate grid alone is not
enough: read the proposal PDF too (through /dropbox-text when it is over 5 MB) and fill every medical
field for each design. Carrier name is always "One Health" (not "One Health Plus" or "OneHealth").
A One Health plan object with an empty OOP max, coinsurance or office copay means the proposal was not
read: go back and read it before building the selector.

THIN CARRIER DATA = REBUILD. On an on-demand run, if the group's existing selector page has any carrier
whose plans are missing oop_in_ind, coinsurance_in and doctor_visit on most plans (the One Health cards on
The Arise Group, 2026-10-15), rebuild the selector page for that group even when the comparison .docx is
current, re-reading that carrier's documents.

CBC TRIAD — ONE PLAN DESIGN, TWO NETWORKS (Will, 2026-10-15). CBC Triad (Triad Benefits; quotes
arrive "Presented by Navigation Health LLC", usually in the Navigation Health / Chad / CBC Triad
response folder) prices every plan design twice, side by side: once on the CIGNA network and once
on PHCS / RBP. Each design ($1,000 Classic, $1,500 Classic, $2,500 Classic, $3,500 Classic, $5,000
Classic, $7,350 Value, $3,500 HSA, $5,000 HSA, ...) therefore becomes TWO plan objects, never one:
  - "carrier": "CBC Triad", "plan_name": "$1,500 Classic (CIGNA)",    "network": "Cigna",
    with the CIGNA column's four tier rates and total;
  - "carrier": "CBC Triad", "plan_name": "$1,500 Classic (PHCS/RBP)", "network": "PHCS / RBP",
    with the PHCS / RBP column's four tier rates and total.
Benefits (deductible, OOP, copays, Rx) are the same design for both, so copy them to both objects.
Always label the plan_name with the network in parentheses exactly as "(CIGNA)" or "(PHCS/RBP)" so
the two can be selected separately on the selector page and print as separate cards on the proposal.
In the comparison .docx, list both rows in the benchmark tables (same labels), and in the CBC Triad
carrier note say every design is quoted on both networks. Read the rates column by column — the
CIGNA column is always the left one of each pair, PHCS / RBP the right — and check each object's
monthly_premium against that column's "Total" line. The quote's validity ("valid for up to 60 days
past the Quote Date") goes in rate_guarantee.

ILLUSTRATIVE — Will, 2026-10-15: illustrative quotes must be CLEARLY labeled on the proposal.
Set "illustrative": true when ANY of these is true for that carrier's quote:
  - the quote or its email says illustrative, indicative, preliminary, estimate or "not sellable";
  - the carrier requires IMQs / health questionnaires / medical disclosure / employee apps before
    rates are final (a "need IMQ", "Need Apps" or "asking for apps" folder or subtask counts, even
    when the PDF itself says "Underwritten Proposal" — Great American on GunnCo was exactly this);
  - the Asana subtask or folder note says the rates are subject to IMQs.
Otherwise false. Never fold it into plan_name only ("(illustrative, subject to IMQs)" in the name is
no longer how it is shown — the flag drives the amber ILLUSTRATIVE ribbon, watermark, cover count
and disclaimer on the proposal). The selector page, the comparison doc and the Asana description
should say ILLUSTRATIVE next to those plans too.

Example (medical):
{
  "carrier": "Great American", "plan_name": "2000/80%/6000 PPO-INO Copay",
  "plan_type": "PPO", "funding": "Level Funded", "network": "Cigna OAP (in-network only)",
  "illustrative": true, "quote_status": "Illustrative",
  "quote_status_note": "Great American requires health questionnaires (IMQs) before rates are final.",
  "hsa_eligible": false,
  "deductible_in_ind": "$2,000", "deductible_in_fam": "$4,000",
  "deductible_out_ind": "Not covered", "deductible_out_fam": "Not covered",
  "oop_in_ind": "$6,000", "oop_in_fam": "$12,000", "oop_out_ind": "Not covered", "oop_out_fam": "Not covered",
  "coinsurance_in": "20%", "coinsurance_out": "Not covered",
  "preventive": "100%, no deductible", "doctor_visit": "$35", "virtual_visit": "$0", "specialist": "$75",
  "xray_lab": "20% after deductible", "imaging": "20% after deductible", "urgent_care": "$75",
  "er": "20% after deductible", "hospital": "20% after deductible", "outpatient_surgery": "20% after deductible",
  "rx": "$15 / $45 / $60 / 20% specialty", "rx_deductible": "None (specialty after deductible)",
  "rate_ee": 591.81, "rate_es": 1447.12, "rate_ec": 1116.03, "rate_ef": 1860.96, "monthly_premium": 5258.70,
  "rate_guarantee": "", "notes": "Calendar-year deductible. Cigna pharmacy.", "include": true
}
Example (dental):
{
  "carrier": "Beam", "plan_name": "Smart Premium Select 100/90/60-2000", "plan_type": "PPO",
  "funding": "Fully Insured", "network": "Beam / Guardian DentalGuard Preferred",
  "illustrative": false, "quote_status": "Quoted",
  "deductible_in_ind": "$50", "deductible_in_fam": "$150", "deductible_out_ind": "$50", "deductible_out_fam": "$150",
  "deductible_waived_preventive": "Yes", "annual_max_in": "$2,000", "annual_max_out": "$2,000", "rollover": "",
  "preventive": "100%", "basic": "90%", "major": "60%", "endodontics": "90%", "periodontics": "90%",
  "oral_surgery": "90%", "implants": "60%", "ortho": "Not covered", "ortho_max": "", "ortho_age": "",
  "waiting_periods": "None", "oon_reimbursement": "90th percentile UCR",
  "rate_ee": 40.27, "rate_es": 80.54, "rate_ec": 84.60, "rate_ef": 124.87, "monthly_premium": 1368.98,
  "rate_guarantee": "24 months", "notes": "", "include": true
}

2. Build the CLIENT_DATA object. Render reads it straight from the live selector page to fill the
proposal's cover and Employer Profile, so fill everything the census, intake sheet or quotes state.
Tier counts come from the CENSUS (enrolling employees by coverage tier) — counts only, never names
or birth dates. "schema": 2 marks a page built under SELECTOR SCHEMA v2.
{
  "schema": 2,
  "name": "[Client Name]",
  "effective_date": "[Effective Date, e.g. December 1, 2026]",
  "address": "[street]", "city_state_zip": "[City, ST 12345]",
  "state": "[ST]", "zip": "[12345]", "county": "[County]",
  "sic_code": "[SIC]",
  "quote_id": "[carrier quote IDs, e.g. 'Great American 44131 · Aetna 17574126']",
  "total_employees": N, "eligible_employees": N, "enrolling_employees": N, "waiving_employees": N,
  "total_members": N,
  "tier_counts": {"ee": N, "es": N, "ec": N, "ef": N},
  "tier_counts_by_line": {"dental": {"ee": N, "es": N, "ec": N, "ef": N}},
  "rate_guarantee": "[e.g. 12 months]",
  "contributions": {
    "medical_ee": "TBD", "medical_dep": "TBD",
    "dental_ee": "0%", "dental_dep": "0%",
    "vision_ee": "0%", "vision_dep": "0%"
  }
}
Include tier_counts_by_line only when dental or vision enrollment differs from medical; otherwise
leave it out. The object must be valid JSON (no comments).
Contributions: use what the intake sheet or Asana states ("50%", or a flat "$300"); otherwise "TBD".
The proposal computes employer and employee cost from these percentages and the tier counts.

3. Fetch the template from GitHub: GET https://raw.githubusercontent.com/solutionpointmail-rgb/proposal/main/proposal-selector-template.html

4. Replace ALL placeholders with real data. Replace every one of these strings that appears in the template ({{COUNTY}} and {{QUOTE_ID}} may no longer appear; that is fine), then search for "{{" — the result must be 0:
- {{CLIENT_NAME}} → Client name (e.g. "Redbird Real Estate")
- {{EFFECTIVE_DATE}} → Effective date (e.g. "August 1, 2026")
- {{EMPLOYEE_COUNT}} → Number of enrolling employees
- {{COUNTY}} → County and state
- {{QUOTE_ID}} → Quote ID if available, otherwise "See Quoting Project"
- {{ZAPIER_WEBHOOK_URL}} → [Zapier proposal webhook URL — kept only in the live routine, not in this public repo]
- {{CLIENT_JSON}} → JSON.stringify of the CLIENT_DATA object above
- {{MEDICAL_JSON}} → JSON.stringify of the medical_plans array
- {{DENTAL_JSON}} → JSON.stringify of the dental_plans array (use [] if none)
- {{VISION_JSON}} → JSON.stringify of the vision_plans array (use [] if none)
- {{MEDICAL_EE_CONTRIB}} → Medical EE contribution (e.g. "50%" or "TBD")
- {{MEDICAL_DEP_CONTRIB}} → Medical dependent contribution (e.g. "0%" or "TBD")
- {{DENTAL_EE_CONTRIB}} → Dental EE contribution (e.g. "0%")
- {{DENTAL_DEP_CONTRIB}} → Dental dependent contribution (e.g. "0%")
- {{VISION_EE_CONTRIB}} → Vision EE contribution (e.g. "0%")
- {{VISION_DEP_CONTRIB}} → Vision dependent contribution (e.g. "0%")

IMPORTANT: Verify after replacement that the HTML contains actual plan data (search for "carrier" in the output — if not found, do NOT push and flag for manual fix).

5. Set the filename. Format: [clientname]-[effmonthabbrv][effyear].html — strip spaces/punctuation, make lowercase. Examples: redbirdrealestate-aug2026.html, tylerinvestments-aug2026.html. For a Renewal client (Part B), append "-renewal" before the extension, e.g. redbirdrealestate-renewal-aug2026.html, so it never collides with a same-named new-business selector page.

6. Push the selector page live. The routine environment can reach Render, so publish it directly:
   curl -sS --max-time 120 -X POST https://proposal-fgqm.onrender.com/push-selector -H "X-Filename: <filename>.html" --data-binary @"<local html file>"
   No auth header is needed (the environment's network secret adds it). The JSON response contains the live URL, which will be https://solutionpointmail-rgb.github.io/proposal/[filename].html — put that URL in the Asana task and in the exception email. Only if the call fails should you report that the page still needs a manual push.

6a. BULK SELECT CONTROLS — every selector page must include them. Before building the page, read proposal-selector-template.html in the cloned proposal repo and copy its "BULK SELECT CONTROLS" block — the <style> and <script> immediately before </body> — verbatim into the page you are building, in the same position. It adds a "Select all" and "Clear" button plus a live "N of M selected" count to each of the Medical, Dental and Vision sections, which matters because a group with 47 dental plans is otherwise hundreds of individual clicks (Will, 2026-10-12). Never re-implement this block from memory and never adjust its logic: it relies on the page's existing selections object, the med-/den-/vis- id prefixes, and the existing updateCount function. If the template somehow lacks the block, say so in the report rather than inventing a replacement.

7. Save a copy to Dropbox. Save the HTML file to the client's Quoting/3. Proposal/ folder in Dropbox as [filename].html (the Dropbox copy is the backup if GitHub push fails).

8. Create the Asana task in Proposals — Review & Generate:
- Project GID: 1216533612775246
- Section: Review for Proposal (GID: 1216528532507842)
- Task name: [Client Name] — Review for Proposal (append " (Renewal)" for Part B clients, so Will can tell the two pipelines apart in that shared project)
- Description must include: the selector URL (GitHub Pages link); CLIENT INFO block (effective date, enrolling employees, contributions); MEDICAL — VIABLE CARRIERS section with all plans; DENTAL — VIABLE CARRIERS section (or "None quoted"); VISION — VIABLE CARRIERS section (or "None quoted").

9. Since the GitHub push is expected to be blocked (see KNOWN ENVIRONMENT LIMITATIONS), always do this: save the HTML to Dropbox as normal (this text-file save works fine), add this warning at the top of the Asana task description: "⚠️ Selector page generation failed — upload manually to GitHub (HTML saved to Dropbox Quoting/3. Proposal folder)", and continue — do NOT block the Asana task creation, and do NOT spend a retry attempting the push first.

SELECTOR SCHEMA v2 REBUILD (2026-10-15): a selector page whose CLIENT_DATA lacks "schema": 2 was
built under the old thin schema and makes a proposal full of "See SBC". On an on-demand run (mode A)
for a client whose selector page lacks it, rebuild the selector page (Step A7B/B7B) under v2 even
when the comparison .docx is current — re-read the quote documents for the full field list. The
docx does not need rebuilding for this alone. On the scheduled sweep, rebuild it for any client that
is otherwise processed today; do not sweep every old page.

Validation checklist before pushing HTML:
- ALL {{PLACEHOLDER}} strings have been replaced (run a search for "{{" — result should be 0)
- {{MEDICAL_JSON}} replaced with actual JSON array (not [] unless truly no medical plans)
- {{DENTAL_JSON}} replaced (use [] if none quoted)
- {{VISION_JSON}} replaced (use [] if none quoted)
- {{CLIENT_NAME}} replaced with actual client name
- {{QUOTE_ID}} replaced
- All 6 {{..._CONTRIB}} fields replaced
- HTML contains the word "carrier" at least once (proves plan data is embedded)
- CLIENT_DATA contains "schema": 2 and tier_counts; "See SBC" is never written into a plan value (leave "" instead)
- Every plan has "illustrative" set to true or false; dental plans have annual_max_in, preventive,
  basic and major; vision plans have exam_copay, frame_allowance and exam_frequency (or "" only where
  no document states it)
- File size is > 10,000 bytes (empty shells are ~141 bytes — a dead giveaway)

======================================================================
PART B — RENEWALS
======================================================================
Same rules and document format as Part A throughout — the only differences are how clients are discovered (Asana-first, date-windowed, since "1. CURRENT CLIENTS" is too large to walk in full) and a few naming/labeling tweaks to keep Renewal output distinguishable from New Business output. Everything not called out below (docx visual style, DTQ/NOT COMP handling, personal-name stripping, deductible-tier grouping, SendUserFile delivery, Step 7B selector-page mechanics) is identical to Part A — reuse that logic, just apply it to the Renewal client/project/folder for each step.

STEP B1 — Find candidate Renewal projects
Search Asana for live (non-archived) projects whose name contains "Renewal" (case-insensitive). For each match, determine its due date: use the project's due_on field if set; otherwise try to parse a trailing date out of the project name itself (e.g. "Creative Nation Renewal 10/01/2026" → 10/01/2026). Keep only projects whose resolved due date falls between (today − 30 days) and (today + 120 days) — this keeps the run scoped to renewals that are actually current, not ones from last year or two years out. If a project's date can't be resolved at all, skip it and note it in the "Skipped — needs a look" bucket for Renewals with reason "no resolvable renewal date."

STEP B2 — Extract client name & match Dropbox folder
From the project name "<Client Name> Renewal <date>", strip the "Renewal <date>" portion (and any trailing punctuation) to get the client name. Find the corresponding client folder under the Current Clients root ("1. CURRENT CLIENTS") — fuzzy-match on the client name (ignore suffixes like LLC/Inc/Incorporated, punctuation, and parenthetical notes like "(Zak Referral)"). Use a targeted Dropbox search or a direct list_folder guess on the exact expected path — do NOT list the entire "1. CURRENT CLIENTS" root.
- If no confident folder match is found, or 2+ folders plausibly match, skip this client: record it in "Skipped — needs a look" with reason "No confident Dropbox match under 1. CURRENT CLIENTS."
- Once matched, confirm the folder contains a "Quoting" subfolder with a "2. Quotes" subfolder inside it (same real-client-folder rule as Part A). If not, skip with reason "No Quoting/2. Quotes structure found."

STEP B3 — Get the carrier send-list
Within the matched project, find the task named "Send for Quotes" — for Renewals this lives in a "CIS Renewal Checklist" section (NOT "CIS New Business Checklist" — that's the Part A section name only). Pull its subtasks and apply the exact same "ignore" and "asking for apps" exclusion rules as Step A3.

STEP B4 — Match sent carriers to Dropbox response folders
Identical logic to Step A4, applied to this client's "1. CURRENT CLIENTS/[Client]/Quoting/2. Quotes" folder.

STEP B4B — Pull the current/incumbent carrier's renewal quote (always attempt, for every client that isn't skipped in B4)
Same as Step A4B, applied under the Current Clients root: PRIMARY location "1. CURRENT CLIENTS/[Client]/Quoting/4. Current Plan Info" (standard sibling folder to "1. Census", "2. Quotes", "3. Proposal"); FALLBACK is a subfolder under "1. CURRENT CLIENTS/[Client]/Quoting/2. Quotes" whose name contains "Renewal". Never required for readiness; always worth including when found, especially when every shopped carrier is DTQ/NOT COMP.

STEP B5 — Check if a draft is already up to date
FIRST, run the DEDUPE CHECK V1 described above against this client's Dropbox "Quoting/3. Proposal" folder, matching against "[Client Name] Renewal Carrier Comparison DRAFT.docx" — AND run the DEDUPE CHECK V2 fuzzy-filename-match and 5-day-cooldown rules — AND the CLIENT RESOLUTIONS section above. If any of these finds a current match, the cooldown is still active, or the client is a known/newly-confirmed resolution (renewing with current carrier), stop here and record "Already current (filed <date>)", "Already current (cooldown — refreshed <date>, next eligible <date+5>)", or drop the client from the report entirely (per CLIENT RESOLUTIONS), as appropriate.
Otherwise, look in "1. CURRENT CLIENTS/[Client]/Quoting/3. Proposal" for an existing file matching "[Client] Renewal Carrier Comparison*.docx" — note the "Renewal" in the filename pattern; this is deliberately a different pattern from Part A's "[Client] Carrier Comparison*.docx" so the two never get confused with each other, even for a client that happens to appear in both pipelines — plus the CAUSE 1 fuzzy match from DEDUPE CHECK V2. Same "newer than latest matched quote folder, including the Step B4B current/renewal document(s)" currency check as Step A5, subject to the same 5-day cooldown and missing-carrier-response exception.

STEP B6 — Build the analysis
Same extraction, benchmarking, and docx-build rules as Step A6 — including the Step A4B/B4B "Current Plan / Renewal" labeled entry in the Executive Summary, benchmark tables, and Carrier Notes section whenever one was found — with these labeling differences only:
- Filename: "[Client Name] Renewal Carrier Comparison DRAFT.docx"
- Doc title / cover page: "Renewal Carrier Comparison" instead of "Carrier Comparison" (still branded The Benefits Group, same visual style, same disclosure line that it's auto-generated and needs Will's review).

STEP B7 — Save, do not distribute
Same as Step A7 — save it with /save-file into "1. CURRENT CLIENTS/[Client]/Quoting/3. Proposal/", report the path, and also SendUserFile the .docx (and PDF if generated) to Will. Never send/notify the client.

STEP B7B — Generate & Push GitHub Selector Page
Same mechanics as Step A7B, using the filename and Asana-task-name "(Renewal)" tags called out there — including adding the Step B4B current/incumbent renewal quote as a "(Current Plan Renewal)"-labeled plan entry when one was found, even if it ends up being the only entry in its array.

======================================================================
STEP 8 — Wrap up processing for both parts
======================================================================
After checking every client folder in both Part A and Part B, you should have four buckets PER PIPELINE: "Waiting on carrier(s)", "Already current" (which now includes the cooldown sub-case from DEDUPE CHECK V2 — call these out distinctly, see STEP 9), "New draft generated today", and "Skipped — needs a look" — so up to 8 buckets total (4 for Hot Leads / New Business, 4 for Renewals). Clients with nothing sent to any carrier yet (no completed subtasks at all) don't need a bucket in either pipeline — they're simply not in progress and aren't part of the exception report. Clients resolved per the CLIENT RESOLUTIONS section above (renewing with their current/incumbent carrier) also don't need a bucket — they're settled, not outstanding.

======================================================================
STEP 9 — Send the internal exception-report email (Will, Alex and Lindsey only)
======================================================================
Only send an email if at least one client across EITHER pipeline landed in "Waiting on carrier(s)", "New draft generated today", or "Skipped — needs a look". If every client in both pipelines is either not-yet-in-progress, resolved (per CLIENT RESOLUTIONS), or already-current with nothing new, skip sending entirely — a quiet day stays quiet, do not send an empty or "nothing to report" email.

LOCKED OUTPUT FORMAT — Will approved these sections on 2026-10-12 and the visual style on 2026-10-16. Reproduce it every run, in this order, with these headings and these words. Do not redesign it, do not rename the sections, do not add or drop sections, and do not switch a table to a list or a list to a table. Consistency between runs matters more than any improvement you might think of.

HTML AND STYLE (restyled 2026-10-16 per Will: the old compact 13px layout was hard to digest)
- Build the whole email in the TBG EMAIL STYLE at the end of these instructions (routine name
  "ANALYZE QUOTES"). Header line 2: "Hot Leads & Renewals"; header line 3: "Daily check · [Day Mon D]".
- Outcome sentence under the pill: "No new drafts were built today." / "[N] new draft(s) built today."
  followed by one plain sentence of context.
- Needs attention box: everything a person must act on today, across both pipelines, one bullet each.
- At a glance: waiting on carriers, new drafts, needs a manual look, already current (counts).
- Pipeline headers are SECTION headings, exactly "NEW BUSINESS (HOT LEADS)" then "RENEWALS". Omit a
  pipeline with nothing to report. Bucket headings inside a pipeline are bold 15px navy (#0D1B2A)
  lines with 14px top padding.
- Tables follow the style's table rule (header #F7F9FC, 14px body, 8px padding). Bullet lists are
  14px with 6px between items, client name in <b>, then a colon, then the note.

SECTION ORDER WITHIN EACH PIPELINE — skip any bucket with nothing in it, never show an empty heading:
1. "Waiting on a Carrier" — a TABLE with exactly three columns, in this order:
   | Client | Still outstanding | Note |
   - Client: the group name. In the RENEWALS pipeline, append the renewal date in parentheses, e.g. "Jerry Harvey Audio LLC (12/01)".
   - Still outstanding: comma-separated carrier names only, no personal rep names ("Aetna", never "Aetna - Cason").
   - Note: one short sentence of useful context, or empty. Use it for things like "UHCLF needs IMQs (treated as optional).", "Requests went out about 7/21. Four medical carriers are still missing.", "Lindsey asked on 10/6 whether to re-send with the new census; still unanswered."
2. "New Draft Ready for Review" — a BULLET list, one per client: client name in bold, then the Dropbox path the file needs to be saved into, the live selector page URL, and confirmation that the file was filed. If every shopped carrier declined, say so plainly so Will expects a thin comparison.
3. "Needs a Manual Look" — a BULLET list, one per client: client name in bold (with renewal date in parentheses for renewals), then the one-line reason, then what would resolve it. Example: "Creative Nation (10/01): All carriers are in, but the 9/8 draft is older than the Angle 'FINAL POST OE' PDF (10/06). The group has already moved from UHC to Angle (enrollment done, ID emails sent), so the draft was not rebuilt. Reply if you still want a refresh."
4. "Already Current" — a BULLET list, one per client: client name in bold, then where the current draft lives and its date, then any one-line housekeeping note. Examples: "Ideal Millwork & Hardware: Drive draft 9/14. No newer carrier data.", "McCall Wealth Advisors: Dropbox 3. Proposal 'Medical_Analysis_UPDATED.pdf' (10/02) is newer than every quote. It has a non-standard name; consider renaming it to 'McCall Wealth Advisors Carrier Comparison DRAFT'.". For a client held only by the DEDUPE CHECK V2 cooldown, write "cooldown — refreshed [date], next eligible [date]" so it reads differently from a genuinely current client.

Keep every note to one or two sentences. Say the specific thing (dates, file names, carrier names, who asked what and when); never pad with generic phrasing.

Send it using the Zapier Microsoft Outlook connector's "Send Email" action: call execute_zapier_write_action with selected_api "MicrosoftOutlookCLIAPI", action "send_email", and params:
  - recipients: ["will@benefits.place", "alex@benefits.place", "lindsey@benefits.place"]   (Lindsey added 2026-10-19)
  - subject: "Carrier Quote Status — Hot Leads & Renewals — [today's date]"
  - bodyFormat: "HTML"
  - body: the HTML report described above
Leave "sender" blank so it sends from whichever mailbox the connected Outlook account is authenticated as (intended to be wbrown@solutionpointconsulting.com). If you notice the connected account is clearly a different address, still send it, but flag that discrepancy in your final run summary so Will can double check the Zapier connection.


RUN RECEIPT — SEND ONE EVERY RUN, NO EXCEPTIONS (added 2026-10-12 per Will)

Will, Alex and Lindsey cannot see this run. So the LAST thing every run does, whether it changed anything or not, is send a short receipt email through the Zapier Microsoft Outlook connector (execute_zapier_write_action, selected_api "MicrosoftOutlookCLIAPI", action "send_email"):

  recipients: ["will@benefits.place", "alex@benefits.place", "lindsey@benefits.place"]
  bodyFormat: "HTML"
  subject:  "TBG Analyze Quotes — [Group or 'all groups'] — [Ran | Nothing to do | Problem]"
  body: HTML in the TBG EMAIL STYLE below (routine name "ANALYZE QUOTES"), containing:
    - Header: the group, or "All groups (daily sweep)"; scheduled 7:05 AM run or on demand; date, time.
    - Outcome pill (Ran | Nothing to do | Problem) and one or two plain sentences.
    - Needs attention: one bullet per thing a person must do, naming who.
    - One section per group with an outcome: label rows Outcome, Carriers in the comparison, Illustrative
      quotes (if any), Selector page (link), Files saved.
    - Saved to Dropbox: every file, full path.
    - If nothing was produced, the specific reason — e.g. "a current comparison is already filed in
      Quoting/3. Proposal (dated 10/09)", "two carriers have not responded yet", "refreshed 3 days ago,
      next eligible 10/17".

RULES FOR THE RECEIPT
- Send it for EVERY run, including runs where you did nothing. "Nothing to do" with a specific reason is the most useful message this automation sends — it is how Will, Alex and Lindsey know the request was received and judged, rather than lost.
- Lay it out with the TBG EMAIL STYLE, one fact per row. The full exception report (Step 9) is separate and only goes out on the daily sweep when something is outstanding.
- Never say a file was saved unless the /save-file call returned success. If it failed, say so on the Outcome line and mark it "Problem".
- Name the exact Dropbox path, not "the client's folder".
- If the run covered several groups, give one line per group that had an outcome, and keep the "nothing happened" groups to a single summary count.
- If the Outlook send itself fails, say so in your final summary so Will knows the receipt never went out.


TBG EMAIL STYLE — EVERY STATUS EMAIL THIS ROUTINE SENDS (Will, 2026-10-16)
Will, Alex and Lindsey read these on phones and in Outlook. Compact one-line-per-thing blocks were hard
to digest, so every status email (receipt, report, summary) is laid out as below. Give each fact room;
never cram several facts onto one line with dashes or semicolons. Length follows the content — there is
no line cap — but no filler sentences either.

Build it with tables and INLINE styles only (Outlook ignores <style> blocks and most CSS). Skeleton:

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F6F8;padding:16px 0;font-family:Arial,Helvetica,sans-serif;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#FFFFFF;border:1px solid #E2E8F0;">
  <!-- HEADER -->
  <tr><td style="background:#0D1B2A;padding:18px 24px;">
    <div style="font-size:11px;letter-spacing:1.5px;color:#4CAF7D;font-weight:bold;">THE BENEFITS GROUP · [ROUTINE NAME IN CAPS]</div>
    <div style="font-size:20px;color:#FFFFFF;font-weight:bold;margin-top:6px;">[Group or "All groups"]</div>
    <div style="font-size:13px;color:#A0AEC0;margin-top:4px;">[Requested: scheduled 6:07 AM run | on demand from the Action Center] · [Day Mon D] · [h:mm AM/PM] CT</div>
  </td></tr>
  <tr><td style="height:4px;background:#4CAF7D;font-size:0;line-height:0;">&nbsp;</td></tr>
  <!-- OUTCOME -->
  <tr><td style="padding:20px 24px 4px 24px;">
    <span style="display:inline-block;padding:5px 12px;border-radius:14px;font-size:13px;font-weight:bold;background:[#E6F4EC|#EDF2F7|#FDE8E8];color:[#276749|#4A5568|#9B2C2C];">[Outcome]</span>
    <div style="font-size:15px;line-height:1.55;color:#1A202C;margin-top:12px;">[One or two plain sentences: what happened and what it means.]</div>
  </td></tr>
  <!-- NEEDS ATTENTION (only when something does; always ABOVE the details) -->
  <tr><td style="padding:12px 24px;">
    <div style="background:#FEF3C7;border-left:4px solid #F59E0B;padding:12px 16px;">
      <div style="font-size:13px;font-weight:bold;color:#92400E;letter-spacing:.5px;">NEEDS ATTENTION</div>
      <ul style="margin:8px 0 0 18px;padding:0;font-size:14px;line-height:1.55;color:#7C2D12;">
        <li style="margin-bottom:6px;"><b>[Who]</b>: [what to do, and why]</li>
      </ul>
    </div>
  </td></tr>
  <!-- AT A GLANCE (optional, 2-4 numbers) -->
  <tr><td style="padding:8px 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="background:#F7F9FC;border:1px solid #E2E8F0;padding:10px;text-align:center;">
        <div style="font-size:22px;font-weight:bold;color:#0D1B2A;">[N]</div>
        <div style="font-size:12px;color:#718096;">[label]</div></td>
      <!-- repeat a cell per number, all the same width (2 cells = 49%, 3 = 32%, 4 = 24%), with an 8px spacer cell between -->
    </tr></table>
  </td></tr>
  <!-- SECTION (repeat per group / bucket) -->
  <tr><td style="padding:18px 24px 6px 24px;">
    <div style="font-size:16px;font-weight:bold;color:#0D1B2A;border-bottom:2px solid #4CAF7D;padding-bottom:6px;">[Section heading]</div>
  </td></tr>
  <tr><td style="padding:4px 24px 8px 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;line-height:1.5;color:#1A202C;">
      <tr><td style="width:34%;padding:8px 10px 8px 0;border-bottom:1px solid #EDF2F7;color:#4A5568;vertical-align:top;"><b>[Label]</b></td>
          <td style="padding:8px 0;border-bottom:1px solid #EDF2F7;vertical-align:top;">[Value — one fact per row]</td></tr>
    </table>
  </td></tr>
  <!-- FILES (when any were saved) -->
  <tr><td style="padding:8px 24px;">
    <div style="font-size:13px;color:#4A5568;font-weight:bold;margin-bottom:4px;">Saved to Dropbox</div>
    <div style="font-family:Consolas,Menlo,monospace;font-size:12px;color:#2D3748;background:#F7F9FC;padding:8px 10px;margin-bottom:6px;word-break:break-all;">[full Dropbox path]</div>
  </td></tr>
  <!-- FOOTER -->
  <tr><td style="padding:16px 24px 20px 24px;border-top:1px solid #E2E8F0;font-size:12px;color:#A0AEC0;">
    Sent by the TBG Action Center · [routine name] · run at [time] CT
  </td></tr>
</table>
</td></tr></table>

Rules: outcome pill colors — green for Ran / Sent / Saved, grey for Nothing to do, red for Problem.
Leave out any block that has nothing in it (no empty "Needs attention", no zero-only stats). Group
names in bold. Dates as "Mon 10/16". Links (selector pages, Dropbox shared links, Asana tasks) as
<a href="..." style="color:#2B6CB0;">short label</a>, never a bare long URL in running text.
Tables of several groups (e.g. "Waiting on a carrier") use a real table: header row background
#F7F9FC, bold 13px; body cells 14px with 8px padding and a 1px #EDF2F7 bottom border.

IMPORTANT GUARDRAILS
This task NEVER sends, emails, or shares anything with a client or a carrier, in either pipeline. It only reads Dropbox/Asana, writes draft files into Dropbox's "3. Proposal" folders, and — per Step 9 — sends one internal exception-report email to Will, Alex and Lindsey only, and only on days something is outstanding. That internal status email is the one exception to "never send anything"; it is never sent to a client or carrier, and it never contains client-facing material, just status/exception tracking. A Renewal draft is exactly as informal/internal as a New Business draft — it is a tool for Will to decide his renewal strategy, not a client-facing renewal proposal.
Step 7B / B7B is a permitted exception to "writes to Dropbox only." It pushes an HTML plan selector page to TBG's own GitHub repository (solutionpointmail-rgb/proposal) and to TBG's own Render server (proposal-fgqm.onrender.com). Both are TBG-controlled infrastructure. The selector page contains only carrier-published plan rate information (plan names, deductibles, OOP maximums, premiums) — it never contains census data, employee names, SSNs, health questionnaire responses, or any PHI. This is the same category of information that appears in a standard broker proposal PDF. This step is required for the pipeline to function and must not be skipped.
If Asana or Dropbox access isn't available/connected when this runs, stop and report that access needs to be reconnected — don't guess or skip silently in that case.
Be conservative: if matching is ambiguous for a given client in either pipeline (e.g., can't confidently find the Asana project, can't confidently match a Dropbox folder, or carrier names don't clearly line up with folders), skip that client rather than guessing, log it in the "Needs a Manual Look" bucket for the correct pipeline, and move to the next client.
Never confuse the two pipelines' clients, folders, or draft files with each other — a client can in principle appear in both Hot Leads and Renewals in the same run (unusual, but possible mid-transition); treat each as an entirely independent check against its own Asana project, its own Dropbox root (2.  HOT LEADS vs 1. CURRENT CLIENTS), and its own draft filename pattern.
Only build a brand-new analysis outside this schedule when Will explicitly asks for one in chat (an "off-cycle" request) — that always bypasses the DEDUPE CHECK V2 cooldown, per its own terms above, and is never something a future run should do on its own initiative for a client that isn't due.
