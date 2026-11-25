import frappe


def get_settings():
    c = frappe.conf
    return frappe._dict(
        dnc_field=c.get("alphax_calling_do_not_call_field"),
        window=c.get("alphax_calling_call_window") or "09:00-21:00",
        weekend=tuple(c.get("alphax_calling_weekend_days") or (4, 5)),
        default_cc=str(c.get("alphax_calling_default_country_code") or "966"),
        callback_owner=c.get("alphax_calling_default_callback_owner"),
        missed_callback_minutes=int(c.get("alphax_calling_missed_callback_minutes") or 60),
        business_lines=c.get("alphax_calling_business_lines") or {},
        webhook_secret=c.get("alphax_calling_webhook_secret"),
        retention_days=int(c.get("alphax_calling_event_retention_days") or 180),
    )
