# Configuracao da API REST do GLPI

A **gemini-incident-api** cria tickets via `apirest.php` usando App-Token e User-Token.

## 1. Subir o GLPI

```bash
docker compose up -d glpi glpi-db
```

Acesse: http://localhost:8081

Na primeira execucao da imagem `diouxx/glpi`, conclua o assistente de instalacao:

1. Escolha idioma
2. Aceite licenca
3. Tipo: **Install**
4. Banco: host `glpi-db`, usuario `glpi`, senha do `.env` (`GLPI_DB_PASSWORD`)
5. Crie usuario **admin** e senha forte

## 2. Habilitar API REST

1. Login como administrador
2. **Configuracao → Geral → API**
3. Ative **API REST**
4. Salve

## 3. Gerar App-Token (aplicacao cliente)

1. **Configuracao → Geral → API → Adicionar cliente API**
2. Nome: `zabbix-glpi-gemini-incident-lab`
3. Ativo: Sim
4. Copie o **App-Token** → `GLPI_APP_TOKEN` no `.env`

## 4. Gerar User-Token (usuario de integracao)

Recomendado: usuario dedicado `zabbix-integration` com perfil que permita abrir chamados.

1. **Administracao → Usuarios →** usuario de integracao
2. Aba **Chaves de acesso remoto** / **API tokens**
3. Gere **User-Token** → `GLPI_USER_TOKEN` no `.env`

## 5. Variaveis no `.env`

```env
GLPI_BASE_URL=http://glpi/apirest.php
GLPI_APP_TOKEN=
GLPI_USER_TOKEN=
GLPI_DEFAULT_ENTITY_ID=0
GLPI_DEFAULT_CATEGORY_ID=
GLPI_DEFAULT_REQUESTER_ID=
GLPI_DEFAULT_TECHNICIAN_ID=
```

> Dentro do Docker Compose, use `http://glpi/apirest.php`. Do host: `http://localhost:8081/apirest.php`.

Depois de preencher os tokens:

```bash
docker compose restart gemini-incident-api
docker compose run --rm glpi-bootstrap
```

O bootstrap valida a API e cria a categoria **Zabbix Alerts** quando possivel.

## 6. Descobrir IDs opcionais

### Entity

Geralmente `0` (root) em instalacoes novas.

### Categoria ITIL

Use a sessao da API para `GET /ITILCategory` ou anote o ID impresso pelo `glpi-bootstrap`.

### Requester / Technician

Liste usuarios na UI (**Administracao → Usuarios**) e anote IDs numericos.

## 7. Testar sessao manualmente

```bash
curl -s -X GET "http://localhost:8081/apirest.php/initSession" \
  -H "Content-Type: application/json" \
  -H "Authorization: user_token $GLPI_USER_TOKEN" \
  -H "App-Token: $GLPI_APP_TOKEN"
```

Resposta esperada:

```json
{"session_token":"..."}
```

## 8. Encerrar sessao

```bash
curl -s -X GET "http://localhost:8081/apirest.php/killSession" \
  -H "Session-Token: SEU_SESSION_TOKEN" \
  -H "App-Token: $GLPI_APP_TOKEN"
```

## Erros comuns

| Erro | Solucao |
|------|---------|
| `ERROR_LOGIN` | User-Token invalido ou usuario inativo |
| `ERROR_APP_TOKEN` | App-Token incorreto ou cliente API desativado |
| `ERROR_RIGHT_MISSING` | Perfil sem permissao para criar Ticket |
| Connection refused | GLPI ainda inicializando — aguarde 1–2 min |

## Gemini + GLPI

Para o fluxo completo do lab:

1. Configure tokens GLPI (este documento)
2. Configure `GEMINI_API_KEY` — [gemini-api-setup.md](gemini-api-setup.md)
3. `docker compose up -d`
