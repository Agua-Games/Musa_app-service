"""Signed entitlements (ADR 0010, phase M1.2).

The platform signs each client's entitlements offline with an Ed25519 private
key that never enters any repository; every artifact image carries the public
key (``data/entitlements-public.key``) and the build FAILS when the signature
is missing, invalid or expired — so a client cannot self-promote tiers by
editing ``museum.config.json``. Development builds (``musa: "0.0.0-unreleased"``)
warn instead of failing.

The signed payload is the canonical JSON of the entitlement fields:

    {"expires": "...", "issued": "...", "modules": [...], "museum_id": "...", "tier": "..."}

Canonical form: UTF-8, keys sorted, no whitespace, ``modules`` sorted — the
same bytes are re-derived at verification time, so the signature covers exactly
these five fields (``source`` and ``signature`` itself stay outside).
"""

import base64
import json
from datetime import date
from pathlib import Path

PAYLOAD_FIELDS = ("museum_id", "tier", "modules", "issued", "expires")

PUBLIC_KEY_FILE = Path(__file__).parent / "data" / "entitlements-public.key"


def canonical_payload(entitlements: dict) -> bytes:
    """The exact bytes the signature covers, derived from a config block."""
    payload = {}
    for field in PAYLOAD_FIELDS:
        if field not in entitlements:
            raise ValueError(f"entitlements: {field!r} is required for signing")
        payload[field] = entitlements[field]
    payload["modules"] = sorted(payload["modules"])
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def generate_keypair() -> tuple[str, str]:
    """A new Ed25519 keypair as (private_b64, public_b64) raw 32-byte keys."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    private = Ed25519PrivateKey.generate()
    private_b64 = base64.b64encode(
        private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode("ascii")
    public_b64 = base64.b64encode(
        private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("ascii")
    return private_b64, public_b64


def sign_payload(payload: bytes, private_key_b64: str) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))
    return base64.b64encode(key.sign(payload)).decode("ascii")


def sign_entitlements(entitlements: dict, private_key_b64: str) -> str:
    return sign_payload(canonical_payload(entitlements), private_key_b64)


def load_public_key(path: Path | None = None) -> str:
    key_path = Path(path) if path else PUBLIC_KEY_FILE
    return key_path.read_text(encoding="utf-8").strip()


def verify_entitlements(config: dict, public_key_b64: str) -> list[str]:
    """Validate the signed entitlements of a client config; returns errors."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    errors: list[str] = []
    entitlements = config.get("entitlements") or {}

    signature = entitlements.get("signature")
    if not signature:
        return ["entitlements.signature is missing — the platform signs this block "
                "at onboarding (docs/entitlements.md); an unsigned config cannot build a release"]

    for field in PAYLOAD_FIELDS:
        if field not in entitlements:
            errors.append(f"entitlements.{field} is required by the signed-entitlements contract")
    if errors:
        return errors

    try:
        payload = canonical_payload(entitlements)
    except ValueError as exc:  # pragma: no cover - covered by the loop above
        return [str(exc)]

    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        key.verify(base64.b64decode(signature), payload)
    except InvalidSignature:
        errors.append(
            "entitlements.signature does not verify — the block was edited after the "
            "platform signed it (tier/modules cannot be changed client-side)"
        )
    except (ValueError, TypeError) as exc:
        errors.append(f"entitlements.signature is malformed: {exc}")

    museum_id = (config.get("museum") or {}).get("id")
    if museum_id and entitlements["museum_id"] != museum_id:
        errors.append(
            f"entitlements.museum_id is {entitlements['museum_id']!r} but museum.id is "
            f"{museum_id!r} — entitlements are issued per museum and are not transferable"
        )

    expires = entitlements.get("expires")
    if expires:
        try:
            if date.fromisoformat(expires) < date.today():
                errors.append(f"entitlements expired on {expires} — ask the platform to re-issue")
        except ValueError:
            errors.append(f"entitlements.expires {expires!r} is not an ISO date (YYYY-MM-DD)")

    return errors
