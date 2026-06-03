#!/bin/sh
set -e

# Ensure the database schema is up to date before starting the process.
# create_all is idempotent (CREATE ... IF NOT EXISTS), so this is safe to run
# on every container start and from multiple services concurrently.
echo "Ensuring database schema..."
python -m app.scripts.init_db

echo "Seeding first admin account..."
python -m app.scripts.seed_admin

exec "$@"
