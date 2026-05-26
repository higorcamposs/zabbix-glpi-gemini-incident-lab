"""
Pydantic models for Zabbix webhooks, alert context, AI analysis and tickets.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ZabbixWebhookPayload(BaseModel):
    """Expected JSON payload from Zabbix webhook (or demo samples)."""

    # Optional webhook auth (fallback if header not sent)
    secret: Optional[str] = None

    event_id: Optional[str] = None
    event_name: Optional[str] = None
    event_severity: Optional[str] = None
    event_status: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    recovery_status: Optional[str] = None

    host_id: Optional[str] = None
    host_name: Optional[str] = None
    host_ip: Optional[str] = None
    host_groups: Optional[str] = None
    host_templates: Optional[str] = None
    host_description: Optional[str] = None

    trigger_id: Optional[str] = None
    trigger_name: Optional[str] = None
    trigger_expression: Optional[str] = None
    trigger_description: Optional[str] = None

    item_name: Optional[str] = None
    item_value: Optional[str] = None
    item_key: Optional[str] = None

    operational_data: Optional[str] = None
    tags: Optional[str] = None
    macros: Optional[str] = None
    problem_url: Optional[str] = None

    # Didactic lab fields
    flow_type: Optional[str] = None
    lab_scenario: Optional[str] = None
    demo_description: Optional[str] = None

    # Optional extended context
    history_summary: Optional[str] = None

    model_config = {"extra": "allow"}


class AlertContext(BaseModel):
    """Normalized and enriched alert context for tickets and Gemini."""

    event_id: str = "unknown"
    event_name: str = "Unknown event"
    event_severity: str = "Not classified"
    event_status: str = "unknown"
    event_datetime: str = ""
    recovery_status: str = ""
    is_recovery: bool = False

    host_id: str = ""
    host_name: str = "unknown-host"
    host_ip: str = ""
    host_groups: str = ""
    host_templates: str = ""
    host_description: str = ""

    trigger_id: str = ""
    trigger_name: str = ""
    trigger_expression: str = ""
    trigger_description: str = ""

    item_name: str = ""
    item_value: str = ""
    item_key: str = ""

    operational_data: str = ""
    tags: str = ""
    macros: str = ""
    problem_url: str = ""
    history_summary: str = ""

    flow_type: str = ""
    lab_scenario: str = ""
    demo_description: str = ""

    # Human-readable summary for prompts
    context_block: str = Field(default="", description="Formatted block for AI and tickets")


class ComandoUtil(BaseModel):
    """Safe diagnostic command suggested by Gemini."""

    objetivo: str = ""
    sistema: str = ""
    comando: str = ""
    observacao: str = ""

    model_config = {"extra": "allow"}


class AIAnalysis(BaseModel):
    """Structured response from Gemini incident analyst."""

    resumo_executivo: str = ""
    impacto_potencial: str = ""
    causa_provavel: str = ""
    possiveis_causas: list[str] = Field(default_factory=list)
    validacoes_recomendadas: list[str] = Field(default_factory=list)
    comandos_uteis: list[ComandoUtil] = Field(default_factory=list)
    proximos_passos_n1: list[str] = Field(default_factory=list)
    proximos_passos_n2: list[str] = Field(default_factory=list)
    criterios_de_escalonamento: list[str] = Field(default_factory=list)
    evidencias_relevantes: list[str] = Field(default_factory=list)
    time_sugerido: str = ""
    prioridade_sugerida: str = ""
    risco_operacional: str = ""
    mensagem_para_chamado: str = ""

    # Set when JSON parse failed and raw text was used
    raw_response: Optional[str] = None

    model_config = {"extra": "allow"}


class TicketDraft(BaseModel):
    """Ticket title and HTML/text content ready for GLPI."""

    title: str
    content: str


class EnrichedTicketPackage(BaseModel):
    """
    Gemini-enriched ticket split for GLPI readability:
    short main description + followup worknote + optional task checklist.
    """

    title: str
    summary_content: str
    followup_content: str
    task_name: str = "Checklist operacional — triagem N1"
    task_content: str = ""
    fallback_collapsible_content: str = ""


class HealthResponse(BaseModel):
    status: str
    app_env: str
    ai_provider: str
    ai_configured: bool
    gemini_configured: bool
    glpi_configured: bool
    webhook_secret_configured: bool


class WebhookResponse(BaseModel):
    success: bool
    message: str
    flow: str
    ticket_id: Optional[int] = None
    event_id: Optional[str] = None
    ai_fallback: Optional[bool] = None
    details: Optional[dict[str, Any]] = None
