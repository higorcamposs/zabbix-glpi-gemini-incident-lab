#!/usr/bin/env python3
"""
Bootstrap the didactic Zabbix lab through the Zabbix API.

Created objects:
- template with fake trapper items and triggers
- two fake Linux hosts
- host macros used by the AI context
- two webhook media types
- webhook user media and two trigger actions

The script is idempotent and can be run multiple times.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx


API_URL = os.getenv("ZABBIX_API_URL", "http://localhost:8080/api_jsonrpc.php")
PUBLIC_ZABBIX_URL = os.getenv("PUBLIC_ZABBIX_URL", "http://localhost:8080").rstrip("/")
ZABBIX_USER = os.getenv("ZABBIX_USER", "")
ZABBIX_PASSWORD = os.getenv("ZABBIX_PASSWORD", "")
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "")
TIMEOUT_SECONDS = int(os.getenv("ZABBIX_BOOTSTRAP_TIMEOUT", "300"))

HOST_GROUP_NAME = "Zabbix GLPI AI Lab"
TEMPLATE_GROUP_NAME = "Templates/Lab"
TEMPLATE_NAME = "Template Lab Fake Linux Trapper"
TRADITIONAL_HOST = "srv-linux-traditional"
AI_HOST = "srv-linux-ai"
MEDIA_TRADITIONAL = "GLPI Traditional Webhook"
MEDIA_AI = "GLPI Gemini Enriched Webhook"
WEBHOOK_USER = os.getenv("ZABBIX_WEBHOOK_USER", ZABBIX_USER)


WEBHOOK_SCRIPT = r"""
try {
    var params = JSON.parse(value);
    var request = new HttpRequest();
    var payload = {};
    var fields = [
        'event_id', 'event_name', 'event_status', 'event_severity', 'event_date',
        'event_time', 'recovery_status', 'host_id', 'host_name', 'host_ip',
        'host_groups', 'host_templates', 'host_description', 'trigger_id',
        'trigger_name', 'trigger_expression', 'trigger_description', 'item_name',
        'item_key', 'item_value', 'operational_data', 'tags', 'macros',
        'problem_url', 'flow_type', 'lab_scenario', 'demo_description'
    ];

    request.addHeader('Content-Type: application/json');
    if (params.secret) {
        request.addHeader('X-Webhook-Token: ' + params.secret);
    }

    for (var i = 0; i < fields.length; i++) {
        payload[fields[i]] = params[fields[i]] || '';
    }

    var response = request.post(params.url, JSON.stringify(payload));
    var status = request.getStatus();

    Zabbix.log(4, '[GLPI lab webhook] status=' + status + ' response=' + response);
    if (status < 200 || status >= 300) {
        throw 'HTTP ' + status + ': ' + response;
    }

    return response;
}
catch (error) {
    Zabbix.log(3, '[GLPI lab webhook] failed: ' + error);
    throw error;
}
"""


@dataclass(frozen=True)
class FakeItem:
    key: str
    name: str
    value_type: int
    units: str = ""


@dataclass(frozen=True)
class FakeTrigger:
    name: str
    expression: str
    scenario: str
    priority: int
    description: str


ITEMS = [
    FakeItem("cpu.util", "CPU utilization", 0, "%"),
    FakeItem("memory.util", "Memory utilization", 0, "%"),
    FakeItem("disk.util", "Disk utilization", 0, "%"),
    FakeItem("service.status", "Demo service status", 3, ""),
]

TRIGGERS = [
    FakeTrigger(
        name="High CPU usage when cpu.util > 90",
        expression=f"last(/{TEMPLATE_NAME}/cpu.util)>90",
        scenario="cpu_high",
        priority=4,
        description="Cenario didatico: CPU acima de 90%. Compara automacao tradicional com ticket enriquecido por IA.",
    ),
    FakeTrigger(
        name="High memory usage when memory.util > 90",
        expression=f"last(/{TEMPLATE_NAME}/memory.util)>90",
        scenario="memory_high",
        priority=4,
        description="Cenario didatico: memoria acima de 90%. Mostra como contexto reduz a triagem manual.",
    ),
    FakeTrigger(
        name="Disk space critical when disk.util > 90",
        expression=f"last(/{TEMPLATE_NAME}/disk.util)>90",
        scenario="disk_full",
        priority=4,
        description="Cenario didatico: disco com uso critico acima de 90%. Demonstra impacto e proximos passos.",
    ),
    FakeTrigger(
        name="Service unavailable when service.status = 0",
        expression=f"last(/{TEMPLATE_NAME}/service.status)=0",
        scenario="service_down",
        priority=4,
        description="Cenario didatico: servico indisponivel. Demonstra analise operacional e runbook.",
    ),
]

COMMON_MACROS = [
    {"macro": "{$ENVIRONMENT}", "value": "lab"},
    {"macro": "{$APPLICATION}", "value": "demo-linux-server"},
    {"macro": "{$OWNER_TEAM}", "value": "N2 Linux"},
    {"macro": "{$CRITICALITY}", "value": "medium"},
    {"macro": "{$BUSINESS_SERVICE}", "value": "Student Demo Platform"},
    {
        "macro": "{$RUNBOOK_URL}",
        "value": os.getenv(
            "LAB_RUNBOOK_URL",
            "https://github.com/higorcamposs/zabbix-glpi-gemini-incident-lab",
        ),
    },
    {
        "macro": "{$DEFAULT_ACTION}",
        "value": "validate process, check resource usage, review recent logs",
    },
    {"macro": "{$ESCALATION_TEAM}", "value": "Linux Operations"},
    {
        "macro": "{$MONITORING_SCOPE}",
        "value": "CPU, memory, disk and service availability",
    },
]


class ZabbixApi:
    def __init__(self, url: str) -> None:
        self.url = url
        self.auth: str | None = None
        self._id = 0
        self.client = httpx.Client(timeout=30.0)

    def call(self, method: str, params: dict[str, Any] | list[Any] | None = None, auth: bool = True) -> Any:
        self._id += 1
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._id,
        }
        headers = {}
        if auth and self.auth:
            headers["Authorization"] = f"Bearer {self.auth}"

        response = self.client.post(self.url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            error = data["error"]
            raise RuntimeError(f"{method} failed: {error.get('message')} - {error.get('data')}")
        return data.get("result")

    def wait(self, timeout: int) -> None:
        deadline = time.time() + timeout
        last_error = ""
        while time.time() < deadline:
            try:
                version = self.call("apiinfo.version", auth=False)
                print(f"Zabbix API available: version={version}")
                return
            except Exception as exc:
                last_error = str(exc)
                print(f"Waiting for Zabbix API at {self.url}: {last_error}")
                time.sleep(5)
        raise TimeoutError(f"Zabbix API did not become available: {last_error}")

    def login(self) -> None:
        self.auth = self.call(
            "user.login",
            {"username": ZABBIX_USER, "password": ZABBIX_PASSWORD},
            auth=False,
        )
        print(f"Authenticated in Zabbix API as {ZABBIX_USER}")


def first(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return items[0] if items else None


def require_env(name: str, value: str) -> None:
    if not value.strip():
        raise RuntimeError(f"{name} is required. Set it in .env before running bootstrap.")


def ensure_host_group(api: ZabbixApi, name: str) -> str:
    result = api.call("hostgroup.get", {"filter": {"name": [name]}, "output": ["groupid", "name"]})
    existing = first(result)
    if existing:
        print(f"Host group exists: {name}")
        return existing["groupid"]

    created = api.call("hostgroup.create", {"name": name})
    groupid = created["groupids"][0]
    print(f"Host group created: {name} ({groupid})")
    return groupid


def ensure_template_group(api: ZabbixApi, name: str) -> str:
    try:
        result = api.call("templategroup.get", {"filter": {"name": [name]}, "output": ["groupid", "name"]})
        existing = first(result)
        if existing:
            print(f"Template group exists: {name}")
            return existing["groupid"]

        created = api.call("templategroup.create", {"name": name})
        groupid = created["groupids"][0]
        print(f"Template group created: {name} ({groupid})")
        return groupid
    except Exception as exc:
        print(f"Template group API unavailable or failed ({exc}); using host group fallback")
        return ensure_host_group(api, name)


def ensure_template(api: ZabbixApi, groupid: str) -> str:
    result = api.call("template.get", {"filter": {"host": [TEMPLATE_NAME]}, "output": ["templateid", "host"]})
    existing = first(result)
    if existing:
        templateid = existing["templateid"]
        api.call("template.update", {"templateid": templateid, "groups": [{"groupid": groupid}]})
        print(f"Template exists: {TEMPLATE_NAME}")
        return templateid

    created = api.call("template.create", {"host": TEMPLATE_NAME, "groups": [{"groupid": groupid}]})
    templateid = created["templateids"][0]
    print(f"Template created: {TEMPLATE_NAME} ({templateid})")
    return templateid


def ensure_items(api: ZabbixApi, templateid: str) -> None:
    for item in ITEMS:
        result = api.call(
            "item.get",
            {
                "hostids": [templateid],
                "filter": {"key_": [item.key]},
                "output": ["itemid", "key_"],
            },
        )
        params = {
            "name": item.name,
            "key_": item.key,
            "hostid": templateid,
            "type": 2,  # Zabbix trapper
            "value_type": item.value_type,
            "delay": "0",
            "units": item.units,
            "description": "Fake trapper item for the Zabbix GLPI AI lab.",
        }
        existing = first(result)
        if existing:
            update_params = dict(params)
            update_params.pop("hostid", None)
            api.call("item.update", {"itemid": existing["itemid"], **update_params})
            print(f"Item updated: {item.key}")
        else:
            api.call("item.create", params)
            print(f"Item created: {item.key}")


def ensure_triggers(api: ZabbixApi, templateid: str) -> None:
    for trigger in TRIGGERS:
        result = api.call(
            "trigger.get",
            {
                "hostids": [templateid],
                "filter": {"description": [trigger.name]},
                "output": ["triggerid", "description"],
            },
        )
        params = {
            "description": trigger.name,
            "expression": trigger.expression,
            "priority": trigger.priority,
            "comments": trigger.description,
            "opdata": "Current value: {ITEM.LASTVALUE}",
            "tags": [
                {"tag": "lab", "value": "zabbix-glpi-gemini"},
                {"tag": "lab_scenario", "value": trigger.scenario},
                {"tag": "flow_type", "value": "{$FLOW_TYPE}"},
            ],
        }
        existing = first(result)
        if existing:
            api.call("trigger.update", {"triggerid": existing["triggerid"], **params})
            print(f"Trigger updated: {trigger.name}")
        else:
            api.call("trigger.create", params)
            print(f"Trigger created: {trigger.name}")


def host_macros(flow_type: str) -> list[dict[str, str]]:
    return [{"macro": "{$FLOW_TYPE}", "value": flow_type}, *COMMON_MACROS]


def ensure_host(api: ZabbixApi, groupid: str, templateid: str, name: str, flow_type: str, description: str) -> str:
    result = api.call(
        "host.get",
        {
            "filter": {"host": [name]},
            "output": ["hostid", "host"],
            "selectInterfaces": ["interfaceid", "ip", "type", "main", "useip", "dns", "port"],
        },
    )
    host_params = {
        "host": name,
        "name": name,
        "groups": [{"groupid": groupid}],
        "templates": [{"templateid": templateid}],
        "description": description,
        "macros": host_macros(flow_type),
    }
    interface = {
        "type": 1,
        "main": 1,
        "useip": 1,
        "ip": "127.0.0.1",
        "dns": "",
        "port": "10050",
    }

    existing = first(result)
    if existing:
        hostid = existing["hostid"]
        api.call("host.update", {"hostid": hostid, **host_params})
        if not existing.get("interfaces"):
            api.call("hostinterface.create", {"hostid": hostid, **interface})
        print(f"Host updated: {name}")
        return hostid

    created = api.call("host.create", {**host_params, "interfaces": [interface]})
    hostid = created["hostids"][0]
    print(f"Host created: {name} ({hostid})")
    return hostid


def common_media_parameters(flow_type: str, url: str) -> list[dict[str, str]]:
    macro_summary = (
        "{$ENVIRONMENT}={$ENVIRONMENT}; "
        "{$APPLICATION}={$APPLICATION}; "
        "{$OWNER_TEAM}={$OWNER_TEAM}; "
        "{$CRITICALITY}={$CRITICALITY}; "
        "{$BUSINESS_SERVICE}={$BUSINESS_SERVICE}; "
        "{$RUNBOOK_URL}={$RUNBOOK_URL}; "
        "{$DEFAULT_ACTION}={$DEFAULT_ACTION}; "
        "{$ESCALATION_TEAM}={$ESCALATION_TEAM}; "
        "{$MONITORING_SCOPE}={$MONITORING_SCOPE}"
    )
    return [
        {"name": "url", "value": url},
        {"name": "secret", "value": WEBHOOK_SHARED_SECRET},
        {"name": "event_id", "value": "{EVENT.ID}"},
        {"name": "event_name", "value": "{EVENT.NAME}"},
        {"name": "event_status", "value": "{EVENT.STATUS}"},
        {"name": "event_severity", "value": "{EVENT.SEVERITY}"},
        {"name": "event_date", "value": "{EVENT.DATE}"},
        {"name": "event_time", "value": "{EVENT.TIME}"},
        {"name": "recovery_status", "value": "{EVENT.RECOVERY.STATUS}"},
        {"name": "host_id", "value": "{HOST.ID}"},
        {"name": "host_name", "value": "{HOST.NAME}"},
        {"name": "host_ip", "value": "{HOST.IP}"},
        {"name": "host_groups", "value": "{TRIGGER.HOSTGROUP.NAME}"},
        {"name": "host_templates", "value": "{HOST.TEMPLATE.NAME}"},
        {"name": "host_description", "value": "{HOST.DESCRIPTION}"},
        {"name": "trigger_id", "value": "{TRIGGER.ID}"},
        {"name": "trigger_name", "value": "{TRIGGER.NAME}"},
        {"name": "trigger_expression", "value": "{TRIGGER.EXPRESSION}"},
        {"name": "trigger_description", "value": "{TRIGGER.DESCRIPTION}"},
        {"name": "item_name", "value": "{ITEM.NAME}"},
        {"name": "item_key", "value": "{ITEM.KEY}"},
        {"name": "item_value", "value": "{ITEM.VALUE}"},
        {"name": "operational_data", "value": "{EVENT.OPDATA}"},
        {"name": "tags", "value": "{EVENT.TAGSJSON}"},
        {"name": "macros", "value": macro_summary},
        {
            "name": "problem_url",
            "value": f"{PUBLIC_ZABBIX_URL}/tr_events.php?triggerid={{TRIGGER.ID}}&eventid={{EVENT.ID}}",
        },
        {"name": "flow_type", "value": flow_type},
        {"name": "lab_scenario", "value": "{EVENT.TAGS.lab_scenario}"},
        {"name": "demo_description", "value": "{TRIGGER.DESCRIPTION}"},
    ]


def ensure_media_type(api: ZabbixApi, name: str, flow_type: str, url: str) -> str:
    result = api.call("mediatype.get", {"filter": {"name": [name]}, "output": ["mediatypeid", "name"]})
    params = {
        "name": name,
        "type": 4,  # webhook
        "status": 0,
        "description": f"Zabbix GLPI AI lab webhook ({flow_type})",
        "script": WEBHOOK_SCRIPT,
        "timeout": os.getenv("ZABBIX_WEBHOOK_TIMEOUT", "60s"),
        "parameters": common_media_parameters(flow_type, url),
    }
    existing = first(result)
    if existing:
        api.call("mediatype.update", {"mediatypeid": existing["mediatypeid"], **params})
        print(f"Media type updated: {name}")
        return existing["mediatypeid"]

    created = api.call("mediatype.create", params)
    mediatypeid = created["mediatypeids"][0]
    print(f"Media type created: {name} ({mediatypeid})")
    return mediatypeid


def get_user(api: ZabbixApi, username: str) -> dict[str, Any]:
    result = api.call(
        "user.get",
        {
            "filter": {"username": [username]},
            "output": ["userid", "username", "alias"],
            "selectMedias": "extend",
        },
    )
    existing = first(result)
    if existing:
        return existing

    result = api.call(
        "user.get",
        {
            "filter": {"alias": [username]},
            "output": ["userid", "username", "alias"],
            "selectMedias": "extend",
        },
    )
    existing = first(result)
    if not existing:
        raise RuntimeError(f"Zabbix user not found: {username}")
    return existing


_ALLOWED_MEDIA_FIELDS = {"mediatypeid", "sendto", "active", "severity", "period"}


def _sanitize_media(media: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields accepted by user.update (Zabbix 7 rejects extras)."""
    clean: dict[str, Any] = {}
    for field in _ALLOWED_MEDIA_FIELDS:
        if field in media and media[field] is not None:
            clean[field] = media[field]
    return clean


