"""
Gemini Incident API — Zabbix webhooks to GLPI tickets (plain and Gemini-enriched).

Endpoints:
  GET  /health
  POST /webhook/zabbix/plain
  POST /webhook/zabbix/gemini
  POST /demo/send-sample/plain
  POST /demo/send-sample/gemini
"""

import json
import logging
from pathlib import Path
from typing import Annotated, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from config import Settings, get_settings
from models import (
    HealthResponse,
    WebhookResponse,
    ZabbixWebhookPayload,
)
from services.gemini_client import GeminiClient, GeminiClientError
from services.glpi_client import GlpiClient, GlpiClientError
from services.incident_builder import (
    build_enriched_package,
    build_plain_ticket,
)
from services.mock_ai import analyze_with_mock
from services.zabbix_context import build_alert_context
from utils.logging import configure_logging

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
settings = get_settings()
logger = configure_logging(settings.log_level)

app = FastAPI(
    title="Zabbix GLPI Gemini Incident Lab API",
    description="Recebe webhooks do Zabbix e abre incidentes no GLPI (com ou sem Gemini).",
    version="1.0.0",
)

EXAMPLES_DIR = Path("/app/examples")
# Fallback when running outside Docker (local dev)
if not EXAMPLES_DIR.exists():
    EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

SAMPLE_SCENARIO_FILES = {
    "cpu_high": {
        "plain": "zabbix_payload_cpu_high_traditional.json",
        "gemini": "zabbix_payload_cpu_high_ai.json",
    },
    "memory_high": {
        "plain": "zabbix_payload_memory_high_traditional.json",
        "gemini": "zabbix_payload_memory_high_ai.json",
    },
    "disk_full": {
        "plain": "zabbix_payload_disk_full_traditional.json",
        "gemini": "zabbix_payload_disk_full_ai.json",
    },
    "service_down": {
        "plain": "zabbix_payload_service_down_traditional.json",
        "gemini": "zabbix_payload_service_down_ai.json",
    },
}

ScenarioName = Literal["cpu_high", "memory_high", "disk_full", "service_down"]


# ---------------------------------------------------------------------------
# Webhook authentication
# ---------------------------------------------------------------------------
def verify_webhook_secret(
    request: Request,
    x_webhook_token: Annotated[Optional[str], Header(alias="X-Webhook-Token")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """
    Validate shared secret from header X-Webhook-Token or JSON field 'secret'.
    Returns 401 if secret is wrong or missing when configured.
    """
    expected = settings.webhook_shared_secret.strip()
    if not expected:
        logger.warning("WEBHOOK_SHARED_SECRET is empty — webhook auth disabled (lab only)")
        return

    provided = x_webhook_token
    if not provided:
        provided = request.headers.get("X-Webhook-Token")

    if provided is not None and provided != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret in header")


async def parse_payload(request: Request) -> ZabbixWebhookPayload:
    """Parse JSON body and optionally validate secret field."""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    payload = ZabbixWebhookPayload.model_validate(body)

    settings = get_settings()
    expected = settings.webhook_shared_secret.strip()
    if expected:
        header_token = request.headers.get("X-Webhook-Token")
        payload_secret = payload.secret
        if header_token != expected and payload_secret != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")

    return payload


def open_glpi_ticket(settings: Settings, title: str, content: str) -> int:
    """Create ticket in GLPI with session lifecycle."""
    if not settings.glpi_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "GLPI is not configured. Set GLPI_USER_TOKEN or "
                "GLPI_API_USERNAME + GLPI_API_PASSWORD in .env"
            ),
        )
    client = GlpiClient(settings)
    try:
        with client:
            return client.create_ticket(title, content)
    except GlpiClientError as exc:
        logger.error("GLPI error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def open_glpi_enriched_ticket(settings: Settings, package) -> dict:
    """Create Gemini-enriched ticket: short body + followup (+ optional task)."""
    if not settings.glpi_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "GLPI is not configured. Set GLPI_USER_TOKEN or "
                "GLPI_API_USERNAME + GLPI_API_PASSWORD in .env"
            ),
        )
    client = GlpiClient(settings)
    try:
        with client:
            return client.create_enriched_ticket_with_worknotes(package)
    except GlpiClientError as exc:
        logger.error("GLPI error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def analyze_alert(ctx, settings: Settings):
    """Run the configured AI provider for the enriched flow."""
    if settings.ai_provider == "mock":
        logger.warning(
            "AI_PROVIDER=mock — using local analysis, not Gemini. "
            "Set AI_PROVIDER=gemini and GEMINI_API_KEY for the real lab flow."
        )
        return analyze_with_mock(ctx)

    if not settings.gemini_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "AI_PROVIDER=gemini requires GEMINI_API_KEY in .env. "
                "Get a free key at https://aistudio.google.com/apikey "
                "or set AI_PROVIDER=mock only as an optional fallback."
            ),
        )

    try:
        gemini = GeminiClient(settings)
        return gemini.analyze(ctx)
    except GeminiClientError as exc:
        logger.error("Gemini error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _load_sample_payload(
    name: ScenarioName,
    flow: Literal["plain", "gemini"],
    settings: Settings,
) -> ZabbixWebhookPayload:
    """Load example JSON for demo endpoints."""
    files = SAMPLE_SCENARIO_FILES.get(name)
    if not files:
        raise HTTPException(status_code=400, detail=f"Unknown sample: {name}")

    filename = files[flow]
    sample_path = EXAMPLES_DIR / filename
    if not sample_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Sample file not found: {sample_path}",
        )

    data = json.loads(sample_path.read_text(encoding="utf-8"))
    if settings.webhook_shared_secret.strip() and "secret" not in data:
        data["secret"] = settings.webhook_shared_secret

    return ZabbixWebhookPayload.model_validate(data)


