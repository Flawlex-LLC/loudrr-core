"""
Tweet score multiplier service.

Calculates karma multiplier based on user's TweetScout score.
Higher scores = better quality engagement = higher multiplier.

Tier thresholds and multipliers are configurable via SiteSettings.

DECIMAL KARMA SYSTEM:
- 4 decimal places internally (database)
- 2 decimal places for display (frontend)
- ROUND_HALF_EVEN (Banker's rounding) for fairness
- No inflation: escrow deducted = karma earned

Default Multipliers (1.0x to 1.2x range):
    Anon (0-99):      1.00x
    Normie (100-199): 1.03x
    Degen (200-399):  1.06x
    Based (400-599):  1.10x
    Legend (600-799): 1.14x
    OG (800-999):     1.17x
    GOAT (1000+):     1.20x
"""
from decimal import Decimal, ROUND_HALF_EVEN

from core.services.settings import get_setting


# Quantize to 4 decimal places for internal precision
KARMA_QUANTIZE = Decimal('0.0001')


def get_tweet_score_multiplier(score: float) -> Decimal:
    """
    Get karma multiplier based on TweetScout score.

    Tiers (configurable via SiteSettings):
        0-99:    1.00x (Anon)
        100-199: 1.03x (Normie)
        200-399: 1.06x (Degen)
        400-599: 1.10x (Based)
        600-799: 1.14x (Legend)
        800-999: 1.17x (OG)
        1000+:   1.20x (GOAT)

    Returns:
        Decimal multiplier (1.0 to 1.2)
    """
    score = int(score)

    # Get thresholds from settings
    goat_threshold = get_setting('TIER_GOAT_THRESHOLD')
    og_threshold = get_setting('TIER_OG_THRESHOLD')
    legend_threshold = get_setting('TIER_LEGEND_THRESHOLD')
    based_threshold = get_setting('TIER_BASED_THRESHOLD')
    degen_threshold = get_setting('TIER_DEGEN_THRESHOLD')
    normie_threshold = get_setting('TIER_NORMIE_THRESHOLD')

    # Get multipliers from settings
    if score >= goat_threshold:
        return Decimal(str(get_setting('TIER_GOAT_MULTIPLIER')))
    elif score >= og_threshold:
        return Decimal(str(get_setting('TIER_OG_MULTIPLIER')))
    elif score >= legend_threshold:
        return Decimal(str(get_setting('TIER_LEGEND_MULTIPLIER')))
    elif score >= based_threshold:
        return Decimal(str(get_setting('TIER_BASED_MULTIPLIER')))
    elif score >= degen_threshold:
        return Decimal(str(get_setting('TIER_DEGEN_MULTIPLIER')))
    elif score >= normie_threshold:
        return Decimal(str(get_setting('TIER_NORMIE_MULTIPLIER')))
    else:
        return Decimal(str(get_setting('TIER_ANON_MULTIPLIER')))


def get_tweet_score_tier(score: float) -> str:
    """
    Get web3-style tier name for display.
    """
    score = int(score)

    # Get thresholds from settings
    goat_threshold = get_setting('TIER_GOAT_THRESHOLD')
    og_threshold = get_setting('TIER_OG_THRESHOLD')
    legend_threshold = get_setting('TIER_LEGEND_THRESHOLD')
    based_threshold = get_setting('TIER_BASED_THRESHOLD')
    degen_threshold = get_setting('TIER_DEGEN_THRESHOLD')
    normie_threshold = get_setting('TIER_NORMIE_THRESHOLD')

    if score >= goat_threshold:
        return "GOAT"
    elif score >= og_threshold:
        return "OG"
    elif score >= legend_threshold:
        return "Legend"
    elif score >= based_threshold:
        return "Based"
    elif score >= degen_threshold:
        return "Degen"
    elif score >= normie_threshold:
        return "Normie"
    else:
        return "Anon"


def calculate_engagement_karma(base_amount: Decimal, tweetscout_score: float) -> tuple[Decimal, Decimal]:
    """
    Calculate karma earned by engager and deducted from poster.

    Uses ROUND_HALF_EVEN (Banker's rounding) for fairness - this prevents
    systematic bias that can occur with ROUND_HALF_UP.

    IMPORTANT: The karma returned is the EXACT amount to:
    - Deduct from post escrow
    - Credit to engager
    This ensures no inflation/deflation in the system.

    Args:
        base_amount: Base karma per engagement (Decimal, usually 1.0000)
        tweetscout_score: Engager's TweetScout score

    Returns:
        Tuple of (karma_amount, multiplier_used)
        - karma_amount: Decimal with 4 decimal places (e.g., 1.0300)
        - multiplier_used: Decimal multiplier (e.g., 1.03)
    """
    # Ensure base_amount is Decimal
    if not isinstance(base_amount, Decimal):
        base_amount = Decimal(str(base_amount))

    multiplier = get_tweet_score_multiplier(tweetscout_score)

    # Calculate karma with 4 decimal places using Banker's rounding
    karma = (base_amount * multiplier).quantize(KARMA_QUANTIZE, rounding=ROUND_HALF_EVEN)

    return karma, multiplier
