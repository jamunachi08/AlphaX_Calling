# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class AXCallEvent(Document):
    """Raw provider event log. Written by the provider-event endpoint; deduped on event_id."""

    pass
