#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# GLPI bootstrap for lab automation
# - installs GLPI database (first run only)
# - enables REST API + credential login
# - ensures an API client that allows Docker network calls
# - ensures a dedicated integration user and lab ITIL category
# -----------------------------------------------------------------------------

GLPI_BOOTSTRAP_TIMEOUT="${GLPI_BOOTSTRAP_TIMEOUT:-600}"
GLPI_CONSOLE_PATH="${GLPI_CONSOLE_PATH:-/var/www/html/glpi/bin/console}"

GLPI_DB_HOST="${GLPI_DB_HOST:-glpi-db}"
GLPI_DB_PORT="${GLPI_DB_PORT:-3306}"
GLPI_DB_NAME="${GLPI_DB_NAME:-glpi}"
GLPI_DB_USER="${GLPI_DB_USER:-glpi}"
GLPI_DB_PASSWORD="${GLPI_DB_PASSWORD:-}"

GLPI_DEFAULT_LANGUAGE="${GLPI_DEFAULT_LANGUAGE:-pt_BR}"
GLPI_DEFAULT_ENTITY_ID="${GLPI_DEFAULT_ENTITY_ID:-0}"
GLPI_LAB_CATEGORY_NAME="${GLPI_LAB_CATEGORY_NAME:-Zabbix Alerts}"
GLPI_API_CLIENT_NAME="${GLPI_API_CLIENT_NAME:-zabbix-glpi-gemini-lab}"

GLPI_API_USERNAME="${GLPI_API_USERNAME:-zabbix-integration}"
GLPI_API_PASSWORD="${GLPI_API_PASSWORD:-zabbix-integration-pass}"

if [[ -z "${GLPI_DB_PASSWORD}" ]]; then
  echo "GLPI_DB_PASSWORD is required"
  exit 1
fi

log() {
  echo "[glpi-bootstrap] $*"
}

run_glpi_console() {
  local args="$*"
  su -s /bin/sh www-data -c "php '${GLPI_CONSOLE_PATH}' ${args}"
}

wait_for_console() {
  local deadline
  deadline=$((SECONDS + GLPI_BOOTSTRAP_TIMEOUT))
  while (( SECONDS < deadline )); do
    if [[ -x "${GLPI_CONSOLE_PATH}" ]]; then
      log "GLPI console is ready: ${GLPI_CONSOLE_PATH}"
      return 0
    fi
    log "Waiting for GLPI console at ${GLPI_CONSOLE_PATH}"
    sleep 5
  done
  log "Timeout waiting for GLPI console"
  return 1
}

install_if_needed() {
  local glpi_root
  local config_file

  glpi_root="$(cd "$(dirname "${GLPI_CONSOLE_PATH}")/.." && pwd)"
  config_file="${glpi_root}/config/config_db.php"

  if [[ -f "${config_file}" ]]; then
    log "GLPI already installed (${config_file} exists)"
    return 0
  fi

  log "GLPI not installed yet. Running db:install"
  run_glpi_console \
    "db:install --db-host='${GLPI_DB_HOST}' --db-port='${GLPI_DB_PORT}' --db-name='${GLPI_DB_NAME}' --db-user='${GLPI_DB_USER}' --db-password='${GLPI_DB_PASSWORD}' --default-language='${GLPI_DEFAULT_LANGUAGE}' --no-interaction --force --no-telemetry"
}

ensure_user() {
  log "Ensuring GLPI integration user '${GLPI_API_USERNAME}'"

  # Create user on first run; on subsequent runs it may already exist.
  run_glpi_console "user:create '${GLPI_API_USERNAME}' --password '${GLPI_API_PASSWORD}' --no-interaction" || true

  # Keep user enabled and with super-admin profile (id=4) for lab simplicity.
  run_glpi_console "user:enable '${GLPI_API_USERNAME}' --no-interaction" || true
  run_glpi_console "user:grant '${GLPI_API_USERNAME}' --profile=4 --entity='${GLPI_DEFAULT_ENTITY_ID}' --recursive --no-interaction" || true
}

