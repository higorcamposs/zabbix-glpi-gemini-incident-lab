#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <host> <item_key> <value>" >&2
  exit 2
fi

HOST_NAME="$1"
ITEM_KEY="$2"
ITEM_VALUE="$3"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_DIR}"

if ! docker compose ps --services --status running | grep -qx "zabbix-sender"; then
  echo "zabbix-sender service is not running. Start the lab with: docker compose up -d" >&2
  exit 1
fi

docker compose exec -T zabbix-sender python /scripts/send_zabbix_value.py \
  --server "${ZABBIX_SENDER_SERVER:-zabbix-server}" \
  --port "${ZABBIX_SENDER_PORT:-10051}" \
  --host "${HOST_NAME}" \
  --key "${ITEM_KEY}" \
  --value "${ITEM_VALUE}"
