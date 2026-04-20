// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Job File", {
    refresh: function (frm) {
        add_customer_website_actions(frm);
        update_customer_website_link(frm);
        setTimeout(function () {
            update_customer_website_link(frm);
        }, 300);
    },

    setup: function (frm) {
        // Filter proposed_system to only show items from "Products" group with BOMs
        frm.set_query('proposed_system', function () {
            return {
                query: 'kaiten_erp.kaiten_erp.api.technical_survey_bom.get_items_with_bom',
                filters: {
                    item_group: 'Products'
                }
            };
        });
    },

    proposed_system: function (frm) {
        // Fetch and populate item price into mrp field when proposed_system is selected
        if (frm.doc.proposed_system) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Price',
                    filters: {
                        item_code: frm.doc.proposed_system,
                        selling: 1
                    },
                    fieldname: 'price_list_rate'
                },
                callback: function (r) {
                    if (r.message && r.message.price_list_rate) {
                        frm.set_value('mrp', r.message.price_list_rate);
                    } else {
                        // If no selling price found, try to get standard rate from Item
                        frappe.call({
                            method: 'frappe.client.get_value',
                            args: {
                                doctype: 'Item',
                                filters: {
                                    name: frm.doc.proposed_system
                                },
                                fieldname: 'standard_rate'
                            },
                            callback: function (r) {
                                if (r.message && r.message.standard_rate) {
                                    frm.set_value('mrp', r.message.standard_rate);
                                }
                            }
                        });
                    }
                }
            });
        } else {
            // Clear mrp if proposed_system is cleared
            frm.set_value('mrp', 0);
        }
    }

});

function get_customer_share_path(frm) {
    if (!frm.doc.custom_web_access_token) {
        return null;
    }

    const route = frm.doc.route || "";
    if (!route) {
        return null;
    }

    return "/" + route.replace(/^\/+/, "") + "?token=" + encodeURIComponent(frm.doc.custom_web_access_token);
}

function update_customer_website_link(frm) {
    const sharePath = get_customer_share_path(frm);
    if (!sharePath) {
        return;
    }

    const anchorSelectors = [
        'a[data-label="See%20on%20Website"]',
        'a[title="See on Website"]',
        'a[href*="/' + (frm.doc.route || "").replace(/^\/+/, "") + '"]'
    ];

    anchorSelectors.forEach(function (selector) {
        $(selector).each(function () {
            $(this).attr("href", sharePath);
            $(this).attr("target", "_blank");
            $(this).attr("rel", "noopener noreferrer");
        });
    });

    $("a").filter(function () {
        return ($(this).text() || "").trim() === "See on Website";
    }).each(function () {
        $(this).attr("href", sharePath);
        $(this).attr("target", "_blank");
        $(this).attr("rel", "noopener noreferrer");
    });
}

function add_customer_website_actions(frm) {
    if (frm.is_new()) {
        return;
    }

    frm.add_custom_button("Open Customer Web View", function () {
        const sharePath = get_customer_share_path(frm);
        if (!sharePath) {
            frappe.msgprint("Web access token or route missing. Save Job File in valid workflow state first.");
            return;
        }

        window.open(sharePath, "_blank", "noopener,noreferrer");
    }, "Website");

    frm.add_custom_button("Copy Customer Share Link", async function () {
        const sharePath = get_customer_share_path(frm);
        if (!sharePath) {
            frappe.msgprint("Web access token or route missing. Save Job File in valid workflow state first.");
            return;
        }

        const shareUrl = window.location.origin + sharePath;
        try {
            await navigator.clipboard.writeText(shareUrl);
            frappe.show_alert({ message: "Customer share link copied", indicator: "green" });
        } catch (error) {
            frappe.msgprint("Could not copy automatically. Use this link: " + shareUrl);
        }
    }, "Website");
}
