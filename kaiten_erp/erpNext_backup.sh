#!/bin/bash

set -e

BENCH_PATH="/home/ubuntu/frappe-bench"
SITES_PATH="$BENCH_PATH/sites"
DEV_BENCH_BACKUP="/home/ubuntu/Main_Backup"

cd "$BENCH_PATH"

# Detect valid sites
echo "📂 Detecting available ERPNext sites..."
echo

SITES=()
for dir in "$SITES_PATH"/*; do
  if [ -d "$dir" ] && [ -f "$dir/site_config.json" ]; then
    SITES+=("$(basename "$dir")")
  fi
done

if [ ${#SITES[@]} -eq 0 ]; then
  echo "❌ No valid ERPNext sites found!"
  exit 1
fi

echo "Select the NUMBER of the site to back up:"

select SITE in "${SITES[@]}"; do
  if [[ -n "$SITE" ]]; then
    echo "✅ Selected site: $SITE"
    break
  else
    echo "❌ Invalid selection. Try again."
  fi
done

SITE_BACKUP_DIR="$DEV_BENCH_BACKUP/$SITE"

# Create Dev_Bench_Backup folder if it doesn't exist
if [ ! -d "$DEV_BENCH_BACKUP" ]; then
  echo
  echo "📁 Creating main backup directory: $DEV_BENCH_BACKUP"
  mkdir -p "$DEV_BENCH_BACKUP"
fi

# Create site-specific folder if it doesn't exist
if [ ! -d "$SITE_BACKUP_DIR" ]; then
  echo "📁 Creating site backup directory: $SITE_BACKUP_DIR"
  mkdir -p "$SITE_BACKUP_DIR"
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATE_STAMP="${TIMESTAMP:0:8}"
TEMP_BACKUP_DIR="$SITES_PATH/$SITE/private/backups"

echo
echo "🚀 Running bench backup for $SITE..."
bench --site "$SITE" backup --with-files --compress

echo
echo "📦 Zipping backup files..."
cd "$TEMP_BACKUP_DIR"

ZIP_NAME="${SITE}_FULL_BACKUP_${TIMESTAMP}.zip"
ZIP_PATH="$SITE_BACKUP_DIR/$ZIP_NAME"

zip -r "$ZIP_PATH" ./*"${DATE_STAMP}"*

echo
echo "🧹 Cleaning raw backup files..."
rm -f ./*"${DATE_STAMP}"*

echo
echo "✅ Backup completed successfully!"
echo "📍 Backup stored at:"
echo "   $ZIP_PATH"
