// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Technical Survey", {
	onload(frm) {
		set_vendor_user_filter(frm);
		
	},

	refresh(frm) {
		set_vendor_user_filter(frm);
		
	},

	assigned_vendor(frm) {
		if (frm.doc.assigned_internal_user) {
			frm.set_value('assigned_internal_user', '');
		}
		set_vendor_user_filter(frm);
	}
	
}
);

function set_vendor_user_filter(frm) {
	if (frm.doc.assigned_vendor) {
		frm.set_query("assigned_internal_user", function () {
			return {
				query: "kaiten_erp.kaiten_erp.api.get_vendorExcutive.get_vendor_executive_users",
				filters: {
					supplier: frm.doc.assigned_vendor
				}
			};
		});
	} else {
		frm.set_query("assigned_internal_user", function () {
			return {
				filters: {
					name: ['in', []]
				}
			};
		});
	}
}
