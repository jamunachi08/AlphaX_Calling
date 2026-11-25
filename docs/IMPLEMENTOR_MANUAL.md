# AlphaX Calling: Implementor Manual

For implementation leads, Frappe developers, telephony engineers and QA · Version 0.2.0 · Target: Frappe/ERPNext v15

## 0. Verification status (read first)

| Layer | Status |
|---|---|
| Pure logic (`utils.py`: phone normalisation, scheduling, signatures, event state machine) | 16 unit tests pass: `python -m unittest alphax_calling.tests.test_utils` |
| Python/JS/JSON syntax | pyflakes, compileall, `node --check`, JSON validation all clean |
| Frappe-bound code (API, reports, hooks, doctypes, webhook) | **Not executed on a live bench by the author.** Written against Frappe v15 APIs. An integration suite is provided (`tests/test_calling.py`) and must be run on staging as the first acceptance step. |
| Carrier, audio, caller ID, SIP | Out of scope. No carrier account existed. Needs the contracted route. |

Treat the first staging run as acceptance. Expect small fixes; none of the design depends on untested assumptions except those listed in section 11.

## 1. Architecture

    Browser (Lead form) ──► alphax_calling.api  ──► AX Lead Call (single authoritative call record)
          ▲   realtime                ▲                    ▲
          │                           │                    │
    Carrier / adapter ──signed──► alphax_calling.events.provider_event ──► AX Call Event (raw, deduped log)

- **AX Lead Call** is the one record per call. Manual logs, dialer taps and carrier events all land here. Names are UUIDs: random for manual/dialer, `uuid5(provider:account:call_id)` for carrier-created calls, so duplicates are impossible at the database level.
- **AX Call Event** stores every provider delivery (name = `uuid5(provider:account:event_id)`), giving idempotency and an audit trail. Purged after `alphax_calling_event_retention_days` (default 180).
- **ToDo** and **Event** (ERPNext) are created for callbacks and demos. Their names are stored as plain text on the call (no hard link, so they remain deletable).
- State machine for carrier events lives in `utils.plan_event` (pure, tested).

### Two ownership rules
1. **The carrier owns technical state** (status, times, measured talk time) once an `ended` event is applied (`final_source = Provider`). The executive can then only add outcome, notes, spoke flag, callback, demo.
2. **The executive owns the assessment.** If the executive closed the record first (`final_source = Human`), a later carrier `ended` event attaches times/ID/measured talk, and sets `reconcile_flag` if the statuses disagree. It never rewrites the executive's status.

## 2. Compatibility and version pins

Record these on staging before sign-off (brief step 1):

    bench version
    bench --site SITE list-apps
    pip freeze | grep -iE "frappe|erpnext"

Pin: `frappe >=15,<16`, `erpnext >=15,<16`, Python ≥ 3.10, MariaDB 10.6+. The app uses these Frappe features: `get_list`/`get_all` with `pluck`, `frappe.rate_limit`, `scheduler_events.cron`, `Notification Log`, `ToDo`, `Event` with `event_participants`, report 5-tuple (`report_summary`), `ignore_links_on_delete`.

Inventory before install (brief step 1): existing Lead buttons/`doctype_js`, call logs (`neotec_voice`, Frappe Telephony `Call Log`), inbound handlers. If another app already adds a Lead "Calling" menu, rename ours or retire the other. This app does not read other apps' call logs. When a provider app becomes the source of truth, post its events to the endpoint in section 6 via a small adapter instead of maintaining two records.

## 3. Installation

    cd /abs/path/alphax_calling
    git init && git add . && git -c user.name=i -c user.email=i@localhost commit -m "AlphaX Calling v0.2.0"
    cd /abs/path/frappe-bench
    bench get-app file:///abs/path/alphax_calling
    bench --site SITE install-app alphax_calling
    bench --site SITE migrate
    bench build --app alphax_calling
    bench --site SITE clear-cache
    bench --site SITE run-tests --app alphax_calling --module alphax_calling.tests.test_calling

