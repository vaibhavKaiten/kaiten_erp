"""
setup_sample_data.py
====================
DEV-ONLY script that seeds the Frappe/ERPNext database with sample master data
required to demo the Kaiten ERP solar installation workflow.

Run with:
    cd /home/lakshya/frappe/frappe-bench
    bench --site <your-site> execute kaiten_erp.kaiten_erp.kaiten_erp.setup_sample_data

Available sites on this bench:
    bench --site uat2.localhost    execute kaiten_erp.kaiten_erp.kaiten_erp.setup_sample_data
    bench --site lakshya.localhost execute kaiten_erp.kaiten_erp.kaiten_erp.setup_sample_data

What this creates (idempotent — skips records that already exist):
  - Item Groups          : Consumable, Inverter, Panel, Battery, Products
  - Supplier Groups      : 3 vendor-specific groups
  - Items                : consumables, inverters, panels, 3 product bundles
  - BOMs                 : 1 active BOM per Product item (components from Consumable)
  - Customers            : 3 sample customers
  - Suppliers            : 3 sample suppliers
  - Users + Roles        : Item Manager, Vendor Executive, Business Supply Admin,
                           Account Manager, Sales Manager
  - Employees            : 5 sample employees linked to those users
  - Leads                : 5 sample solar-project leads
  - Sales Orders         : 3 sample Sales Orders (one per product)

⚠  WARNING — DO NOT RUN IN PRODUCTION  ⚠
"""

import frappe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exists(doctype: str, name: str) -> bool:
	return bool(frappe.db.exists(doctype, name))


def _insert(doc_dict: dict) -> None:
	"""Insert a document, ignoring if it already exists."""
	doctype = doc_dict["doctype"]
	name_key = doc_dict.get("name") or doc_dict.get(
		{
			"Item": "item_code",
			"Item Group": "item_group_name",
			"Supplier Group": "supplier_group_name",
			"User": "email",
			"Employee": "employee_number",
			"Lead": "lead_name",
			"Customer": "customer_name",
			"Supplier": "supplier_name",
			"BOM": "item",
			"Sales Order": "name",
		}.get(doctype, "name"),
		None,
	)
	# For doctypes where existence is checked by a specific field
	check_name = doc_dict.get("name") or name_key
	if check_name and _exists(doctype, check_name):
		print(f"  [skip] {doctype}: {check_name}")
		return
	doc = frappe.get_doc(doc_dict)
	doc.insert(ignore_permissions=True)
	print(f"  [ok]   {doctype}: {doc.name}")


def _ensure_company() -> str:
	company = frappe.defaults.get_global_default("company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw(
			"No Company found on this site. Please complete the ERPNext Setup Wizard first:\n"
			"  Open http://<your-site> in a browser and finish the setup wizard, then re-run this script."
		)
	return company


def _get_default_company() -> str:
	return _ensure_company()


# ---------------------------------------------------------------------------
# 1. Item Groups
# ---------------------------------------------------------------------------

def _ensure_root_item_group() -> None:
	if not _exists("Item Group", "All Item Groups"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "All Item Groups",
				"is_group": 1,
			}
		).insert(ignore_permissions=True)
		print("  [ok]   Item Group (root): All Item Groups")
	else:
		print("  [skip] Item Group (root): All Item Groups")


def _create_item_groups() -> None:
	print("\n--- Item Groups ---")
	_ensure_root_item_group()
	groups = [
		("All Item Groups", None, 1),   # already handled above but harmless
		("Consumable", "All Item Groups", 0),
		("Inverter", "All Item Groups", 0),
		("Panel", "All Item Groups", 0),
		("Battery", "All Item Groups", 0),
		("Products", "All Item Groups", 0),
	]
	for group_name, parent, is_group in groups:
		if group_name == "All Item Groups":
			continue
		if _exists("Item Group", group_name):
			print(f"  [skip] Item Group: {group_name}")
			continue
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": group_name,
				"parent_item_group": parent,
				"is_group": is_group,
			}
		).insert(ignore_permissions=True)
		print(f"  [ok]   Item Group: {group_name}")


# ---------------------------------------------------------------------------
# 2. Territories
# ---------------------------------------------------------------------------

