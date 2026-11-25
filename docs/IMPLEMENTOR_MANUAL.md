# AlphaX Calling: Implementor Manual

For implementation leads, Frappe developers, telephony engineers and QA · Version 0.4.0 · Target: Frappe/ERPNext v15

## 0. Verification status (read first)

| Layer | Status |
|---|---|
| Pure logic (`utils.py`, `twilio_utils.py`: phone normalisation, scheduling, signatures, event state machine, Twilio token/signature/TwiML/status mapping) | 24 unit tests pass: `python -m unittest alphax_calling.tests.test_utils alphax_calling.tests.test_twilio_utils alphax_calling.tests.test_tools`. The Twilio request-signature code reproduces Twilio's documented example value. |
| Python/JS/JSON syntax | pyflakes, compileall, `node --check`, JSON validation all clean |
| Frappe-bound code (API, reports, hooks, doctypes, webhook) | **Not executed on a live bench by the author.** Written against Frappe v15 APIs. An integration suite is provided (`tests/test_calling.py`) and must be run on staging as the first acceptance step. |
| Twilio adapter and browser softphone (`twilio_adapter.py`, `softphone.js`) | Written, **never run against a live Twilio account or browser**. See section 7A for what to verify. |
| Settings form, readiness checks, connection tests, bridge-config endpoint, workspace (`setup.py`, `config.py`, settings DocType) | Written, **not executed on a bench**. Covered by `TestSettings` in the integration suite. |
| Production Saudi carrier, caller ID, SIP trunk | Out of scope. Needs a CST-licensed carrier contract (section 7A.1). |

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
    git init && git add . && git -c user.name=i -c user.email=i@localhost commit -m "AlphaX Calling v0.4.0"
    cd /abs/path/frappe-bench
    bench get-app file:///abs/path/alphax_calling
    bench --site SITE install-app alphax_calling
    bench --site SITE migrate
    bench build --app alphax_calling
    bench --site SITE clear-cache
    bench --site SITE run-tests --app alphax_calling --module alphax_calling.tests.test_calling

Serve Desk over HTTPS. Managed hosting: push to an authorised Git repository and use the provider's custom-app flow. Upgrade: `bench update --apps alphax_calling` then `migrate`. Rollback: check out the previous tag, `migrate`, `bench build`. New fields are additive; removing the app leaves `tabAX Lead Call` data in place.

## 4. Configuration: the AX Calling Settings form

Everything is configured in the app: **Desk → AlphaX Calling → Settings** (a workspace with shortcuts is created on install/migrate). Only System Manager can open it. Secrets use encrypted Password fields. The older `site_config.json` keys still work as a fallback when the form field is empty.

| Section | What you enter |
|---|---|
| General | Calling enabled (master switch), **Provider** (Manual / Twilio / Carrier SIP Bridge), default country code, Public HTTPS URL (only behind a proxy), call window and weekend (default 09:00-21:00, Fri-Sat), do-not-call field, default callback owner, missed-call callback minutes, event retention days |
| Business numbers (table) | Number, business line, company, caller ID registered to the company, provider reference (Twilio phone SID or trunk/DID), inbound owner, active. Numbers scope inbound matching and fill the reports |
| Twilio | Account SID, Auth token, API key SID and secret, TwiML App SID, caller ID. Prefix checks (AC, SK, AP) and E.164 normalisation on save |
| Carrier SIP Bridge | Signing secret (Generate secret button), SIP server, port, transport, authentication (IP allow-list or registration), username, password, outbound proxy, carrier IP addresses, codecs, concurrent channels, support contact |
| Addresses to give the provider | The exact Voice URL, status URL, provider-event URL and bridge-config URL for this site |
| Carrier, compliance and data | Licensed carrier, contract reference, route tested, hosting region, retention confirmed, privacy/PDPL review done. Recording is fixed at "disabled" |
| Acceptance and release | Tested versions (Capture versions button), the seven acceptance tests with result, tester, date, anonymised call IDs and observed result, pilot approval |
| Readiness | Live checklist (below) |

### Buttons
- **Setup guide**: provider choice, Twilio steps with your real URLs, carrier enquiry list, bridge steps, go-live, troubleshooting.
- **Check readiness**: scheduler, HTTPS, time zone, master switch, provider fields, business numbers, default owner, compliance records, recording off, last test, events in 24 h, review queue, reconciliation flags, acceptance results, approval. Statuses: ok, warn, fail. `ready` is true only with no failed check and all seven tests passed.
- **Actions → Test connection**: Twilio: account and token, API key and TwiML App, Voice URL equals this site's URL, caller ID owned or verified. Bridge: secret strength, signature round-trip, and a full event-pipeline dry run that is rolled back.
- **Actions → Generate secret**: stores a new signing secret and shows it once.
- **Actions → Capture versions**: frappe, erpnext, app, Python, time zone.
- **Actions → Approve pilot**: refuses unless `ready`.

