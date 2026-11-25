import frappe


def delete_lead_calls(doc, method=None):
    names = frappe.get_all("AX Lead Call", filters={"lead": doc.name}, pluck="name", limit_page_length=0)
    if names:
        frappe.db.delete("AX Call Event", {"call": ["in", names]})
        frappe.db.delete("AX Lead Call", {"name": ["in", names]})


def link_calls_to_opportunity(doc, method=None):
    if doc.get("opportunity_from") == "Lead" and doc.get("party_name"):
        frappe.db.sql(
            "update `tabAX Lead Call` set opportunity=%s where lead=%s and (opportunity is null or opportunity='')",
            (doc.name, doc.party_name))
