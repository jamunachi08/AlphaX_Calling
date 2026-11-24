# AlphaX Calling v0.1.0

A standalone Frappe app targeting ERPNext v15. Open a saved Lead and use the Calling menu. Call mobile and Call phone launch the device's registered telephone handler. An installed and provisioned softphone can handle the call. Log call is a separate, explicit action. Incoming calls can also be logged manually. No carrier account is bundled.

## Install on staging

Extract the ZIP. The directory containing pyproject.toml is the app repository root. To install directly from the extracted source with Bench, initialize a local Git repository there (skip initialization if using an existing Git checkout).

    cd /absolute/path/to/alphax_calling
    git init
    git add .
    git -c user.name="Staging Installer" -c user.email="installer@localhost" commit -m "AlphaX Calling v0.1.0"
    cd /absolute/path/to/frappe-bench
    bench get-app file:///absolute/path/to/alphax_calling
    bench --site YOUR-STAGING-SITE install-app alphax_calling
    bench build --app alphax_calling
    bench --site YOUR-STAGING-SITE clear-cache

Use HTTPS for Desk. Browser-generated UUIDs identify a single submission during a retry. A functioning telephone handler is needed only to test dialing. The remaining workflow can be tested with fictional Leads. For managed hosting, import the extracted app into an authorized Git repository and install through the provider's custom app workflow.

## Configure and use

If the implementation has a Lead do-not-call Check field, map its actual fieldname using the site setting below. A checked field blocks the app's dial action. A configured field that does not exist also blocks dialing. Without this mapping, dialing follows Lead write permission alone.

    bench --site YOUR-STAGING-SITE set-config alphax_calling_do_not_call_field custom_do_not_call

Call notes, direction and reported result appear in the standard Lead timeline as a comment from the signed-in user. The call ID also identifies the structured AX Lead Call record used for reporting. Callback requested requires a future date and an active owner with write permission on the Lead. The owner sees the commitment in AX Callback Queue and closes it from the Lead's Calling menu. Demo agreed records the outcome only.

Open AX Executive Calls in the Desk search to see counts for the rolling 30 days, grouped by the executive who logged the call, across Leads the viewer may read. Report access is configured for Sales User, Sales Manager and System Manager. The reported answer count is user-entered. The system does not measure audio, phone network status or duration.

## Staging smoke test

1. Create a test Lead with a test number. Give two test sales executives write access to the Lead. Keep a second Lead restricted to one executive.
2. Open Calling → Call mobile and verify the configured phone handler receives the saved number. If you mapped a do-not-call field, enable it and confirm the dial action is blocked.
3. Log an outbound call with Callback requested, assign the other executive, and choose a future time. Verify one entry in the timeline and one callback in the recipient's queue.
4. Sign in as the recipient. Complete the callback on the Lead and verify the queue clears. Verify the completion entry is attributed to the recipient.
5. Log an inbound call. Check the executive report, including the restricted Lead case, and verify that removing Lead access also removes its rows from reports.

## Next integration milestone

Evaluate the deployed neotec_voice and Frappe Telephony versions on staging. Select one provider call log as the authoritative source for carrier calls and link manual call records explicitly if reconciled. Next integrations are authenticated event delivery, browser audio, inbound caller matching and measured talk time. Carrier integration, recordings, WhatsApp and automatic Opportunity links are outside v0.1.0.
