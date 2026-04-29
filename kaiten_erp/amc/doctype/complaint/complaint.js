frappe.ui.form.on("Complaint", {
	refresh(frm) {
		// Add any custom logic here
	},
	
	amc_contract(frm) {
		// Fetch SLA details from contract
		if (frm.doc.amc_contract) {
			frappe.call({
				method: "frappe.client.get",
				args: {
					doctype: "AMC Contract",
					name: frm.doc.amc_contract
				},
				callback(r) {
					if (r.message) {
						// Auto-set SLA hours
					}
				}
			});
		}
	}
});
