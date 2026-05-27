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
        "lab_scenario": "cpu_high",
        "secret": "lab-webhook-secret"
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

def test_health_endpoint_security():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    # Auditoria de segurança: Proibido expor segredos no health
    secrets = ["gemini_api_key", "glpi_api_password", "glpi_user_token", "webhook_shared_secret"]
    for s in secrets:
        assert s not in data

def test_webhook_unauthorized(sample_payload):
    sample_payload["secret"] = "wrong-secret"
    response = client.post("/webhook/zabbix/plain", json=sample_payload)
    assert response.status_code == 401

def test_enriched_package_logic(sample_payload):
    payload = ZabbixWebhookPayload.model_validate(sample_payload)
    ctx = build_alert_context(payload)
    mock_analysis = AIAnalysis(
        resumo_executivo="Teste de analise",
        impacto_potencial="Baixo",
        causa_provavel="Teste",
        mensagem_para_chamado="Texto chamado",
        prioridade_sugerida="Baixa",
        time_sugerido="Linux"
    )
    package = build_enriched_package(ctx, mock_analysis)
    assert "[AI/Zabbix]" in package.title
    assert len(package.summary_content) > 0
    assert len(package.followup_content) > 0

def test_ai_parsing_fallback(sample_payload):
    # Simula falha no parsing de JSON do Gemini
    payload = ZabbixWebhookPayload.model_validate(sample_payload)
    ctx = build_alert_context(payload)
    # AIAnalysis com raw_response simulando falha de parse
    analysis = AIAnalysis(raw_response="Resposta bruta do Gemini que não é JSON")
    package = build_enriched_package(ctx, analysis)
    assert "Aviso: A análise estruturada falhou" in package.followup_content
    assert "Resposta bruta do Gemini que não é JSON" in package.followup_content
