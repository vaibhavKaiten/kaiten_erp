import frappe
import csv
from collections import defaultdict

def create_phantom_boms():
    """Create Phantom BOMs with is_phantom checked BEFORE adding items"""
    
    print("=" * 70)
    print("CREATING PHANTOM BOMs - is_phantom SET BEFORE ADDING ITEMS")
    print("=" * 70)
    
    csv_file_path = '/home/ubuntu/frappe-bench/apps/kaiten_erp/BOM (new 2) - BOM (new 2).csv'
    
    # Parse CSV and group by BOM ID
    bom_data = defaultdict(lambda: {"items": [], "item_code": None})
    current_bom_id = None
    
    with open(csv_file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Check if this row starts a new BOM
            if row['ID'] and row['ID'].strip():
                current_bom_id = row['ID'].strip()
                # Set parent item for this BOM
                if row['Item'] and row['Item'].strip():
                    bom_data[current_bom_id]["item_code"] = row['Item'].strip()
            
            # Add child item if present (for current BOM)
            if current_bom_id and row['Item Code (Items)'] and row['Item Code (Items)'].strip():
                child_item_code = row['Item Code (Items)'].strip()
                qty = float(row['Qty (Items)']) if row['Qty (Items)'] else 1.0
                rate = float(row['Rate (Items)']) if row['Rate (Items)'] else 0.0
                uom = row['UOM (Items)'].strip() if row['UOM (Items)'] and row['UOM (Items)'].strip() else "Nos"
                
                bom_data[current_bom_id]["items"].append({
                    "item_code": child_item_code,
                    "qty": qty,
                    "uom": uom,
                    "rate": rate
                })
    
    print(f"\nParsed {len(bom_data)} BOMs from CSV")
    print("-" * 70)
    
    created_count = 0
    error_count = 0
    
    # Create BOMs with is_phantom set BEFORE adding child items
    for bom_id, data in sorted(bom_data.items()):
        try:
            # Step 1: Create new BOM document
            bom = frappe.new_doc("BOM")
            
            # Step 2: Set basic fields including is_phantom FIRST
            bom.item = data["item_code"]
            bom.company = "Rajasthan Solar (Demo)"
            bom.quantity = 1.0
            bom.is_phantom = 1  # SET PHANTOM CHECKBOX FIRST
            bom.is_active = 0   # Draft status
            
            # Step 3: NOW add child items AFTER is_phantom is set
            for item in data["items"]:
                bom.append("items", {
                    "item_code": item["item_code"],
                    "qty": item["qty"],
                    "uom": item["uom"],
                    "rate": item["rate"]
                })
            
            # Step 4: Insert the BOM
            bom.insert(ignore_permissions=True)
            
            created_count += 1
            print(f"✓ PHANTOM BOM: {bom_id} ({data['item_code']}) - {len(data['items'])} items")
            
        except Exception as e:
            error_count += 1
            print(f"✗ Error {bom_id}: {str(e)}")
    
    print("-" * 70)
    print(f"\nCREATION SUMMARY:")
    print(f"Successfully created: {created_count} Phantom BOMs")
    print(f"Errors: {error_count}")
    print("\n" + "=" * 70)
    print("✓ ALL PHANTOM BOMs CREATED WITH CHECKBOX CHECKED!")
    print("=" * 70)

if __name__ == "__main__":
    import frappe
    import os
    os.chdir('/home/ubuntu/frappe-bench/sites')
    frappe.init(site='rgespuat.koristu.app')
    frappe.connect()
    frappe.db.begin()
    create_phantom_boms()
    frappe.db.commit()
    frappe.destroy()
