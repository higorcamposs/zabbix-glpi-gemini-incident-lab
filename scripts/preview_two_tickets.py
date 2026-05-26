#!/usr/bin/env python3
"""
Preview or create two GLPI tickets: plain (minimal) vs Gemini-enriched.

Usage (from repo root):
  python scripts/preview_two_tickets.py           # preview only
  python scripts/preview_two_tickets.py --glpi    # create tickets in GLPI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "app"))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

from config import get_settings  # noqa: E402
from models import ZabbixWebhookPayload  # noqa: E402
from services.gemini_client import GeminiClient  # noqa: E402
from services.glpi_client import GlpiClient  # noqa: E402
from services.incident_builder import build_enriched_package, build_plain_ticket  # noqa: E402
from services.zabbix_context import build_alert_context  # noqa: E402

EXAMPLES = REPO_ROOT / "examples"


def load_payload(name: str, flow: str) -> ZabbixWebhookPayload:
    suffix = "traditional" if flow == "plain" else "ai"
    path = EXAMPLES / f"zabbix_payload_{name}_{suffix}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return ZabbixWebhookPayload.model_validate(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview plain vs Gemini GLPI tickets")
    parser.add_argument(
        "--glpi",
        action="store_true",
        help="Create tickets in GLPI (requires tokens in .env)",
    )
    parser.add_argument(
        "--scenario",
        default="cpu_high",
        choices=["cpu_high", "memory_high", "disk_full", "service_down"],
    )
    args = parser.parse_args()
    settings = get_settings()

    print("=" * 60)
    print("1) FLUXO TRADICIONAL — chamado simples (sem IA)")
    print("=" * 60)

    ctx_plain = build_alert_context(load_payload(args.scenario, "plain"))
    ticket_plain = build_plain_ticket(ctx_plain)
    print(f"Título: {ticket_plain.title}\n")
    print(ticket_plain.content)
    print()

    print("=" * 60)
    print("2) FLUXO GEMINI — chamado enriquecido")
    print("=" * 60)

    if not settings.gemini_configured:
        print("ERRO: GEMINI_API_KEY não configurada no .env", file=sys.stderr)
        return 1

    ctx_ai = build_alert_context(load_payload(args.scenario, "gemini"))
    print(f"Chamando Gemini ({settings.gemini_model})...")
    analysis = GeminiClient(settings).analyze(ctx_ai)
    package = build_enriched_package(ctx_ai, analysis)

    print(f"Título: {package.title}\n")
    print("--- Descrição principal (curta) ---")
    print(package.summary_content)
    print("\n--- Acompanhamento (análise completa) ---")
    print(package.followup_content[:2000], "...\n" if len(package.followup_content) > 2000 else "")
    print()

    print("=" * 60)
    print("Resumo da análise Gemini (JSON)")
    print("=" * 60)
    print(
        json.dumps(
            analysis.model_dump(exclude={"raw_response"}),
            ensure_ascii=False,
            indent=2,
        )
    )

    if args.glpi:
        if not settings.glpi_configured:
            print("\nGLPI não configurado (GLPI_USER_TOKEN vazio).", file=sys.stderr)
            return 1
        print("\n" + "=" * 60)
        print("Criando tickets no GLPI...")
        print("=" * 60)
        with GlpiClient(settings) as client:
            id_plain = client.create_ticket(ticket_plain.title, ticket_plain.content)
            print(f"Ticket tradicional criado: ID {id_plain}")
            result = client.create_enriched_ticket_with_worknotes(package)
            print(
                f"Ticket Gemini criado: ID {result['ticket_id']} "
                f"| followup={result.get('followup_id')} "
                f"| task={result.get('task_id')} "
                f"| fallback_inline={result.get('used_inline_fallback')}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
