# Changelog

## 0.2.0
Corrections to 0.1.2
- Result and outcome were free-text Data fields; now validated Select fields.
- Lead deletion could be blocked by call records; calls are removed with the Lead (`on_trash`, `ignore_links_on_delete`).
- Reports paged through every Lead in the system; now filter the matching calls' Leads only (same visibility rules).
- "Open callbacks" in the executive report were attributed to the logger; now attributed to the callback owner, with overdue count.
- `crypto.randomUUID` fails on plain HTTP staging; added a fallback.
- Timeline comments flattened line breaks in notes; preserved.
- Callback was only a field on the record; now also a ToDo (assignment alerts), reschedulable, overdue-notified every 15 min.
- DocType JSON lacked list-view fields, sort order and metadata; added. Built-in "Do Not Contact" Lead status now blocks dialing.
- Package data patterns widened (JS, CSV, report scripts).

Brief requirements added
- Demo agreed creates a linked Event. Company, business line, source label, started/answered/ended, talk seconds.
- Dial attempts recorded; unlogged attempts surfaced. Executive-confirmed "spoke with customer" kept apart from reported answer.
- Provider-event endpoint (HMAC, replay window, dedupe, order tolerance, terminal states, late-event protection), inbound matching within company, review queue, missed-call callback owner, stale-call reconciliation flag, retention purge.
- Opportunity linkage and Opportunity call-history button. Realtime incoming-call alert to the authorised agent.

Intelligence
- Saudi number normalisation (Arabic digits, 05…, 00966, +966 (0)…), Fri/Sat weekend and call-window warnings, shared-number detection limited to Leads the user can read, no-answer streak advice, next-working-day retry suggestion.
- Arabic translations for all UI strings.
