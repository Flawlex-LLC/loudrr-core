"""
Django-rules predicates for core business logic.

This module centralizes ALL permission checks that were previously scattered
across views, services, and models. Use these predicates to check if
an action is allowed before performing it.

Total rules: 45 (centralized from across the codebase)

Usage:
    import rules

    # Check permission
    if rules.test_rule('core.can_engage', user):
        # perform action

    # Or use predicates directly
    from core.rules import is_not_banned, has_x_account
    if is_not_banned(user) and has_x_account(user):
        ...
"""
import rules
from decimal import Decimal
from django.utils import timezone


# ============================================================================
# USER STATE PREDICATES (5 rules)
# ============================================================================

@rules.predicate
def is_not_banned(user):
    """User must not be banned to perform most actions."""
    if not user:
        return False
    return not getattr(user, 'is_banned', False)


@rules.predicate
def is_active(user):
    """User must be active."""
    if not user:
        return False
    return getattr(user, 'is_active', True)


@rules.predicate
def is_whitelisted(user):
    """User must be whitelisted to access the app."""
    if not user:
        return False
    return getattr(user, 'is_whitelisted', False)


@rules.predicate
def has_loud_access(user):
    """User has LOUD feature enabled."""
    if not user:
        return False
    return getattr(user, 'loud_access', False)


@rules.predicate
def is_staff(user):
    """User is staff member."""
    if not user:
        return False
    return getattr(user, 'is_staff', False)


@rules.predicate
def is_superuser(user):
    """User is superuser."""
    if not user:
        return False
    return getattr(user, 'is_superuser', False)


# ============================================================================
# ACCOUNT REQUIREMENT PREDICATES (2 rules)
# ============================================================================

@rules.predicate
def has_x_account(user):
    """User has linked X/Twitter account."""
    if not user:
        return False
    return bool(getattr(user, 'x_username', None))


@rules.predicate
def has_telegram_linked(user):
    """User has Telegram linked."""
    if not user:
        return False
    return bool(getattr(user, 'telegram_id', None))


# ============================================================================
# REFERRAL PREDICATES (4 rules)
# ============================================================================

@rules.predicate
def has_referral_code(user):
    """User has a valid referral code."""
    if not user:
        return False
    return bool(getattr(user, 'referral_code', None))


@rules.predicate
def can_be_referrer(user):
    """User can refer others (whitelisted, not banned, has code)."""
    if not user:
        return False
    return (
        getattr(user, 'is_whitelisted', False) and
        not getattr(user, 'is_banned', False) and
        bool(getattr(user, 'referral_code', None))
    )


@rules.predicate
def was_referred(user):
    """User was referred by someone."""
    if not user:
        return False
    return getattr(user, 'referred_by_id', None) is not None


@rules.predicate
def has_referrals(user):
    """User has referred at least one person."""
    if not user:
        return False
    return getattr(user, 'total_referrals', 0) > 0


# ============================================================================
# CREDIT PREDICATES (6 rules)
# ============================================================================

@rules.predicate
def has_positive_credits(user):
    """User has credits > 0."""
    if not user:
        return False
    return getattr(user, 'credits', Decimal('0')) > Decimal('0')


@rules.predicate
def has_sufficient_credits_for_post(user):
    """User has enough credits to create a post (minimum POST_COST)."""
    if not user:
        return False
    from core.services.settings import get_setting
    post_cost_min = get_setting('POST_COST_MIN', 5)
    return getattr(user, 'credits', Decimal('0')) >= Decimal(str(post_cost_min))


@rules.predicate
def can_earn_more_today(user):
    """User hasn't hit daily earn cap."""
    if not user:
        return False
    from core.services.settings import get_setting
    daily_cap = Decimal(str(get_setting('DAILY_EARN_CAP', 100)))
    daily_earned = getattr(user, 'daily_credits_earned', Decimal('0'))
    return daily_earned < daily_cap


@rules.predicate
def daily_earned_reset_needed(user):
    """Check if user's daily earned needs to be reset (new day)."""
    if not user:
        return False
    reset_at = getattr(user, 'daily_earned_reset_at', None)
    if not reset_at:
        return True
    return reset_at.date() < timezone.now().date()


