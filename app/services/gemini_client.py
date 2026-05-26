"""
Gemini client for structured incident analysis from Zabbix alert context.
"""

import json
import logging
from pathlib import Path

from google import genai
from google.genai import types

from config import Settings
from models import AIAnalysis, AlertContext

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "incident_analyst_prompt.txt"


class GeminiClientError(Exception):
    """Raised when Gemini API call fails."""


class GeminiClient:
    """Calls Google Gemini to analyze Zabbix alerts and return structured JSON."""

    def __init__(self, settings: Settings):
        if not settings.gemini_configured:
            raise GeminiClientError("GEMINI_API_KEY is not configured")
        self.model_name = settings.gemini_model
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def _load_system_prompt(self) -> str:
        if PROMPT_PATH.exists():
            return PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "Você é um analista especialista em monitoramento e operação de TI. "
            "Analise o alerta e retorne JSON com: resumo_executivo, impacto_potencial, "
            "causa_provavel, proximos_passos_n1, proximos_passos_n2, evidencias_relevantes, "
            "time_sugerido, prioridade_sugerida, mensagem_para_chamado."
        )

    def _build_user_message(self, ctx: AlertContext) -> str:
        recovery_note = (
            "Este evento é um RECOVERY (problema resolvido)."
            if ctx.is_recovery
            else "Este evento é um PROBLEM (alerta ativo)."
        )
        return (
            f"{recovery_note}\n\n"
            "Analise o seguinte alerta do Zabbix e produza a resposta em JSON conforme instruções:\n\n"
            f"{ctx.context_block}"
        )

    def analyze(self, ctx: AlertContext) -> AIAnalysis:
        """
        Send alert context to Gemini and parse structured AIAnalysis.

        Falls back to raw text in mensagem_para_chamado if JSON is invalid.
        """
        system_prompt = self._load_system_prompt()
        user_message = self._build_user_message(ctx)

        logger.info(
            "Gemini analyze: model=%s event_id=%s host=%s",
            self.model_name,
            ctx.event_id,
            ctx.host_name,
        )

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise GeminiClientError(f"Gemini API error: {exc}") from exc

        raw_text = (response.text or "").strip()
        if not raw_text:
            raise GeminiClientError("Gemini returned empty response")

        return self._parse_response(raw_text)

    def _parse_response(self, raw_text: str) -> AIAnalysis:
        """Parse JSON from Gemini; fallback to raw text on failure."""
        try:
            # Strip markdown code fences if present
            text = raw_text
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(
                    line for line in lines if not line.strip().startswith("```")
                )
            data = json.loads(text)
            if isinstance(data, list) and data:
                data = data[0]
            analysis = AIAnalysis.model_validate(data)
            return analysis
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Gemini JSON parse failed, using raw fallback: %s", exc)
            return AIAnalysis(
                resumo_executivo="Análise gerada pela IA (formato não estruturado).",
                mensagem_para_chamado=raw_text,
                impacto_potencial="Validar manualmente com o time de operações.",
                causa_provavel="Não estruturada automaticamente.",
                proximos_passos_n1=["Revisar a análise bruta anexada abaixo."],
                proximos_passos_n2=["Escalar para N2 se necessário."],
                raw_response=raw_text,
            )
