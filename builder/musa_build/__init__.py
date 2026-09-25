"""MUSA app-service builder.

Turns a client repository (``museum.config.json`` + ``content/``) into the
museum's static site. The build gate travels with this artifact: a card that
violates the collection contract fails the build, and nothing ``draft`` — and
nothing above the entitled tier — reaches the published payload.

See docs/HANDOFF.md (M0) and docs/adr/0003-onboarding-de-clientes.md.
"""

__version__ = "0.2.0"

# Version of the collection contract this builder implements. Must equal the
# "x-contract-version" of the bundled schemas/card.schema.json (see
# schemas/COMPATIBILITY.md in the platform repository).
CONTRACT_VERSION = "1.0.0"
