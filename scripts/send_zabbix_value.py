#!/usr/bin/env python3
"""
Send one fake metric value to Zabbix using the native sender protocol.

This keeps the lab portable: students do not need zabbix_sender installed on
their workstation. The examples call this script inside the zabbix-sender
container created by docker compose.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys


def _read_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("connection closed while reading Zabbix response")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def send_value(server: str, port: int, host: str, key: str, value: str, timeout: float) -> dict:
    payload = {
        "request": "sender data",
        "data": [
            {
                "host": host,
                "key": key,
                "value": value,
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    packet = b"ZBXD\x01" + struct.pack("<Q", len(body)) + body

    with socket.create_connection((server, port), timeout=timeout) as sock:
        sock.sendall(packet)
        header = _read_exact(sock, 13)
        if header[:5] != b"ZBXD\x01":
            raise RuntimeError(f"invalid Zabbix response header: {header!r}")
        length = struct.unpack("<Q", header[5:13])[0]
        response_body = _read_exact(sock, length)

    response = json.loads(response_body.decode("utf-8"))
    info = response.get("info", "")
    if response.get("response") != "success" or "failed: 0" not in info:
        raise RuntimeError(f"Zabbix rejected value: {response}")
    return response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a fake trapper metric to Zabbix")
    parser.add_argument("--server", default="zabbix-server", help="Zabbix server host")
    parser.add_argument("--port", type=int, default=10051, help="Zabbix trapper port")
    parser.add_argument("--host", required=True, help="Zabbix host name")
    parser.add_argument("--key", required=True, help="Zabbix item key")
    parser.add_argument("--value", required=True, help="Value to send")
    parser.add_argument("--timeout", type=float, default=10.0, help="Socket timeout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        response = send_value(args.server, args.port, args.host, args.key, args.value, args.timeout)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"sent host={args.host} key={args.key} value={args.value} "
        f"response={response.get('response')} info={response.get('info')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
