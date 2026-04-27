frappe.ui.form.on("AMC Contract", {
	refresh(frm) {
		// Add any custom logic here
	},
	
	contract_type(frm) {
		// Auto-set visits per year based on type
		const visit_defaults = {
			"Basic": 2,
			"Comprehensive": 4,
			"Premium": 6
		};
		
		if (frm.doc.contract_type && !frm.doc.visits_per_year) {
			frm.set_value("visits_per_year", visit_defaults[frm.doc.contract_type]);
		}
	}
});