def _create_territories() -> None:
	print("\n--- Territories ---")
	# Create root if missing (setup wizard not yet run)
	if not _exists("Territory", "All Territories"):
		frappe.get_doc(
			{
				"doctype": "Territory",
				"territory_name": "All Territories",
				"is_group": 1,
			}
		).insert(ignore_permissions=True)
		print("  [ok]   Territory: All Territories")
	else:
		print("  [skip] Territory: All Territories")

	if not _exists("Territory", "jaipur"):
		frappe.get_doc(
			{
				"doctype": "Territory",
				"territory_name": "jaipur",
				"parent_territory": "All Territories",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		print("  [ok]   Territory: jaipur")
	else:
		print("  [skip] Territory: jaipur")


# ---------------------------------------------------------------------------
# 3. Sales Persons
# ---------------------------------------------------------------------------

def _create_sales_persons() -> None:
	print("\n--- Sales Persons ---")
	persons = [
		("Nitin Jha", "Sales Team"),
		("Sample Executive", "Sales Team"),
	]
	for person_name, parent in persons:
		if frappe.db.exists("Sales Person", {"sales_person_name": person_name}):
			print(f"  [skip] Sales Person: {person_name}")
			continue
		frappe.get_doc(
			{
				"doctype": "Sales Person",
				"sales_person_name": person_name,
				"parent_sales_person": parent,
				"is_group": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		print(f"  [ok]   Sales Person: {person_name}")


# ---------------------------------------------------------------------------
# 4. Supplier Groups
# ---------------------------------------------------------------------------

def _create_supplier_groups() -> None:
	print("\n--- Supplier Groups ---")
	if not _exists("Supplier Group", "All Supplier Groups"):
		frappe.get_doc(
			{
				"doctype": "Supplier Group",
				"supplier_group_name": "All Supplier Groups",
				"is_group": 1,
			}
		).insert(ignore_permissions=True)
		print("  [ok]   Supplier Group (root): All Supplier Groups")
	else:
		print("  [skip] Supplier Group (root): All Supplier Groups")
	groups = [
		"Meter Installation & Commissioning Vendor",
		"Solar Installation Vendor",
		"Structure and Project Installation Vendor",
	]
	for g in groups:
		if _exists("Supplier Group", g):
			print(f"  [skip] Supplier Group: {g}")
			continue
		frappe.get_doc(
			{
				"doctype": "Supplier Group",
				"supplier_group_name": g,
				"parent_supplier_group": "All Supplier Groups",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		print(f"  [ok]   Supplier Group: {g}")


# ---------------------------------------------------------------------------
# 3. Items
# ---------------------------------------------------------------------------

def _make_item(item_code: str, item_name: str, item_group: str, is_stock: int = 1, hsn: str = "73181500") -> dict:
	return {
		"doctype": "Item",
		"item_code": item_code,
		"item_name": item_name,
		"item_group": item_group,
		"stock_uom": "Nos",
		"is_stock_item": is_stock,
		"is_purchase_item": 1,
		"is_sales_item": 1,
		"include_item_in_manufacturing": 1,
		"gst_hsn_code": hsn,
	}


def _create_items() -> None:
	print("\n--- Items ---")

	# Use a single common HSN code (73181500 = hardware/fasteners) that is
	# always present in india_compliance's seeded GST HSN Code master.
	_CONSUMABLE_HSN = {
		"DCDB": "73181500",
		"Demo Item Group": "73181500",
		"Earthing Chemical": "73181500",
		"Elenky Bolt": "73181500",
		"End Clamp": "73181500",
		"Gi Spray": "73181500",
		"Golden Fastner": "73181500",
		"Inverter": "73181500",
		"J-Hook": "73181500",
		"L-KUNDA": "73181500",
		"LA": "73181500",
		"MC4 Connector": "73181500",
		"Meter": "73181500",
		"Mid Clamp": "73181500",
		"MIP Box": "73181500",
		"Nut Bolt": "73181500",
		"Panel Nut Bolt": "73181500",
		"Panels": "73181500",
		"Saddle": "73181500",
		"Silver Fastner": "73181500",
		"Structure": "73181500",
		"Sub Assemblies": "73181500",
		"Wire Tape": "73181500",
		"Wiring": "73181500",
	}
	consumables = list(_CONSUMABLE_HSN.keys())
	for code in consumables:
		if _exists("Item", code):
			print(f"  [skip] Item: {code}")
			continue
		item = _make_item(code, code, "Consumable", hsn=_CONSUMABLE_HSN[code])
		frappe.get_doc(item).insert(ignore_permissions=True)
		print(f"  [ok]   Item: {code}")

	inverters = [
		("Luminious GTI 10 KW TP", "Luminious GTI 10 KW TP"),
		("Luminious GTI 100 KW TP", "Luminious GTI 100 KW TP"),
		("Luminious GTI 12 KW TP", "Luminious GTI 12 KW TP"),
	]
	for code, name in inverters:
		if _exists("Item", code):
			print(f"  [skip] Item: {code}")
			continue
		frappe.get_doc(_make_item(code, name, "Inverter", hsn="73181500")).insert(ignore_permissions=True)
		print(f"  [ok]   Item: {code}")

	panels = [
		("Adani Mono bifacial 540 DCR", "Adani Mono bifacial 540 DCR"),
		("Adani Mono bifacial 540 NDCR", "Adani Mono bifacial 540 NDCR"),
		("Adani bifacial topcon 615 NDCR", "Adani bifacial topcon 615 NDCR"),
	]
	for code, name in panels:
		if _exists("Item", code):
			print(f"  [skip] Item: {code}")
			continue
		frappe.get_doc(_make_item(code, name, "Panel", hsn="73181500")).insert(ignore_permissions=True)
		print(f"  [ok]   Item: {code}")

	# Products — the sellable system bundles
	products = [
		("10KW- DIAMOND- 3P- TOPCON", "10 KW Diamond 3-Phase Topcon System"),
		("10KW- GOLD- 3P- BIFACIAL", "10 KW Gold 3-Phase Bifacial System"),
		("10KW- SILVER- 3P- BIFACIAL", "10 KW Silver 3-Phase Bifacial System"),
	]
	for code, name in products:
		if _exists("Item", code):
			print(f"  [skip] Item: {code}")
			continue
		frappe.get_doc(_make_item(code, name, "Products", is_stock=0, hsn="73181500")).insert(
			ignore_permissions=True
		)
		print(f"  [ok]   Item: {code}")


# ---------------------------------------------------------------------------
# 4. BOMs  (one BOM per Product item, using Consumable components)
# ---------------------------------------------------------------------------

_BOM_COMPONENTS = {
	"10KW- DIAMOND- 3P- TOPCON": [
		{"item_code": "Adani bifacial topcon 615 NDCR", "qty": 24, "uom": "Nos", "item_group": "Panel"},
		{"item_code": "Luminious GTI 10 KW TP", "qty": 1, "uom": "Nos", "item_group": "Inverter"},
		{"item_code": "Structure", "qty": 1, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "MC4 Connector", "qty": 10, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "Wiring", "qty": 50, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "MIP Box", "qty": 1, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "DCDB", "qty": 1, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "Earthing Chemical", "qty": 2, "uom": "Nos", "item_group": "Consumable"},
	],
	"10KW- GOLD- 3P- BIFACIAL": [
		{"item_code": "Adani Mono bifacial 540 DCR", "qty": 22, "uom": "Nos", "item_group": "Panel"},
		{"item_code": "Luminious GTI 10 KW TP", "qty": 1, "uom": "Nos", "item_group": "Inverter"},
		{"item_code": "Structure", "qty": 1, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "MC4 Connector", "qty": 8, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "Wiring", "qty": 45, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "MIP Box", "qty": 1, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "Nut Bolt", "qty": 20, "uom": "Nos", "item_group": "Consumable"},
	],
	"10KW- SILVER- 3P- BIFACIAL": [
		{"item_code": "Adani Mono bifacial 540 NDCR", "qty": 20, "uom": "Nos", "item_group": "Panel"},
		{"item_code": "Luminious GTI 10 KW TP", "qty": 1, "uom": "Nos", "item_group": "Inverter"},
		{"item_code": "Structure", "qty": 1, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "MC4 Connector", "qty": 8, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "Wiring", "qty": 40, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "End Clamp", "qty": 16, "uom": "Nos", "item_group": "Consumable"},
		{"item_code": "Mid Clamp", "qty": 20, "uom": "Nos", "item_group": "Consumable"},
	],
}


def _create_boms() -> None:
	print("\n--- BOMs ---")
	company = _get_default_company()

	for product_code, components in _BOM_COMPONENTS.items():
		# Skip if an active BOM for this item already exists
		existing = frappe.db.get_value(
			"BOM", {"item": product_code, "is_active": 1, "docstatus": 1}, "name"
		)
		if existing:
			print(f"  [skip] BOM for: {product_code} (active BOM {existing} exists)")
			continue

		bom_items = []
		for comp in components:
			bom_items.append(
				{
					"doctype": "BOM Item",
					"item_code": comp["item_code"],
					"qty": comp["qty"],
					"uom": comp["uom"],
				}
			)

		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": product_code,
				"quantity": 1,
				"company": company,
				"is_active": 1,
				"is_default": 1,
				"items": bom_items,
			}
		)
		bom.insert(ignore_permissions=True)
		bom.submit()
		print(f"  [ok]   BOM: {bom.name} → {product_code}")


# ---------------------------------------------------------------------------
# 5. Customers
# ---------------------------------------------------------------------------

_CUSTOMERS = [
	{
		"doctype": "Customer",
		"customer_name": "Sharma Solar Pvt Ltd",
		"customer_group": "Commercial",
		"territory": "All Territories",
		"customer_type": "Company",
	},
	{
		"doctype": "Customer",
		"customer_name": "Rajesh Kumar",
		"customer_group": "Individual",
		"territory": "All Territories",
		"customer_type": "Individual",
	},
	{
		"doctype": "Customer",
		"customer_name": "Green Energy Solutions",
		"customer_group": "Commercial",
		"territory": "All Territories",
		"customer_type": "Company",
	},
]


def _create_customers() -> None:
	print("\n--- Customers ---")
	for c in _CUSTOMERS:
		if frappe.db.exists("Customer", c["customer_name"]):
			print(f"  [skip] Customer: {c['customer_name']}")
			continue
		frappe.get_doc(c).insert(ignore_permissions=True)
		print(f"  [ok]   Customer: {c['customer_name']}")


# ---------------------------------------------------------------------------
# 6. Suppliers
# ---------------------------------------------------------------------------

_SUPPLIERS = [
	{
		"doctype": "Supplier",
		"supplier_name": "SunTech Installations Pvt Ltd",
		"supplier_group": "Solar Installation Vendor",
		"supplier_type": "Company",
		"country": "India",
	},
	{
		"doctype": "Supplier",
		"supplier_name": "Jaipur Structure Works",
		"supplier_group": "Structure and Project Installation Vendor",
		"supplier_type": "Company",
		"country": "India",
	},
	{
		"doctype": "Supplier",
		"supplier_name": "Metro Meter Services",
		"supplier_group": "Meter Installation & Commissioning Vendor",
		"supplier_type": "Company",
		"country": "India",
	},
]


def _create_suppliers() -> None:
	print("\n--- Suppliers ---")
	for s in _SUPPLIERS:
		if frappe.db.exists("Supplier", s["supplier_name"]):
			print(f"  [skip] Supplier: {s['supplier_name']}")
			continue
		frappe.get_doc(s).insert(ignore_permissions=True)
		print(f"  [ok]   Supplier: {s['supplier_name']}")


# ---------------------------------------------------------------------------
# 7. Users
# ---------------------------------------------------------------------------

_USERS = [
	{
		"email": "item.manager@kaiten.dev",
		"first_name": "Arjun",
		"last_name": "Mehta",
		"role": "Stock Manager",
		"label": "Item Manager",
	},
	{
		"email": "vendor.exec@kaiten.dev",
		"first_name": "Priya",
		"last_name": "Sharma",
		"role": "Vendor Executive",
		"label": "Vendor Executive",
	},
	{
		"email": "supply.admin@kaiten.dev",
		"first_name": "Vikram",
		"last_name": "Singh",
		"role": "Purchase Manager",
		"label": "Business Supply Admin",
	},
	{
		"email": "account.manager@kaiten.dev",
		"first_name": "Neha",
		"last_name": "Gupta",
		"role": "Accounts Manager",
		"label": "Account Manager",
	},
	{
		"email": "sales.manager@kaiten.dev",
		"first_name": "Rohit",
		"last_name": "Verma",
		"role": "Sales Manager",
		"label": "Sales Manager",
	},
]


def _create_users() -> None:
	print("\n--- Users ---")
	for u in _USERS:
		email = u["email"]
		if _exists("User", email):
			print(f"  [skip] User: {email}")
			continue
		user_doc = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": u["first_name"],
				"last_name": u["last_name"],
				"send_welcome_email": 0,
				"user_type": "System User",
				"new_password": "Kaiten@2026!",
				"roles": [{"role": u["role"]}],
			}
		)
		user_doc.insert(ignore_permissions=True)
		print(f"  [ok]   User: {email} ({u['label']}) — role: {u['role']}")


# ---------------------------------------------------------------------------
# 8. Employees
# ---------------------------------------------------------------------------

def _create_employees() -> None:
	print("\n--- Employees ---")
	company = _get_default_company()

	employees = [
		("Arjun", "Mehta", "Stores", "item.manager@kaiten.dev"),
		("Priya", "Sharma", "Operations", "vendor.exec@kaiten.dev"),
		("Vikram", "Singh", "Purchase", "supply.admin@kaiten.dev"),
		("Neha", "Gupta", "Accounts", "account.manager@kaiten.dev"),
		("Rohit", "Verma", "Sales", "sales.manager@kaiten.dev"),
	]

	for first, last, dept, user_email in employees:
		full_name = f"{first} {last}"
		# Check by user_id to keep it idempotent
		existing = frappe.db.get_value("Employee", {"user_id": user_email}, "name")
		if existing:
			print(f"  [skip] Employee: {full_name} (linked to {user_email})")
			continue

		# Ensure department exists
		if not _exists("Department", f"{dept} - {company[:2]}") and not _exists(
			"Department", dept
		):
			try:
				frappe.get_doc(
					{
						"doctype": "Department",
						"department_name": dept,
						"company": company,
					}
				).insert(ignore_permissions=True)
			except Exception:
				pass  # department may already exist under different name convention

		emp = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": first,
				"last_name": last,
				"gender": "Male" if first in ("Arjun", "Vikram", "Rohit") else "Female",
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2024-01-01",
				"status": "Active",
				"company": company,
				"user_id": user_email,
			}
		)
		emp.insert(ignore_permissions=True)
		print(f"  [ok]   Employee: {full_name}")


