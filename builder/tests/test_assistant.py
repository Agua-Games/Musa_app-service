"""M4.2 tests: the assistant endpoint and its anti-abuse stack.

Route-level tests (TestClient on the fixture museum) with injected fakes —
no real provider call ever happens here. Each layer is tested in isolation
by constructing the AssistantService with the knob that isolates it.
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from musa_build.assistant import (
    GREETING_ANSWER,
    OFFTOPIC_ANSWER,
    PROVIDER_DETAIL,
    QUOTA_DETAIL,
    RATE_LIMIT_DETAIL,
    TURNSTILE_DETAIL,
    AssistantService,
    FakeLLMClient,
    ProviderBreaker,
    ProviderError,
    estimate_cost_usd,
)
from musa_build.serve import create_app

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "client-ok"

MATCHING_QUESTION = "quem é o autor de Painting One?"
OFFTOPIC_QUESTION = "quem ganhou o campeonato de futebol xyzqw?"


class FailingLLM:
    """Provider that always fails — drives the circuit breaker."""

    def __init__(self):
        self.calls = 0

    def complete(self, *, system, user):
        self.calls += 1
        raise ProviderError("boom")


class AssistantTestBase(unittest.TestCase):
    service_kwargs: dict = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = self.service_kwargs.get("llm_client") or FakeLLMClient()
        kwargs = dict(self.service_kwargs)
        kwargs["llm_client"] = self.fake
        self.service = AssistantService(**kwargs)
        self.app = create_app(FIXTURE, data_dir=Path(self.tmp.name),
                              assistant_service=self.service)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.state.serve.store.close()
        self.tmp.cleanup()

    def ask(self, question=MATCHING_QUESTION, **extra):
        body = {"question": question}
        body.update(extra)
        return self.client.post("/assistant/ask", json=body)


class TestModuleGate(AssistantTestBase):
    def test_museum_without_module_gets_404(self):
        self.app.state.serve.modules = []  # entitlement without "assistant"
        res = self.ask()
        self.assertEqual(res.status_code, 404)
        self.assertEqual(self.fake.calls, 0)

    def test_empty_question_422(self):
        self.assertEqual(self.ask("").status_code, 422)
        self.assertEqual(self.ask("   ").status_code, 422)
        res = self.client.post("/assistant/ask", json={})
        self.assertEqual(res.status_code, 422)

    def test_question_too_long_422(self):
        res = self.ask("x" * 2001)
        self.assertEqual(res.status_code, 422)


class TestHappyPath(AssistantTestBase):
    def test_grounded_answer_with_suggestions(self):
        res = self.ask()
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("answer", body)
        self.assertNotIn("data", body)  # no envelope — the chat UI's shape
        suggested = body["suggestedArtifacts"]
        self.assertTrue(suggested)
        self.assertEqual(suggested[0]["id"], "painting-one")
        self.assertEqual(suggested[0]["title"], "Painting One")
        self.assertEqual(self.fake.calls, 1)

    def test_not_configured_503(self):
        service = AssistantService(llm_client=None)
        app = create_app(FIXTURE, data_dir=Path(tempfile.mkdtemp()),
                         assistant_service=service)
        client = TestClient(app)
        res = client.post("/assistant/ask", json={"question": MATCHING_QUESTION})
        self.assertEqual(res.status_code, 503)
        app.state.serve.store.close()


class TestCannedAnswers(AssistantTestBase):
    """Greetings, overviews and off-topic never reach the provider."""

    def test_greeting_canned(self):
        res = self.ask("olá")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["answer"], GREETING_ANSWER)
        self.assertEqual(self.fake.calls, 0)

    def test_greeting_with_small_tail_canned(self):
        res = self.ask("oi tudo bem")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["answer"], GREETING_ANSWER)
        self.assertEqual(self.fake.calls, 0)

    def test_overview_canned(self):
        res = self.ask("o que tem no acervo do museu?")
        self.assertEqual(res.status_code, 200)
        self.assertIn("peças", res.json()["answer"])
        self.assertEqual(self.fake.calls, 0)

    def test_offtopic_refused_without_llm(self):
        res = self.ask(OFFTOPIC_QUESTION)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["answer"], OFFTOPIC_ANSWER)
        self.assertEqual(res.json()["suggestedArtifacts"], [])
        self.assertEqual(self.fake.calls, 0)

    def test_stopwords_are_not_retrieval_evidence(self):
        # Cards carry "de"/"do"/"em" in free-text fields; a question made of
        # stopwords alone must never "match" and reach the provider.
        res = self.ask("o que é de do da em no na um uma")
        self.assertEqual(res.json()["answer"], OFFTOPIC_ANSWER)
        self.assertEqual(self.fake.calls, 0)


class TestRateLimit(AssistantTestBase):
    service_kwargs = {"rpm": 3}

    def test_fourth_ask_in_a_minute_is_429(self):
        codes = [self.ask().status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])
        res = self.ask()
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.json()["detail"], RATE_LIMIT_DETAIL)
        self.assertEqual(res.headers.get("retry-after"), "60")

    def test_canned_layers_do_not_spare_the_rate_limit(self):
        # Even cost-free answers are rate-limited: the point is to stop a bot.
        codes = [self.ask(OFFTOPIC_QUESTION).status_code for _ in range(4)]
        self.assertEqual(codes[-1], 429)


class TestDailyQuota(AssistantTestBase):
    service_kwargs = {"daily_tokens": 10}  # the fake spends 10 tokens per ask

    def test_quota_exhaustion_is_429_and_logged(self):
        first = self.ask()
        self.assertEqual(first.status_code, 200)
        second = self.ask()
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["detail"], QUOTA_DETAIL)
        self.assertEqual(self.fake.calls, 1)  # the 429 never reached the LLM


class TestProviderBreaker(AssistantTestBase):
    service_kwargs = {"rpm": 100, "llm_client": FailingLLM()}

    def test_five_failures_open_the_circuit(self):
        for _ in range(5):
            res = self.ask()
            self.assertEqual(res.status_code, 503)
            self.assertEqual(res.json()["detail"], PROVIDER_DETAIL)
        self.assertEqual(self.fake.calls, 5)
        # Circuit open: the 6th ask is refused WITHOUT calling the provider.
        res = self.ask()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(self.fake.calls, 5)

    def test_half_open_after_cooldown(self):
        clock = [0.0]
        breaker = ProviderBreaker(threshold=2, cooldown_s=300,
                                  clock=lambda: clock[0])
        service = AssistantService(llm_client=FailingLLM(), rpm=100,
                                   breaker=breaker)
        app = create_app(FIXTURE, data_dir=Path(tempfile.mkdtemp()),
                         assistant_service=service)
        client = TestClient(app)
        client.post("/assistant/ask", json={"question": MATCHING_QUESTION})
        client.post("/assistant/ask", json={"question": MATCHING_QUESTION})
        self.assertTrue(breaker.is_open())
        clock[0] = 301.0  # cooldown elapsed: one probe is allowed through
        self.assertFalse(breaker.is_open())
        app.state.serve.store.close()


class TestTurnstile(AssistantTestBase):
    service_kwargs = {
        "turnstile_secret": "test-secret",
        "turnstile_verifier": staticmethod(lambda secret, token, ip: token == "good"),
    }

    def test_bad_token_403_no_llm(self):
        res = self.ask(turnstile_token="bad")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["detail"], TURNSTILE_DETAIL)
        self.assertEqual(self.fake.calls, 0)

    def test_missing_token_403(self):
        res = self.ask()
        self.assertEqual(res.status_code, 403)

    def test_good_token_passes(self):
        res = self.ask(turnstile_token="good")
        self.assertEqual(res.status_code, 200)
        # also accepted inside the context object (the frontend's shape)
        res = self.client.post("/assistant/ask", json={
            "question": MATCHING_QUESTION,
            "context": {"turnstile_token": "good"},
        })
        self.assertEqual(res.status_code, 200)


class TestTelemetry(AssistantTestBase):
    def test_every_outcome_is_logged_with_cost_estimate(self):
        events = []

        class Recorder:
            def log(self, event, **fields):
                events.append((event, fields))

        self.app.state.serve.logger = Recorder()
        self.ask()                    # ok
        self.ask(OFFTOPIC_QUESTION)   # refusal_offtopic
        logged = [f for e, f in events if e == "assistant_ask"]
        self.assertEqual(len(logged), 2)
        self.assertEqual(logged[0]["outcome"], "ok")
        self.assertIn("cost_usd_estimate", logged[0])
        self.assertIn("ip_hash", logged[0])
        self.assertNotIn("127.0.0.1", str(logged[0]))  # IP never logged raw
        self.assertEqual(logged[1]["outcome"], "refusal_offtopic")
        self.assertEqual(logged[1]["cost_usd_estimate"], 0.0)


class TestCostEstimate(unittest.TestCase):
    def test_off_peak_table(self):
        # 1M fresh input + 1M cached + 1M output = 0.15 + 0.003 + 0.60
        cost = estimate_cost_usd(2_000_000, 1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 0.753, places=6)

    def test_zero_usage_is_zero_cost(self):
        self.assertEqual(estimate_cost_usd(0, 0, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