### Fallback site_config keys
`alphax_calling_do_not_call_field`, `alphax_calling_call_window`, `alphax_calling_weekend_days`, `alphax_calling_default_country_code`, `alphax_calling_default_callback_owner`, `alphax_calling_missed_callback_minutes`, `alphax_calling_business_lines`, `alphax_calling_webhook_secret`, `alphax_calling_twilio`, `alphax_calling_public_url`, `alphax_calling_event_retention_days`. Prefer the form. Set the site time zone (System Settings) to Asia/Riyadh.

### The bridge pulls its carrier settings from the app
`GET /api/method/alphax_calling.setup.bridge_config` with the same signature headers (empty body) returns the carrier SIP details (including the SIP password), business numbers and the event URL. `tools/alphax_fetch_config.py` does this. Carrier details are therefore entered once, in the app.

### Tools (folder `tools/`, standard library only)
- `alphax_send_event.py`: sends signed scenarios (`inbound-answered`, `inbound-missed`, `outbound-answered`, `outbound-busy`, `outbound-noanswer`) or replays one event to prove deduplication. Use it for carrier certification and acceptance tests 2-6 before real traffic exists.
- `alphax_fetch_config.py`: signed fetch of the bridge settings.
- `asterisk/`: a PJSIP trunk template and notes (untested starting point).

### Provider-switch procedure (pilot to production)
1. Collect the carrier answers with the Setup guide enquiry list; enter them in the compliance and carrier sections.
2. Switch Provider to Carrier SIP Bridge; fill the SIP fields and business numbers; Generate secret.
3. Build/configure the bridge; verify with `alphax_send_event.py`; Test connection.
4. Re-run the seven acceptance tests on the real route; record evidence; Capture versions; Check readiness; Approve pilot.
5. Existing history is unchanged: calls from both providers live in the same record type.

## 5. Roles and permissions

| Role | Access |
|---|---|
| Sales User | Lead form actions need Lead **write**. Reports are visible. Cannot open AX Lead Call records. |
| Sales Manager | Reports; sees and resolves **review items only** (calls with no Lead) in the AX Lead Call list. |
| System Manager | Full access to AX Lead Call, AX Call Event and the Settings form (only role that can open it). |

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

Browser audio is included only through the Twilio trial adapter (section 7A). For production the recommended path, in order (brief step 2):
1. Confirm the carrier route with a softphone (two-way audio, caller ID, inbound routing, call IDs).
2. If the carrier gives a SIP trunk, bridge WebRTC↔SIP (Frappe Telephony or LiveKit SIP). The browser dialer must call `alphax_calling.api.dial_number`, pass the returned `attempt` as the provider's client reference, and use the returned E.164 number. Do not let any dialer bypass `dial_number`; it enforces permission, Do Not Contact and creates the attempt.
3. Write a small adapter that turns the provider's webhooks into the section 6 payload and signs them. Keep provider specifics in the adapter, not here.
4. Keep recording disabled. Verify hosting region and retention with the carrier (see section 9).

## 7A. Carrier recommendation and the included browser-calling solution

### 7A.1 Honest answer on "free"
There is **no free production carrier for Saudi Arabia**. Voice that reaches the Saudi phone network must go through a CST-licensed operator (stc, Mobily, Zain and licensed resellers such as Salam). Carriers say unlicensed international SIP for local Saudi numbers risks interruption, and spoofed or unregistered caller IDs are blocked, so the caller ID must be a number registered to your company. Typical programmable-number limits: an 05 mobile number cannot be bought as a programmable SIP number; geographic, 9200 and 800 numbers are the options. Publicly advertised starting prices quoted on a third-party comparison page (confirm directly with each carrier): Mobily Business SIP trunk about SAR 747.50 one-time plus SAR 598/month for 3 channels and 5 landline numbers; stc Business from about SAR 2,300 setup plus SAR 1,150/month for 10 extensions. Some wholesale offers require 12-month contracts. Compliance, KYC (commercial registration and local address) and lead time are the real work.

