"""M4.3 tests: per-IP rate limits on login (brute force) and the write API.

Reads stay unlimited; the assistant has its own stack (test_assistant.py).
Limits are injected via create_app kwargs so each test isolates one knob;
0 disables (the load harness measures throughput, not policy).
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from musa_build.serve import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
TOKEN = "test-token-123"


class RateLimitBase(unittest.TestCase):
    write_rpm: int | None = None
    login_rpm: int | None = None

    def setUp(self):
        # Per-test app: the limiter is in-memory state, so sharing one app
        # across methods would leak one test's budget into the next.
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.repo = root / "repo"
        shutil.copytree(CLIENT_OK, self.repo)
        self._old_token = os.environ.get("MUSA_ADMIN_TOKEN")
        os.environ["MUSA_ADMIN_TOKEN"] = TOKEN
        self.client = TestClient(create_app(
            self.repo, data_dir=root / "data",
            write_rpm=self.write_rpm, login_rpm=self.login_rpm))
        self.auth = {"Authorization": f"Bearer {TOKEN}"}

    def tearDown(self):
        self.client.app.state.serve.store.close()
        if self._old_token is None:
            os.environ.pop("MUSA_ADMIN_TOKEN", None)
        else:
            os.environ["MUSA_ADMIN_TOKEN"] = self._old_token
        self._tmp.cleanup()


class TestLoginRateLimit(RateLimitBase):
    login_rpm = 3

    def test_brute_force_is_throttled(self):
        codes = [
            self.client.post("/auth/login",
                             json={"email": "mallory@evil.example",
                                   "password": f"guess-{i}"}).status_code
            for i in range(5)
        ]
        self.assertEqual(codes[:3], [401, 401, 401])
        self.assertEqual(codes[3:], [429, 429])

    def test_429_carries_retry_after(self):
        for i in range(4):
            res = self.client.post("/auth/login",
                                   json={"email": "a@b.c", "password": f"x{i}"})
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.headers.get("retry-after"), "60")


class TestWriteRateLimit(RateLimitBase):
    write_rpm = 2

    def _write(self, n: int) -> list[int]:
        return [
            self.client.post("/collections",
                             json={"id": f"flood-{i}", "title": "Flood"},
                             headers=self.auth).status_code
            for i in range(n)
        ]

    def test_writes_beyond_the_limit_are_429(self):
        codes = self._write(4)
        self.assertEqual(codes[:2], [201, 201])
        self.assertEqual(codes[2:], [429, 429])

    def test_the_limit_applies_before_auth(self):
        # An unauthenticated flood burns the same budget: the limiter is the
        # first line, not the token check.
        codes = [
            self.client.post("/collections",
                             json={"id": f"noauth-{i}", "title": "x"}).status_code
            for i in range(3)
        ]
        self.assertEqual(codes, [401, 401, 429])

    def test_reads_are_not_limited(self):
        self._write(3)  # exhaust the write budget
        for _ in range(10):
            self.assertEqual(self.client.get("/collections").status_code, 200)
            self.assertEqual(self.client.get("/items/painting-one").status_code, 200)


class TestDefaultsAllowNormalUse(RateLimitBase):
    """With no overrides (env defaults 60 writes / 5 logins per minute),
    the curator's normal day — including a handful of logins — just works."""

    def test_normal_admin_flow_passes(self):
        self.assertEqual(
            self.client.post("/auth/login",
                             json={"email": "c@f.e", "password": TOKEN}).status_code, 200)
        res = self.client.post("/collections",
                               json={"id": "normal-flow", "title": "Normal"},
                               headers=self.auth)
        self.assertEqual(res.status_code, 201)
        patch = self.client.post("/items",
                                 json={"asset_id": "painting-one",
                                       "descricao": "edição normal"},
                                 headers=self.auth)
        self.assertEqual(patch.status_code, 200)


if __name__ == "__main__":
    unittest.main()
