# Webhooks Zabbix 7

O lab provisiona os webhooks automaticamente com:

```bash
docker compose run --rm zabbix-bootstrap
```

Objetos criados:

- Media Type `GLPI Traditional Webhook`
- Media Type `GLPI Gemini Enriched Webhook`
- Action `LAB - GLPI Traditional flow`
- Action `LAB - GLPI AI enriched flow`
- Host `srv-linux-traditional`
- Host `srv-linux-ai`
- Template `Template Lab Fake Linux Trapper`

## Endpoints

| Fluxo | Endpoint interno Docker |
|-------|-------------------------|
| Tradicional | `http://gemini-incident-api:8000/webhook/zabbix/plain` |
| Gemini | `http://gemini-incident-api:8000/webhook/zabbix/gemini` |

O Zabbix envia o header:

```text
X-Webhook-Token: <WEBHOOK_SHARED_SECRET>
```

## Payload JSON

O Media Type envia os campos:

```json
{
  "secret": "<WEBHOOK_SHARED_SECRET>",
  "event_id": "{EVENT.ID}",
  "event_name": "{EVENT.NAME}",
  "event_status": "{EVENT.STATUS}",
  "event_severity": "{EVENT.SEVERITY}",
  "event_date": "{EVENT.DATE}",
  "event_time": "{EVENT.TIME}",
  "recovery_status": "{EVENT.RECOVERY.STATUS}",
  "host_id": "{HOST.ID}",
  "host_name": "{HOST.NAME}",
  "host_ip": "{HOST.IP}",
  "host_groups": "{TRIGGER.HOSTGROUP.NAME}",
  "host_templates": "{HOST.TEMPLATE.NAME}",
  "host_description": "{HOST.DESCRIPTION}",
  "trigger_id": "{TRIGGER.ID}",
  "trigger_name": "{TRIGGER.NAME}",
  "trigger_expression": "{TRIGGER.EXPRESSION}",
  "trigger_description": "{TRIGGER.DESCRIPTION}",
  "item_name": "{ITEM.NAME}",
  "item_key": "{ITEM.KEY}",
  "item_value": "{ITEM.VALUE}",
  "operational_data": "{EVENT.OPDATA}",
  "tags": "{EVENT.TAGSJSON}",
  "macros": "{$ENVIRONMENT}=...; {$ESCALATION_TEAM}=...; {$MONITORING_SCOPE}=...",
  "problem_url": "http://localhost:8080/tr_events.php?triggerid={TRIGGER.ID}&eventid={EVENT.ID}",
  "flow_type": "traditional|ai",
  "lab_scenario": "{EVENT.TAGS.lab_scenario}",
  "demo_description": "{TRIGGER.DESCRIPTION}"
}
```

Se alguma macro de tag nao for expandida, a API infere `lab_scenario` pelo nome da trigger ou chave do item.

## Configuracao manual equivalente

Se quiser montar manualmente:

1. Crie dois Media Types do tipo **Webhook**.
2. Use os endpoints acima.
3. Configure `Content-Type: application/json`.
4. Configure `X-Webhook-Token` com o valor de `WEBHOOK_SHARED_SECRET`.
5. Action para `srv-linux-traditional` → `GLPI Traditional Webhook`.
6. Action para `srv-linux-ai` → `GLPI Gemini Enriched Webhook`.

## Teste sem Zabbix

```bash
set -a
source .env
set +a

curl -X POST http://localhost:8000/webhook/zabbix/plain \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_SHARED_SECRET" \
  -d @examples/zabbix_payload_cpu_high_traditional.json | jq .

curl -X POST http://localhost:8000/webhook/zabbix/gemini \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_SHARED_SECRET" \
  -d @examples/zabbix_payload_cpu_high_ai.json | jq .
```

Ou endpoints de demo:

```bash
curl -X POST "http://localhost:8000/demo/send-sample/plain?name=cpu_high" \
  -H "X-Webhook-Token: $WEBHOOK_SHARED_SECRET" | jq .
```

## Troubleshooting

| Sintoma | Causa provavel | Acao |
|---------|----------------|------|
| `401` na API | Secret incorreto | Conferir `WEBHOOK_SHARED_SECRET` |
| `502` na API | GLPI indisponivel ou token invalido | `docker compose logs gemini-incident-api` |
| `503` no fluxo Gemini | Sem `GEMINI_API_KEY` | [docs/gemini-api-setup.md](gemini-api-setup.md) |
| Sem problema no Zabbix | Valor nao chegou no trapper | Rodar script `examples/` novamente |
