"""
Build GLPI ticket title and content for plain and AI-enriched flows.

Plain flow: minimal ticket (essential fields only).
Enriched flow: short ticket body + full analysis for ITILFollowup (+ optional Task).
"""

import json
import re

from models import AIAnalysis, AlertContext, ComandoUtil, EnrichedTicketPackage, TicketDraft

# Default thresholds per lab scenario (display in summary)
_SCENARIO_LIMITS: dict[str, str] = {
    "cpu_high": "> 90%",
    "memory_high": "> 90%",
    "disk_full": "> 90%",
    "service_down": "= 0 (indisponível)",
}


def _list_to_text(items: list[str], prefix: str = "- ") -> str:
    if not items:
        return f"{prefix}(nenhum)"
    return "\n".join(f"{prefix}{item}" for item in items)


def _macro_value(macros: str, key: str) -> str:
    """Extract {$KEY}=value from macros summary string."""
    if not macros:
        return ""
    pattern = re.compile(rf"\{{\${key}\}}\s*=\s*([^;]+)", re.IGNORECASE)
    match = pattern.search(macros)
    return match.group(1).strip() if match else ""


def _derive_limit(ctx: AlertContext) -> str:
    scenario = (ctx.lab_scenario or "").lower()
    if scenario in _SCENARIO_LIMITS:
        return _SCENARIO_LIMITS[scenario]
    expr = ctx.trigger_expression or ""
    if ">" in expr:
        part = expr.split(">")[-1].strip().rstrip(")")
        return f"> {part}" if part else "conforme trigger"
    if "=" in expr:
        part = expr.split("=")[-1].strip().rstrip(")")
        return f"= {part}" if part else "conforme trigger"
    return "conforme trigger"


def _short_ai_summary(analysis: AIAnalysis, max_chars: int = 380) -> str:
    """Two or three lines for the main ticket body."""
    text = (analysis.resumo_executivo or "").strip()
    if not text and analysis.mensagem_para_chamado:
        text = analysis.mensagem_para_chamado.strip().split("\n")[0]
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + "…"


