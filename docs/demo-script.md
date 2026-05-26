# Roteiro de apresentacao

Tempo sugerido: 15 a 20 minutos.

## Objetivo

Mostrar a diferenca entre:

- **Automacao tradicional**: alerta vira chamado tecnico cru.
- **Operacao inteligente**: alerta vira chamado com contexto, impacto, causa provavel e proximos passos (**Gemini real**).

## Preparacao

```bash
cp .env.example .env
# Preencher WEBHOOK_SHARED_SECRET, senhas dos bancos e GEMINI_API_KEY
docker compose up -d
docker compose ps
curl -s http://localhost:8000/health | jq .
```

Confirme:

- Zabbix: http://localhost:8080 (credenciais locais em `ZABBIX_USER` / `ZABBIX_PASSWORD`)
- GLPI: http://localhost:8081
- `.env` com `AI_PROVIDER=gemini` e `GEMINI_API_KEY` preenchida
- Tokens GLPI em `.env` para abrir tickets reais

Se `AUTO_TRIGGER_DEMO_ALERTS=true`, dois tickets podem ja existir no GLPI — use isso para abrir a comparacao ou defina `false` para demo manual.

```bash
docker compose run --rm zabbix-bootstrap   # se hosts ausentes
```

## 1. Mostrar hosts no Zabbix

Abra o Zabbix e mostre:

- `srv-linux-traditional`
- `srv-linux-ai`

Explique: hosts fake, metricas via trapper (`zabbix_sender`), sem servidor Linux real.

## 2. Mostrar itens e triggers

No template `Template Lab Fake Linux Trapper`:

**Itens:**

- `cpu.util`
- `memory.util`
- `disk.util`
- `service.status`

**Triggers:**

- `High CPU usage when cpu.util > 90`
- `High memory usage when memory.util > 90`
- `Disk space critical when disk.util > 90`
- `Service unavailable when service.status = 0`

Mostre **Media Types**: `GLPI Traditional Webhook` e `GLPI Gemini Enriched Webhook`.

## 3. GLPI antes dos alertas (opcional)

Se `AUTO_TRIGGER_DEMO_ALERTS=false`, mostre GLPI sem tickets do lab.

## 4. Disparar alerta tradicional

```bash
./examples/send_cpu_high_traditional.sh
docker compose logs --tail=20 gemini-incident-api
```

No Zabbix: **Monitoring > Problems** — host `srv-linux-traditional`.

No GLPI: ticket `[Zabbix] High - High CPU usage when cpu.util > 90 - srv-linux-traditional`.

Destaque: dados tecnicos, sem interpretacao de impacto ou passos.

## 5. Disparar alerta com Gemini

```bash
./examples/send_cpu_high_ai.sh
```

No Zabbix: problema em `srv-linux-ai`.

No GLPI: ticket `[AI/Zabbix] High - ... - srv-linux-ai`.

Mostre no corpo:

- Resumo executivo
- Impacto potencial
- Causa provavel
- Proximos passos N1 / N2
- Evidencias e time sugerido
- Aviso de governanca (validar antes de agir em producao)

Mencione: chamada real ao Gemini (`GEMINI_API_KEY`), nao mock.

## 6. Comparar antes/depois

| Ponto | Tradicional | Com Gemini |
|-------|-------------|------------|
| Conteudo | Campos do alerta | Analise operacional estruturada |
| N1 | Interpreta tudo | Recebe triagem inicial |
| N2 | Contexto limitado | Hipotese e evidencias |
| Governanca | Automacao simples | IA como apoio + validacao humana |

## 7. Outros cenarios (opcional)

```bash
./examples/send_memory_high_traditional.sh
./examples/send_memory_high_ai.sh
./examples/send_disk_full_traditional.sh
./examples/send_disk_full_ai.sh
./examples/send_service_down_traditional.sh
./examples/send_service_down_ai.sh
```

## 8. Recovery

```bash
./examples/recover_traditional.sh
./examples/recover_ai.sh
```

Valores:

```text
cpu.util=20
memory.util=35
disk.util=40
service.status=1
```

## Fallback mock (nota rapida)

Se a rede ou a chave falhar na hora:

```env
AI_PROVIDER=mock
```

```bash
docker compose restart gemini-incident-api
```

Explique que e apenas contingencia — o lab foi desenhado para Gemini real.

## Fechamento

> A automacao tradicional reduz trabalho repetitivo. A operacao inteligente adiciona contexto para reduzir tempo de triagem, melhorar encaminhamento e padronizar resposta — sempre com validacao humana antes de agir em producao.
