"""
Deterministic mock incident analysis for the no-cost classroom lab.

The mock keeps the AI flow useful without a Gemini key. It is intentionally
simple and scenario-based so students can compare the plain ticket with a
structured operational analysis.
"""

import logging

from models import AIAnalysis, AlertContext

logger = logging.getLogger(__name__)


def analyze_with_mock(ctx: AlertContext) -> AIAnalysis:
    """Return a realistic AIAnalysis based on the lab scenario."""
    scenario = (ctx.lab_scenario or "").lower()
    logger.info(
        "Mock AI analyze: scenario=%s event_id=%s host=%s",
        scenario or "unknown",
        ctx.event_id,
        ctx.host_name,
    )

    if ctx.is_recovery:
        return _recovery_analysis(ctx)
    if scenario == "cpu_high":
        return _cpu_high(ctx)
    if scenario == "memory_high":
        return _memory_high(ctx)
    if scenario == "disk_full":
        return _disk_full(ctx)
    if scenario == "service_down":
        return _service_down(ctx)
    return _generic(ctx)


def _owner_team(ctx: AlertContext) -> str:
    return "N2 Linux" if "OWNER_TEAM" in ctx.macros or "Linux" in ctx.host_groups else "Operacoes"


def _priority(ctx: AlertContext, default: str = "Alta") -> str:
    severity = ctx.event_severity.lower()
    if severity in {"disaster", "high"}:
        return "Alta"
    if severity in {"average", "warning"}:
        return "Media"
    return default


def _cpu_high(ctx: AlertContext) -> AIAnalysis:
    return AIAnalysis(
        resumo_executivo=(
            f"O host {ctx.host_name} reportou uso elevado de CPU no item "
            f"{ctx.item_key or 'cpu.util'}, com valor atual {ctx.item_value or 'acima do limite'}. "
            "O alerta sugere saturacao de processamento e deve ser validado antes de escalar."
        ),
        impacto_potencial=(
            "Aplicacoes hospedadas podem apresentar lentidao, timeouts e aumento de fila de "
            "processamento enquanto a CPU permanecer acima do limite."
        ),
        causa_provavel=(
            "Pico de carga, processo consumindo CPU de forma anormal, job em execucao ou "
            "capacidade insuficiente para a demanda do momento."
        ),
        proximos_passos_n1=[
            "Confirmar se o alerta permanece ativo no Zabbix e verificar o horario de inicio.",
            "Validar se existe manutencao, deploy ou rotina batch em andamento.",
            "Coletar top de processos por CPU e load average para anexar ao chamado.",
        ],
        proximos_passos_n2=[
            "Analisar processos com maior consumo e correlacionar com logs da aplicacao.",
            "Avaliar limite de recursos, thread pools e necessidade de ajuste de capacidade.",
            "Definir mitigacao: reinicio controlado, throttling, rollback ou escalonamento horizontal.",
        ],
        evidencias_relevantes=[
            f"Trigger: {ctx.trigger_name}",
            f"Item: {ctx.item_key} = {ctx.item_value}",
            f"Dados operacionais: {ctx.operational_data or 'nao informado'}",
            f"Macros do host: {ctx.macros or 'nao informado'}",
        ],
        time_sugerido=_owner_team(ctx),
        prioridade_sugerida=_priority(ctx),
        mensagem_para_chamado=(
            "CPU acima do limite configurado. Validar processos consumidores, correlacionar "
            "com mudancas recentes e acionar N2 se a saturacao persistir."
        ),
    )