Serve Desk over HTTPS. Managed hosting: push to an authorised Git repository and use the provider's custom-app flow. Upgrade: `bench update --apps alphax_calling` then `migrate`. Rollback: check out the previous tag, `migrate`, `bench build`. New fields are additive; removing the app leaves `tabAX Lead Call` data in place.

## 4. Configuration (site_config.json)

Set with `bench --site SITE set-config KEY VALUE` (use `--parse` for JSON values).

| Key | Default | Purpose |
|---|---|---|
| `alphax_calling_do_not_call_field` | none | Fieldname of a Check on Lead that blocks dialing. A configured but missing field also blocks. The built-in status *Do Not Contact* always blocks. |
| `alphax_calling_call_window` | `"09:00-21:00"` | Advisory window (site time zone). |
| `alphax_calling_weekend_days` | `[4,5]` | Python weekday numbers (Mon=0). Default Friday/Saturday. |
| `alphax_calling_default_country_code` | `"966"` | Used to normalise local numbers. |
| `alphax_calling_default_callback_owner` | none | Fallback owner for missed inbound calls when the Lead owner is inactive or has no write access. |
| `alphax_calling_missed_callback_minutes` | `60` | Due time for automatic missed-call callbacks. |
| `alphax_calling_business_lines` | `{}` | Map of business number → company and line. Used to scope inbound matching and to fill reports. |
| `alphax_calling_webhook_secret` | none | HMAC secret for provider events. Endpoint refuses (503) until set. |
| `alphax_calling_event_retention_days` | `180` | Raw event retention. |

Example:

    bench --site SITE set-config alphax_calling_business_lines '{"+966112223333": {"company": "AlphaX Co", "business_line": "Sales"}}' --parse
    bench --site SITE set-config alphax_calling_webhook_secret "$(openssl rand -hex 32)"

Set the site time zone (System Settings) to Asia/Riyadh; all carrier timestamps are converted to it.

## 5. Roles and permissions

| Role | Access |
|---|---|
| Sales User | Lead form actions need Lead **write**. Reports are visible. Cannot open AX Lead Call records. |
| Sales Manager | Reports; sees and resolves **review items only** (calls with no Lead) in the AX Lead Call list. |
| System Manager | Full access to AX Lead Call and AX Call Event. |

Visibility rule (brief "Access control"): every user-facing read goes through Lead permissions. `lead_panel` requires Lead read. Reports filter calls by `frappe.get_list("Lead")`, which applies roles, User Permissions, sharing and assignment. Inbound notifications are sent only after `has_permission(Lead, read)` for the target user. Same-number warnings list only Leads the viewer can read and never state how many hidden ones exist. `AX Lead Call` list access is restricted by `permission_query_conditions`/`has_permission`.

**Note on exports:** the AX Lead Call list is limited to System Manager (full) and Sales Manager (review items). Exports of call data for others go through the reports, which are filtered.

## 6. Provider event contract

`POST /api/method/alphax_calling.events.provider_event` · JSON body · guest access, authenticated by signature.

Headers:
- `X-AlphaX-Timestamp`: Unix seconds. Rejected if more than 300 s from server time.
- `X-AlphaX-Signature`: lowercase hex `HMAC-SHA256(secret, timestamp + "." + raw_body)`.

Body:

| Field | Required | Notes |
|---|---|---|
| `provider`, `account`, `call_id` | yes (account optional) | Together identify the call. Max 140 chars. |
| `event_id` | yes | Unique per delivery per provider/account. Same ID again → `Duplicate`. |
| `event_type` | yes | `call.initiated`, `call.ringing`, `call.answered`, `call.ended`. |
| `occurred_at` | yes | ISO-8601 with offset, or epoch seconds. |
| `direction` | for new calls | `inbound` or `outbound`. |
| `from`, `to` | for new calls | Any format; normalised to E.164. Inbound customer = `from`; outbound customer = `to`. |
| `business_number` | optional | Else the other leg. Used for `alphax_calling_business_lines`. |
| `client_ref` | outbound | The `attempt` id returned by `dial_number`. Carry it through the provider request (brief step 3). |
| `status` | on `call.ended` | `completed`, `busy`, `no-answer`, `failed`, `cancelled`, `declined`, `rejected`, `missed`. Mapped to Answered, Busy, Unanswered, Failed. |
| `duration_seconds` | on `call.ended` | Measured talk time. If absent, derived from answered→ended. |
| `agent` | inbound | Email of the answering/targeted Desk user. Must be enabled. |

