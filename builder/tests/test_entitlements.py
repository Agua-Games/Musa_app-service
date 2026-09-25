"""Signed-entitlements tests (M1.2): the falsifiable gate of ADR 0010.

A client editing tier/modules after the platform signed the config must fail
the build — the same way a contract violation does.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from musa_build import __version__
from musa_build.build import BuildFailure, build_site
from musa_build.entitlements import (
    canonical_payload,
    generate_keypair,
    sign_entitlements,
    verify_entitlements,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
FRONTEND = FIXTURES / "frontend"


def make_config(**overrides):
    entitlements = {
        "museum_id": "fixture-museum",
        "tier": "silver",
        "modules": ["assistant", "store"],
        "issued": "2026-09-25",
        "expires": "2999-01-01",
    }
    entitlements.update(overrides)
    return {"museum": {"id": "fixture-museum"}, "entitlements": entitlements}


class VerifyEntitlementsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_b64, cls.public_b64 = generate_keypair()

    def sign(self, config):
        config["entitlements"]["signature"] = sign_entitlements(
            config["entitlements"], self.private_b64
        )
        return config

    def test_a_signed_config_verifies(self):
        config = self.sign(make_config())
        self.assertEqual(verify_entitlements(config, self.public_b64), [])

    def test_a_tampered_tier_fails(self):
        config = self.sign(make_config())
        config["entitlements"]["tier"] = "gold"  # self-promotion attempt
        errors = verify_entitlements(config, self.public_b64)
        self.assertTrue(any("does not verify" in e for e in errors), errors)

    def test_added_modules_fail(self):
        config = self.sign(make_config())
        config["entitlements"]["modules"].append("streaming")
        self.assertTrue(verify_entitlements(config, self.public_b64))

    def test_a_missing_signature_fails(self):
        errors = verify_entitlements(make_config(), self.public_b64)
        self.assertTrue(any("signature is missing" in e for e in errors), errors)

    def test_another_museums_entitlements_fail(self):
        config = self.sign(make_config(museum_id="other-museum"))
        errors = verify_entitlements(config, self.public_b64)
        self.assertTrue(any("not transferable" in e for e in errors), errors)

    def test_expired_entitlements_fail(self):
        config = self.sign(make_config(expires="2020-01-01"))
        errors = verify_entitlements(config, self.public_b64)
        self.assertTrue(any("expired" in e for e in errors), errors)

    def test_the_payload_is_canonical(self):
        # key order and module order do not change the signed bytes
        a = canonical_payload({"tier": "silver", "museum_id": "m", "modules": ["b", "a"],
                               "issued": "2026-01-01", "expires": "2027-01-01"})
        b = canonical_payload({"modules": ["a", "b"], "museum_id": "m", "tier": "silver",
                               "expires": "2027-01-01", "issued": "2026-01-01"})
        self.assertEqual(a, b)
        self.assertEqual(a, b'{"expires":"2027-01-01","issued":"2026-01-01",'
                          b'"modules":["a","b"],"museum_id":"m","tier":"silver"}')


class BuildGateTest(unittest.TestCase):
    """End-to-end: a release-pinned client must carry a valid signature."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.private_b64, self.public_b64 = generate_keypair()
        self.key_file = self.tmp / "test-public.key"
        self.key_file.write_text(self.public_b64 + "\n", encoding="utf-8")
        self.repo = self.tmp / "client"
        shutil.copytree(CLIENT_OK, self.repo)
        # promote the fixture to a release pin so the signature gate applies
        self.config_path = self.repo / "museum.config.json"
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["musa"] = __version__
        config["entitlements"].update({
            "museum_id": "fixture-museum",
            "issued": "2026-09-25",
            "expires": "2999-01-01",
        })
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def sign_config(self):
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["entitlements"]["signature"] = sign_entitlements(
            config["entitlements"], self.private_b64
        )
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

    def build(self):
        return build_site(self.repo, FRONTEND, self.tmp / "site",
                          entitlements_key=self.key_file)

    def test_signed_release_config_builds(self):
        self.sign_config()
        report = self.build()
        self.assertTrue(report.ok, report.errors)

    def test_unsigned_release_config_fails_the_build(self):
        with self.assertRaises(BuildFailure) as ctx:
            self.build()
        self.assertTrue(any("signature is missing" in e for e in ctx.exception.report.errors))

    def test_the_falsifiable_proof_tampered_tier_fails_the_build(self):
        self.sign_config()
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["entitlements"]["tier"] = "gold"  # edited after signing
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(BuildFailure) as ctx:
            self.build()
        self.assertTrue(any("does not verify" in e for e in ctx.exception.report.errors))

    def test_dev_pin_still_accepts_unsigned_with_a_warning(self):
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["musa"] = "0.0.0-unreleased"
        config["entitlements"].pop("signature", None)
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        report = self.build()
        self.assertTrue(report.ok, report.errors)
        self.assertTrue(any("unsigned entitlements" in w for w in report.warnings))


if __name__ == "__main__":
    unittest.main()
