#!/usr/bin/env python3
"""
Auto-trigger demo alerts after Zabbix bootstrap.

When AUTO_TRIGGER_DEMO_ALERTS=true (default), sends cpu.util=95 to both lab hosts
so students see two GLPI tickets on first boot: plain and Gemini-enriched.
"""

from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path

# Allow importing send_zabbix_value from the same directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from send_zabbix_value import send_value  # noqa: E402

AUTO_TRIGGER = os.getenv("AUTO_TRIGGER_DEMO_ALERTS", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
ZABBIX_SERVER = os.getenv("ZABBIX_SENDER_SERVER", "zabbix-server")
ZABBIX_PORT = int(os.getenv("ZABBIX_SENDER_PORT", "10051"))
WAIT_SECONDS = int(os.getenv("DEMO_TRIGGER_WAIT_SECONDS", "300"))
POLL_INTERVAL = 5

TRADITIONAL_HOST = "srv-linux-traditional"
AI_HOST = "srv-linux-ai"
DEMO_KEY = "cpu.util"
DEMO_VALUE = "95"


def wait_for_trapper(server: str, port: int, timeout: int) -> None:
    """Wait until Zabbix trapper port accepts connections."""
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with socket.create_connection((server, port), timeout=5.0):
                print(f"Zabbix trapper reachable at {server}:{port}")
                return
        except OSError as exc:
            last_error = str(exc)
            print(f"Waiting for Zabbix trapper at {server}:{port}: {last_error}")
            time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Zabbix trapper not available: {last_error}")


def main() -> int:
    if not AUTO_TRIGGER:
        print("AUTO_TRIGGER_DEMO_ALERTS=false — skipping demo alert trigger")
        return 0

    print("AUTO_TRIGGER_DEMO_ALERTS=true — triggering demo CPU alerts")
    try:
        wait_for_trapper(ZABBIX_SERVER, ZABBIX_PORT, WAIT_SECONDS)
        # Brief pause so bootstrap actions are fully active
        time.sleep(3)

        send_value(ZABBIX_SERVER, ZABBIX_PORT, TRADITIONAL_HOST, DEMO_KEY, DEMO_VALUE, 10.0)
        print(f"Sent {DEMO_KEY}={DEMO_VALUE} to {TRADITIONAL_HOST} (traditional flow)")

        time.sleep(2)

        send_value(ZABBIX_SERVER, ZABBIX_PORT, AI_HOST, DEMO_KEY, DEMO_VALUE, 10.0)
        print(f"Sent {DEMO_KEY}={DEMO_VALUE} to {AI_HOST} (Gemini flow)")

    except Exception as exc:
        print(f"Demo trigger failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Demo alerts sent. Check Zabbix Problems and GLPI tickets "
        "(traditional + AI/Zabbix enriched)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