configure_glpi_db() {
  log "Applying API and lab defaults directly in GLPI database"

  php <<'PHP'
<?php
$host = getenv('GLPI_DB_HOST') ?: 'glpi-db';
$port = getenv('GLPI_DB_PORT') ?: '3306';
$db = getenv('GLPI_DB_NAME') ?: 'glpi';
$user = getenv('GLPI_DB_USER') ?: 'glpi';
$pass = getenv('GLPI_DB_PASSWORD') ?: '';
$entityId = (int)(getenv('GLPI_DEFAULT_ENTITY_ID') ?: '0');
$clientName = getenv('GLPI_API_CLIENT_NAME') ?: 'zabbix-glpi-gemini-lab';
$categoryName = getenv('GLPI_LAB_CATEGORY_NAME') ?: 'Zabbix Alerts';

$dsn = sprintf('mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4', $host, $port, $db);
$pdo = new PDO($dsn, $user, $pass, [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
]);

// API settings
$settings = [
    'enable_api' => '1',
    'enable_api_login_credentials' => '1',
    'enable_api_login_external_token' => '0',
];

$selCfg = $pdo->prepare("SELECT id FROM glpi_configs WHERE context = 'core' AND name = :name LIMIT 1");
$updCfg = $pdo->prepare("UPDATE glpi_configs SET value = :value WHERE id = :id");
$insCfg = $pdo->prepare("INSERT INTO glpi_configs (context, name, value) VALUES ('core', :name, :value)");

foreach ($settings as $name => $value) {
    $selCfg->execute([':name' => $name]);
    $row = $selCfg->fetch();
    if ($row) {
        $updCfg->execute([':value' => $value, ':id' => $row['id']]);
    } else {
        $insCfg->execute([':name' => $name, ':value' => $value]);
    }
}

// API client for Docker network calls (no app token required in lab)
$selClient = $pdo->prepare("SELECT id FROM glpi_apiclients WHERE name = :name ORDER BY id ASC LIMIT 1");
$selClient->execute([':name' => $clientName]);
$client = $selClient->fetch();

if ($client) {
    $updClient = $pdo->prepare("
        UPDATE glpi_apiclients
        SET is_active = 1,
            ipv4_range_start = NULL,
            ipv4_range_end = NULL,
            ipv6 = NULL,
            app_token = NULL,
            dolog_method = 0,
            comment = :comment,
            date_mod = NOW()
        WHERE id = :id
    ");
    $updClient->execute([
        ':comment' => 'API client managed by zabbix-glpi-gemini lab bootstrap',
        ':id' => $client['id'],
    ]);
} else {
    $insClient = $pdo->prepare("
        INSERT INTO glpi_apiclients (
            entities_id, is_recursive, name, is_active,
            ipv4_range_start, ipv4_range_end, ipv6, app_token,
            dolog_method, comment, date_creation, date_mod
        ) VALUES (
            :entities_id, 1, :name, 1,
            NULL, NULL, NULL, NULL,
            0, :comment, NOW(), NOW()
        )
    ");
    $insClient->execute([
        ':entities_id' => $entityId,
        ':name' => $clientName,
        ':comment' => 'API client managed by zabbix-glpi-gemini lab bootstrap',
    ]);
}

// Lab ITIL category
$selCategory = $pdo->prepare("
    SELECT id FROM glpi_itilcategories
    WHERE entities_id = :entities_id AND name = :name
    ORDER BY id ASC
    LIMIT 1
");
$selCategory->execute([
    ':entities_id' => $entityId,
    ':name' => $categoryName,
]);
$category = $selCategory->fetch();

if ($category) {
    $updCategory = $pdo->prepare("
        UPDATE glpi_itilcategories
        SET completename = :completename,
            is_recursive = 1,
            is_helpdeskvisible = 1,
            is_incident = 1,
            is_request = 1,
            is_problem = 1,
            is_change = 1,
            date_mod = NOW()
        WHERE id = :id
    ");
    $updCategory->execute([
        ':completename' => $categoryName,
        ':id' => $category['id'],
    ]);
} else {
    $insCategory = $pdo->prepare("
        INSERT INTO glpi_itilcategories (
            entities_id, is_recursive, itilcategories_id, name, completename, level,
            comment, is_helpdeskvisible, is_incident, is_request, is_problem, is_change,
            date_creation, date_mod
        ) VALUES (
            :entities_id, 1, 0, :name, :completename, 1,
            :comment, 1, 1, 1, 1, 1,
            NOW(), NOW()
        )
    ");
    $insCategory->execute([
        ':entities_id' => $entityId,
        ':name' => $categoryName,
        ':completename' => $categoryName,
        ':comment' => 'Created by zabbix-glpi-gemini lab bootstrap',
    ]);
}

echo "GLPI database defaults applied successfully\n";
PHP
}

main() {
  log "Starting GLPI bootstrap"
  wait_for_console
  install_if_needed
  run_glpi_console "config:set enable_api 1 --no-interaction"
  run_glpi_console "config:set enable_api_login_credentials 1 --no-interaction"
  run_glpi_console "config:set enable_api_login_external_token 0 --no-interaction"
  ensure_user
  configure_glpi_db
  log "GLPI bootstrap completed"
}

main "$@"