def _memory_high(ctx: AlertContext) -> AIAnalysis:
    return AIAnalysis(
        resumo_executivo=(
            f"O host {ctx.host_name} reportou uso elevado de memoria, com valor atual "
            f"{ctx.item_value or 'acima do limite'}. O cenario indica risco de degradacao "
            "por pressao de memoria."
        ),
        impacto_potencial=(
            "Pode haver lentidao, swap excessivo, falhas de alocacao e encerramento de processos "
            "caso a memoria continue saturada."
        ),
        causa_provavel=(
            "Crescimento de consumo por processo, vazamento de memoria, cache sem liberacao ou "
            "carga acima do esperado."
        ),
        proximos_passos_n1=[
            "Confirmar uso de memoria, swap e tendencia recente no Zabbix.",
            "Identificar os principais processos consumidores de memoria.",
            "Verificar mudancas recentes, deploys e rotinas agendadas.",
        ],
        proximos_passos_n2=[
            "Investigar possivel vazamento de memoria na aplicacao ou servico.",
            "Avaliar ajuste de parametros, reinicio controlado ou aumento de capacidade.",
            "Correlacionar metricas de memoria com logs de OOM, garbage collection ou swap.",
        ],
        evidencias_relevantes=[
            f"Trigger: {ctx.trigger_name}",
            f"Item: {ctx.item_key} = {ctx.item_value}",
            f"Host groups: {ctx.host_groups or 'nao informado'}",
        ],
        time_sugerido=_owner_team(ctx),
        prioridade_sugerida=_priority(ctx),
        mensagem_para_chamado=(
            "Memoria acima do limite. Validar consumidores, tendencia e risco de swap/OOM antes "
            "de executar qualquer acao corretiva."
        ),
    )


def _disk_full(ctx: AlertContext) -> AIAnalysis:
    return AIAnalysis(
        resumo_executivo=(
            f"O host {ctx.host_name} sinalizou uso critico de disco em {ctx.item_key or 'disk.util'}, "
            f"com valor atual {ctx.item_value or 'acima do limite'}. O risco operacional e alto "
            "porque o crescimento pode impedir gravacoes e afetar servicos."
        ),
        impacto_potencial=(
            "Servicos podem parar de gravar logs ou dados, bancos podem rejeitar transacoes e "
            "processos podem falhar por falta de espaco."
        ),
        causa_provavel=(
            "Crescimento de logs, arquivos temporarios, dumps, backups, cache ou retencao acima "
            "do planejado."
        ),
        proximos_passos_n1=[
            "Confirmar o filesystem afetado e o percentual atual no Zabbix.",
            "Verificar crescimento recente de logs, temporarios e backups.",
            "Nao apagar arquivos sem validar dono, criticidade e politica de retencao.",
        ],
        proximos_passos_n2=[
            "Identificar diretorios responsaveis pelo crescimento e definir limpeza segura.",
            "Avaliar expansao de volume, ajuste de retencao ou rotacao de logs.",
            "Correlacionar com mudancas recentes em aplicacoes, backups ou rotinas batch.",
        ],
        evidencias_relevantes=[
            f"Trigger: {ctx.trigger_name}",
            f"Item: {ctx.item_key} = {ctx.item_value}",
            f"Dados operacionais: {ctx.operational_data or 'nao informado'}",
        ],
        time_sugerido=_owner_team(ctx),
        prioridade_sugerida=_priority(ctx),
        mensagem_para_chamado=(
            "Disco acima do limite critico. Priorizar validacao do filesystem, origem do crescimento "
            "e acao segura de limpeza ou expansao."
        ),
    )


