frappe.ui.form.on("Opportunity", {
    refresh(frm) {
        if (frm.is_new() || frm.doc.opportunity_from !== "Lead") return;
        frm.add_custom_button(__("Call history"), async () => {
            const panel = await frappe.xcall("alphax_calling.api.opportunity_calls", {opportunity: frm.doc.name});
            alphax_calling.show_history(panel, __("Call history of the source Lead"));
        });
    },
});
