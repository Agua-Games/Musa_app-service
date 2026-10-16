"""M4.2 — the assistant's server side: grounded answers + anti-abuse stack.

The endpoint (``POST /assistant/ask``, wired in serve.py) answers visitor
questions about the collection with an LLM, and protects the tenant's wallet
first. Layers, cheapest first:

1. module gate       — museums without the "assistant" module get 404 (in the
                       route, same stealth rule as the content gate);
2. turnstile         — Cloudflare Turnstile, only when MUSA_TURNSTILE_SECRET
                       is set (fail closed on verifier errors);
3. rate limit        — sliding window per client IP (MUSA_ASSISTANT_RPM,
                       default 10/min);
4. canned answers    — greetings and "what do you have?" overviews never
                       touch the provider (cost zero);
5. off-topic filter  — a question sharing NO token with the public search
                       index is refused WITHOUT calling the provider — the
                       single strongest cost protection, because the grounding
                       rule would make such a call pointless anyway;
6. daily quota       — token budget per museum per UTC day
                       (MUSA_ASSISTANT_DAILY_TOKENS, default 200k);
7. provider breaker  — 5 consecutive provider failures open the circuit for
                       300 s: 503 without calling the provider.

Grounding: the provider only ever sees the retrieved public cards plus a
system prompt that describes the card fields and forbids inventing beyond
them — the same "context before content" rule as the OCR batch pipeline
(docs/M2_notas.md). Every ask is logged by the route as ``assistant_ask``
with a cost estimate, so per-tenant spend is auditable; IPs are logged
hashed (LGPD).

Provider configuration: DEEPSEEK_API_KEY (+ optional MUSA_DEEPSEEK_MODEL,
default "deepseek-chat"). MUSA_LLM_FAKE=1 installs a deterministic stand-in
for dev/tests/beta — the pipeline runs end-to-end with ~zero cost.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from .api import _tokenize

# USD per 1M tokens — DeepSeek off-peak table (Sep/2026, see docs/M4_custos.md).
# Peak hours double the input prices; the estimate intentionally stays on the
# optimistic side and is labeled an estimate in the logs.
PRICE_INPUT_MISS = 0.15
PRICE_INPUT_HIT = 0.003
PRICE_OUTPUT = 0.60

DEFAULT_RPM = 10
DEFAULT_DAILY_TOKENS = 200_000
BREAKER_THRESHOLD = 5
BREAKER_COOLDOWN_S = 300
QUESTION_MAX_CHARS = 2000
RETRIEVE_K = 8
SUGGESTED_K = 3

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
TURNSTILE_SITE_VERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

GREETING_ANSWER = (
    "Olá! Sou o assistente do museu. Pergunte sobre as obras, autores, "
    "materiais ou coleções do nosso acervo."
)
OFFTOPIC_ANSWER = (
    "Só consigo responder sobre o acervo do museu — obras, autores, "
    "materiais e coleções. Posso ajudar com algo do acervo?"
)
RATE_LIMIT_DETAIL = "muitas perguntas seguidas; aguarde um instante e tente de novo"
QUOTA_DETAIL = "a cota diária do assistente esgotou; tente novamente amanhã"
PROVIDER_DETAIL = "o assistente está temporariamente indisponível; tente em alguns minutos"
TURNSTILE_DETAIL = "a verificação anti-robô falhou; recarregue a página e tente de novo"
NOT_CONFIGURED_DETAIL = "assistant not configured (no LLM provider)"

GREETINGS = {
    "olá", "ola", "oi", "oii", "hello", "hi", "hey",
    "bom dia", "boa tarde", "boa noite", "e aí", "eae",
}
GREETING_HEADS = {"olá", "ola", "oi", "hello", "hi", "hey"}

# Museum-meta vocabulary: questions about the museum itself get a canned
# overview instead of an LLM call (cost zero, always correct).
MUSEUM_META = {
    "museu", "acervo", "colecao", "coleção", "colecoes", "coleções",
    "obras", "exposicao", "exposição", "galeria", "galerias",
}

# PT/EN stopwords never count as retrieval evidence: cards carry them in
# free-text fields, so without this filter any question with "de"/"the"
# would "match" and burn provider tokens on an off-topic call.
STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "num", "numa", "e", "ou", "que",
    "com", "por", "para", "pra", "se", "ao", "aos", "à", "às", "é",
    "foi", "sao", "são", "tem", "têm", "me", "te", "lhe", "nos", "vos",
    "seu", "sua", "seus", "suas", "ele", "ela", "esse", "essa", "isso",
    "the", "of", "and", "in", "to", "is", "are", "was", "were", "an",
}

# Card fields the provider is allowed to see (slim public records).
CONTEXT_FIELDS = (
    "asset_id", "titulo", "autor", "data", "data_iso",
    "material", "descricao", "tags", "colecao",
)

SYSTEM_TEMPLATE = """Você é o assistente virtual do museu "{museum}". Regras estritas:
1. Responda SOMENTE com base nas fichas do acervo fornecidas abaixo. Nunca invente obras, autores, datas ou fatos.
2. Se a pergunta não puder ser respondida com essas fichas, diga educadamente que só consegue falar sobre o acervo do museu.
3. Responda em português, de forma curta (até ~120 palavras) e acolhedora.
4. Ao mencionar uma peça, use o título exato da ficha.

