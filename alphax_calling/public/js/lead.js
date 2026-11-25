frappe.ui.form.on("Lead", {
    refresh(frm) {
        if (frm.is_new() || !frm.perm[0]?.read) return;
        const api = "alphax_calling.api.", lead = frm.doc.name, ax = alphax_calling;
        const menu = __("Calling");
        const panel = () => frappe.xcall(api + "lead_panel", {lead});

        const banner = p => {
            try {
                frm.dashboard.clear_headline();
                const s = p.summary, lines = [];
                if (s.attempts) lines.push(__("Calls: {0} · Answered: {1} · Open callbacks: {2} ({3} overdue)",
                    [s.attempts, s.answered, s.open_callbacks, s.overdue_callbacks]));
                if (p.pending.length) lines.push(__("{0} call(s) are waiting for your outcome. Use Calling → Log call.", [p.pending.length]));
                (p.advice || []).slice(0, 2).forEach(a => lines.push(a));
                if (lines.length) frm.dashboard.set_headline_alert(lines.map(ax.esc).join("<br>"),
                    s.overdue_callbacks || s.streak >= 3 ? "red" : p.pending.length ? "orange" : "blue");
            } catch (e) { /* banner is optional */ }
        };
        panel().then(banner).catch(() => {});

        frm.add_custom_button(__("Call history"), async () => ax.show_history(await panel()), menu);
        if (!frm.perm[0]?.write) return;

        const log_dialog = (p, pending) => {
            const locked = !!(pending && pending.final_source === "Provider");
            const request_id = pending ? pending.name : ax.uuid();
            const cb = "eval:doc.outcome=='Callback requested' || doc.schedule_callback";
            const dialog = new frappe.ui.Dialog({
                title: pending ? __("Record the outcome of your call") : __("Log a call"),
                fields: [
                    {fieldname: "direction", label: __("Direction"), fieldtype: "Select", options: "Outbound\nInbound",
                        reqd: 1, default: pending ? pending.direction : "Outbound", read_only: locked ? 1 : 0},
                    {fieldname: "call_status", label: __("Reported result"), fieldtype: "Select", reqd: 1,
                        options: "\nAnswered\nUnanswered\nBusy\nFailed", default: locked ? pending.call_status : "",
                        read_only: locked ? 1 : 0},
                    {fieldname: "spoke", label: __("I spoke with the customer"), fieldtype: "Check",
                        depends_on: "eval:doc.call_status=='Answered'"},
                    {fieldname: "talk_minutes", label: __("Talk time (minutes)"), fieldtype: "Float",
                        depends_on: locked ? "eval:0" : "eval:doc.call_status=='Answered'"},
                    {fieldname: "outcome", label: __("Outcome"), fieldtype: "Select",
                        options: "\nCallback requested\nDemo agreed\nInformation sent\nWrong number\nNo interest"},
                    {fieldname: "demo_at", label: __("Demo date and time"), fieldtype: "Datetime",
                        depends_on: "eval:doc.outcome=='Demo agreed'", mandatory_depends_on: "eval:doc.outcome=='Demo agreed'"},
                    {fieldname: "schedule_callback", label: __("Schedule a retry"), fieldtype: "Check",
                        depends_on: "eval:['Unanswered','Busy','Failed'].includes(doc.call_status) && doc.outcome!='Callback requested'"},
                    {fieldname: "callback_owner", label: __("Callback owner"), fieldtype: "Link", options: "User",
                        default: frappe.session.user, depends_on: cb, mandatory_depends_on: cb},
                    {fieldname: "due_at", label: __("Callback due"), fieldtype: "Datetime",
                        default: p.suggested_due, depends_on: cb, mandatory_depends_on: cb},
                    {fieldname: "note", label: __("Call notes"), fieldtype: "Small Text"},
                ],
                primary_action_label: __("Save call"),
                primary_action: async values => {
                    dialog.disable_primary_action();
                    try {
                        await frappe.xcall(api + "log_call", {...values, lead, request_id});
                        dialog.hide();
                        await frm.reload_doc();
                    } finally { dialog.enable_primary_action(); }
                },
            });
            dialog.show();
        };
        const open_log = async () => { const p = await panel(); log_dialog(p, p.pending[0]); };

        const dial = async (fieldname, phone_app) => {
            let r = await frappe.xcall(api + "dial_number", {lead, fieldname});
            if (r.needs_confirmation) {
                const ok = await new Promise(res => frappe.confirm(
                    r.warnings.map(w => "• " + ax.esc(w)).join("<br>") + "<br><br>" + __("Dial anyway?"),
                    () => res(true), () => res(false)));
                if (!ok) return;
                r = await frappe.xcall(api + "dial_number", {lead, fieldname, confirmed: 1});
            }
            if (ax.softphone.available() && !phone_app) {
                await ax.softphone.dial(r.number, r.attempt, frm.doc.lead_name || lead);
                await new Promise(res => setTimeout(res, 3000));  // let the carrier's end event arrive
            } else {
                window.location.href = "tel:" + r.number;
            }
            const p = await panel();
            log_dialog(p, p.pending.find(x => x.name === r.attempt));  // prompt for the result after the call
        };

        for (const [field, label] of [["mobile_no", "Call mobile"], ["phone", "Call phone"]]) {
            if (frm.doc[field]) frm.add_custom_button(__(label), () => dial(field), menu);
        }
        if (ax.softphone.available() && frm.doc.mobile_no) {
            frm.add_custom_button(__("Call mobile with phone app"), () => dial("mobile_no", true), menu);
        }
        frm.add_custom_button(__("Log call"), open_log, menu);

        const pick = async (title, cta, method, extra) => {
            const rows = await frappe.xcall(api + "my_open_callbacks", {lead});
            if (!rows.length) return frappe.msgprint(__("You have no open callbacks on this Lead."));
            frappe.prompt([{fieldname: "call", fieldtype: "Select", label: __("Callback"), reqd: 1,
                options: rows.map(r => ({value: r.name, label: frappe.datetime.str_to_user(r.due_at)}))}, ...extra],
                async values => { await frappe.xcall(api + method, values); await frm.reload_doc(); }, title, cta);
        };
        frm.add_custom_button(__("Complete my callback"), () => pick(__("Complete callback"), __("Complete"), "complete_callback", []), menu);
        frm.add_custom_button(__("Reschedule my callback"), () => pick(__("Reschedule callback"), __("Reschedule"),
            "reschedule_callback", [{fieldname: "due_at", label: __("New time"), fieldtype: "Datetime", reqd: 1}]), menu);
    },
});
