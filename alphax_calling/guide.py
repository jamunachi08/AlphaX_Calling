"""In-app guidance: everything an implementor needs to take a provider from contract to go-live."""
import frappe
from frappe import _

ACCEPTANCE = [
    ("Outbound answered", "Saudi test mobile rings, caller ID is correct, audio works both ways, and exactly one outbound record shows the correct Lead, executive and duration."),
    ("Incoming return call", "The same business number accepts the call. The correct authorized agent sees the matching Lead, and one incoming record identifies the answering user."),
    ("Shared or unknown number", "The application requests a match or queues review. It discloses no inaccessible Lead."),
    ("Busy, unanswered and missed", "Provider status is preserved, talk time is zero and a missed inbound call has one identifiable callback owner."),
    ("Callback and conversion", "Saving the callback twice creates one commitment. After Lead conversion, the Opportunity displays the existing call and the manager report counts it once."),
    ("Retry or browser closure", "Replayed events and a closed browser still yield one finalized record. Late events cannot reverse a completed call."),
    ("Access control", "Users with restricted Lead access receive the same restrictions in search, timeline, reports, exports and inbound notifications."),
]


def urls(base=None):
    from alphax_calling.config import get_settings
    base = (base or get_settings().public_url or frappe.utils.get_url()).rstrip("/")
    m = base + "/api/method/alphax_calling."
    return {"base": base, "twilio_voice": m + "twilio_adapter.voice", "twilio_status": m + "twilio_adapter.status",
            "provider_events": m + "events.provider_event", "bridge_config": m + "setup.bridge_config"}


def get_guide():
    u = urls()
    return [
        {"title": _("1. Choose the route"), "body": [
            _("There is no free production carrier for Saudi Arabia. Voice that reaches the Saudi phone network must go through a CST-licensed operator (stc, Mobily, Zain or a licensed reseller such as Salam)."),
            _("Pilot (free): choose Twilio. A 30-day trial supports browser calling to up to five verified numbers. It cannot present your Saudi business number."),
            _("Production: choose Carrier SIP Bridge. Contract a CST-licensed SIP trunk, run a bridge (LiveKit SIP, Asterisk or FreeSWITCH) and let it post signed events to this app."),
            _("Manual: no provider. Executives dial with their phone or softphone and log the result.")]},
        {"title": _("2. Twilio trial setup"), "body": [
            _("Create the trial account. Verify the executives' test mobiles (maximum five)."),
            _("Console, Voice, Geo permissions: enable Saudi Arabia."),
            _("Create an API key. Copy the Account SID, Auth token, API key SID and API key secret into the Twilio section here."),
            _("Create a TwiML App. Voice Request URL: {0} (POST). Copy its SID here.").format(u["twilio_voice"]),
            _("Optional, for inbound tests: on the trial number set 'A call comes in' to {0} (POST).").format(u["twilio_voice"]),
            _("Enter the trial number as Caller ID. Save. Press Test connection, then Check readiness."),
            _("Allow the microphone when the browser asks, then call a verified mobile from a Lead.")]},
        {"title": _("3. Carrier enquiry (send to stc, Mobily, Zain or a licensed reseller)"), "body": [
            _("Can you provision a Saudi business number for incoming and outgoing calls from an ERPNext browser dialer?"),
            _("Supported SIP or browser integration, authentication method (IP allow-list or registration), test-number availability and onboarding lead time."),
            _("Outbound caller ID rules and registration, inbound routing, concurrent call limit, handling of busy or unanswered calls."),
            _("How do we receive call identifiers, answer and end timestamps, call status and call-detail records for reconciliation? Can webhooks be sent, and with what retry policy?"),
            _("Does the call-ended event carry a measured duration and distinct busy, no-answer and declined statuses? Is voicemail flagged?"),
            _("Are caller and called numbers delivered in E.164? Can the provider return a client reference we pass on outbound calls?"),
            _("One-time setup, monthly number and channel fees, per-minute tariffs, contract minimum term, support coverage and service responsibilities."),
            _("Media and metadata hosting regions, retention controls and the ability to disable recording."),
            _("Which company documents are required (typically commercial registration, national address and authorised signatory details; confirm with the carrier)?"),
            _("Record every answer in the Carrier and compliance section and the SIP details below.")]},
        {"title": _("4. Carrier SIP Bridge setup"), "body": [
            _("Select Carrier SIP Bridge. Fill the carrier SIP fields, business numbers (with company and whether the caller ID is registered) and compliance fields."),
            _("Press Generate secret and give it to the bridge operator. Never e-mail it; use a password manager."),
            _("The bridge posts signed JSON events to {0}. Header X-AlphaX-Timestamp (Unix seconds) and X-AlphaX-Signature (hex HMAC-SHA256 of timestamp + '.' + raw body).").format(u["provider_events"]),
            _("The bridge can fetch its SIP settings from {0} with the same signature (GET, empty body), so carrier details live only here.").format(u["bridge_config"]),
            _("For outbound calls the bridge must pass the attempt id created by Dial as client_ref and the same id back in every event."),
            _("Event mapping: call setup = call.initiated, ringing = call.ringing, answer = call.answered, hangup = call.ended with status completed, busy, no-answer, failed, cancelled or declined and duration_seconds."),
            _("Use tools/alphax_send_event.py to send test events before connecting real traffic. Press Test connection for an in-app pipeline self-test."),
            _("Keep recording disabled. Confirm hosting region and retention with the carrier.")]},
        {"title": _("5. Acceptance and go-live"), "body": [
            _("Run each acceptance test on staging with approved test numbers. Record the result, tester, date and anonymised call IDs in the Acceptance evidence table."),
            _("Press Capture versions, fill the carrier route, then Check readiness. Every failure must be cleared."),
            _("When all seven tests pass and readiness has no failures, press Approve pilot. Start with one company, one business number and two executives.")]},
        {"title": _("6. Troubleshooting"), "body": [
            _("Twilio webhook returns 403: the public URL differs from the one Twilio calls. Set Public HTTPS URL."),
            _("Browser does not ring: the Desk tab must stay open; check microphone permission and that Provider is Twilio and saved."),
            _("Event returns 401: wrong secret or clock more than 5 minutes off. Check server time."),
            _("Event returns 422: a required field is missing or client_ref belongs to another call."),
            _("Calls stay Dialing: no end event arrived. They are flagged for reconciliation after 4 hours."),
            _("Inbound calls go to review: the number is unknown or shared. A Sales Manager links them from the AX Lead Call list.")]},
    ]
