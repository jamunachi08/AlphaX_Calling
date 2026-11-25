# Asterisk starting templates (NOT tested against a carrier)

These are a starting point for the bridge between a CST-licensed SIP trunk and the browser. Fill the values from
AlphaX Calling Settings (or `tools/alphax_fetch_config.py`). Adapt to what the carrier specifies (many Saudi carriers
use IP authentication, not registration; ask which codecs and which source IPs they use).

Pieces you still have to build or choose:
1. **Browser leg**: WebRTC endpoints in Asterisk (SIP.js in the browser), or LiveKit SIP. The Lead's Call button must call
   `alphax_calling.api.dial_number`, then place the call and carry the returned `attempt` id as the call's client reference.
2. **Event forwarder**: a small service listening to Asterisk (ARI/AMI) or LiveKit webhooks and posting signed events to
   the provider-event URL. Mapping: channel created = call.initiated, ringing = call.ringing, answered = call.answered,
   hangup = call.ended (status completed / busy / no-answer / failed / cancelled / declined, duration_seconds).
   Validate it first with `tools/alphax_send_event.py`.
3. **Security**: TLS for SIP/WebRTC, firewall to the carrier IPs, fail2ban, recording disabled, in-country media if the
   carrier requires it.
