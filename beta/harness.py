"""M4.5 — ServeHarness: owns the `musa-build serve` subprocess lifecycle for
one DISPOSABLE client-repo copy.

Extracted from run_beta.run() (M3.1) so the edge suite can REBOOT the server
with a mutated environment or config (no admin token, corrupted overlay,
re-tiered museum.config.json) — something the personas/misuse suites never
needed. Behavior for the existing suites is unchanged: one boot, one client.

stderr goes to a file (not DEVNULL) so a failed boot is diagnosable — the
edge case "corrupted overlay" asserts on the boot error message.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from .client import ApiClient

PLATFORM_ROOT = Path(__file__).resolve().parent.parent
BUILDER_DIR = PLATFORM_ROOT / "builder"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServeHarness:
    def __init__(self, work_repo: Path, data_dir: Path, *, token: str,
                 log_dir: Path | None = None):
        self.work_repo = Path(work_repo)
        self.data_dir = Path(data_dir)
        self.token = token
        self.log_dir = Path(log_dir) if log_dir else self.data_dir
        self._server: subprocess.Popen | None = None
        self._stderr_path: Path | None = None
        self._stderr_fh = None
        self.client: ApiClient | None = None

    # -- lifecycle ---------------------------------------------------------
    def boot(self, *, env_overrides: dict | None = None, drop_env: tuple = (),
             expect_up: bool = True, timeout_s: float = 30.0) -> ApiClient | None:
        """Boot the serve subprocess. With expect_up=False the caller expects
        the boot to FAIL: returns None when the server never answers health
        (the edge suite then asserts on boot_stderr())."""
        env = dict(os.environ)
        env["MUSA_ADMIN_TOKEN"] = self.token
        # The beta never touches a real LLM provider: the fake client keeps
        # the assistant pipeline exercised with ~zero cost (M4.2), even if
        # DEEPSEEK_API_KEY happens to be set in the dev environment.
        env["MUSA_LLM_FAKE"] = "1"
        # The beta is not the rate-limit surface (M4.3 unit tests own it):
        # persona/misuse/edge storms must not trip 429s from 127.0.0.1.
        env.setdefault("MUSA_WRITE_RPM", "0")
        env.setdefault("MUSA_LOGIN_RPM", "0")
        env["PYTHONPATH"] = str(BUILDER_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        for name in drop_env:
            env.pop(name, None)
        env.update(env_overrides or {})

        port = _free_port()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._stderr_path = self.log_dir / f"serve-stderr-{port}.log"
        self._stderr_fh = self._stderr_path.open("w", encoding="utf-8", errors="replace")
        self._server = subprocess.Popen(
            [sys.executable, "-m", "musa_build", "serve",
             "--repo", str(self.work_repo), "--data-dir", str(self.data_dir),
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(BUILDER_DIR), env=env,
            stdout=self._stderr_fh, stderr=self._stderr_fh,
        )
        client = ApiClient(f"http://127.0.0.1:{port}")
        if self._wait_health(client, timeout_s):
            self.client = client
            return client
        # Boot failed (or is hopelessly slow). Do not leave a zombie behind.
        self.stop()
        if expect_up:
            raise RuntimeError(
                f"serve did not come up on port {port} — see {self._stderr_path}")
        return None

    def reboot(self, **kwargs) -> ApiClient | None:
        self.stop()
        return self.boot(**kwargs)

    def stop(self) -> None:
        if self._server is not None:
            self._server.terminate()
            try:
                self._server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._server.kill()
                self._server.wait(timeout=10)
            self._server = None
        if self._stderr_fh is not None:
            self._stderr_fh.close()
            self._stderr_fh = None
        self.client = None

    def boot_stderr(self) -> str:
        """What the last boot wrote to stderr (read after a failed boot)."""
        if not self._stderr_path or not self._stderr_path.is_file():
            return ""
        return self._stderr_path.read_text(encoding="utf-8", errors="replace")

    # -- internals -----------------------------------------------------------
    def _wait_health(self, client: ApiClient, timeout_s: float = 30.0) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            # A dead process never answers — fail fast instead of polling
            # the full timeout (the edge suite boots broken servers on purpose).
            if self._server is not None and self._server.poll() is not None:
                return False
            try:
                if client.health(timeout=1.5).ok:
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False
