frappe.query_reports["AX Executive Calls"] = {
    filters: [
        {fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -30)},
        {fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today()},
        {fieldname: "executive", label: __("Executive"), fieldtype: "Link", options: "User"},
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company"},
        {fieldname: "business_line", label: __("Business line"), fieldtype: "Data"},
    ],
};
