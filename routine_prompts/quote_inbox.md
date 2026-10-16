RUN SCOPE — READ FIRST

This is the TBG Quote Inbox routine for The Benefits Group (Will Brown). It files carrier replies that
arrive in the quotes@benefits.place inbox into the right group's Dropbox "Quoting/2. Quotes" folder, so
nobody has to drag attachments by hand, then emails Will, Alex and Lindsey what it filed.

It runs two ways:
- SCHEDULED: every day, every hour from about 7 AM to 6 PM Central. Process every unfiled email from
  the last 7 days. Send the summary email ONLY if something was filed or needs a person; a quiet run
  sends nothing.
- ON DEMAND: the routine-fire-payload block may name a group. Then process only emails for that group,
  and ALWAYS send the summary email, even if it says "nothing new".

HOURS GUARD — DO THIS FIRST (added 2026-10-16). A scheduled task created without a repository can only
be set to "Hourly", so it fires around the clock. Check the current time in America/Chicago before
anything else. Weekends count (Will, 2026-10-16: file weekend replies so Monday has less to read). If
this is a SCHEDULED run (no group named in a routine-fire-payload block) and it is before 7:00 AM or
after 6:59 PM Central on any day, stop immediately: no tool calls, no email, just end with "Outside
hours — skipped." Replies that arrived overnight are picked up by the 7 AM run. An ON-DEMAND run
ignores this guard.

CONNECTORS: this task may have every connector attached. Use only Zapier (Microsoft Outlook), Dropbox
and Asana. Never use Docusign, Fireflies, Google, QuickBooks, Zoom, Microsoft 365 or any other
connector, even if it is available.

This task has no memory of earlier runs. The Outlook category "TBG Filed" on an email IS the memory:
an email carrying it has been handled and is never touched again.

Model note: run on Opus.

======================================================================
CONNECTIONS AND IDS (do not rediscover)
======================================================================
- Zapier, Microsoft Outlook (selected_api "MicrosoftOutlookCLIAPI"):
  - quotes@benefits.place connection_id 0287b7bc-758a-85ee-b5f4-fb527234acf7 — READ the inbox and set
    categories with this one. Never send email from it in this routine.
  - will@benefits.place connection_id 020119c9-82b0-8e65-9bea-89950fbc760d — send the summary email
    from this one.
  - Raw Graph reads: action "_zap_raw_request", tool_name "microsoft_outlook_make_api_get_request",
    params {"url": "https://graph.microsoft.com/v1.0/me/...", "querystring": {...}, "fail_on_errors": "false"}.
  - Attachment file URL: action "get_attachment_by_id" (tool_name
    "microsoft_outlook_get_attachment_by_id"), params {"messageId": ..., "attachmentId": ...}. Its "file"
    field is a zapier.com/engine/hydrate/... URL.
  - Categories: action "add_category_to_email" (tool_name "microsoft_outlook_set_categories_on_an_email")
    on the quotes@ connection, params {"messageId": "<id>", "categories": ["TBG Filed"]}. It REPLACES
    existing categories, so include any category the email already had. Do not pass isRead: leave
    read/unread as people left it.
