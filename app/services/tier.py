"""The tier system — TweetScout score → tier name + karma multiplier.

The canonical thresholds/multipliers (spec §5.3). A higher score means
higher-quality engagement, so a higher multiplier on every karma earned.

    Tier    | Min score | Multiplier
    Anon    |        0  |   1.00
    Normie  |      100  |   1.10
    Degen   |      200  |   1.15
    Based   |      400  |   1.20
    Legend  |      600  |   1.25
    OG      |      800  |   1.30
    GOAT    |     1000  |   1.35

Karma uses ROUND_HALF_EVEN (banker's rounding) to 4 dp — the karma deducted
from a post's escrow equals the karma credited to the engager, so there is no
inflation. The tier names match what the live frontend already renders.

These mirror the `TIER_*_THRESHOLD` / `TIER_*_MULTIPLIER` dynamic settings;
they live here as the source of truth and can be made runtime-overridable later.
"""
from decimal import Decimal, ROUND_HALF_EVEN

# 4-dp precision for all internal karma math
KARMA_QUANTIZE = Decimal("0.0001")

# (name, min_score, multiplier) — ordered HIGHEST threshold first so the
# first match wins on a simple top-down scan.
TIERS: list[tuple[str, int, Decimal]] = [
    ("GOAT", 1000, Decimal("1.35")),
    ("OG", 800, Decimal("1.30")),
    ("Legend", 600, Decimal("1.25")),
    ("Based", 400, Decimal("1.20")),
    ("Degen", 200, Decimal("1.15")),
    ("Normie", 100, Decimal("1.10")),
    ("Anon", 0, Decimal("1.00")),
]


def _band(score: float) -> tuple[str, int, Decimal]:
    s = int(score or 0)
    for band in TIERS:
        if s >= band[1]:
            return band
    return TIERS[-1]  # Anon — unreachable since the last threshold is 0


def tier_for(score: float) -> str:
    """The tier name for a TweetScout score (e.g. 'Based')."""
    return _band(score)[0]


def multiplier_for(score: float) -> Decimal:
    """The karma multiplier for a TweetScout score (e.g. Decimal('1.20'))."""
    return _band(score)[2]


def karma_for(base: Decimal, score: float) -> tuple[Decimal, Decimal]:
    """Return (karma, multiplier) for a base amount at a given score.

    karma = base × multiplier, banker's-rounded to 4 dp. This exact amount is
    both deducted from escrow and credited to the engager — no inflation.
    """
    if not isinstance(base, Decimal):
        base = Decimal(str(base))
    multiplier = multiplier_for(score)
    karma = (base * multiplier).quantize(KARMA_QUANTIZE, rounding=ROUND_HALF_EVEN)
    return karma, multiplier
