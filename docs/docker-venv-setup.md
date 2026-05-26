# Docker + venv setup

Este repositorio agora tem dois modos oficiais:

1. Docker Compose para executar o lab completo em qualquer SO.
2. `venv` para desenvolvimento local da API Python.

## 1) Lab completo com Docker (recomendado)

Linux/macOS:

```bash
cp .env.example .env
```

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

Depois preencha os valores obrigatorios no `.env` e suba o ambiente:

```bash
docker compose up -d --build
docker compose ps
```

## 2) API local com venv (opcional para desenvolvimento)

Use este modo quando quiser editar e debugar a API fora do container.

1. Suba a infraestrutura no Docker:

```bash
docker compose up -d zabbix-db zabbix-server zabbix-web glpi-db glpi zabbix-sender
```

2. Crie o ambiente virtual e instale dependencias.

Linux/macOS:

```bash
bash scripts/setup_venv.sh
```

Windows (PowerShell):

```powershell
.\scripts\setup_venv.ps1
```

3. Ajuste o `.env` para API local (fora do Docker):

```env
GLPI_BASE_URL=http://localhost:8081/apirest.php
API_PORT=8000
```

4. Pare a API em container para evitar conflito de porta:

```bash
docker compose stop gemini-incident-api
```

5. Rode a API local.

Linux/macOS:

```bash
bash scripts/run_api_local.sh
```

Windows (PowerShell):

```powershell
.\scripts\run_api_local.ps1
```

## Observacoes importantes

- O bootstrap padrao do Zabbix cria webhooks apontando para `http://gemini-incident-api:8000`.
- Se voce quiser que os webhooks chamem a API local, ajuste manualmente o endpoint no Zabbix para um host acessivel pelos containers (ex.: `host.docker.internal:8000` em Docker Desktop).
- O endpoint de health permanece em `http://localhost:8000/health`.
