#!/usr/bin/env python3
"""
Validate and prepare the GLPI side of the lab.

GLPI usually requires the first web installation and API token generation to be
done in the UI. When tokens are present, this script validates the API and
creates the "Zabbix Alerts" category if possible.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx


GLPI_BASE_URL = os.getenv("GLPI_BASE_URL", "http://localhost:8081/apirest.php").rstrip("/")
GLPI_APP_TOKEN = os.getenv("GLPI_APP_TOKEN", "")
GLPI_USER_TOKEN = os.getenv("GLPI_USER_TOKEN", "")
GLPI_DEFAULT_ENTITY_ID = int(os.getenv("GLPI_DEFAULT_ENTITY_ID", "0") or "0")
TIMEOUT_SECONDS = int(os.getenv("GLPI_BOOTSTRAP_TIMEOUT", "240"))
CATEGORY_NAME = os.getenv("GLPI_LAB_CATEGORY_NAME", "Zabbix Alerts")


def mask(value: str) -> str:
    if not value:
        return "(empty)"
    return "****"


class GlpiApi:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.session_token: str | None = None
        self.client = httpx.Client(timeout=30.0)

    def init_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"user_token {GLPI_USER_TOKEN}",
        }
        if GLPI_APP_TOKEN.strip():
            headers["App-Token"] = GLPI_APP_TOKEN
        return headers

    def session_headers(self) -> dict[str, str]:
        if not self.session_token:
            raise RuntimeError("GLPI session is not initialized")
        headers = {
            "Content-Type": "application/json",
            "Session-Token": self.session_token,
        }
        if GLPI_APP_TOKEN.strip():
            headers["App-Token"] = GLPI_APP_TOKEN
        return headers

    def wait_http(self, timeout: int) -> None:
        deadline = time.time() + timeout
        last_error = ""
        while time.time() < deadline:
            try:
                response = self.client.get(self.base_url, timeout=10.0)
                if response.status_code < 500:
                    print(f"GLPI HTTP is reachable: {self.base_url}")
                    return
                last_error = f"HTTP {response.status_code}"
            except Exception as exc:
                last_error = str(exc)
            print(f"Waiting for GLPI at {self.base_url}: {last_error}")
            time.sleep(5)
        raise TimeoutError(f"GLPI did not become reachable: {last_error}")

    def init_session(self) -> None:
        response = self.client.get(f"{self.base_url}/initSession", headers=self.init_headers())
        response.raise_for_status()
        data = response.json()
        token = data.get("session_token")
        if not token:
            raise RuntimeError(f"initSession did not return session_token: {data}")
        self.session_token = token
        print("GLPI API session initialized")

    def kill_session(self) -> None:
        if not self.session_token:
            return
        try:
            self.client.get(f"{self.base_url}/killSession", headers=self.session_headers())
            print("GLPI API session closed")
        finally:
            self.session_token = None

    def get_categories(self) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.base_url}/ITILCategory",
            headers=self.session_headers(),
            params={"range": "0-999"},
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    def create_category(self) -> int:
        payload = {
            "input": {
                "name": CATEGORY_NAME,
                "entities_id": GLPI_DEFAULT_ENTITY_ID,
                "is_recursive": 1,
                "comment": "Created by the Zabbix GLPI AI incident lab bootstrap.",
            }
        }
        response = self.client.post(
            f"{self.base_url}/ITILCategory",
            headers=self.session_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        category_id = data.get("id")
        if category_id is None and isinstance(data, list) and data:
            category_id = data[0].get("id")
        if category_id is None:
            raise RuntimeError(f"ITILCategory creation did not return id: {data}")
        return int(category_id)


def print_manual_token_instructions() -> None:
    print(
        """
GLPI API tokens are not configured yet.

Manual one-time setup:
1. Open GLPI: http://localhost:8081
2. Finish the GLPI installation wizard if this is the first run.
3. Enable REST API in Configuration > General > API.
4. Create an API client and copy its App-Token to GLPI_APP_TOKEN.
5. Create or choose an integration user and generate its User-Token.
6. Put both tokens in .env and run:
   docker compose restart gemini-incident-api
   docker compose run --rm glpi-bootstrap

The lab uses AI_PROVIDER=gemini by default; set GEMINI_API_KEY in .env or use AI_PROVIDER=mock.
"""
    )


def main() -> int:
    print("Starting GLPI bootstrap")
    print(f"GLPI API URL: {GLPI_BASE_URL}")
    print(f"GLPI app token: {mask(GLPI_APP_TOKEN)}")
    print(f"GLPI user token: {mask(GLPI_USER_TOKEN)}")

    api = GlpiApi(GLPI_BASE_URL)
    try:
        api.wait_http(TIMEOUT_SECONDS)
        if not GLPI_USER_TOKEN.strip():
            print_manual_token_instructions()
            return 0

        api.init_session()
        categories = api.get_categories()
        existing = next((item for item in categories if item.get("name") == CATEGORY_NAME), None)
        if existing:
            print(f"GLPI category exists: {CATEGORY_NAME} (id={existing.get('id')})")
        else:
            category_id = api.create_category()
            print(f"GLPI category created: {CATEGORY_NAME} (id={category_id})")
            print(f"Optional: set GLPI_DEFAULT_CATEGORY_ID={category_id} in .env")
    except httpx.HTTPStatusError as exc:
        print(f"GLPI bootstrap HTTP error: {exc.response.status_code} {exc.response.text[:500]}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"GLPI bootstrap failed: {exc}", file=sys.stderr)
        return 1
    finally:
        api.kill_session()

    print("GLPI bootstrap completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
