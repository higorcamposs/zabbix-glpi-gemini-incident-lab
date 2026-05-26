"""
GLPI REST API client: session management, tickets, followups and tasks.
"""

import logging
from typing import Any, Optional

import httpx

from config import Settings
from models import EnrichedTicketPackage

logger = logging.getLogger(__name__)


def mask_secret(value: str, visible: int = 0) -> str:
    """Mask sensitive values for safe logging."""
    if not value:
        return "(empty)"
    return "****"


class GlpiClientError(Exception):
    """Raised when GLPI API returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class GlpiClient:
    """
    GLPI REST client for lab/demo use.

    Flow: initSession -> Ticket -> ITILFollowup (+ optional TicketTask) -> killSession
    """

    def __init__(self, settings: Settings):
        self.base_url = settings.glpi_base_url.rstrip("/")
        self.app_token = settings.glpi_app_token
        self.user_token = settings.glpi_user_token
        self.entity_id = settings.glpi_default_entity_id
        self.category_id = settings.glpi_default_category_id
        self.requester_id = settings.glpi_default_requester_id
        self.technician_id = settings.glpi_default_technician_id
        self.create_task = settings.glpi_create_task
        self._session_token: Optional[str] = None

    def _with_app_token(self, headers: dict[str, str]) -> dict[str, str]:
        if self.app_token.strip():
            headers["App-Token"] = self.app_token
        return headers

    def _headers_init(self) -> dict[str, str]:
        return self._with_app_token(
            {
                "Content-Type": "application/json",
                "Authorization": f"user_token {self.user_token}",
            }
        )

    def _headers_session(self) -> dict[str, str]:
        if not self._session_token:
            raise GlpiClientError("Session not initialized. Call init_session() first.")
        return self._with_app_token(
            {
                "Content-Type": "application/json",
                "Session-Token": self._session_token,
            }
        )

    def _ensure_session(self) -> None:
        if not self._session_token:
            self.init_session()

    def _extract_id(self, data: Any, key: str = "id") -> int:
        item_id = data.get(key) if isinstance(data, dict) else None
        if item_id is None and isinstance(data, list) and data:
            item_id = data[0].get(key)
        if item_id is None:
            raise GlpiClientError(f"GLPI response did not return {key}", body=data)
        return int(item_id)

    def _post_item(self, endpoint: str, input_data: dict[str, Any]) -> int:
        """POST to a GLPI item endpoint and return new record id."""
        self._ensure_session()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    url,
                    headers=self._headers_session(),
                    json={"input": input_data},
                )
                response.raise_for_status()
                return self._extract_id(response.json())
        except httpx.HTTPStatusError as exc:
            logger.error(
                "GLPI POST %s failed: HTTP %s body=%s",
                endpoint,
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise GlpiClientError(
                f"POST {endpoint} failed: {exc.response.text}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise GlpiClientError(f"POST {endpoint} connection error: {exc}") from exc

    def init_session(self) -> str:
        """Start GLPI API session and store session token."""
        url = f"{self.base_url}/initSession"
        logger.info(
            "GLPI initSession -> %s (app_token=%s)",
            url,
            mask_secret(self.app_token),
        )
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=self._headers_init())
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("GLPI initSession failed: HTTP %s", exc.response.status_code)
            raise GlpiClientError(
                f"initSession failed: {exc.response.text}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("GLPI initSession connection error: %s", exc)
            raise GlpiClientError(f"initSession connection error: {exc}") from exc

        token = data.get("session_token")
        if not token:
            raise GlpiClientError("initSession did not return session_token", body=data)

        self._session_token = token
        logger.info("GLPI session started (token=%s)", mask_secret(token))
        return token

    def kill_session(self) -> None:
        """End GLPI API session."""
        if not self._session_token:
            return
        url = f"{self.base_url}/killSession"
        try:
            with httpx.Client(timeout=15.0) as client:
                client.get(url, headers=self._headers_session())
            logger.info("GLPI session ended")
        except httpx.HTTPError as exc:
            logger.warning("GLPI killSession warning: %s", exc)
        finally:
            self._session_token = None

    def health_check(self) -> bool:
        """Return True if initSession succeeds."""
        try:
            self.init_session()
            self.kill_session()
            return True
        except GlpiClientError:
            return False

    def create_ticket(self, title: str, content: str) -> int:
        """Create an incident ticket in GLPI."""
        input_data: dict[str, Any] = {
            "name": title[:255],
            "content": content,
            "entities_id": self.entity_id,
            "type": 1,
            "urgency": 3,
            "impact": 3,
            "priority": 3,
        }
        if self.category_id is not None:
            input_data["itilcategories_id"] = self.category_id
        if self.requester_id is not None:
            input_data["_users_id_requester"] = self.requester_id
        if self.technician_id is not None:
            input_data["_users_id_assign"] = self.technician_id

        logger.info("GLPI create ticket: title=%s", title[:80])
        ticket_id = self._post_item("Ticket", input_data)
        logger.info("GLPI ticket created: id=%s", ticket_id)
        return ticket_id

    def update_ticket_content(self, ticket_id: int, content: str) -> None:
        """Update ticket description (fallback when followup cannot be created)."""
        self._ensure_session()
        url = f"{self.base_url}/Ticket/{ticket_id}"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.put(
                    url,
                    headers=self._headers_session(),
                    json={"input": {"content": content}},
                )
                response.raise_for_status()
            logger.info("GLPI ticket updated: id=%s", ticket_id)
        except httpx.HTTPStatusError as exc:
            raise GlpiClientError(
                f"update ticket failed: {exc.response.text}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise GlpiClientError(f"update ticket connection error: {exc}") from exc

    def create_followup(self, ticket_id: int, content: str) -> int:
        """
        Create ITILFollowup (Acompanhamento) on a ticket.

        This is the preferred place for full AI operational analysis.
        """
        followup_id = self._post_item(
            "ITILFollowup",
            {
                "itemtype": "Ticket",
                "items_id": ticket_id,
                "content": content,
                "is_private": 0,
            },
        )
        logger.info("GLPI followup created: id=%s ticket=%s", followup_id, ticket_id)
        return followup_id

    def create_ticket_task(self, ticket_id: int, name: str, content: str) -> int:
        """Create TicketTask with operational checklist."""
        task_id = self._post_item(
            "TicketTask",
            {
                "tickets_id": ticket_id,
                "name": name[:255],
                "content": content,
                "state": 1,
                "is_private": 0,
            },
        )
        logger.info("GLPI task created: id=%s ticket=%s", task_id, ticket_id)
        return task_id

    def create_enriched_ticket_with_worknotes(
        self,
        package: EnrichedTicketPackage,
    ) -> dict[str, Any]:
        """
        Create ticket with short description, then followup (+ optional task).

        If followup creation fails, appends collapsible full analysis to ticket body.
        """
        ticket_id = self.create_ticket(package.title, package.summary_content)

        result: dict[str, Any] = {
            "ticket_id": ticket_id,
            "followup_id": None,
            "task_id": None,
            "followup_created": False,
            "task_created": False,
            "used_inline_fallback": False,
        }

        try:
            followup_id = self.create_followup(ticket_id, package.followup_content)
            result["followup_id"] = followup_id
            result["followup_created"] = True
        except GlpiClientError as exc:
            logger.warning(
                "GLPI followup failed for ticket %s, using collapsible fallback: %s",
                ticket_id,
                exc,
            )
            merged = package.summary_content + package.fallback_collapsible_content
            self.update_ticket_content(ticket_id, merged)
            result["used_inline_fallback"] = True

        if self.create_task and package.task_content.strip():
            try:
                task_id = self.create_ticket_task(
                    ticket_id,
                    package.task_name,
                    package.task_content,
                )
                result["task_id"] = task_id
                result["task_created"] = True
            except GlpiClientError as exc:
                logger.warning(
                    "GLPI task failed for ticket %s (non-blocking): %s",
                    ticket_id,
                    exc,
                )

        return result

    def __enter__(self) -> "GlpiClient":
        self.init_session()
        return self

    def __exit__(self, *args: Any) -> None:
        self.kill_session()
