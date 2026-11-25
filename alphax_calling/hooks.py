app_name = "alphax_calling"
app_title = "AlphaX Calling"
app_publisher = "AlphaX"
app_description = "Calls, callbacks and call history on ERPNext Leads"
app_license = "Proprietary"
required_apps = ["erpnext"]

app_include_js = ["/assets/alphax_calling/js/alphax_calling.js", "/assets/alphax_calling/js/softphone.js"]
boot_session = "alphax_calling.boot.boot_session"
doctype_js = {"Lead": "public/js/lead.js", "Opportunity": "public/js/opportunity.js"}

doc_events = {
    "Lead": {"on_trash": "alphax_calling.doc_events.delete_lead_calls"},
    "Opportunity": {"after_insert": "alphax_calling.doc_events.link_calls_to_opportunity"},
}

permission_query_conditions = {"AX Lead Call": "alphax_calling.permissions.query_conditions"}
has_permission = {"AX Lead Call": "alphax_calling.permissions.has_permission"}
ignore_links_on_delete = ["AX Lead Call", "AX Call Event"]

after_install = "alphax_calling.setup.after_migrate"
after_migrate = ["alphax_calling.setup.after_migrate"]

scheduler_events = {
    "cron": {"*/15 * * * *": ["alphax_calling.tasks.notify_overdue_callbacks"]},
    "hourly": ["alphax_calling.tasks.flag_stale_provider_calls"],
    "daily": ["alphax_calling.tasks.purge_old_events"],
}
