"""
Normalize Zabbix webhook payloads into a single AlertContext object.
"""

from models import AlertContext, ZabbixWebhookPayload


def _safe(value: str | None, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _is_recovery(payload: ZabbixWebhookPayload) -> bool:
    recovery = _safe(payload.recovery_status).lower()
    status = _safe(payload.event_status).lower()
    if recovery in ("yes", "1", "true", "resolved", "ok"):
        return True
    if status in ("resolved", "ok", "recovery"):
        return True
    name = _safe(payload.event_name).lower()
    return "resolved" in name or "recovery" in name


def _looks_unexpanded_macro(value: str) -> bool:
    return value.startswith("{") and value.endswith("}")


def _derive_lab_scenario(payload: ZabbixWebhookPayload) -> str:
    """Best-effort scenario inference when a Zabbix macro is not expanded."""
    explicit = _safe(payload.lab_scenario)
    if explicit and not _looks_unexpanded_macro(explicit):
        return explicit

    text = " ".join(
        [
            _safe(payload.event_name),
            _safe(payload.trigger_name),
            _safe(payload.item_key),
        ]
    ).lower()
    if "cpu" in text:
        return "cpu_high"
    if "memory" in text or "mem" in text:
        return "memory_high"
    if "disk" in text or "vfs.fs" in text:
        return "disk_full"
    if "service" in text:
        return "service_down"
    return explicit


def _build_context_block(ctx: AlertContext) -> str:
    """Format alert data as a readable block for prompts and ticket bodies."""
    lines = [
        f"Event ID: {ctx.event_id}",
        f"Event: {ctx.event_name}",
        f"Severidade: {ctx.event_severity}",
        f"Status: {ctx.event_status}",
        f"Recovery status: {ctx.recovery_status}",
        f"Data/Hora: {ctx.event_datetime}",
        f"Tipo: {'RECOVERY' if ctx.is_recovery else 'PROBLEM'}",
        f"Fluxo didático: {ctx.flow_type}",
        f"Cenário do lab: {ctx.lab_scenario}",
        f"Descrição da demo: {ctx.demo_description}",
        "",
        "=== Host ===",
        f"Nome: {ctx.host_name}",
        f"ID: {ctx.host_id}",
        f"IP: {ctx.host_ip}",
        f"Grupos: {ctx.host_groups}",
        f"Templates: {ctx.host_templates}",
        f"Descrição: {ctx.host_description}",
        "",
        "=== Trigger ===",
        f"ID: {ctx.trigger_id}",
        f"Nome: {ctx.trigger_name}",
        f"Expressão: {ctx.trigger_expression}",
        f"Descrição: {ctx.trigger_description}",
        f"Dados operacionais: {ctx.operational_data}",
        "",
        "=== Item ===",
        f"Nome: {ctx.item_name}",
        f"Chave: {ctx.item_key}",
        f"Valor atual: {ctx.item_value}",
        "",
        "=== Contexto adicional ===",
        f"Tags: {ctx.tags}",
        f"Macros: {ctx.macros}",
        f"URL do problema: {ctx.problem_url}",
    ]
    if ctx.history_summary:
        lines.extend(["", "=== Histórico resumido ===", ctx.history_summary])
    return "\n".join(lines)


def build_alert_context(payload: ZabbixWebhookPayload) -> AlertContext:
    """
    Convert raw Zabbix webhook JSON into a normalized AlertContext.

    This is the single object used by incident_builder and gemini_client.
    """
    event_date = _safe(payload.event_date)
    event_time = _safe(payload.event_time)
    event_datetime = f"{event_date} {event_time}".strip() or "N/A"

    ctx = AlertContext(
        event_id=_safe(payload.event_id, "unknown"),
        event_name=_safe(payload.event_name, "Unknown event"),
        event_severity=_safe(payload.event_severity, "Not classified"),
        event_status=_safe(payload.event_status, "unknown"),
        event_datetime=event_datetime,
        recovery_status=_safe(payload.recovery_status),
        is_recovery=_is_recovery(payload),
        host_id=_safe(payload.host_id),
        host_name=_safe(payload.host_name, "unknown-host"),
        host_ip=_safe(payload.host_ip),
        host_groups=_safe(payload.host_groups),
        host_templates=_safe(payload.host_templates),
        host_description=_safe(payload.host_description),
        trigger_id=_safe(payload.trigger_id),
        trigger_name=_safe(payload.trigger_name),
        trigger_expression=_safe(payload.trigger_expression),
        trigger_description=_safe(payload.trigger_description),
        item_name=_safe(payload.item_name),
        item_value=_safe(payload.item_value),
        item_key=_safe(payload.item_key),
        operational_data=_safe(payload.operational_data),
        tags=_safe(payload.tags),
        macros=_safe(payload.macros),
        problem_url=_safe(payload.problem_url),
        history_summary=_safe(payload.history_summary),
        flow_type=_safe(payload.flow_type),
        lab_scenario=_derive_lab_scenario(payload),
        demo_description=_safe(payload.demo_description),
    )
    ctx.context_block = _build_context_block(ctx)
    return ctx
