# Configuracao da API REST do GLPI (Opcional)

No fluxo padrao deste laboratorio, **nao e necessario configurar GLPI manualmente**.

Quando voce roda:

```bash
docker compose up -d
```

o `glpi-bootstrap` ja faz automaticamente:

- instalacao inicial do GLPI no banco
- habilitacao da API REST
- liberacao de login por credenciais
- criacao/atualizacao do cliente API do lab
- criacao da categoria ITIL `Zabbix Alerts`

## Credenciais padrao de integracao

```env
GLPI_API_USERNAME=zabbix-integration
GLPI_API_PASSWORD=zabbix-integration-pass
GLPI_BASE_URL=http://glpi/apirest.php
```

## Quando usar este documento

Use este guia apenas se quiser:

- trocar para autenticacao por token (`GLPI_USER_TOKEN`)
- customizar App-Token / cliente API
- alterar usuario de integracao e perfil

## 1. Reexecutar bootstrap automatico

```bash
docker compose run --rm glpi-bootstrap
```

## 2. Verificar saude da API

```bash
curl -s http://localhost:8000/health | jq .
```

Campos esperados:

- `glpi_configured=true`
- `status=ok`

## 3. (Opcional) Testar sessao GLPI por credenciais

```bash
BASIC_AUTH="$(printf '%s' 'zabbix-integration:zabbix-integration-pass' | base64)"

curl -s -X GET "http://localhost:8081/apirest.php/initSession" \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic $BASIC_AUTH"
```

## 4. (Opcional) Modo token

Se preferir token em vez de credenciais:

```env
GLPI_APP_TOKEN=
GLPI_USER_TOKEN=
GLPI_API_USERNAME=
GLPI_API_PASSWORD=
```

Depois:

```bash
docker compose restart gemini-incident-api
```

## Erros comuns

| Erro | Solucao |
|------|---------|
| `glpi_configured=false` em `/health` | Defina `GLPI_USER_TOKEN` **ou** `GLPI_API_USERNAME` + `GLPI_API_PASSWORD` |
| `ERROR_NOT_ALLOWED_IP` no GLPI | Reexecute `docker compose run --rm glpi-bootstrap` |
| `ERROR_GLPI_LOGIN` | Confirme usuario/senha no `.env` |
| Ticket nao aparece | Verifique logs: `docker compose logs glpi-bootstrap gemini-incident-api` |

## Gemini + GLPI

Para o fluxo completo:

1. Configure `GEMINI_API_KEY` (obrigatorio)
2. `docker compose up -d`
3. Dispare scripts de `examples/`
