frappe.query_reports["AX Callback Queue"] = {
    filters: [{fieldname: "scope", label: __("Show"), fieldtype: "Select", options: "Mine\nTeam", default: "Mine",
        description: __("Team is available to Sales Managers and shows every callback on Leads you can read.")}],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "state" && data) {
            const color = {Overdue: "red", "Due today": "orange"}[data.state];
            if (color) value = `<span style="color:var(--${color}-500)"><b>${value}</b></span>`;
        }
        return value;
    },
};
