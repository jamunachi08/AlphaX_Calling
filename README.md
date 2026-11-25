# AlphaX Calling v0.2.0

Lead calling, callbacks and call history for ERPNext v15 (Frappe v15). Standalone Frappe app; no carrier account is bundled.

**Works today (no carrier needed):** KSA-aware number normalisation, tap-to-dial with a recorded attempt, guarded dialing
(Do Not Contact, call window, shared numbers, repeated no-answer), manual call logging, outcomes, callbacks with ToDo and
overdue alerts, demo → Event, Lead call banner and history, Opportunity link, manager reports, Arabic UI strings.

**Ready for the carrier:** signed, idempotent provider-event endpoint (`alphax_calling.events.provider_event`) with
inbound matching, review queue, missed-call callback ownership and reconciliation flags.

**Not included:** browser audio (WebRTC/SIP), recordings, WhatsApp calling. See the Implementor Manual for the adapter contract.

Documentation: `docs/USER_MANUAL.md` · `docs/IMPLEMENTOR_MANUAL.md` · `CHANGELOG.md`

## Quick install (staging)

    cd /absolute/path/to/alphax_calling && git init && git add . && git -c user.name=i -c user.email=i@localhost commit -m "AlphaX Calling v0.2.0"
    cd /absolute/path/to/frappe-bench
    bench get-app file:///absolute/path/to/alphax_calling
    bench --site YOUR-SITE install-app alphax_calling
    bench --site YOUR-SITE migrate && bench build --app alphax_calling && bench --site YOUR-SITE clear-cache

Pure-logic tests (no bench): `python -m unittest alphax_calling.tests.test_utils`
