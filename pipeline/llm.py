"""LLM providers for the structuring agent (ADR 0012): interface + DeepSeek + mock.

The agent only knows ``provider.complete_json(system, user) -> (payload, usage)``.
Swapping providers or models is configuration, not code. DeepSeek is
OpenAI-compatible (base https://api.deepseek.com); JSON mode requires the word
"json" in the prompt — the agent's prompts already include it.

Credentials: DEEPSEEK_API_KEY from the environment only — never from a repo file.
"""

import json
import os
from pathlib import Path

import requests

API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"

# USD per 1M tokens, as published (api-docs.deepseek.com pricing, verified
# 2026-05 via secondary coverage). Logged per call so the R$/card of M2.6 is an
# aggregation, not an estimate. Review on provider price changes.
RATES = {
    "deepseek-v4-flash": {"input": 0.14, "output": 0.28, "as_of": "2026-05"},
}


class DeepSeekProvider:
    """Pay-per-token JSON-mode provider (ADR 0012 baseline)."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not set — credentials live outside the repo")

    def complete_json(self, system: str, user: str, max_tokens: int = 2500) -> tuple[dict, dict]:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},  # reasoning eats max_tokens and leaves content empty
                "temperature": 0,
                "max_tokens": max_tokens,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"]["content"] or ""
        if not content.strip():
            raise ValueError(f"empty completion (finish_reason={choice.get('finish_reason')})")
        usage = data.get("usage") or {}
        rate = RATES.get(self.model, {})
        cost_usd = (
            usage.get("prompt_tokens", 0) * rate.get("input", 0)
            + usage.get("completion_tokens", 0) * rate.get("output", 0)
        ) / 1_000_000
        return json.loads(content), {
            "model": self.model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "cost_usd": round(cost_usd, 8),
            "rate_as_of": rate.get("as_of"),
        }


class MockProvider:
    """Deterministic offline provider for tests: parses 'Label: value' lines."""

    name = "mock"

    LABELS = {
        "título": "titulo", "titulo": "titulo", "autor": "autor", "data": "data",
        "material": "material", "dimensões": "dimensoes", "dimensoes": "dimensoes",
        "descrição": "descricao", "descricao": "descricao",
    }

    def __init__(self, fail_first: bool = False):
        self._fail_first = fail_first

    def complete_json(self, system: str, user: str, max_tokens: int = 1500) -> tuple[dict, dict]:
        if self._fail_first:
            self._fail_first = False
            return {"card": {"titulo": ""}, "provenance": {}}, self._usage()  # invalid on purpose
        card: dict = {}
        provenance: dict = {}
        pending_label: str | None = None  # modern layout: label alone on its line
        for line in user.splitlines():
            line = line.replace("：", ":")  # OCR often yields fullwidth colons
            if ":" in line:
                label, _, value = line.partition(":")
                field = self.LABELS.get(label.strip().lower())
                if field and value.strip():
                    card[field] = value.strip()
                    provenance[field] = {"source": "ocr_read", "confidence": 0.9}
                pending_label = None
                continue
            stripped = line.strip()
            if stripped.lower() in self.LABELS:
                pending_label = stripped.lower()
            elif pending_label and stripped:
                card[self.LABELS[pending_label]] = stripped
                provenance[self.LABELS[pending_label]] = {"source": "ocr_read", "confidence": 0.85}
                pending_label = None
        return {"card": card, "provenance": provenance}, self._usage()

    def _usage(self) -> dict:
        return {"model": self.name, "prompt_tokens": 0, "completion_tokens": 0,
                "cost_usd": 0.0, "rate_as_of": None}


def make_provider(name: str = "deepseek", **kwargs):
    if name == "deepseek":
        return DeepSeekProvider(**kwargs)
    if name == "mock":
        return MockProvider(**kwargs)
    raise ValueError(f"unknown provider {name!r}")
