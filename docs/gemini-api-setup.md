# Configuracao da API Gemini (Google AI Studio)

O fluxo inteligente do lab (`srv-linux-ai`) chama o **Gemini real** para interpretar alertas do Zabbix antes de abrir o chamado no GLPI.

## Pre-requisitos

- Conta Google
- `AI_PROVIDER=gemini` no `.env` (padrao em `.env.example`)
- Modelo recomendado: `gemini-2.0-flash-lite` (baixo custo / free tier)

## Passo a passo

### 1. Abrir o Google AI Studio

Acesse: **https://aistudio.google.com/apikey**

### 2. Criar a API Key

1. Faca login com sua conta Google
2. Clique em **Create API key** (ou **Get API key**)
3. Escolha um projeto Google Cloud existente ou crie um novo (o assistente guia)
4. Copie a chave gerada pelo Google AI Studio

### 3. Configurar o `.env`

```bash
cp .env.example .env
```

Edite:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash-lite
```

### 4. Reiniciar a API

```bash
docker compose restart gemini-incident-api
```

### 5. Validar

```bash
curl -s http://localhost:8000/health | jq .
```

Esperado:

```json
{
  "ai_provider": "gemini",
  "gemini_configured": true,
  "ai_configured": true
}
```

### 6. Testar o fluxo enriquecido

Com GLPI configurado:

```bash
./examples/send_cpu_high_ai.sh
```

Ou sem Zabbix:

```bash
set -a
source .env
set +a

curl -X POST "http://localhost:8000/demo/send-sample/gemini?name=cpu_high" \
  -H "X-Webhook-Token: $WEBHOOK_SHARED_SECRET" | jq .
```

## Variavel de ambiente no SDK

O cliente usa `google-genai` com a chave passada explicitamente a partir de `GEMINI_API_KEY`. A chave **nunca** aparece em logs.

Se `GEMINI_API_KEY` estiver vazia e `AI_PROVIDER=gemini`, o endpoint `/webhook/zabbix/gemini` retorna **503** com mensagem orientando a configurar a chave.

## Modo mock (fallback opcional)

Use apenas em sala sem internet ou sem conta Google:

```env
AI_PROVIDER=mock
GEMINI_API_KEY=
```

```bash
docker compose restart gemini-incident-api
```

A analise sera gerada localmente por regras didaticas — **nao** e o fluxo principal do lab.

## Aviso sobre Free Tier e custos

> Os limites e condicoes do Free Tier podem mudar. Este projeto nao se responsabiliza por custos caso o usuario altere modelo, habilite billing ou rode uso em alto volume.

Recomendacoes para palestra:

- Manter `gemini-2.0-flash-lite`
- Evitar loops automatizados disparando centenas de alertas
- Desativar `AUTO_TRIGGER_DEMO_ALERTS` se for repetir a demo varias vezes no mesmo dia

## Erros comuns

| Erro / sintoma | Solucao |
|----------------|---------|
| `gemini_configured: false` no `/health` | Preencher `GEMINI_API_KEY` e reiniciar API |
| HTTP 503 no webhook gemini | Chave ausente com `AI_PROVIDER=gemini` |
| HTTP 502 `Gemini API error` | Chave invalida, quota excedida ou rede bloqueada |
| Ticket sem secao de IA | Verificar `AI_PROVIDER=mock` por engano |
| JSON nao estruturado no ticket | Gemini respondeu fora do formato; ticket abre com aviso e texto bruto |
