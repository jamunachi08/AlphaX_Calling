# Changelog

## 0.4.0
- **AX Calling Settings** form is now the single place for provider setup (Manual / Twilio / Carrier SIP Bridge), business numbers, carrier SIP details, compliance records, acceptance evidence and pilot approval. site_config keys remain a fallback.
- In-app setup guide, live readiness checklist, connection tests (Twilio API checks; bridge pipeline dry run), signing-secret generator, version capture, approval gate.
- Signed `bridge_config` endpoint so a bridge reads carrier settings from the app. Tools for carrier certification (`alphax_send_event.py`, `alphax_fetch_config.py`) and an Asterisk template.
- Workspace with shortcuts; per-number inbound owner; master on/off switch. 24 pure-logic tests.

## 0.3.0
- Free-pilot browser calling: Twilio trial adapter (token, voice webhook, status callbacks, signature verification), bundled Twilio Voice SDK 2.19.0 (Apache-2.0), in-browser softphone with incoming-call panel, outbound limited to the registered dial attempt.
- Recommendation and setup for pilot vs production carrier (Implementor Manual §7A). 22 pure-logic tests.

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