def _verify_demo_token(
    x_webhook_token: Optional[str],
    settings: Settings,
) -> None:
    expected = settings.webhook_shared_secret.strip()
    if expected and x_webhook_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Application health and configuration presence (no secret values)."""
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        ai_provider=settings.ai_provider,
        ai_configured=settings.ai_configured,
        gemini_configured=settings.gemini_configured,
        glpi_configured=settings.glpi_configured,
        webhook_secret_configured=bool(settings.webhook_shared_secret.strip()),
    )


@app.post(
    "/webhook/zabbix/plain",
    response_model=WebhookResponse,
    dependencies=[Depends(verify_webhook_secret)],
)
async def webhook_zabbix_plain(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> WebhookResponse:
    """
    Receive Zabbix alert and open a simple GLPI ticket without AI.
    """
    payload = await parse_payload(request)
    ctx = build_alert_context(payload)
    logger.info(
        "Webhook plain received: event_id=%s host=%s scenario=%s recovery=%s",
        ctx.event_id,
        ctx.host_name,
        ctx.lab_scenario,
        ctx.is_recovery,
    )
    ticket = build_plain_ticket(ctx)

    ticket_id = open_glpi_ticket(settings, ticket.title, ticket.content)

    return WebhookResponse(
        success=True,
        message="Ticket created (plain flow, no AI)",
        flow="plain",
        ticket_id=ticket_id,
        event_id=ctx.event_id,
    )


@app.post(
    "/webhook/zabbix/gemini",
    response_model=WebhookResponse,
    dependencies=[Depends(verify_webhook_secret)],
)
async def webhook_zabbix_gemini(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> WebhookResponse:
    """
    Receive Zabbix alert, analyze with Gemini (or mock fallback), open enriched GLPI ticket.
    """
    payload = await parse_payload(request)
    ctx = build_alert_context(payload)
    logger.info(
        "Webhook enriched received: provider=%s event_id=%s host=%s scenario=%s recovery=%s",
        settings.ai_provider,
        ctx.event_id,
        ctx.host_name,
        ctx.lab_scenario,
        ctx.is_recovery,
    )

    analysis = analyze_alert(ctx, settings)
    package = build_enriched_package(ctx, analysis)
    glpi_result = open_glpi_enriched_ticket(settings, package)

    used_fallback = settings.ai_provider == "mock" or bool(analysis.raw_response)
    return WebhookResponse(
        success=True,
        message=f"Ticket created (AI-enriched flow, provider={settings.ai_provider})",
        flow="gemini",
        ticket_id=glpi_result["ticket_id"],
        event_id=ctx.event_id,
        ai_fallback=used_fallback,
        details={
            "ai_provider": settings.ai_provider,
            "prioridade_sugerida": analysis.prioridade_sugerida,
            "time_sugerido": analysis.time_sugerido,
            "followup_id": glpi_result.get("followup_id"),
            "task_id": glpi_result.get("task_id"),
            "followup_created": glpi_result.get("followup_created"),
            "task_created": glpi_result.get("task_created"),
            "used_inline_fallback": glpi_result.get("used_inline_fallback"),
        },
    )


@app.post(
    "/demo/send-sample/plain",
    response_model=WebhookResponse,
)
async def demo_send_sample_plain(
    name: Annotated[
        ScenarioName,
        Query(description="Sample payload scenario"),
    ] = "cpu_high",
    x_webhook_token: Annotated[Optional[str], Header(alias="X-Webhook-Token")] = None,
    settings: Settings = Depends(get_settings),
) -> WebhookResponse:
    """
    Load an example Zabbix payload and process the traditional (no AI) flow.
    """
    _verify_demo_token(x_webhook_token, settings)
    payload = _load_sample_payload(name, "plain", settings)
    ctx = build_alert_context(payload)
    ticket = build_plain_ticket(ctx)
    ticket_id = open_glpi_ticket(settings, ticket.title, ticket.content)
    return WebhookResponse(
        success=True,
        message=f"Demo sample '{name}' processed (plain)",
        flow="plain",
        ticket_id=ticket_id,
        event_id=ctx.event_id,
    )


@app.post(
    "/demo/send-sample/gemini",
    response_model=WebhookResponse,
)
async def demo_send_sample_gemini(
    name: Annotated[
        ScenarioName,
        Query(description="Sample payload scenario"),
    ] = "cpu_high",
    x_webhook_token: Annotated[Optional[str], Header(alias="X-Webhook-Token")] = None,
    settings: Settings = Depends(get_settings),
) -> WebhookResponse:
    """
    Load an example Zabbix payload and process the Gemini-enriched flow.
    """
    _verify_demo_token(x_webhook_token, settings)
    payload = _load_sample_payload(name, "gemini", settings)
    ctx = build_alert_context(payload)
    analysis = analyze_alert(ctx, settings)
    package = build_enriched_package(ctx, analysis)
    glpi_result = open_glpi_enriched_ticket(settings, package)
    used_fallback = settings.ai_provider == "mock" or bool(analysis.raw_response)
    return WebhookResponse(
        success=True,
        message=f"Demo sample '{name}' processed (provider={settings.ai_provider})",
        flow="gemini",
        ticket_id=glpi_result["ticket_id"],
        event_id=ctx.event_id,
        ai_fallback=used_fallback,
        details={
            "followup_id": glpi_result.get("followup_id"),
            "task_created": glpi_result.get("task_created"),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