# ============================================================================
# HONESTY & TRUST PREDICATES (3 rules)
# ============================================================================

@rules.predicate
def has_good_honesty_score(user):
    """User has honesty score above minimum threshold (not suspicious)."""
    if not user:
        return False
    return getattr(user, 'honesty_score', 50) >= 10


@rules.predicate
def has_excellent_honesty_score(user):
    """User has excellent honesty score (trusted user)."""
    if not user:
        return False
    return getattr(user, 'honesty_score', 50) >= 40


@rules.predicate
def has_perfect_honesty_score(user):
    """User has never failed verification (perfect 50)."""
    if not user:
        return False
    return getattr(user, 'honesty_score', 50) == 50


# ============================================================================
# TWEETSCOUT TIER PREDICATES (6 rules)
# ============================================================================

@rules.predicate
def is_tier_anon(user):
    """User is ANON tier (no/low TweetScout score)."""
    if not user:
        return False
    score = float(getattr(user, 'tweetscout_score', 0) or 0)
    from core.services.settings import get_setting
    return score < get_setting('TIER_NORMIE_THRESHOLD', 20)


@rules.predicate
def is_tier_normie_or_above(user):
    """User is NORMIE tier or above."""
    if not user:
        return False
    score = float(getattr(user, 'tweetscout_score', 0) or 0)
    from core.services.settings import get_setting
    return score >= get_setting('TIER_NORMIE_THRESHOLD', 20)


@rules.predicate
def is_tier_degen_or_above(user):
    """User is DEGEN tier or above."""
    if not user:
        return False
    score = float(getattr(user, 'tweetscout_score', 0) or 0)
    from core.services.settings import get_setting
    return score >= get_setting('TIER_DEGEN_THRESHOLD', 100)


@rules.predicate
def is_tier_based_or_above(user):
    """User is BASED tier or above."""
    if not user:
        return False
    score = float(getattr(user, 'tweetscout_score', 0) or 0)
    from core.services.settings import get_setting
    return score >= get_setting('TIER_BASED_THRESHOLD', 300)


@rules.predicate
def is_tier_legend_or_above(user):
    """User is LEGEND tier or above."""
    if not user:
        return False
    score = float(getattr(user, 'tweetscout_score', 0) or 0)
    from core.services.settings import get_setting
    return score >= get_setting('TIER_LEGEND_THRESHOLD', 500)


@rules.predicate
def is_tier_og_or_goat(user):
    """User is OG or GOAT tier (highest tiers)."""
    if not user:
        return False
    score = float(getattr(user, 'tweetscout_score', 0) or 0)
    from core.services.settings import get_setting
    return score >= get_setting('TIER_OG_THRESHOLD', 1000)


# ============================================================================
# ONBOARDING PREDICATES (3 rules)
# ============================================================================

@rules.predicate
def has_completed_onboarding(user):
    """User has completed onboarding (has TweetScout score)."""
    if not user:
        return False
    score = getattr(user, 'tweetscout_score', None)
    return score is not None and float(score or 0) > 0


@rules.predicate
def needs_onboarding(user):
    """User needs to complete onboarding."""
    if not user:
        return False
    return not has_completed_onboarding(user)


@rules.predicate
def is_new_user(user):
    """User was created recently (within 24 hours)."""
    if not user:
        return False
    from datetime import timedelta
    created_at = getattr(user, 'created_at', None)
    if not created_at:
        return False
    return timezone.now() - created_at < timedelta(hours=24)


# ============================================================================
# STREAK PREDICATES (4 rules)
# ============================================================================

@rules.predicate
def has_active_streak(user):
    """User has an active streak (engaged yesterday or today)."""
    if not user:
        return False
    from datetime import timedelta
    last_date = getattr(user, 'last_engagement_date', None)
    if not last_date:
        return False
    today = timezone.now().date()
    return last_date >= today - timedelta(days=1)


@rules.predicate
def has_7_day_streak(user):
    """User has 7+ day streak."""
    if not user:
        return False
    return getattr(user, 'current_streak', 0) >= 7


