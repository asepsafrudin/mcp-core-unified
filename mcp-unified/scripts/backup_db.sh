#!/bin/bash
# MCP Database Backup Script
set -e

BACKUP_DIR=\"/var/backups/mcp-unified\"
DB_URL=\"${DATABASE_URL:-postgresql://localhost/mcp_db}\"

mkdir -p $BACKUP_DIR
pg_dump \"${DB_URL#postgresql://}\" > \"$BACKUP_DIR/db-$(date +%Y%m%d-%H%M).sql\"

echo \"✅ Backup completed: $BACKUP_DIR/db-$(date +%Y%m%d-%H%M).sql\"