def _comandos_to_html(comandos: list[ComandoUtil]) -> str:
    if not comandos:
        return "<p><em>Nenhum comando sugerido.</em></p>"
    rows = []
    for cmd in comandos:
        rows.append(
            f"<tr>"
            f"<td>{cmd.sistema or 'Geral'}</td>"
            f"<td>{cmd.objetivo or '—'}</td>"
            f"<td><code>{cmd.comando or '—'}</code></td>"
            f"<td>{cmd.observacao or '—'}</td>"
            f"</tr>"
        )
    return (
        "<table border='1' cellpadding='6' cellspacing='0' "
        "style='border-collapse:collapse;width:100%'>"
        "<thead><tr>"
        "<th>Sistema</th><th>Objetivo</th><th>Comando</th><th>Observação</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def build_plain_ticket(ctx: AlertContext) -> TicketDraft:
    """Minimal GLPI ticket — essential monitoring data only."""
    title = f"[Zabbix] {ctx.event_severity} - {ctx.host_name}"
    limit = _derive_limit(ctx)

    content = f"""<p><strong>Alerta automático do Zabbix</strong> (sem análise de IA)</p>

<p>
  <strong>Resumo:</strong> {ctx.event_name}<br>
  <strong>Host:</strong> {ctx.host_name}<br>
  <strong>IP:</strong> {ctx.host_ip or 'N/A'}<br>
  <strong>Severidade:</strong> {ctx.event_severity}<br>
  <strong>Valor atual:</strong> {ctx.item_value or 'N/A'}<br>
  <strong>Limite:</strong> {limit}<br>
  <strong>Quando:</strong> {ctx.event_datetime or 'N/A'}
</p>

<p>
  <strong>Link no Zabbix:</strong>
  <a href="{ctx.problem_url}">{ctx.problem_url or 'N/A'}</a>
</p>

<p><em>Triagem manual necessária. Consulte o Zabbix para detalhes adicionais.</em></p>
"""
    return TicketDraft(title=title, content=content)


def build_followup_content(ctx: AlertContext, analysis: AIAnalysis) -> str:
    """Full AI analysis for GLPI ITILFollowup (worknote)."""
    n1_steps = _list_to_text(analysis.proximos_passos_n1)
    n2_steps = _list_to_text(analysis.proximos_passos_n2)
    evidencias = _list_to_text(analysis.evidencias_relevantes)
    validacoes = _list_to_text(analysis.validacoes_recomendadas)
    causas_alt = _list_to_text(analysis.possiveis_causas)
    escalonamento = _list_to_text(analysis.criterios_de_escalonamento)
    comandos_html = _comandos_to_html(analysis.comandos_uteis)

    mensagem_block = ""
    if analysis.mensagem_para_chamado:
        mensagem_block = f"""
<h3>Mensagem profissional para o chamado</h3>
<blockquote>{analysis.mensagem_para_chamado}</blockquote>
"""

    parsing_note = ""
    if analysis.raw_response:
        parsing_note = f"""
<p style="color:#b45309"><strong>Aviso:</strong> Resposta da IA fora do JSON esperado.
Validar trecho bruto abaixo.</p>
<pre>{analysis.raw_response[:4000]}</pre>
"""

    return f"""<h2>Análise operacional completa (IA / Gemini)</h2>
<p><em>Worknote gerado automaticamente para apoio ao N1/N2.</em></p>

<h3>Resumo executivo</h3>
<p>{analysis.resumo_executivo or ctx.event_name}</p>

<h3>Impacto potencial</h3>
<p>{analysis.impacto_potencial or 'A validar.'}</p>

<h3>Causa provável</h3>
<p>{analysis.causa_provavel or 'A investigar.'}</p>

<h3>Possíveis causas</h3>
<pre>{causas_alt}</pre>

<h3>Evidências relevantes</h3>
<pre>{evidencias}</pre>

<h3>Validações recomendadas</h3>
<pre>{validacoes}</pre>

<h3>Próximos passos — N1</h3>
<pre>{n1_steps}</pre>

<h3>Próximos passos — N2</h3>
<pre>{n2_steps}</pre>

<h3>Critérios de escalonamento</h3>
<pre>{escalonamento}</pre>

<h3>Comandos úteis</h3>
{comandos_html}

<h3>Encaminhamento</h3>
<ul>
  <li><strong>Time sugerido:</strong> {analysis.time_sugerido or 'A confirmar'}</li>
  <li><strong>Prioridade sugerida:</strong> {analysis.prioridade_sugerida or 'A confirmar'}</li>
  <li><strong>Risco operacional:</strong> {analysis.risco_operacional or 'A confirmar'}</li>
</ul>
{mensagem_block}
<h3>Contexto Zabbix</h3>
<ul>
  <li><strong>Event ID:</strong> {ctx.event_id}</li>
  <li><strong>Host:</strong> {ctx.host_name} ({ctx.host_ip or 'N/A'})</li>
  <li><strong>Trigger:</strong> {ctx.trigger_name}</li>
  <li><strong>Item:</strong> {ctx.item_key} = {ctx.item_value}</li>
  <li><strong>Link:</strong> <a href="{ctx.problem_url}">{ctx.problem_url or 'N/A'}</a></li>
</ul>
<p><em>Governança: validar análise e comandos antes de agir em produção.</em></p>
{parsing_note}
"""


def build_task_checklist(ctx: AlertContext, analysis: AIAnalysis) -> str:
    """Operational checklist for GLPI TicketTask."""
    team = analysis.time_sugerido or _macro_value(ctx.macros, "OWNER_TEAM") or "time responsável"
    commands_hint = ""
    if analysis.comandos_uteis:
        first = analysis.comandos_uteis[0]
        commands_hint = f" (ex.: <code>{first.comando}</code>)"

    return f"""<p><strong>Checklist sugerido para triagem inicial</strong></p>
<ul>
  <li>[ ] Validar alerta ativo no Zabbix e registrar Event ID {ctx.event_id}</li>
  <li>[ ] Acessar o host <strong>{ctx.host_name}</strong> ({ctx.host_ip or 'IP a confirmar'})</li>
  <li>[ ] Executar comandos de diagnóstico seguros{commands_hint}</li>
  <li>[ ] Validar impacto no serviço/aplicação afetada</li>
  <li>[ ] Documentar evidências no acompanhamento do chamado</li>
  <li>[ ] Escalar para <strong>{team}</strong> se os critérios de escalonamento forem atingidos</li>
</ul>
<p><em>Prioridade sugerida: {analysis.prioridade_sugerida or 'A confirmar'}</em></p>
"""


def build_fallback_collapsible(ctx: AlertContext, analysis: AIAnalysis) -> str:
    """Collapsible section when ITILFollowup API is unavailable."""
    full = build_followup_content(ctx, analysis)
    return f"""
<hr>
<details>
  <summary><strong>Análise completa da IA (fallback — ver também Acompanhamentos se disponível)</strong></summary>
  {full}
</details>
"""


def build_enriched_summary(ctx: AlertContext, analysis: AIAnalysis) -> str:
    """Short main ticket description."""
    business = _macro_value(ctx.macros, "BUSINESS_SERVICE") or "A confirmar"
    application = _macro_value(ctx.macros, "APPLICATION") or ctx.host_description or "N/A"
    limit = _derive_limit(ctx)
    short_summary = _short_ai_summary(analysis)

    return f"""<p><strong>Alerta Zabbix com apoio de IA (Gemini)</strong></p>

<p>
  <strong>Resumo do alerta:</strong> {ctx.event_name}<br>
  <strong>Host:</strong> {ctx.host_name}<br>
  <strong>IP:</strong> {ctx.host_ip or 'N/A'}<br>
  <strong>Severidade:</strong> {ctx.event_severity}<br>
  <strong>Valor atual:</strong> {ctx.item_value or 'N/A'}<br>
  <strong>Limite:</strong> {limit}<br>
  <strong>Aplicação / serviço:</strong> {application}<br>
  <strong>Serviço de negócio:</strong> {business}
</p>

<p><strong>Síntese da IA (2–3 linhas):</strong><br>
{short_summary}</p>

<p>
  <strong>Link no Zabbix:</strong>
  <a href="{ctx.problem_url}">{ctx.problem_url or 'N/A'}</a>
</p>

<p><em>
  A análise operacional completa (impacto, causas, comandos, passos N1/N2 e escalonamento)
  está registrada nos <strong>Acompanhamentos</strong> deste chamado.
</em></p>
"""


def build_enriched_package(ctx: AlertContext, analysis: AIAnalysis) -> EnrichedTicketPackage:
    """Build all GLPI artifacts for the Gemini-enriched flow."""
    title = f"[AI/Zabbix] {ctx.event_severity} - {ctx.event_name} - {ctx.host_name}"
    return EnrichedTicketPackage(
        title=title,
        summary_content=build_enriched_summary(ctx, analysis),
        followup_content=build_followup_content(ctx, analysis),
        task_name="Checklist operacional — triagem N1",
        task_content=build_task_checklist(ctx, analysis),
        fallback_collapsible_content=build_fallback_collapsible(ctx, analysis),
    )


def build_enriched_ticket(ctx: AlertContext, analysis: AIAnalysis) -> TicketDraft:
    """
    Legacy single-body ticket (summary only).
    Prefer build_enriched_package() + GlpiClient.create_enriched_ticket_with_worknotes().
    """
    package = build_enriched_package(ctx, analysis)
    return TicketDraft(title=package.title, content=package.summary_content)


def payload_summary_json(ctx: AlertContext) -> str:
    """Compact JSON summary for API responses."""
    return json.dumps(
        {
            "event_id": ctx.event_id,
            "host_name": ctx.host_name,
            "severity": ctx.event_severity,
            "is_recovery": ctx.is_recovery,
        },
        ensure_ascii=False,
    )