@rules.predicate
def has_14_day_streak(user):
    """User has 14+ day streak."""
    if not user:
        return False
    return getattr(user, 'current_streak', 0) >= 14


@rules.predicate
def has_30_day_streak(user):
    """User has 30+ day streak."""
    if not user:
        return False
    return getattr(user, 'current_streak', 0) >= 30


# ============================================================================
# PERMISSION RULES (composable predicates)
# ============================================================================

# Basic app access
rules.add_perm('core.can_access_app', is_not_banned & is_active & is_whitelisted)

# Feature access
rules.add_perm('core.can_access_loud', is_not_banned & has_loud_access)
rules.add_perm('core.can_earn_credits', is_not_banned & is_active & has_x_account & can_earn_more_today)
rules.add_perm('core.can_spend_credits', is_not_banned & is_active & has_positive_credits)

# Session & Engagement
rules.add_perm('core.can_start_session', is_not_banned & has_x_account)

# Waitlist management (admin only)
rules.add_perm('core.can_approve_waitlist', is_staff)
rules.add_perm('core.can_reject_waitlist', is_staff)

# User management (admin only)
rules.add_perm('core.can_ban_user', is_staff)
rules.add_perm('core.can_grant_credits', is_staff)
rules.add_perm('core.can_revoke_credits', is_superuser)

# Post creation
rules.add_perm('core.can_create_post', is_not_banned & has_x_account & has_sufficient_credits_for_post)

# Onboarding
rules.add_perm('core.can_complete_onboarding', is_not_banned & has_x_account & needs_onboarding)

# Referral
rules.add_perm('core.can_share_referral', is_whitelisted & has_referral_code)
rules.add_perm('core.can_be_referrer', can_be_referrer)


# ============================================================================
# HELPER FUNCTIONS FOR COMPLEX CHECKS
# ============================================================================

def check_user_can_spend(user, amount: Decimal) -> tuple[bool, str]:
    """
    Check if user can spend a specific amount.
    Returns (can_spend, error_message).
    """
    if not user:
        return False, "User not found"
    if getattr(user, 'is_banned', False):
        return False, "Account is suspended"
    credits = getattr(user, 'credits', Decimal('0'))
    if credits < amount:
        return False, f"Insufficient credits. Have {credits:.2f}, need {amount:.2f}"
    return True, ""


def check_user_can_earn(user, amount: Decimal) -> tuple[bool, str, Decimal]:
    """
    Check if user can earn a specific amount.
    Returns (can_earn, error_message, actual_amount).
    Actual amount may be less than requested due to daily cap.
    """
    if not user:
        return False, "User not found", Decimal('0')
    if getattr(user, 'is_banned', False):
        return False, "Account is suspended", Decimal('0')
    if not getattr(user, 'x_username', None):
        return False, "X account required", Decimal('0')

    from core.services.settings import get_setting
    daily_cap = Decimal(str(get_setting('DAILY_EARN_CAP', 100)))
    daily_earned = getattr(user, 'daily_credits_earned', Decimal('0'))

    remaining = daily_cap - daily_earned
    if remaining <= 0:
        return False, "Daily earning cap reached", Decimal('0')

    actual_amount = min(amount, remaining)
    return True, "", actual_amount


def check_session_requirements(user, session_start_time, engagement_count: int) -> tuple[bool, str]:
    """
    Check if session meets requirements for claiming.
    Returns (meets_requirements, error_message).
    """
    from core.services.settings import get_setting

    # Check minimum engagements
    min_to_claim = get_setting('MIN_ENGAGEMENTS_TO_CLAIM', 10)
    if engagement_count < min_to_claim:
        return False, f"Need at least {min_to_claim} engagements to claim (have {engagement_count})"

    # Check minimum session duration
    if session_start_time:
        min_duration = get_setting('MIN_SESSION_DURATION_SECONDS', 150)
        elapsed = (timezone.now() - session_start_time).total_seconds()
        if elapsed < min_duration:
            remaining = int(min_duration - elapsed)
            return False, f"Session too short. Wait {remaining} more seconds."

    return True, ""
