import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.zabbix_context import build_alert_context
from app.services.incident_builder import build_plain_ticket, build_enriched_package
from app.models import ZabbixWebhookPayload, AIAnalysis

client = TestClient(app)

@pytest.fixture
def sample_payload():
    return {
        "event_id": "123",
        "event_name": "High CPU usage",
        "event_severity": "High",
        "host_name": "srv-linux-ai",
        "item_key": "cpu.util",
        "item_value": "95",
        "flow_type": "ai",
        "lab_scenario": "cpu_high"
    }

def test_alert_context_construction(sample_payload):
    payload = ZabbixWebhookPayload.model_validate(sample_payload)
    ctx = build_alert_context(payload)
    assert ctx.host_name == "srv-linux-ai"
    assert ctx.item_value == "95"

def test_plain_ticket_generation(sample_payload):
    payload = ZabbixWebhookPayload.model_validate(sample_payload)
    ctx = build_alert_context(payload)
    ticket = build_plain_ticket(ctx)
    assert "[Zabbix]" in ticket.title
    assert "srv-linux-ai" in ticket.content

def test_enriched_package_generation(sample_payload):
    payload = ZabbixWebhookPayload.model_validate(sample_payload)
    ctx = build_alert_context(payload)
    analysis = AIAnalysis(
        resumo_executivo="CPU está muito alta.",
        impacto_potencial="Lentidão geral.",
        causa_provavel="Processo pesado.",
        possiveis_causas=["App", "Log rotation"],
        validacoes_recomendadas=["Check top"],
        comandos_uteis=[],
        proximos_passos_n1=[],
        proximos_passos_n2=[],
        criterios_de_escalonamento=[],
        evidencias_relevantes=[],
        time_sugerido="Linux",
        prioridade_sugerida="Alta",
        risco_operacional="Baixo",
        mensagem_para_chamado="CPU Alta"
    )
    package = build_enriched_package(ctx, analysis)
    assert "[AI/Zabbix]" in package.title
    assert package.summary_content is not None
    assert package.followup_content is not None

def test_health_endpoint_security():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    # Garantir que segredos não vazam
    assert "gemini_api_key" not in data
    assert "glpi_user_token" not in data
    assert "glpi_api_password" not in data

def test_webhook_unauthorized(sample_payload):
    # Sem o header X-Webhook-Token correto
    response = client.post("/webhook/zabbix/plain", json=sample_payload)
    assert response.status_code == 401

def test_webhook_authorized(sample_payload, monkeypatch):
    monkeypatch.setenv("WEBHOOK_SHARED_SECRET", "test-secret")
    headers = {"X-Webhook-Token": "test-secret"}
    # Mockando a resposta do GLPI para não precisar de ambiente real nos testes unitários
    pass