#!/bin/bash
# Creates the analytics database (wadw) and the Neurana ERP database (nedb)
# on first Postgres volume init. Both live on this same server.
# For already-initialized volumes this script does NOT run.
set -euo pipefail

DW_NAME="${DW_NAME:-wadw}"
NE_NAME="${NE_DB_NAME:-nedb}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	SELECT 'CREATE DATABASE ${DW_NAME}'
	WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DW_NAME}')\gexec
	SELECT 'CREATE DATABASE ${NE_NAME}'
	WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${NE_NAME}')\gexec
EOSQL

echo "analytics database '${DW_NAME}' is ready"
echo "neurana database '${NE_NAME}' is ready"
