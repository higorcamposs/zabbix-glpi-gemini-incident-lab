#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/lib/send_trapper_value.sh" "srv-linux-ai" "cpu.util" "20"
"${SCRIPT_DIR}/lib/send_trapper_value.sh" "srv-linux-ai" "memory.util" "35"
"${SCRIPT_DIR}/lib/send_trapper_value.sh" "srv-linux-ai" "disk.util" "40"
"${SCRIPT_DIR}/lib/send_trapper_value.sh" "srv-linux-ai" "service.status" "1"