# ---------------------------------------------------------------------------
# 9. Leads
# ---------------------------------------------------------------------------

_LEADS = [
	{
		"lead_name": "Suresh Agarwal",
		"email_id": "suresh.agarwal@example.com",
		"mobile_no": "9810001001",
		"status": "Open",
		"source": "Cold Calling",
		"city": "Jaipur",
		"state": "Rajasthan",
		"country": "India",
	},
	{
		"lead_name": "Kavita Nair",
		"email_id": "kavita.nair@example.com",
		"mobile_no": "9820002002",
		"status": "Open",
		"source": "Reference",
		"city": "Jaipur",
		"state": "Rajasthan",
		"country": "India",
	},
	{
		"lead_name": "Mohan Lal Textile Mills",
		"email_id": "ml.textiles@example.com",
		"mobile_no": "9830003003",
		"status": "Replied",
		"source": "Advertisement",
		"city": "Jaipur",
		"state": "Rajasthan",
		"country": "India",
	},
	{
		"lead_name": "Anita Sharma",
		"email_id": "anita.sharma@example.com",
		"mobile_no": "9840004004",
		"status": "Open",
		"source": "Walk In",
		"city": "Jaipur",
		"state": "Rajasthan",
		"country": "India",
	},
	{
		"lead_name": "Ramesh Builders Pvt Ltd",
		"email_id": "ramesh.builders@example.com",
		"mobile_no": "9850005005",
		"status": "Interested",
		"source": "Reference",
		"city": "Jaipur",
		"state": "Rajasthan",
		"country": "India",
	},
]


