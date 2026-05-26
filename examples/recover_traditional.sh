#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/lib/send_trapper_value.sh" "srv-linux-traditional" "cpu.util" "20"
"${SCRIPT_DIR}/lib/send_trapper_value.sh" "srv-linux-traditional" "memory.util" "35"
"${SCRIPT_DIR}/lib/send_trapper_value.sh" "srv-linux-traditional" "disk.util" "40"
"${SCRIPT_DIR}/lib/send_trapper_value.sh" "srv-linux-traditional" "service.status" "1"
