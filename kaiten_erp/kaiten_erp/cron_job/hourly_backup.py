import os
import subprocess
import zipfile
from datetime import datetime
import frappe


def take_full_backup():
    site = frappe.local.site

    bench_path = "/home/ubuntu/frappe-bench"
    sites_path = os.path.join(bench_path, "sites")
    main_backup_path = "/home/ubuntu/Main_Backup"

    site_backup_dir = os.path.join(main_backup_path, site)
    os.makedirs(site_backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_stamp = timestamp[:8]

    temp_backup_dir = os.path.join(
        sites_path, site, "private", "backups"
    )

    # Step 1 — Run bench backup
    subprocess.run(
        ["bench", "--site", site, "backup", "--with-files", "--compress"],
        cwd=bench_path,
        check=True
    )

    # Step 2 — Collect today's backup files
    files_to_zip = [
        f for f in os.listdir(temp_backup_dir)
        if date_stamp in f
    ]

    if not files_to_zip:
        frappe.log_error("No backup files found", "Hourly Backup")
        return

    # Step 3 — Create final zip
    zip_name = f"{site}_FULL_BACKUP_{timestamp}.zip"
    zip_path = os.path.join(site_backup_dir, zip_name)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files_to_zip:
            full_path = os.path.join(temp_backup_dir, file)
            zipf.write(full_path, arcname=file)

    # Step 4 — Cleanup raw files
    for file in files_to_zip:
        os.remove(os.path.join(temp_backup_dir, file))

    frappe.logger().info(f"Backup stored at {zip_path}")