**Recommendation**
| Purpose | Choice | Cost |
|---|---|---|
| Prove the whole flow now (browser audio, events, callbacks, reports) | **Twilio trial** (included adapter) | Free: 30 days, no card |
| Production for the Saudi business number | A **CST-licensed SIP trunk** from stc Business, Mobily Business or Zain Business (ask all three the brief's enquiry questions), bridged to the browser with open-source **LiveKit SIP**, **Asterisk** or **FreeSWITCH** | Carrier fees; the bridge software is free |

Twilio trial limits that matter: calls and inbound only to/from **verified numbers** (up to 5, SMS verification), caller ID is the trial number or a verified number, the trial expires after 30 days, and destination countries are controlled by Geo permissions (enable Saudi Arabia and confirm). Twilio's regulatory guidelines list only toll-free (+966 800) numbers for Saudi Arabia, so do not expect a Saudi local business number from Twilio. The trial therefore proves audio, events and workflow; it cannot show your Saudi business number as caller ID. A Telnyx trial (USD 5 credit) is more restrictive: one verified number. Re-check all limits at sign-up, they change.

### 7A.2 What is included
- `twilio_adapter.get_token`: issues a short-lived browser access token (identity = hex of the Desk user).
- `twilio_adapter.voice`: Twilio's Voice webhook. **Outbound** from the browser: dials only the exact attempt created by `dial_number` for that user and number within 5 minutes (prevents a token holder dialing arbitrary numbers). **Inbound**: matches the caller inside the company, rings the Lead owner's browser (else the default callback owner), and records a missed call with a callback owner if nobody can be rung.
- `twilio_adapter.status`: Twilio status callbacks, translated by `twilio_utils.canonical_event` into the section 6 events and processed by the same pipeline (dedupe, ordering, terminal states). Twilio's per-leg events use `ParentCallSid` as the call ID.
- Every webhook verifies `X-Twilio-Signature`. Browser SDK v2.19.0 (Apache-2.0) is bundled under `public/js/vendor/`, no CDN needed.
- Lead buttons switch to the browser softphone when configured (**Call mobile with phone app** keeps `tel:`). After hang-up the outcome form opens. A small panel handles mute, hang up and incoming calls.
- Recording is never requested.

### 7A.3 Setup (staging)
1. Create the Twilio trial. Verify up to five test mobiles (the executives' real Saudi numbers). Obtain the trial phone number (this is the caller ID).
2. Console → Voice → Geo permissions: enable Saudi Arabia.
3. Create an **API key** (note SID and secret). Note Account SID and Auth Token.
4. Create a **TwiML App** with Voice Request URL `https://SITE/api/method/alphax_calling.twilio_adapter.voice`, method POST. Note its SID.
5. Optional for inbound tests: on the trial number set "A call comes in" to the same URL (webhook, POST). In trial, only verified numbers can call in.
6. Open **AlphaX Calling → Settings**, set Provider to Twilio, enter the Twilio fields and the caller ID, add the business number row, save, then press **Test connection** and **Check readiness**. Set `host_name` to the `https://` address (or fill Public HTTPS URL if behind a proxy).
7. Reload Desk. The browser asks for microphone permission on the first call. Test: Lead with a verified Saudi mobile → Calling → Call mobile.

Secrets are stored encrypted by Frappe. Never put them in Git. Turn on Twilio usage alerts and keep Geo permissions limited to Saudi Arabia.

### 7A.4 Verify on first run (not testable without Twilio)
1. Signature validation passes (if 403 behind a proxy, set `alphax_calling_public_url` so the URL matches what Twilio calls exactly).
2. The webhook returns XML (the adapter uses Frappe's raw download response with `inline` disposition; confirm Twilio does not report "invalid TwiML").
3. One outbound answered call gives one AX Lead Call with measured duration; `provider_call_id` is the Twilio parent SID.
4. Busy / no-answer / declined map to Busy / Unanswered; talk time zero.
5. Inbound from a verified number rings the Lead owner's open Desk tab; with Desk closed it records a missed call and creates a callback ToDo.
6. A replayed status callback shows `Duplicate` in AX Call Event.
7. SDK events (`accept`, `disconnect`, `incoming`, `customParameters`) behave as coded in `softphone.js`.

### 7A.5 Moving to production
Keep `dial_number`, the event contract (section 6) and all UI. Replace the Twilio adapter with: licensed trunk → SBC/bridge (LiveKit SIP, Asterisk or FreeSWITCH) → browser (SIP.js/WebRTC), and a small service that posts signed section 6 events with the attempt ID as `client_ref`. Nothing else in the app changes. Decide recording, hosting region and retention with the carrier before go-live.

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
