frappe.ui.form.on("Lead", {
    refresh(frm) {
        if (frm.is_new() || !frm.perm[0]?.write) return;
        const menu = __("Calling");
        const api = "alphax_calling.api.";
        const lead = frm.doc.name;
        const dial = async fieldname => {
            const number = await frappe.xcall(api + "dial_number", {lead, fieldname});
            window.location.href = "tel:" + number;
        };
        for (const [field, label] of [["mobile_no", "Call mobile"], ["phone", "Call phone"]]) {
            if (frm.doc[field]) frm.add_custom_button(__(label), () => dial(field), menu);
        }
        frm.add_custom_button(__("Log call"), () => {
            const request_id = crypto.randomUUID();
            const dialog = new frappe.ui.Dialog({
                title: __("Log a call"),
                fields: [
                    {fieldname:"direction", label:__("Direction"), fieldtype:"Select", options:"Outbound\nInbound", reqd:1},
                    {fieldname:"call_status", label:__("Reported result"), fieldtype:"Select", options:"\nAnswered\nUnanswered\nBusy\nFailed", reqd:1},
                    {fieldname:"outcome", label:__("Outcome"), fieldtype:"Select", options:"\nCallback requested\nDemo agreed\nInformation sent\nWrong number\nNo interest"},
                    {fieldname:"note", label:__("Call notes"), fieldtype:"Small Text"},
                    ...[
                        {fieldname:"callback_owner", label:__("Callback owner"), fieldtype:"Link", options:"User", default:frappe.session.user},
                        {fieldname:"due_at", label:__("Callback due"), fieldtype:"Datetime"}
                    ].map(f => ({...f, depends_on:"eval:doc.outcome=='Callback requested'", mandatory_depends_on:"eval:doc.outcome=='Callback requested'"}))
                ],
                primary_action_label: __("Save call"),
                primary_action: async values => {
                    dialog.disable_primary_action();
                    try {
                        await frappe.xcall(api + "log_call", {...values, lead, request_id});
                        dialog.hide();
                        await frm.reload_doc();
                    } finally { dialog.enable_primary_action(); }
                }
            });
            dialog.show();
        }, menu);
        frm.add_custom_button(__("Complete my callback"), async () => {
            const rows = await frappe.xcall(api + "my_open_callbacks", {lead});
            if (!rows.length) return frappe.msgprint(__("You have no open callbacks on this Lead."));
            frappe.prompt([{fieldname:"call", fieldtype:"Select", label:__("Callback"), reqd:1,
                options:rows.map(r => ({value:r.name, label:frappe.datetime.str_to_user(r.due_at) + " · " + r.name}))}],
                async values => {
                    await frappe.xcall(api + "complete_callback", values);
                    await frm.reload_doc();
                }, __("Complete callback"), __("Complete"));
        }, menu);
    }
});
