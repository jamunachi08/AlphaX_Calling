window.alphax_calling = {
    esc: s => frappe.utils.escape_html(s == null ? "" : String(s)),
    uuid() {
        if (window.crypto && crypto.randomUUID) return crypto.randomUUID();  // needs HTTPS
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
            const r = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
            return (c === "x" ? r : (r & 3) | 8).toString(16);
        });
    },
    show_history(panel, title) {
        const e = this.esc, rows = (panel.history || []).map(r => `<tr>
            <td>${e(frappe.datetime.str_to_user(r.creation))}</td><td>${e(__(r.direction))}</td>
            <td>${e(__(r.call_status))}${r.reconcile_flag ? " ⚠" : ""}</td><td>${e(r.outcome ? __(r.outcome) : "")}</td>
            <td>${e(r.executive_name)}</td><td>${r.spoke ? "✔" : ""}</td>
            <td>${r.talk_seconds ? Math.round(r.talk_seconds / 6) / 10 : ""}</td>
            <td>${r.callback_owner ? e(r.owner_name) + " · " + e(frappe.datetime.str_to_user(r.due_at)) + (r.completed_at ? " ✔" : "") : ""}</td></tr>`).join("");
        frappe.msgprint({title: title || __("Call history"), wide: true, message: rows ? `<div style="overflow-x:auto"><table class="table table-bordered table-sm">
            <thead><tr><th>${__("When")}</th><th>${__("Direction")}</th><th>${__("Result")}</th><th>${__("Outcome")}</th>
            <th>${__("Executive")}</th><th>${__("Spoke")}</th><th>${__("Minutes")}</th><th>${__("Callback")}</th></tr></thead>
            <tbody>${rows}</tbody></table></div>` : __("No calls recorded.")});
    },
};

frappe.realtime.on("alphax_incoming_call", d => {
    frappe.show_alert({message: __("Incoming call: {0}", [alphax_calling.esc(d.lead_name || d.lead)]) + " " +
        frappe.utils.get_form_link("Lead", d.lead, true, __("Open Lead")), indicator: "green"}, 30);
});
