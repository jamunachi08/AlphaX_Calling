frappe.ui.form.on("AX Calling Settings", {
    async refresh(frm) {
        const api = "alphax_calling.setup.", esc = s => frappe.utils.escape_html(s == null ? "" : String(s));
        if (frm.is_new()) return;

        const renderUrls = async () => {
            const u = await frappe.xcall(api + "get_urls");
            const row = (l, v) => `<tr><td><b>${esc(l)}</b></td><td><code style="user-select:all">${esc(v)}</code></td></tr>`;
            frm.set_df_property("urls_html", "options", `<table class="table table-bordered table-sm">
                ${row(__("Twilio Voice URL (TwiML App and number), POST"), u.twilio_voice)}
                ${row(__("Twilio status callbacks (set automatically)"), u.twilio_status)}
                ${row(__("Provider events (bridge posts here), POST"), u.provider_events)}
                ${row(__("Bridge settings (signed GET)"), u.bridge_config)}</table>`);
            frm.refresh_field("urls_html");
        };
        const renderReady = async () => {
            const r = await frappe.xcall(api + "readiness");
            const color = {ok: "green", warn: "orange", fail: "red"}, icon = {ok: "✔", warn: "!", fail: "✖"};
            const rows = r.checks.map(c => `<tr><td style="color:var(--${color[c.status]}-500);width:24px"><b>${icon[c.status]}</b></td>
                <td><b>${esc(c.label)}</b><br><span class="text-muted">${esc(c.detail)}</span>
                ${c.status !== "ok" && c.fix ? `<br><i>${esc(c.fix)}</i>` : ""}</td></tr>`).join("");
            const head = r.ready ? __("Ready: all acceptance tests passed and no check has failed.")
                : __("Not ready: {0} failed, {1} to review.", [r.summary.fail, r.summary.warn]);
            frm.set_df_property("readiness_html", "options", `<p><b>${esc(head)}</b></p><table class="table table-bordered table-sm">${rows}</table>`);
            frm.refresh_field("readiness_html");
        };
        const guide = async () => {
            const g = await frappe.xcall(api + "guide");
            frappe.msgprint({title: __("Setup guide"), wide: true, message: g.map(s =>
                `<h5>${esc(s.title)}</h5><ul>${s.body.map(b => `<li>${esc(b)}</li>`).join("")}</ul>`).join("")});
        };
        const call = (method, after) => async () => { const r = await frappe.xcall(api + method); await after(r); };

        frm.add_custom_button(__("Setup guide"), guide);
        frm.add_custom_button(__("Check readiness"), () => renderReady().then(() => frm.scroll_to_field("readiness_html")));
        frm.add_custom_button(__("Test connection"), call("test_connection", async r => {
            frappe.msgprint({title: r.ok ? __("Connection test passed") : __("Connection test failed"), indicator: r.ok ? "green" : "red",
                message: r.steps.map(x => `${x.ok ? "✔" : "✖"} <b>${esc(x.step)}</b> ${esc(x.detail)}`).join("<br>")});
            await frm.reload_doc();
        }), __("Actions"));
        frm.add_custom_button(__("Generate secret"), () => frappe.confirm(
            __("Create a new signing secret? The bridge must be updated with it."),
            call("generate_secret", async v => {
                frappe.msgprint({title: __("Copy the secret now"), message: `<code style="user-select:all;word-break:break-all">${esc(v)}</code><br><br>${__("It is stored encrypted and will not be shown again.")}`});
                await frm.reload_doc();
            })), __("Actions"));
        frm.add_custom_button(__("Capture versions"), call("capture_versions", async () => frm.reload_doc()), __("Actions"));
        frm.add_custom_button(__("Approve pilot"), () => frappe.confirm(
            __("Approve the limited sales pilot?"), call("approve_pilot", async () => frm.reload_doc())), __("Actions"));

        await Promise.all([renderUrls(), renderReady()]).catch(() => {});
    },
});
