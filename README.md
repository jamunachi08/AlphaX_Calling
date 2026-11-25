# AlphaX Calling v0.4.0

Lead calling, callbacks and call history for ERPNext v15 (Frappe v15). Standalone Frappe app; no carrier account is bundled.

**Works today (no carrier needed):** KSA-aware number normalisation, tap-to-dial with a recorded attempt, guarded dialing
(Do Not Contact, call window, shared numbers, repeated no-answer), manual call logging, outcomes, callbacks with ToDo and
overdue alerts, demo → Event, Lead call banner and history, Opportunity link, manager reports, Arabic UI strings.

**Ready for the carrier:** signed, idempotent provider-event endpoint (`alphax_calling.events.provider_event`) with
inbound matching, review queue, missed-call callback ownership and reconciliation flags.

**Everything is configured inside the app:** open *AlphaX Calling → Settings*. Pick a provider, fill its fields, press Test connection and Check readiness. The form holds the carrier SIP details, business numbers, compliance records, acceptance evidence and the go-live approval; it also has a built-in setup guide.

**Browser calling (free pilot):** Twilio trial adapter with a bundled WebRTC softphone (Implementor Manual §7A). No free carrier exists for production in Saudi Arabia; production needs a CST-licensed SIP trunk (stc, Mobily, Zain) with an open-source bridge.

**Not included:** production SIP bridge, recordings, WhatsApp calling.

Documentation: `docs/USER_MANUAL.md` · `docs/IMPLEMENTOR_MANUAL.md` · `CHANGELOG.md`

## Quick install (staging)

    cd /absolute/path/to/alphax_calling && git init && git add . && git -c user.name=i -c user.email=i@localhost commit -m "AlphaX Calling v0.4.0"
    cd /absolute/path/to/frappe-bench
    bench get-app file:///absolute/path/to/alphax_calling
    bench --site YOUR-SITE install-app alphax_calling
    bench --site YOUR-SITE migrate && bench build --app alphax_calling && bench --site YOUR-SITE clear-cache

Pure-logic tests (no bench): `python -m unittest alphax_calling.tests.test_utils alphax_calling.tests.test_twilio_utils alphax_calling.tests.test_tools`
