"""Build-time gating (M0.6).

The gate runs in the build, never in the client (docs/HANDOFF.md §0.2): a
``draft`` item — or one whose tier is above the museum's entitlement — must not
reach the published payload at all, not even filtered out of view. Every
decision is recorded with a reason so the build report can answer "why is this
piece not on the site?" in one line.
"""

from dataclasses import dataclass, field

TIER_ORDER = {"bronze": 1, "silver": 2, "gold": 3}

PUBLISHED = "published"


@dataclass
class Decision:
    included: bool
    reasons: list[str] = field(default_factory=list)


def _tier_rank(tier: str) -> int | None:
    return TIER_ORDER.get((tier or "").lower())


def check_tier(entitled_tier: str) -> None:
    """Fail fast on a config file whose entitlement tier is unknown."""
    if _tier_rank(entitled_tier) is None:
        raise ValueError(
            f"unknown entitlement tier {entitled_tier!r} — expected one of {sorted(TIER_ORDER)}"
        )


def gate_status(status: str | None) -> Decision:
    """Fail closed: anything that is not explicitly published stays out."""
    if status is None:
        return Decision(False, ["website_status missing (treated as draft)"])
    if status != PUBLISHED:
        return Decision(False, [f"website_status is {status!r}"])
    return Decision(True)


def gate_tier(tier: str | None, entitled_tier: str) -> Decision:
    """A record with no tier is bronze (least privilege). Unknown tier: fail closed."""
    if tier is None:
        return Decision(True)  # no requirement => available from bronze up
    rank = _tier_rank(tier)
    if rank is None:
        return Decision(False, [f"unknown tier {tier!r}"])
    if rank > TIER_ORDER[entitled_tier]:
        return Decision(False, [f"tier {tier!r} is above the entitled tier {entitled_tier!r}"])
    return Decision(True)


def gate_record(record: dict, entitled_tier: str) -> Decision:
    """Combine both gates for one card or collection record."""
    status = gate_status(record.get("website_status"))
    tier = gate_tier(record.get("tier"), entitled_tier)
    reasons = status.reasons + tier.reasons
    return Decision(status.included and tier.included, reasons)
