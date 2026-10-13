DRAFT FORMAT FOR AUTO-SEND — ADDED 2026-10-13, OVERRIDES THE EMAIL LAYOUT DESCRIBED IN STEP 4

Every carrier subtask that carries an email (everything except the UHCLF / Arlo / SANA portal tasks and
Imagine360's "schedule a conversation" task) uses this exact layout in its description, each label on
its own line. The "tbg-send-quotes-emails" routine reads it literally and sends it from
quotes@benefits.place, so nothing may be paraphrased or rearranged:

AUTO-SEND READY
TO: <carrier address>; <second address if any>
CC: lindsey@benefits.place; alex@benefits.place; will@benefits.place
SUBJECT: Encrypt - <Group Name> - <Carrier label> Medical Quote Request
ATTACH: <exact census filename attached in Asana> (ABA: also the claims/renewal files)
---BODY---
<Contact first name(s)>,

Can you send medical quotes for <Group Name>? <ATTACHMENT LINE>

Address <street, city, state ZIP>
SIC <code>
Tax ID <9-digit EIN>
Desired Effective Date <MM/DD/YYYY>

Lindsey

**PLEASE REPLY ALL TO THIS EMAIL**
---END---
<internal notes for Lindsey: exclusions, minimums met, and so on. Never sent.>

<ATTACHMENT LINE> is "Census and current plan info attached." only when current plan info really exists
for the group; otherwise "Census attached. The group does not currently offer benefits." Renewal
projects add "Current Carrier: <X>" as its own line after the effective date (Step 5b); new-business
projects never name the incumbent.

THE FIRST LINE "AUTO-SEND READY" GOES IN ONLY WHEN THE DRAFT IS CLEAN. All of these must be true:
- Address is complete (street, city, state, ZIP) and the sources agree. A conflict between the
  Typeform, Info Sheet or census means NOT clean.
- SIC is present.
- Tax ID is exactly 9 digits (an EIN). 8 digits, letters or a missing value means NOT clean.
- Desired Effective Date is a real date, not TBD or blank.
- The census is attached in Asana, on the "Send for Quotes" task or the project's "Save Census" or
  "Save Info Sheet" task, and ATTACH names that exact file.
- Every TO address is one of the carriers in Step 4 of these instructions.
- Nothing about the group is unresolved (for example census headcount vs Info Sheet headcount).

If ANY item fails, write the same layout WITHOUT the "AUTO-SEND READY" line, and put one line after
"---END---" starting "NOT READY: " that names exactly what is missing (e.g. "NOT READY: Tax ID
14090374 is 8 digits; address ZIP conflicts with the Typeform"). A person then fixes the draft and adds
"AUTO-SEND READY" as the first line when it is right. In a clean draft, do not write the words "NOTE:",
"confirm", "adjust", "TBD", "verify" or "not provided" anywhere in the description; the send routine
treats them as open questions and will hold the email.
