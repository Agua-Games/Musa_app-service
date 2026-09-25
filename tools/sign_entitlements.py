"""MUSA platform tool — sign a client repository's entitlements (ADR 0010).

The private Ed25519 key lives OUTSIDE any repository (a platform secret, like
the GHCR pull token). Only this tool may write ``entitlements.signature``;
every release build verifies it with the public key embedded in the image.

Usage:

    # one-time: create the platform keypair (private key OUT of the repo!)
    python tools/sign_entitlements.py generate-key --out /path/to/musa-entitlements-ed25519.key

    # onboarding or tier change: sign a client repository's museum.config.json
    python tools/sign_entitlements.py sign --repo ../DemoMuseum \
        --key /path/to/musa-entitlements-ed25519.key [--expires 2027-09-25]

``sign`` re-reads tier/modules from the config (edit them there first — the
file is the request, the signature is the platform's approval), stamps
``issued``/``museum_id`` and writes the signature back, in place.
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "builder"))

from musa_build.entitlements import (  # noqa: E402
    canonical_payload,
    generate_keypair,
    sign_payload,
)


def _cmd_generate_key(args) -> int:
    private_b64, public_b64 = generate_keypair()
    out = Path(args.out)
    if out.exists():
        print(f"refusing to overwrite existing key: {out}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(private_b64 + "\n", encoding="utf-8")
    print(f"private key written to {out}")
    print("KEEP IT OUTSIDE ANY REPOSITORY — whoever has it can issue entitlements.")
    print()
    print("public key (embed as builder/musa_build/data/entitlements-public.key):")
    print(public_b64)
    return 0


def _cmd_sign(args) -> int:
    repo = Path(args.repo)
    config_path = repo / "museum.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    entitlements = config.get("entitlements") or {}

    private_b64 = Path(args.key).read_text(encoding="utf-8").strip()

    entitlements["museum_id"] = (config.get("museum") or {}).get("id")
    entitlements["issued"] = date.today().isoformat()
    if args.expires:
        entitlements["expires"] = args.expires
    elif not entitlements.get("expires"):
        entitlements["expires"] = (date.today() + timedelta(days=365)).isoformat()

    # The signature covers exactly the canonical payload fields; "source" and
    # any other annotations stay outside the signed bytes.
    payload = canonical_payload(entitlements)
    entitlements["signature"] = sign_payload(payload, private_b64)

    config["entitlements"] = entitlements
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"signed: {payload.decode('utf-8')}")
    print(f"written to {config_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sign-entitlements",
        description="Sign a client repository's entitlements block (ADR 0010).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate-key", help="create the platform Ed25519 keypair (one-time)")
    gen.add_argument("--out", required=True, help="private key path — OUTSIDE any repository")
    gen.set_defaults(func=_cmd_generate_key)

    sign = commands.add_parser("sign", help="sign museum.config.json entitlements in place")
    sign.add_argument("--repo", required=True, help="client repository root")
    sign.add_argument("--key", required=True, help="platform private key path")
    sign.add_argument("--expires", help="entitlement expiry (YYYY-MM-DD); default: +1 year")
    sign.set_defaults(func=_cmd_sign)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