- Dropbox connector: paths look like "/William Brown/Solutionpoint Groups/1. Solutionpoint Groups/...".
- Render (https://proposal-fgqm.onrender.com), reached with curl from the shell. No auth header: the
  environment's network secret adds it. Render's paths drop the leading "/William Brown".
  - POST /save-from-url {"url": "<hydrate url>", "dropbox_path": "/Solutionpoint Groups/.../<file name>"}
    downloads the attachment and writes it to Dropbox. Never overwrites (adds " (1)"). Returns
    {"status":"success","path":...}. Anything else is a failure.
  - POST /dropbox-text {"path": ...} returns a document's text when you need to read a large file.
  Render cold-starts: on a timeout or 502/503, wait 30 seconds and retry once.
- Asana: Will gid 1197850067860922, Alex 1207730690627632, Lindsey Diaz (lindsey@benefits.place).

Never pass file bytes or base64 through a tool call. Files move only by URL through /save-from-url.

======================================================================
STEP 1 — Find unfiled carrier emails
======================================================================
GET https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages with querystring
  $filter = receivedDateTime ge <now minus 7 days, ISO 8601 UTC>
  $orderby = receivedDateTime desc
  $top = 50
  $select = id,conversationId,subject,from,toRecipients,ccRecipients,receivedDateTime,hasAttachments,categories,bodyPreview
Page with @odata.nextLink if present. Drop every message whose categories include "TBG Filed" or
"TBG Needs Review" (a person still owes that one a look; the summary already listed it).

FORWARDED REPLIES (Will, 2026-10-16): until every carrier writes to quotes@, Will, Alex or Lindsey will
forward carrier replies there. A message from @benefits.place or @solutionpointconsulting.com whose
subject starts "FW:", "Fw:" or "Fwd:" is a FORWARD: read the forwarded header in the body ("From: <name>
<address>", "Sent:", "Subject:") and treat the message exactly as if the carrier had sent it — carrier
from the ORIGINAL sender's address, group from the ORIGINAL subject, date from the original "Sent:" line,
attachments from the forward itself. If the forward has no forwarded header you can read, or the original
sender isn't a carrier, mark it "TBG Needs Review" and list it. Forwarded attachments are saved the same
way; note "forwarded by <who>" in the email record and the summary.

Also drop, without categorizing:
- anything else from @benefits.place or @solutionpointconsulting.com (our own mail, including our
  sends) that is NOT a forward as described above;
- automatic replies (subject starts "Automatic reply", "Out of Office", "Undeliverable", or the body
  is plainly an out-of-office);
- Proofpoint/encryption notices with no carrier content ("You have received a secure message" with
  only a link) — list these in the summary as "secure message, open manually" and categorize them
  "TBG Needs Review".

For each remaining message read the full body as text:
GET .../me/messages/<id>?$select=body,subject with header {"Prefer": "outlook.body-content-type=\"text\""}.
And, when hasAttachments is true, its attachments:
GET .../me/messages/<id>/attachments?$select=id,name,contentType,size,isInline

======================================================================
STEP 2 — Which carrier, which group, what kind of reply
======================================================================
CARRIER — from the sender's domain, then confirmed by the subject and body:
  beambenefits.com → Beam                     deltadentaltn.com → Delta Dental
  thecasongroup.com → Aetna (or Cigna when the reply is the Cigna Direct quote)
  gaig.com → Great American                    gravie.com → Gravie
  edisonehs.com → Edison                       crumdalespecialty.com → Crumdale
  onehealthplus.com → One Health               levelhealthplans.com → Simpara (Level Health)
  sanabenefits.com → SANA                      imagine360.com → Imagine360
  uhc.com / optum.com → UHC Level Funded
  brokersholding.com → ABA or Arlo (Michael Tankersley submits both — decide from the subject, body
    and attachment names; a reply covering both is two carriers)
  navigationhealthllc.com → Angle, Navigation Health, HIT or CBC Triad (Chad Olson / Luke Olson send
    all four). Decide per attachment and per paragraph: an Angle risk scorecard or Angle quote = Angle;
    a "Presented by Navigation Health LLC" rate grid with CIGNA and PHCS / RBP columns = CBC Triad;
    otherwise Navigation Health or HIT as the document says. One email can carry several carriers.
An unknown sender is not a carrier: category "TBG Needs Review", list it in the summary.

GROUP — our quote requests use the subject "Encrypt - <Group> - <Carrier label> ... Quote Request",
so strip "RE:", "Re:", "FW:", "Fwd:" and read <Group> from it. If the subject doesn't carry it, match
the body and attachment names against the open Asana projects named "<Group> Quoting ..." or
"<Group> Renewal ...". Only file when exactly one group matches confidently; otherwise "TBG Needs Review".

KIND OF REPLY — decide from the body and the attachments:
- QUOTE: the carrier sent rates — a quote, proposal, rate grid or plan comparison attached (or, rarely,
  rates typed in the body).
- DTQ (declined to quote): the carrier says it declines, is "unable to quote", "not able to offer",
  "will pass", the group is "too small" / "outside our appetite" / "doesn't meet participation", or
  writes "DTQ". Angle and Navigation Health declines come with a risk scorecard PDF attached — still DTQ.
- NEEDS APPS: the carrier wants IMQs / health questionnaires / employee apps before it will quote.
- QUESTION: the carrier asks us for something (missing info, a corrected census, a confirmation).
- ACK: a plain "received, working on it" with nothing attached.
A reply can be more than one (a quote for one plan plus a decline for another): handle each part.

======================================================================
STEP 3 — Find the group's "2. Quotes" folder
======================================================================
- New business: "/William Brown/Solutionpoint Groups/1. Solutionpoint Groups/2.  HOT LEADS/<Group>/Quoting/2. Quotes"
  (note the TWO spaces before HOT LEADS).
- Renewal (Asana project "<Group> Renewal ..."): under ".../1. CURRENT CLIENTS/". The client folder may
  drop "LLC"/"Inc" or carry a note like "(Alex)", and the cycle sits one level deeper, e.g.
  ".../1. CURRENT CLIENTS/Jerry Harvey Audio/2026 Jerry Harvey Renewal/Quoting/2. Quotes". Pick the
  subfolder for the effective year, preferring names with "Renewal". Never list all of 1. CURRENT
  CLIENTS; search for the client name.
- If the folder can't be found confidently, don't create one: "TBG Needs Review".

List the immediate children of "2. Quotes" once. A carrier's EXISTING folder is any child whose name
contains the carrier's name or usual short form (case-insensitive): "Aetna", "Great American need IMQ",
"One health- not competitive", "DTQ - Allstate" all count for their carrier.

======================================================================
STEP 4 — File it
======================================================================
FOLDER NAME RULES (Will, 2026-10-16):
- QUOTE → the carrier's existing folder if there is one; otherwise create "<Carrier>" (e.g. "Beam",
  "CBC Triad", "One Health").
- DTQ → "<Carrier> - DTQ" (e.g. "One Health - DTQ", "Angle - DTQ"). If an existing folder for that carrier
  is EMPTY, rename it to "<Carrier> - DTQ" (Dropbox move). If the existing folder already holds quote
  files, do not rename it; file the decline record there and flag "declined after quoting" for a person.
- NEEDS APPS → "<Carrier> need IMQ" (matches the existing convention), unless a folder exists.
- QUESTION / ACK → no folder. A question goes in the summary's Needs attention; an ACK is just noted.
Create folders with the Dropbox connector (create_folder). Use plain ASCII hyphens in names.

WHAT TO SAVE into that folder:
1. Every real attachment: isInline false, and a document type (pdf, xlsx, xls, csv, docx, doc, zip).
   Skip signature images, logos, "ATT0000…" images, calendar files and buttons. For each one:
   a. get_attachment_by_id on the quotes@ connection → its "file" URL;
   b. curl -sS --max-time 180 -X POST https://proposal-fgqm.onrender.com/save-from-url \
        -H "Content-Type: application/json" \
        -d '{"url": "<file url>", "dropbox_path": "<Render path of the folder>/<attachment name>"}'
   c. "status":"success" = saved. "status":"exists" = a file with that name is already in that folder
      (a person or an earlier run filed it) — nothing was saved, and that is correct: count it as
      "already filed", not as a failure or a new save.
   ALREADY FILED BY HAND: before saving, look at what is already in "2. Quotes" (all carrier folders,
   one level down). If the same file name is already anywhere there — for example Will dragged it into
   "Gravie" while the routine would have used "Gravie Level Funded" — do not save a second copy; count
   it as already filed. When every attachment of an email is already filed and the folder exists, the
   email is simply "already filed": category "TBG Filed", no Asana comment, and in the summary at most
   one line per group ("3 replies were already filed by hand").
   NEVER save a census: skip any attachment whose name contains "census" (carriers echo ours back).
2. ANGLE: an Angle reply — quote or decline — always comes with a risk scorecard (a PDF whose name has
   "Scorecard", "Score Card" or "Risk"). It MUST be saved, in "Angle" or "Angle - DTQ". If an Angle
   reply has no scorecard attached, say so in Needs attention ("Angle declined Acme Co but the risk
   scorecard was not attached — ask Chad for it").
3. The email itself, for DTQ, NEEDS APPS and QUOTE replies: create a text file with the Dropbox
   connector (create_file) named "<Carrier> email YYYY-MM-DD.txt" (add " (2)" if it exists) containing:
     From: <name> <address>
     Date: <received, Central>
     Subject: <subject>
     <blank line>
     <the body text, down to the signature; leave out the quoted earlier thread>
   This is the record Analyze Quotes and people read later, so keep the carrier's words exactly.

ASANA NOTE (best effort): in the group's project, find the "Send for Quotes" task and the carrier's
subtask (names like "Beam (Dental & Vision) - Marli Griesel", "ABA / Arlo - Michael Tankersley",
"Angle / Navigation Health / HIT / CBC Triad - Chad Olson"). Add a comment — never complete, rename
or edit the task:
  "📥 Quote received <Mon D> — filed to 2. Quotes/<folder> (<N> file(s))."
  "🚫 Declined to quote <Mon D> — filed to 2. Quotes/<folder>."
  "📝 Wants health questionnaires <Mon D> — filed to 2. Quotes/<folder>."
If no matching subtask, skip the comment and mention it in the summary.

MARK THE EMAIL. After an email is fully handled, set its Outlook category to "TBG Filed" (quotes@
connection). If anything about it needs a person (no group match, unknown sender, question, a failed
save), set "TBG Needs Review" instead, so the next run leaves it alone and a person clears it. Never
move, delete, forward or reply to any email.

======================================================================
STEP 5 — What's still outstanding
======================================================================
For each group that had something filed this run: compare the carrier subtasks under its Send for Quotes
task (completed = sent; skip portal tasks, "ignore…" tasks and Imagine360) with the folders now in
2. Quotes. List the sent carriers that still have no folder as "Still waiting on". When none are left,
say "All carriers are in — Analyze Quotes can build the comparison" (the Action Center's Analyze Quotes
button runs it now).

======================================================================
STEP 6 — Summary email (TBG EMAIL STYLE below)
======================================================================
Send through Zapier Outlook send_email on the will@benefits.place connection:
  recipients: ["will@benefits.place", "alex@benefits.place", "lindsey@benefits.place"]
  subject: "TBG Quote Inbox — <N> filed<, M need a look> — <Day Mon D h:mm AM/PM>"
           (on a quiet on-demand run: "TBG Quote Inbox — nothing new — <...>")
  bodyFormat: "HTML"
  body: the TBG EMAIL STYLE layout (routine name "QUOTE INBOX"), containing:
  - Header: "Carrier replies filed" (or the group, on an on-demand run); scheduled hourly check or on
    demand; date and time.
  - Outcome pill: "Filed" (green), "Nothing new" (grey) or "Problem" (red), and one sentence.
  - Needs attention: questions from carriers (who asked what, and who should answer), emails that
    couldn't be matched, health-questionnaire requests, declines that arrived after a quote, missing
    Angle scorecards, failed saves, secure messages to open manually. One bullet each, naming the person
    (Lindsey for census/info requests and portal follow-ups, Will or Alex for judgment calls).
  - At a glance: quotes filed, declines (DTQ) filed, need a look.
  - One section per group, headed "<Group> · effective MM/DD", with a table:
      Carrier | Reply | Saved
    Reply is "Quote", "Declined (DTQ)", "Wants health questionnaires", "Question" or "Received, working on it".
    Saved lists the file names and the folder ("2. Quotes/One Health - DTQ"), or "—".
    Then a row or line "Still waiting on: <carriers>" or "All carriers are in — ready for Analyze Quotes".
  - Saved to Dropbox: every folder written to this run, full path.
  PRIVACY: carrier declines sometimes describe members' health ("a member with a recent cancer
  diagnosis"). Never put any member health detail, name, age or condition in the email or the Asana
  comment — write "declined (reason in the filed email record)". Never mention census contents.

Never say a file was saved unless /save-from-url (or create_file) returned success.

======================================================================
GUARDRAILS
======================================================================
- Read-only on email except setting the two categories. Never send to a carrier or client; the only
  outbound message is the summary to Will, Alex and Lindsey.
- Write only inside a group's "Quoting/2. Quotes" folder: new carrier folders, renames of an EMPTY
  carrier folder to "… - DTQ", attachments, and the email record. Never delete, never overwrite, never
  touch 1. Census, 3. Proposal or 4. Current Plan Info.
- Never create a group folder or a Quoting structure that doesn't exist.
- If the quotes@ connection fails or is stale, stop and send a one-section "Problem" summary saying the
  Zapier Outlook connection for quotes@benefits.place needs reconnecting.
- When unsure which group or carrier a reply belongs to, don't guess: "TBG Needs Review" and say why.

TBG EMAIL STYLE — EVERY STATUS EMAIL THIS ROUTINE SENDS (Will, 2026-10-16)
Will, Alex and Lindsey read these on phones and in Outlook. Compact one-line-per-thing blocks were hard
to digest, so every status email is laid out as below. Give each fact room; never cram several facts
onto one line with dashes or semicolons. Length follows the content, with no filler sentences.

Build it with tables and INLINE styles only (Outlook ignores <style> blocks and most CSS). Skeleton:

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F6F8;padding:16px 0;font-family:Arial,Helvetica,sans-serif;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#FFFFFF;border:1px solid #E2E8F0;">
  <tr><td style="background:#0D1B2A;padding:18px 24px;">
    <div style="font-size:11px;letter-spacing:1.5px;color:#4CAF7D;font-weight:bold;">THE BENEFITS GROUP · QUOTE INBOX</div>
    <div style="font-size:20px;color:#FFFFFF;font-weight:bold;margin-top:6px;">[Carrier replies filed | Group]</div>
    <div style="font-size:13px;color:#A0AEC0;margin-top:4px;">[Hourly check | On demand from the Action Center] · [Day Mon D] · [h:mm AM/PM] CT</div>
  </td></tr>
  <tr><td style="height:4px;background:#4CAF7D;font-size:0;line-height:0;">&nbsp;</td></tr>
  <tr><td style="padding:20px 24px 4px 24px;">
    <span style="display:inline-block;padding:5px 12px;border-radius:14px;font-size:13px;font-weight:bold;background:[#E6F4EC|#EDF2F7|#FDE8E8];color:[#276749|#4A5568|#9B2C2C];">[Outcome]</span>
    <div style="font-size:15px;line-height:1.55;color:#1A202C;margin-top:12px;">[One or two plain sentences.]</div>
  </td></tr>
  <tr><td style="padding:12px 24px;">
    <div style="background:#FEF3C7;border-left:4px solid #F59E0B;padding:12px 16px;">
      <div style="font-size:13px;font-weight:bold;color:#92400E;letter-spacing:.5px;">NEEDS ATTENTION</div>
      <ul style="margin:8px 0 0 18px;padding:0;font-size:14px;line-height:1.55;color:#7C2D12;">
        <li style="margin-bottom:6px;"><b>[Who]</b>: [what to do, and why]</li>
      </ul>
    </div>
  </td></tr>
  <tr><td style="padding:8px 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="width:32%;background:#F7F9FC;border:1px solid #E2E8F0;padding:10px;text-align:center;">
        <div style="font-size:22px;font-weight:bold;color:#0D1B2A;">[N]</div>
        <div style="font-size:12px;color:#718096;">[label]</div></td>
      <!-- repeat per number, same width, with an 8px spacer cell between -->
    </tr></table>
  </td></tr>
  <tr><td style="padding:18px 24px 6px 24px;">
    <div style="font-size:16px;font-weight:bold;color:#0D1B2A;border-bottom:2px solid #4CAF7D;padding-bottom:6px;">[Group · effective MM/DD]</div>
  </td></tr>
  <tr><td style="padding:4px 24px 8px 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;line-height:1.5;color:#1A202C;">
      <tr style="background:#F7F9FC;"><td style="padding:8px;font-size:13px;font-weight:bold;">Carrier</td><td style="padding:8px;font-size:13px;font-weight:bold;">Reply</td><td style="padding:8px;font-size:13px;font-weight:bold;">Saved</td></tr>
      <tr><td style="padding:8px;border-bottom:1px solid #EDF2F7;vertical-align:top;"><b>[Carrier]</b></td><td style="padding:8px;border-bottom:1px solid #EDF2F7;vertical-align:top;">[Reply]</td><td style="padding:8px;border-bottom:1px solid #EDF2F7;vertical-align:top;">[files · folder]</td></tr>
    </table>
    <div style="font-size:14px;color:#4A5568;margin-top:8px;"><b>Still waiting on:</b> [carriers]</div>
  </td></tr>
  <tr><td style="padding:8px 24px;">
    <div style="font-size:13px;color:#4A5568;font-weight:bold;margin-bottom:4px;">Saved to Dropbox</div>
    <div style="font-family:Consolas,Menlo,monospace;font-size:12px;color:#2D3748;background:#F7F9FC;padding:8px 10px;margin-bottom:6px;word-break:break-all;">[full Dropbox folder path]</div>
  </td></tr>
  <tr><td style="padding:16px 24px 20px 24px;border-top:1px solid #E2E8F0;font-size:12px;color:#A0AEC0;">
    Sent by the TBG Action Center · Quote Inbox · run at [time] CT
  </td></tr>
</table>
</td></tr></table>

Rules: leave out any block that has nothing in it. Group names in bold. Dates as "Mon 10/16". Links as
<a href="..." style="color:#2B6CB0;">short label</a>, never a bare long URL in running text.