Responses: `200 {"ok":true,"result":"Applied|Attached|Ignored Late|Duplicate","call":"<id>"}`; `401` bad signature/timestamp; `400` bad JSON; `422` missing/invalid fields or `client_ref` already bound to a different provider call; `503` secret not configured. Rate limit: 1200 requests/minute/IP. Retry any non-2xx. All retries are safe.

Signing example:

    import hashlib, hmac, json, time, requests
    secret = "…"; body = json.dumps({...}).encode(); ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    requests.post("https://SITE/api/method/alphax_calling.events.provider_event", data=body,
                  headers={"Content-Type": "application/json", "X-AlphaX-Timestamp": ts, "X-AlphaX-Signature": sig})

Behaviour guarantees:
- **Dedupe:** a repeated `event_id` is stored once and acknowledged as `Duplicate` (race-safe through the primary key).
- **Order tolerance:** an event that would move a call backwards is `Ignored Late` and logged.
- **Terminal states:** after the carrier's `ended`, every further event is `Ignored Late`. A completed call cannot be reversed.
- **Browser independence:** records finalise from events alone; closing the browser changes nothing.
- **Inbound matching:** normalise, match Lead mobile/phone, restrict by company when the business number maps to one. Exactly one match → linked. Zero or several → `Needs Review` with a reason; nothing is disclosed.
- **Missed inbound:** a matched, unanswered inbound call gets exactly one callback owner (Lead owner, else default owner, else review) and a ToDo.
- **Reconciliation:** hourly job sets `reconcile_flag` on carrier calls with no end event for 4 hours. A mismatch between executive status and carrier status also sets it. Reconcile by comparing with the provider's call-detail records; there is no polling of provider APIs in this version.

## 7. Browser audio and carrier integration

Not included. Recommended path, in order (brief step 2):
1. Confirm the carrier route with a softphone (two-way audio, caller ID, inbound routing, call IDs).
2. If the carrier gives a SIP trunk, bridge WebRTC↔SIP (Frappe Telephony or LiveKit SIP). The browser dialer must call `alphax_calling.api.dial_number`, pass the returned `attempt` as the provider's client reference, and use the returned E.164 number. Do not let any dialer bypass `dial_number`; it enforces permission, Do Not Contact and creates the attempt.
3. Write a small adapter that turns the provider's webhooks into the section 6 payload and signs them. Keep provider specifics in the adapter, not here.
4. Keep recording disabled. Verify hosting region and retention with the carrier (see section 9).

## 8. Data model summary (AX Lead Call)

| Group | Fields |
|---|---|
| Call | lead, company, business_line, direction, source (Manual Log / Dialer Tap / Provider Event), call_status, provider_status, spoke, outcome, note, executive, answered_by, counterparty_number, business_number |
| Timing | started_at, answered_at, ended_at, talk_seconds (forced 0 unless Answered) |
| Follow-up | callback_owner, due_at, completed_by/at, todo, demo_at, event, opportunity |
| Carrier | provider, provider_account, provider_call_id, provider_key, last_event_at, reconcile_flag |
| Control | is_final, final_source (Human/Provider), review_status/reason, reviewed_by/at, human_updated_by/at |

`call_status` values: Dialing and Ringing are live; Answered, Unanswered, Busy, Failed are final. Outcome is separate and always the executive's assessment (brief step 5).

Whitelisted methods (`alphax_calling.api.*`): `dial_number`, `log_call`, `complete_callback`, `reschedule_callback`, `my_open_callbacks`, `lead_panel`, `opportunity_calls`, `resolve_review`. All state-changing ones are POST-only except `my_open_callbacks`.

## 9. Carrier enquiry: how this app maps