def _service_down(ctx: AlertContext) -> AIAnalysis:
    return AIAnalysis(
        resumo_executivo=(
            f"O host {ctx.host_name} reportou indisponibilidade de servico pelo item "
            f"{ctx.item_key or 'service.status'}, com valor {ctx.item_value or '0'}. "
            "O evento indica que um servico monitorado nao esta respondendo conforme esperado."
        ),
        impacto_potencial=(
            "Usuarios ou sistemas dependentes podem perder acesso ao servico ate que o processo "
            "seja recuperado ou a causa seja mitigada."
        ),
        causa_provavel=(
            "Processo parado, falha de dependencia, configuracao invalida, recurso esgotado ou "
            "reinicio incompleto apos mudanca."
        ),
        proximos_passos_n1=[
            "Confirmar no Zabbix se o status permanece indisponivel.",
            "Verificar status do servico e ultimas linhas de log.",
            "Checar se houve deploy, manutencao ou reinicio planejado.",
        ],
        proximos_passos_n2=[
            "Analisar logs completos do servico e dependencias externas.",
            "Validar configuracao, credenciais de servico e portas/listeners.",
            "Executar recuperacao controlada conforme runbook e registrar evidencias.",
        ],
        evidencias_relevantes=[
            f"Trigger: {ctx.trigger_name}",
            f"Item: {ctx.item_key} = {ctx.item_value}",
            f"Runbook: {ctx.macros or 'nao informado'}",
        ],
        time_sugerido=_owner_team(ctx),
        prioridade_sugerida=_priority(ctx),
        mensagem_para_chamado=(
            "Servico indisponivel. Validar status, logs e dependencias antes de reiniciar ou "
            "executar a acao padrao."
        ),
    )


def _recovery_analysis(ctx: AlertContext) -> AIAnalysis:
    return AIAnalysis(
        resumo_executivo=(
            f"O evento em {ctx.host_name} foi normalizado no Zabbix. O recovery deve ser usado "
            "para confirmar estabilidade e encerrar o atendimento com evidencias."
        ),
        impacto_potencial=(
            "O impacto imediato aparenta ter cessado, mas e necessario validar se a normalizacao "
            "se manteve por alguns minutos."
        ),
        causa_provavel="Recovery automatico apos retorno da metrica ao limite esperado.",
        proximos_passos_n1=[
            "Confirmar que o trigger esta em OK no Zabbix.",
            "Verificar se nao ha eventos correlacionados ativos para o mesmo host.",
            "Registrar horario de normalizacao e valor atual da metrica.",
        ],
        proximos_passos_n2=[
            "Revisar causa raiz se o evento for recorrente.",
            "Ajustar capacidade, thresholds ou runbook caso a recorrencia seja confirmada.",
        ],
        evidencias_relevantes=[
            f"Status do evento: {ctx.event_status}",
            f"Recovery status: {ctx.recovery_status or 'nao informado'}",
            f"Item: {ctx.item_key} = {ctx.item_value}",
        ],
        time_sugerido=_owner_team(ctx),
        prioridade_sugerida="Baixa",
        mensagem_para_chamado=(
            "Recovery recebido. Validar estabilidade, ausencia de eventos correlacionados e "
            "documentar evidencias antes do encerramento."
        ),
    )


def _generic(ctx: AlertContext) -> AIAnalysis:
    return AIAnalysis(
        resumo_executivo=(
            f"O host {ctx.host_name} gerou um alerta Zabbix com severidade "
            f"{ctx.event_severity}. O contexto recebido deve ser validado pelo N1 antes de escalar."
        ),
        impacto_potencial="Impacto a confirmar conforme servico afetado, horario e dependencia.",
        causa_provavel="Causa tecnica ainda nao determinada com os dados enviados.",
        proximos_passos_n1=[
            "Confirmar status atual do evento no Zabbix.",
            "Validar host, item, trigger e dados operacionais recebidos.",
            "Coletar logs ou metricas complementares antes de acionar N2.",
        ],
        proximos_passos_n2=[
            "Analisar causa raiz com base nas evidencias coletadas.",
            "Atualizar runbook e regra de monitoramento se necessario.",
        ],
        evidencias_relevantes=[
            f"Trigger: {ctx.trigger_name or 'nao informado'}",
            f"Item: {ctx.item_key or 'nao informado'} = {ctx.item_value or 'nao informado'}",
            f"Tags: {ctx.tags or 'nao informado'}",
        ],
        time_sugerido=_owner_team(ctx),
        prioridade_sugerida=_priority(ctx, default="Media"),
        mensagem_para_chamado="Alerta recebido com contexto limitado. Validar evidencias e classificar impacto.",
    )