def _create_leads() -> None:
	print("\n--- Leads ---")
	for lead_data in _LEADS:
		name = lead_data["lead_name"]
		if frappe.db.exists("Lead", {"lead_name": name}):
			print(f"  [skip] Lead: {name}")
			continue
		lead = frappe.get_doc({"doctype": "Lead", **lead_data})
		lead.insert(ignore_permissions=True)
		print(f"  [ok]   Lead: {name}")


# ---------------------------------------------------------------------------
# 10. Sales Orders  (sample — one per product, linked to sample customers)
# ---------------------------------------------------------------------------

def _create_sales_orders() -> None:
	print("\n--- Sales Orders ---")
	company = _get_default_company()

	orders = [
		{
			"customer": "Sharma Solar Pvt Ltd",
			"item_code": "10KW- DIAMOND- 3P- TOPCON",
			"rate": 450000,
			"qty": 1,
		},
		{
			"customer": "Rajesh Kumar",
			"item_code": "10KW- GOLD- 3P- BIFACIAL",
			"rate": 380000,
			"qty": 1,
		},
		{
			"customer": "Green Energy Solutions",
			"item_code": "10KW- SILVER- 3P- BIFACIAL",
			"rate": 330000,
			"qty": 1,
		},
	]

	for order in orders:
		customer = order["customer"]
		item_code = order["item_code"]

		# Check if a draft/submitted SO already exists for this customer + item
		existing = frappe.db.get_value(
			"Sales Order Item",
			{"item_code": item_code, "docstatus": ["<", 2]},
			"parent",
		)
		if existing:
			print(f"  [skip] Sales Order for {customer} / {item_code} (SO {existing} exists)")
			continue

		# Ensure customer exists before creating SO
		if not frappe.db.exists("Customer", customer):
			print(f"  [skip] Sales Order for {customer} — customer not found")
			continue

		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": customer,
				"company": company,
				"order_type": "Sales",
				"delivery_date": frappe.utils.add_days(frappe.utils.today(), 30),
				"items": [
					{
						"doctype": "Sales Order Item",
						"item_code": item_code,
						"qty": order["qty"],
						"rate": order["rate"],
						"delivery_date": frappe.utils.add_days(frappe.utils.today(), 30),
					}
				],
			}
		)
		try:
			so.insert(ignore_permissions=True)
			print(f"  [ok]   Sales Order: {so.name} → {customer} / {item_code}")
		except Exception as e:
			print(f"  [skip] Sales Order for {customer} / {item_code} — {e}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def execute():
	print()
	print("=" * 70)
	print("  ⚠  KAITEN ERP — SAMPLE DATA SEEDER  ⚠")
	print("=" * 70)
	print()
	print("  WARNING: This script inserts SAMPLE / DUMMY data into the database.")
	print("  It is intended ONLY for development and demo environments.")
	print()
	print("  DO NOT RUN THIS SCRIPT IN A PRODUCTION SITE.")
	print()
	print("  Records created will be real database rows. Removing them later")
	print("  requires manual cleanup or a fresh site restore.")
	print()
	print("=" * 70)
	print()

	import sys

	if sys.stdin.isatty():
		# Interactive terminal — ask for confirmation
		try:
			confirm = input("  Type  YES  to continue, or anything else to abort: ").strip()
		except (EOFError, KeyboardInterrupt):
			print("\nAborted.")
			return
		if confirm != "YES":
			print("\nAborted. Nothing was changed.")
			return
	else:
		# Non-interactive (bench execute) — proceed automatically, warning already printed above
		print("  Running non-interactively via bench execute. Proceeding...")

	print()
	frappe.set_user("Administrator")

	_ensure_company()
	_create_item_groups()
	_create_territories()
	_create_sales_persons()
	_create_supplier_groups()
	_create_items()
	_create_boms()
	_create_customers()
	_create_suppliers()
	_create_users()
	_create_employees()
	_create_leads()
	_create_sales_orders()

	frappe.db.commit()

	print()
	print("=" * 70)
	print("  Sample data seeding COMPLETE.")
	print("  Default password for all sample users: Kaiten@2026!")
	print("  Run  bench --site <your-site> clear-cache  to refresh the desk.")
	print("=" * 70)
	print()