def ensure_user_media(api: ZabbixApi, userid: str, mediatypeids: list[str]) -> None:
    user = get_user(api, WEBHOOK_USER)
    raw_medias = user.get("medias") or []
    medias = [_sanitize_media(m) for m in raw_medias]
    existing_media_type_ids = {media.get("mediatypeid") for media in medias}

    changed = False
    for mediatypeid in mediatypeids:
        if mediatypeid in existing_media_type_ids:
            continue
        medias.append(
            {
                "mediatypeid": mediatypeid,
                "sendto": ["glpi-lab@example.local"],
                "active": 0,
                "severity": 63,
                "period": "1-7,00:00-24:00",
            }
        )
        changed = True

    if changed:
        api.call("user.update", {"userid": userid, "medias": medias})
        print(f"User media updated: userid={userid}")
    else:
        print(f"User media already configured: userid={userid}")


def ensure_action(api: ZabbixApi, name: str, hostid: str, userid: str, mediatypeid: str) -> None:
    operation = {
        "operationtype": 0,
        "esc_step_from": 1,
        "esc_step_to": 1,
        "esc_period": "0",
        "opmessage_usr": [{"userid": userid}],
        "opmessage": {
            "default_msg": 0,
            "mediatypeid": mediatypeid,
            "subject": "{EVENT.SEVERITY}: {EVENT.NAME}",
            "message": "{EVENT.NAME}",
        },
    }
    recovery_operation = {
        "operationtype": 0,
        "opmessage_usr": [{"userid": userid}],
        "opmessage": {
            "default_msg": 0,
            "mediatypeid": mediatypeid,
            "subject": "RECOVERY: {EVENT.NAME}",
            "message": "{EVENT.NAME}",
        },
    }
    params = {
        "name": name,
        "eventsource": 0,
        "status": 0,
        "esc_period": "1m",
        "filter": {
            "evaltype": 0,
            "conditions": [
                {
                    "conditiontype": 1,  # Host
                    "operator": 0,
                    "value": hostid,
                }
            ],
        },
        "operations": [operation],
        "recovery_operations": [recovery_operation],
    }

    result = api.call("action.get", {"filter": {"name": [name]}, "output": ["actionid", "name"]})
    existing = first(result)
    if existing:
        api.call("action.update", {"actionid": existing["actionid"], **params})
        print(f"Action updated: {name}")
    else:
        api.call("action.create", params)
        print(f"Action created: {name}")