Use the brief's enquiry list as is. Add these answers needed by the app:
- Can the provider echo a client reference on outbound calls (maps to `client_ref`)?
- Can webhooks be signed, or can an adapter sign them? Retry policy and maximum delay?
- Is `from`/`to` supplied in E.164 for inbound calls? Is the dialed business number supplied?
- Does `call.ended` include a measured duration and a distinct status for busy/no-answer/declined?
- Voicemail: does the provider mark it? (If not, "Answered" may include voicemail, which is why the report uses executive-confirmed conversations.)
- Data residency for metadata and any media; retention controls; ability to disable recording.

## 10. Acceptance tests (brief) mapped to this app

| Brief test | What the app provides | How to run | Needs carrier? |
|---|---|---|---|
| Outbound answered | Attempt record, normalised number, executive, Lead; talk time | Dial from a test Lead, finish call, check one record. With a carrier: send events with `client_ref`; verify one record, measured duration | Audio, caller ID: yes |
| Incoming return call | Matching inside company, `answered_by`, realtime alert to authorised agent, single record | Post `inbound` events with a test Lead's number | Routing: yes |
| Shared or unknown number | `Needs Review`, no disclosure, manager link action | Two Leads with the same number; post inbound event; check list as Sales Manager and as Sales User | No |
| Busy, unanswered, missed | Provider status preserved, talk 0, one callback owner for missed inbound | Post `ended` with `busy` / `no-answer`; inbound unanswered | Real statuses: yes |
| Callback and conversion | Idempotent callback, one ToDo, Opportunity link, one count in report | Save twice; create Opportunity from Lead; check Opportunity button and report | No |
| Retry or browser closure | Duplicate/late events ignored; finalisation without browser | Replay events; close browser mid-call; `test_provider_events_dedupe_and_late` | No |
| Access control | Lead-permission filtering in panel, reports, notifications, review list | Restricted Lead per executive; verify panel, both reports, alerts, AX Lead Call list | No |

Retain per test: app versions, anonymised call IDs, observed results. Sign-off needs the automated suite green plus the carrier-dependent items.

### Extra checks to run on first deploy
1. Install and `migrate` complete; AX Lead Call, AX Call Event and both reports exist.
2. Delete a test Lead that has calls; deletion succeeds and its calls disappear.
3. A `Dialer Tap` double click yields one attempt.
4. Arabic user sees translated menu.
5. Overdue notification arrives within 15 minutes of a due time (scheduler must be enabled: `bench --site SITE enable-scheduler`).
6. Reports with 0 rows render without error.

## 11. Known limits and assumptions to verify

- Dial outcome of a `tel:` link cannot be observed; attempts remain "Dialing" until the executive logs them or a carrier event arrives. They show under *Awaiting executive update*.
- `ignore_links_on_delete` and `on_trash` ordering are both used so that Lead deletion works regardless of the exact Frappe delete sequence; verify with extra check 2.
- Reports cap at 20,000 calls per query and say so. Use date filters.
- Same-number matching uses SQL `REPLACE` over mobile/phone and a last-9-digit `LIKE`; very large Lead tables may need an indexed normalised number field (roadmap).
- Arabic-Indic digits in Lead phone fields are normalised for dialing but not by the SQL pre-filter during inbound matching.
- No prayer-time logic; the call window is a simple advisory range.
- No agent-presence, queueing, IVR or recording. No WhatsApp calling (evaluate separately per the brief).
- Booking a demo does not check the executive's calendar for conflicts.

## 12. Operations

- Scheduler jobs: every 15 min overdue notifications; hourly stale-carrier flag; daily event purge. Check *Scheduled Job Log*.
- Errors: *Error Log* titled "AlphaX Calling…". Webhook failures show as non-2xx at the provider; the cause is in the response body.
- Backups: include `tabAX Lead Call` and `tabAX Call Event`. Raw events contain phone numbers: handle under the company's privacy policy and Saudi PDPL obligations (confirm with legal).
- Secret rotation: change `alphax_calling_webhook_secret`, update the adapter, in that order within the 5-minute window or briefly accept failures and retries.

## 13. Roadmap (after pilot feedback)

Browser audio via WebRTC/SIP adapter; provider-detail reconciliation job; indexed normalised phone field on Lead; browser meeting links; Chatwoot conversations; dictated call notes; per-hour answer-rate insights; manager escalation for callbacks overdue more than 24 hours.
