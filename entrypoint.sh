#!/bin/bash
set -e

# Seed reporting/resources from bundled defaults on first run.
# Only copies if the bind-mounted directory is empty.
target="/app/reporting/resources"
default="/app/defaults/reporting_resources"
if [ -d "$default" ] && [ -z "$(ls -A "$target" 2>/dev/null)" ]; then
    echo "[ghostbadger] Seeding reporting/resources from image defaults..."
    cp -r "$default/." "$target/"
fi

exec "$@"
