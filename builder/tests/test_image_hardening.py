"""M4.1 guard tests: the production hardening of the artifact image cannot be
silently reverted.

The Dockerfile is declarative — the only way to keep the hardening honest
without building the image on every push is to pin its invariants here. The
runtime proof (beta suite inside the image with a read-only root FS, as the
unprivileged user) runs in the release pipeline's smoke gate (release.yml).
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DOCKERFILE = ROOT / "Dockerfile"
RELEASE_YML = ROOT / ".github" / "workflows" / "release.yml"


class ImageHardeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        cls.release = RELEASE_YML.read_text(encoding="utf-8")

    def test_runtime_user_is_unprivileged(self):
        self.assertIn("useradd --system --gid musa --uid 1000 musa", self.dockerfile)
        self.assertIn("USER musa", self.dockerfile)
        self.assertNotIn("USER root", self.dockerfile)

    def test_no_bytecode_writes_and_unbuffered_logs(self):
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.dockerfile)
        self.assertIn("PYTHONUNBUFFERED=1", self.dockerfile)

    def test_healthcheck_targets_the_health_endpoint(self):
        self.assertIn("HEALTHCHECK", self.dockerfile)
        self.assertIn("/health", self.dockerfile)

    def test_release_pipeline_proves_hardening_before_push(self):
        # the smoke gate runs the beta suite inside the image with a
        # read-only root filesystem, before the push step
        smoke = self.release.index("--read-only")
        push = self.release.index("Push the verified image")
        self.assertLess(smoke, push)
        self.assertIn("uid=1000(musa)", self.release)
        self.assertIn("-m beta.run_beta", self.release)


if __name__ == "__main__":
    unittest.main()