As fichas usam estes campos: titulo (nome da obra), autor, data (texto livre, ex.: "séc. XVII"), data_iso (ano estruturado), material, descricao, tags, colecao (núcleo do museu).

Fichas do acervo relevantes para a pergunta:
{cards}"""


def estimate_cost_usd(prompt_tokens: int, cached_tokens: int,
                      completion_tokens: int) -> float:
    """Optimistic (off-peak) cost estimate for one provider call."""
    miss = max(prompt_tokens - cached_tokens, 0)
    return (miss * PRICE_INPUT_MISS + cached_tokens * PRICE_INPUT_HIT
            + completion_tokens * PRICE_OUTPUT) / 1_000_000


class ProviderError(Exception):
    """The LLM provider failed (network, HTTP != 200, malformed payload)."""


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0


class DeepSeekClient:
    """Minimal chat-completions client for the DeepSeek API."""

    def __init__(self, api_key: str, *, model: str = "deepseek-chat",
                 base_url: str = DEEPSEEK_BASE_URL, timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, *, system: str, user: str) -> LLMResponse:
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 400,
                },
                timeout=self.timeout,
            )
        except Exception as exc:  # network layer
            raise ProviderError(f"provider unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"provider HTTP {resp.status_code}")
        try:
            payload = resp.json()
            text = payload["choices"][0]["message"]["content"]
        except Exception as exc:
            raise ProviderError(f"malformed provider payload: {exc}") from exc
        usage = payload.get("usage") or {}
        return LLMResponse(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            cached_tokens=int(usage.get("prompt_cache_hit_tokens") or 0),
        )


class FakeLLMClient:
    """Deterministic provider stand-in (MUSA_LLM_FAKE=1): dev, tests, beta.

    Echoes the card titles found in the system prompt so the full pipeline
    (retrieval -> prompt -> answer -> suggestions) runs with ~zero cost and
    no network. Token usage is tiny on purpose: hammering scenarios can run
    hundreds of asks without tripping the daily quota.
    """

    def __init__(self):
        self.calls = 0

    def complete(self, *, system: str, user: str) -> LLMResponse:
        self.calls += 1
        titles = re.findall(r'"titulo":\s*"([^"]+)"', system)
        cited = ", ".join(titles[:3]) or "o acervo"
        return LLMResponse(
            text=(f"(resposta simulada) Com base no acervo — {cited} — "
                  f"a resposta para a sua pergunta está nas fichas citadas."),
            prompt_tokens=8,
            completion_tokens=2,
            cached_tokens=0,
        )


class RateLimiter:
    """Sliding-window per-key rate limiter (single-tenant process)."""

    def __init__(self, rpm: int, clock=time.monotonic):
        self.rpm = rpm
        self.clock = clock
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= 60.0:
                hits.popleft()
            if len(hits) >= self.rpm:
                return False
            hits.append(now)
            return True


class DailyQuota:
    """Token budget per UTC day; resets on the first call of a new day."""

    def __init__(self, limit: int):
        self.limit = limit
        self._day: str | None = None
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        day = datetime.now(timezone.utc).date().isoformat()
        if day != self._day:
            self._day = day
            self._used = 0

    def exhausted(self) -> bool:
        with self._lock:
            self._roll()
            return self._used >= self.limit

    def record(self, tokens: int) -> None:
        with self._lock:
            self._roll()
            self._used += tokens

    @property
    def used(self) -> int:
        with self._lock:
            self._roll()
            return self._used


class ProviderBreaker:
    """Circuit breaker: N consecutive failures open the circuit for
    ``cooldown_s`` seconds — while open, no provider call is made."""

    def __init__(self, threshold: int = BREAKER_THRESHOLD,
                 cooldown_s: float = BREAKER_COOLDOWN_S, clock=time.monotonic):
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self.clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if self.clock() - self._opened_at >= self.cooldown_s:
                return False  # half-open: one probe is allowed through
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> bool:
        """Returns True when this failure OPENED the circuit."""
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold and self._opened_at is None:
                self._opened_at = self.clock()
                return True
            return False


@dataclass
class AskOutcome:
    """What the service decided; the route maps it to HTTP + telemetry."""

    status: int
    outcome: str  # ok | greeting | overview | refusal_offtopic | rate_limited
                  # | quota_exceeded | provider_error | provider_down
                  # | turnstile_failed | not_configured
    answer: str | None = None
    suggested: list[dict] = field(default_factory=list)
    detail: str | None = None
    retry_after: int | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cache_hit: int = 0

    @property
    def cost_usd(self) -> float:
        return estimate_cost_usd(self.tokens_in, self.cache_hit, self.tokens_out)


def _default_turnstile_verifier(secret: str, token: str, remote_ip: str) -> bool:
    """Cloudflare Turnstile siteverify. Fail closed on any error."""
    try:
        resp = httpx.post(
            TURNSTILE_SITE_VERIFY,
            data={"secret": secret, "response": token, "remoteip": remote_ip},
            timeout=10.0,
        )
        return bool(resp.json().get("success"))
    except Exception:
        return False


def _overview_answer(state) -> str:
    names = [str(c.get("title") or c["id"]) for c in state.collections[:5]]
    base = f"Nosso acervo tem {len(state.items)} peças"
    if names:
        base += ", em coleções como " + ", ".join(names)
    return base + ". Pergunte sobre uma obra, autor ou material!"


def build_system_prompt(state, cards: list[dict]) -> str:
    """Grounding context: museum identity + field glossary + the retrieved
    cards — the provider never sees anything beyond the public collection."""
    lines = []
    for card in cards:
        slim = {k: v for k, v in card.items() if k in CONTEXT_FIELDS and v is not None}
        lines.append(json.dumps(slim, ensure_ascii=False))
    return SYSTEM_TEMPLATE.format(museum=state.museum_id, cards="\n".join(lines))


class AssistantService:
    """The anti-abuse stack around one LLM client, for one tenant process."""

    def __init__(self, *, llm_client=None, rpm: int = DEFAULT_RPM,
                 daily_tokens: int = DEFAULT_DAILY_TOKENS,
                 turnstile_secret: str | None = None,
                 turnstile_verifier=None,
                 breaker: ProviderBreaker | None = None):
        self.llm_client = llm_client
        self.rate_limiter = RateLimiter(rpm)
        self.quota = DailyQuota(daily_tokens)
        self.breaker = breaker or ProviderBreaker()
        self.turnstile_secret = turnstile_secret
        self.turnstile_verifier = turnstile_verifier or _default_turnstile_verifier

    @classmethod
    def from_env(cls, llm_client=None) -> "AssistantService":
        """Wire the provider from the environment (serve boot)."""
        if llm_client is None:
            if os.environ.get("MUSA_LLM_FAKE") == "1":
                llm_client = FakeLLMClient()
            elif os.environ.get("DEEPSEEK_API_KEY"):
                llm_client = DeepSeekClient(
                    os.environ["DEEPSEEK_API_KEY"],
                    model=os.environ.get("MUSA_DEEPSEEK_MODEL", "deepseek-chat"),
                )
        return cls(
            llm_client=llm_client,
            rpm=int(os.environ.get("MUSA_ASSISTANT_RPM", str(DEFAULT_RPM))),
            daily_tokens=int(os.environ.get("MUSA_ASSISTANT_DAILY_TOKENS",
                                            str(DEFAULT_DAILY_TOKENS))),
            turnstile_secret=os.environ.get("MUSA_TURNSTILE_SECRET") or None,
        )

    def _retrieve(self, state, question: str) -> tuple[list[str], list[dict]]:
        """Tokens of the question, and the top-K public cards ranked by how
        many question tokens each one matches in the search index. Stopwords
        never count as evidence (see STOPWORDS)."""
        tokens = [t for t in _tokenize(question) if t not in STOPWORDS]
        scores: dict[str, int] = {}
        for token in tokens:
            for asset_id in state.index["terms"].get(token, []):
                scores[asset_id] = scores.get(asset_id, 0) + 1
        ranked = sorted(scores, key=lambda a: (-scores[a], a))[:RETRIEVE_K]
        by_id = {i["asset_id"]: i for i in state.items}
        return tokens, [by_id[a] for a in ranked if a in by_id]

    def ask(self, *, state, question: str, client_ip: str,
            turnstile_token: str | None = None) -> AskOutcome:
        if self.llm_client is None:
            return AskOutcome(503, "not_configured", detail=NOT_CONFIGURED_DETAIL)

        if self.turnstile_secret is not None:
            if not turnstile_token or not self.turnstile_verifier(
                    self.turnstile_secret, turnstile_token, client_ip):
                return AskOutcome(403, "turnstile_failed", detail=TURNSTILE_DETAIL)

        if not self.rate_limiter.allow(client_ip):
            return AskOutcome(429, "rate_limited",
                              detail=RATE_LIMIT_DETAIL, retry_after=60)

        tokens, cards = self._retrieve(state, question)
        if not cards:
            normalized = " ".join(tokens)
            if (normalized in GREETINGS
                    or (tokens and tokens[0] in GREETING_HEADS and len(tokens) <= 4)):
                return AskOutcome(200, "greeting", answer=GREETING_ANSWER)
            if any(t in MUSEUM_META for t in tokens):
                return AskOutcome(200, "overview", answer=_overview_answer(state))
            # The strongest cost protection: off-topic never reaches the LLM.
            return AskOutcome(200, "refusal_offtopic", answer=OFFTOPIC_ANSWER)

        if self.quota.exhausted():
            return AskOutcome(429, "quota_exceeded",
                              detail=QUOTA_DETAIL, retry_after=3600)
        if self.breaker.is_open():
            return AskOutcome(503, "provider_down",
                              detail=PROVIDER_DETAIL,
                              retry_after=int(self.breaker.cooldown_s))

        system = build_system_prompt(state, cards)
        try:
            resp = self.llm_client.complete(system=system, user=question)
        except ProviderError:
            opened = self.breaker.record_failure()
            return AskOutcome(503, "provider_down" if opened else "provider_error",
                              detail=PROVIDER_DETAIL,
                              retry_after=int(self.breaker.cooldown_s) if opened else None)
        self.breaker.record_success()
        self.quota.record(resp.prompt_tokens + resp.completion_tokens)

        suggested = [
            {"id": c["asset_id"], "title": c.get("titulo") or c["asset_id"]}
            for c in cards[:SUGGESTED_K]
        ]
        return AskOutcome(
            200, "ok",
            answer=resp.text.strip(),
            suggested=suggested,
            tokens_in=resp.prompt_tokens,
            tokens_out=resp.completion_tokens,
            cache_hit=resp.cached_tokens,
        )
