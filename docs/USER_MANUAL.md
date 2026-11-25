# AlphaX Calling: User Manual

For sales executives and sales managers · Version 0.2.0

## 1. What it does

AlphaX Calling lives inside the **Lead** form. It helps you call a customer, record what happened, promise a next step, and make sure nothing is forgotten. Every call is kept on the Lead, so a colleague (with access to that Lead) can see the full story.

You will see:
- a **Calling** menu on the Lead (top right),
- a coloured **banner** at the top of the Lead summarising calls and giving advice,
- **ToDo** items and notifications for your callbacks,
- two reports: **AX Callback Queue** and **AX Executive Calls**.

> This version places the call through your phone or installed softphone (a `tel:` link). It does not carry audio itself. When your company connects a carrier, calls handled by that carrier are added to the same history automatically.

## 2. Making a call

1. Open the Lead and choose **Calling → Call mobile** (or **Call phone**).
2. If something deserves your attention, you will see a short warning and a question, **Dial anyway?** Typical warnings:
   - outside the allowed calling hours, or it is Friday/Saturday,
   - the number is not Saudi (check the country code),
   - the same number is on another Lead you can access,
   - the last three attempts were not answered.
   Press **Yes** to continue or **No** to stop. These are advice, not blocks.
3. Your phone or softphone opens with the number already in international format (for example `0551234567` becomes `+966551234567`).
4. A form opens: **Record the outcome of your call**. Fill it in after you finish talking (see section 3). If you close it, nothing is lost: the Lead banner reminds you, and **Calling → Log call** reopens it.

**When dialing is blocked:** the Lead has status *Do Not Contact*, a company do-not-call field is ticked, or the number is missing/invalid. Fix the Lead or ask your manager; do not work around it.

## 3. Recording the call

| Field | How to use it |
|---|---|
| **Direction** | Outbound (you called) or Inbound (the customer called). |
| **Reported result** | Answered, Unanswered, Busy or Failed. This is the technical result of the call, not your opinion of it. |
| **I spoke with the customer** | Tick only if you really spoke with the customer. Voicemail or a family member who took a message is *Answered* but not a conversation. Managers count only ticked calls as real customer conversations. |
| **Talk time (minutes)** | Only for Answered calls. Unanswered, Busy and Failed calls always count as zero. |
| **Outcome** | Your assessment: *Callback requested*, *Demo agreed*, *Information sent*, *Wrong number*, *No interest*, or blank. |
| **Call notes** | What was said and agreed. Line breaks are kept. Maximum 4,000 characters. |

### Outcomes that need more information
- **Callback requested:** choose the **callback owner** and a **future** date/time. The suggestion is the next working day at 10:00 (Friday and Saturday are skipped).
- **Demo agreed:** choose the **demo date and time** (future). A calendar **Event** with the Lead as participant is created for you.
- **Unanswered / Busy / Failed:** tick **Schedule a retry** to book a callback without changing the outcome.

Pressing **Save call** twice, or on a weak connection, never creates two records or two callbacks.

## 4. Callbacks

- A callback creates a **ToDo** for the owner and appears in **AX Callback Queue**.
- If it becomes overdue, the owner receives a notification (checked every 15 minutes).
- **Calling → Complete my callback** closes it; the completion is recorded under your name.
- **Calling → Reschedule my callback** moves it to a new future time. Only the owner can complete or reschedule.

**Missed inbound calls** (carrier-connected sites): the system assigns one callback owner, normally the Lead owner, due within the configured time (default 60 minutes).

## 5. The Lead banner and history

The banner shows the number of calls, how many were answered, open and overdue callbacks, any calls waiting for your outcome, and up to two pieces of advice, such as:
- *Three attempts in a row went unanswered: try a different time or channel.*
- *Five in a row: stop calling, send a message, review the Lead.*
- *Information was sent but no follow-up is scheduled.*

**Calling → Call history** lists the most recent calls with who handled them, the outcome and callbacks. When a Lead becomes an Opportunity, the Opportunity has a **Call history** button showing the same calls (still counted once in reports).

## 6. Reports

### AX Callback Queue
Lists open callbacks, overdue first, with status, hours overdue, Lead, mobile and notes. Executives see their own. Sales Managers can switch **Show → Team** to see every callback on Leads they can read.

### AX Executive Calls (managers)
Filter by dates (default last 30 days), executive, company and business line.

| Column | Meaning |
|---|---|
| Attempts | All dial attempts and logged calls, including ones never completed. |
| Answered (reported) | Carrier or executive says answered. May include voicemail. |
| Answer rate % | Answered ÷ attempts. |
| Customer conversations (confirmed) | Calls the executive ticked "I spoke with the customer". Use this as the human-contact measure. |
| Unique Leads reached | Distinct Leads with at least one confirmed conversation. |
| Talk minutes | Zero for unanswered calls. Reported by the executive, or measured by the carrier when connected. |
| Demos agreed | Calls with that outcome. |
| Open / Overdue callbacks | Counted for the callback owner, regardless of the date filter. |
| Awaiting executive update | Calls older than 15 minutes where the executive has not yet recorded the outcome. |

Reports only include Leads you are allowed to read. Calls on Leads you cannot read never appear, even in totals.

## 7. Sales managers: review queue

Inbound calls from an unknown or shared number are not guessed. They wait in **AX Lead Call** with *Review status = Needs Review* (open the AX Lead Call list and filter on that). Open one, press **Link to Lead**, choose the correct Lead (and a callback owner if it was a missed call). You will only see these unmatched calls, never other Leads' calls.

## 8. Arabic

Set your user language to Arabic to see the Calling menu, dialogs, warnings and advice in Arabic.

## 9. Privacy and good practice

- You only see calls for Leads you can read; the same rules apply to history, reports and exports.
- Recording is off. Do not rely on the system to record audio.
- Log calls the same day. Write facts, not opinions; notes are visible to everyone with access to the Lead.
- Never mark a call "spoke with the customer" unless it is true. Managers rely on it.
- Respect Do Not Contact and the calling window.

## 10. Quick answers

| Question | Answer |
|---|---|
| I closed the outcome form by mistake. | **Calling → Log call** reopens it for your last unfinished call. |
| The call button is missing. | You need write access to the Lead, and the Lead must have a mobile or phone number. |
| My phone did not open. | Your device has no `tel:` handler. Install a softphone or use your phone and log the call manually. |
| I cannot set a callback in the past. | By design. Pick a future time. |
| Someone else owns my callback. | Only the owner can complete it. Ask your manager to relink or create a new callback. |
| A warning appeared about another Lead. | The number is shared. Check you are on the right Lead. You see only Leads you may access. |
| The call is marked with ⚠ in history. | The carrier's record disagrees with what was logged. A manager will reconcile it. |
