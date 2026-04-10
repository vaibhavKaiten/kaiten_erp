// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Technical Survey", {

	onload(frm) {
		set_vendor_user_filter(frm);
		setup_assigned_vendor_filter(frm);
		if (frm.doc.custom_job_file && frm.is_new()) {
			fetch_job_file_data(frm);
		}
	},

	refresh(frm) {
		set_vendor_user_filter(frm);
		setup_assigned_vendor_filter(frm);
	},

	custom_job_file(frm) {
		if (!frm.doc.custom_job_file) return;
		fetch_job_file_data(frm);
	},

	assigned_vendor(frm) {
		if (frm.doc.assigned_internal_user) {
			frm.set_value('assigned_internal_user', '');
		}
		set_vendor_user_filter(frm);
		setup_assigned_vendor_filter(frm);
	}

});


function setup_assigned_vendor_filter(frm) {
	const territory = frm.doc.territory;
	if (!territory) return;

	frm.set_query('assigned_vendor', function() {
		return {
			query: 'kaiten_erp.kaiten_erp.api.lead_vendor.get_technical_vendors',
			filters: { territory: territory }
		};
	});

	frm.set_df_property('assigned_vendor', 'description',
		__('Technical vendors active in {0}', [territory]));
}


function fetch_job_file_data(frm) {
	frappe.db.get_value("Job File", frm.doc.custom_job_file, [
		"monthly_consumption",
		"existing_load_kw",
		"required_load_kw",
		"sanctioned_load_kw",
		"phase_type",
		"discom",
		"proposed_system",
		"custom_roof_area_sqft",
		"custom_roof_type",
		"custom_site_type",
		"custom_area_suitability",
		"preferred_visit_date",
		"preferred_time_slot"
	]).then(r => {
		if (!r.message) return;
		let d = r.message;
		frm.set_value({
			monthly_consumption: d.monthly_consumption,
			existing_load_kw: d.existing_load_kw,
			required_load_kw: d.required_load_kw,
			sanctioned_load_kw: d.sanctioned_load_kw,
			discom: d.discom,
			phase_type_copy: d.phase_type,
			proposed_system_kw__tier: d.proposed_system,
			roof_area_sqft: d.custom_roof_area_sqft,
			roof_type: d.custom_roof_type,
			site_type: d.custom_site_type,
			area_suitability: d.custom_area_suitability,
			data_ycke: d.preferred_visit_date,
			data_tila: d.preferred_time_slot
		});
	});
}

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