def ensure_global_macro(api: ZabbixApi) -> None:
    try:
        result = api.call(
            "usermacro.get",
            {
                "globalmacro": True,
                "filter": {"macro": ["{$ZABBIX.URL}"]},
                "output": ["globalmacroid", "macro", "value"],
            },
        )
        existing = first(result)
        if existing:
            api.call(
                "usermacro.updateglobal",
                {"globalmacroid": existing["globalmacroid"], "value": f"{PUBLIC_ZABBIX_URL}/"},
            )
            print("Global macro updated: {$ZABBIX.URL}")
            return
        api.call("usermacro.createglobal", {"macro": "{$ZABBIX.URL}", "value": f"{PUBLIC_ZABBIX_URL}/"})
        print("Global macro created: {$ZABBIX.URL}")
    except Exception as exc:
        print(f"Global macro setup skipped: {exc}")


def main() -> int:
    print("Starting Zabbix bootstrap")
    print(f"API URL: {API_URL}")
    api = ZabbixApi(API_URL)
    try:
        require_env("ZABBIX_PASSWORD", ZABBIX_PASSWORD)
        require_env("ZABBIX_USER", ZABBIX_USER)
        require_env("WEBHOOK_SHARED_SECRET", WEBHOOK_SHARED_SECRET)
        api.wait(TIMEOUT_SECONDS)
        api.login()

        host_groupid = ensure_host_group(api, HOST_GROUP_NAME)
        template_groupid = ensure_template_group(api, TEMPLATE_GROUP_NAME)
        templateid = ensure_template(api, template_groupid)
        ensure_items(api, templateid)
        ensure_triggers(api, templateid)

        traditional_hostid = ensure_host(
            api,
            host_groupid,
            templateid,
            TRADITIONAL_HOST,
            "traditional",
            "Fake Linux server for the traditional Zabbix to GLPI flow without AI.",
        )
        ai_hostid = ensure_host(
            api,
            host_groupid,
            templateid,
            AI_HOST,
            "ai",
            "Fake Linux server for the AI-enriched Zabbix to GLPI flow.",
        )

        traditional_mediaid = ensure_media_type(
            api,
            MEDIA_TRADITIONAL,
            "traditional",
            "http://gemini-incident-api:8000/webhook/zabbix/plain",
        )
        ai_mediaid = ensure_media_type(
            api,
            MEDIA_AI,
            "ai",
            "http://gemini-incident-api:8000/webhook/zabbix/gemini",
        )

        user = get_user(api, WEBHOOK_USER)
        userid = user["userid"]
        ensure_user_media(api, userid, [traditional_mediaid, ai_mediaid])
        ensure_action(api, "LAB - GLPI Traditional flow", traditional_hostid, userid, traditional_mediaid)
        ensure_action(api, "LAB - GLPI AI enriched flow", ai_hostid, userid, ai_mediaid)
        ensure_global_macro(api)

    except Exception as exc:
        print(f"Zabbix bootstrap failed: {exc}", file=sys.stderr)
        return 1

    print("Zabbix bootstrap completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
