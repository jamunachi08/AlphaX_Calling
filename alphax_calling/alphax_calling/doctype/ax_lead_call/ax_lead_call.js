frappe.ui.form.on("AX Lead Call", {
    refresh(frm) {
        if (frm.doc.review_status !== "Needs Review") return;
        frm.dashboard.set_headline_alert(frappe.utils.escape_html(frm.doc.review_reason || __("Needs review")), "orange");
        frm.add_custom_button(__("Link to Lead"), () => {
            frappe.prompt([
                {fieldname: "lead", label: __("Lead"), fieldtype: "Link", options: "Lead", reqd: 1, default: frm.doc.lead},
                {fieldname: "callback_owner", label: __("Callback owner"), fieldtype: "Link", options: "User",
                    description: __("Needed for a missed inbound call with no Lead owner.")},
            ], async values => {
                await frappe.xcall("alphax_calling.api.resolve_review", {call: frm.doc.name, ...values});
                frm.reload_doc();
            }, __("Link call to Lead"), __("Link"));
        });
    },
});
