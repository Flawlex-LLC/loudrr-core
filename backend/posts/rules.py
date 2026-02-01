"""
Django-rules predicates for posts and engagement business logic.

These predicates centralize ALL permission checks for:
- Post creation and management
- Engagement eligibility and settlement
- Campaign entry and winner selection

The rules mirror checks in:
- core/services/posts.py
- core/services/engagements.py
- core/services/settlement.py
- core/services/campaigns.py
"""
import rules
from decimal import Decimal
from django.utils import timezone


# ============================================================================
# POST PREDICATES
# ============================================================================

@rules.predicate
def is_post_owner(user, post):
    """User owns the post."""
    if not user or not post:
        return False
    return post.user_id == user.id


@rules.predicate
def is_not_post_owner(user, post):
    """User does NOT own the post (required for engagement)."""
    if not user or not post:
        return False
    return post.user_id != user.id


@rules.predicate
def post_is_active(user, post):
    """Post is in ACTIVE status."""
    if not post:
        return False
    from posts.models import Post
    return post.status == Post.Status.ACTIVE


@rules.predicate
def post_has_escrow(user, post):
    """Post has escrow remaining to pay engagers."""
    if not post:
        return False
    return post.escrow > Decimal('0')


@rules.predicate
def post_has_enough_escrow_for_user(user, post):
    """Post has enough escrow to pay this user's tier multiplier."""
    if not user or not post:
        return False
    from core.services.settings import get_setting
    from core.services.tweet_score import get_tweet_score_multiplier

    base_credit = Decimal(str(get_setting('CREDIT_PER_ENGAGEMENT', 1)))
    multiplier = get_tweet_score_multiplier(user.tweetscout_score or 0)
    min_escrow = base_credit * multiplier
    return post.escrow >= min_escrow


@rules.predicate
def not_already_engaged(user, post):
    """User hasn't engaged this post yet."""
    if not user or not post:
        return False
    from posts.models import Engagement
    return not Engagement.objects.filter(user=user, post=post).exists()


@rules.predicate
def is_post_completed(user, post):
    """Post is completed (escrow depleted)."""
    if not post:
        return False
    from posts.models import Post
    return post.status == Post.Status.COMPLETED


@rules.predicate
def is_post_cancelled(user, post):
    """Post is cancelled."""
    if not post:
        return False
    from posts.models import Post
    return post.status == Post.Status.CANCELLED


# ============================================================================
# POST CREATION PREDICATES
# ============================================================================

@rules.predicate
def has_enough_credits_to_post(user):
    """User has enough credits to create a new post."""
    if not user:
        return False
    from core.services.settings import get_setting
    post_cost = Decimal(str(get_setting('POST_COST', 5)))
    return user.credits >= post_cost


@rules.predicate
def is_valid_x_link(user, x_link):
    """Validates X/Twitter link format."""
    if not x_link:
        return False
    import re
    # Matches x.com/user/status/ID or twitter.com/user/status/ID
    pattern = r'^https://(x\.com|twitter\.com)/[\w]+/status/\d+(\?.*)?$'
    return bool(re.match(pattern, x_link))


# ============================================================================
# ENGAGEMENT PREDICATES
# ============================================================================

@rules.predicate
def not_in_cooldown(user):
    """User is not in engagement cooldown period."""
    if not user:
        return False
    from django.core.cache import cache
    cooldown_key = f"engagement_cooldown:{user.id}"
    return not cache.get(cooldown_key)


@rules.predicate
def engagement_not_already_credited(user, engagement):
    """Engagement hasn't been credited yet (idempotency check)."""
    if not engagement:
        return False
    return not engagement.credit_granted


@rules.predicate
def engagement_is_verified(user, engagement):
    """Engagement has been verified."""
    if not engagement:
        return False
    return engagement.verified


@rules.predicate
def engagement_not_verified(user, engagement):
    """Engagement has NOT been verified yet."""
    if not engagement:
        return False
    return not engagement.verified


# ============================================================================
# SETTLEMENT PREDICATES
# ============================================================================

@rules.predicate
def can_be_settled(user, engagement):
    """Engagement can be settled (verified + not yet credited)."""
    if not engagement:
        return False
    return engagement.verified and not engagement.credit_granted


@rules.predicate
def post_allows_settlement(user, engagement):
    """The engagement's post is in a state that allows settlement."""
    if not engagement or not engagement.post:
        return False
    from posts.models import Post
    return engagement.post.status == Post.Status.ACTIVE


@rules.predicate
def post_has_escrow_for_settlement(user, engagement):
    """The engagement's post has escrow remaining."""
    if not engagement or not engagement.post:
        return False
    return engagement.post.escrow > Decimal('0')


# ============================================================================
# CAMPAIGN PREDICATES
# ============================================================================

@rules.predicate
def campaign_is_active(user, campaign):
    """Campaign is in ACTIVE status and within time window."""
    if not campaign:
        return False
    from posts.models import Campaign
    now = timezone.now()
    deadline = campaign.entry_deadline or campaign.ends_at
    return (
        campaign.status == Campaign.Status.ACTIVE and
        campaign.starts_at <= now <= deadline
    )


@rules.predicate
def campaign_has_started(user, campaign):
    """Campaign has started."""
    if not campaign:
        return False
    return timezone.now() >= campaign.starts_at


@rules.predicate
def campaign_not_ended(user, campaign):
    """Campaign has not ended (deadline not passed)."""
    if not campaign:
        return False
    deadline = campaign.entry_deadline or campaign.ends_at
    return timezone.now() <= deadline


@rules.predicate
def campaign_not_full(user, campaign):
    """Campaign hasn't reached max entries."""
    if not campaign:
        return False
    if not campaign.max_entries:
        return True
    from posts.models import CampaignEntry
    current_count = campaign.entries.filter(
        status__in=[
            CampaignEntry.EntryStatus.ELIGIBLE,
            CampaignEntry.EntryStatus.WINNER,
            CampaignEntry.EntryStatus.CLAIMED,
        ]
    ).count()
    return current_count < campaign.max_entries


@rules.predicate
def not_already_entered(user, campaign):
    """User hasn't entered this campaign yet."""
    if not user or not campaign:
        return False
    return not campaign.entries.filter(user=user).exists()


@rules.predicate
def winners_not_announced(user, campaign):
    """Winners have not been announced yet."""
    if not campaign:
        return False
    return campaign.winners_announced_at is None


# ============================================================================
# CAMPAIGN ELIGIBILITY PREDICATES
# ============================================================================

@rules.predicate
def meets_campaign_xp_requirement(user, campaign):
    """User meets the campaign's minimum XP requirement."""
    if not user or not campaign:
        return False
    if not campaign.min_sponsored_xp or campaign.min_sponsored_xp <= 0:
        return True
    return user.sponsored_xp >= campaign.min_sponsored_xp


@rules.predicate
def meets_campaign_engagement_requirement(user, campaign):
    """User meets the campaign's minimum engagement requirement."""
    if not user or not campaign:
        return False
    if not campaign.min_engagements or campaign.min_engagements <= 0:
        return True
    return user.total_engagements >= campaign.min_engagements


@rules.predicate
def meets_campaign_post_requirement(user, campaign):
    """User meets the campaign's minimum posts requirement."""
    if not user or not campaign:
        return False
    if not campaign.min_posts or campaign.min_posts <= 0:
        return True
    return user.total_posts >= campaign.min_posts


@rules.predicate
def meets_campaign_streak_requirement(user, campaign):
    """User meets the campaign's minimum streak requirement."""
    if not user or not campaign:
        return False
    if not campaign.min_streak or campaign.min_streak <= 0:
        return True
    return user.current_streak >= campaign.min_streak


@rules.predicate
def meets_campaign_tweetscout_requirement(user, campaign):
    """User meets the campaign's minimum TweetScout score requirement."""
    if not user or not campaign:
        return False
    if not campaign.min_tweetscout_score or campaign.min_tweetscout_score <= 0:
        return True
    user_score = user.tweetscout_score or 0
    return user_score >= campaign.min_tweetscout_score


@rules.predicate
def meets_campaign_x_linked_requirement(user, campaign):
    """User meets the campaign's X account linked requirement."""
    if not user or not campaign:
        return False
    if not campaign.require_x_linked:
        return True
    return bool(user.x_username)


@rules.predicate
def meets_all_campaign_requirements(user, campaign):
    """User meets ALL campaign eligibility requirements."""
    if not user or not campaign:
        return False
    from core.services.campaigns import CampaignService
    is_eligible, _ = CampaignService.check_eligibility(user, campaign)
    return is_eligible


# ============================================================================
# CAMPAIGN WINNER SELECTION PREDICATES
# ============================================================================

@rules.predicate
def is_campaign_entry_eligible(user, entry):
    """Campaign entry is in eligible status."""
    if not entry:
        return False
    from posts.models import CampaignEntry
    return entry.status == CampaignEntry.EntryStatus.ELIGIBLE


@rules.predicate
def is_campaign_winner(user, entry):
    """User is a winner in this campaign entry."""
    if not entry:
        return False
    return entry.is_winner


@rules.predicate
def has_not_claimed_prize(user, entry):
    """Winner has not claimed their prize yet."""
    if not entry:
        return False
    return not entry.prize_claimed


# ============================================================================
# PERMISSION RULES
# ============================================================================

# --- Post Creation ---
# User can create a post if:
# - Authenticated
# - Not banned
# - Has X account linked
# - Has enough credits
rules.add_perm(
    'posts.can_create_post',
    rules.is_authenticated &
    ~rules.predicate(lambda u, p=None: u.is_banned if u else True) &
    rules.predicate(lambda u, p=None: bool(u.x_username) if u else False) &
    has_enough_credits_to_post
)

# --- Post Management ---
# User can cancel their own post if owner OR staff
rules.add_perm(
    'posts.can_cancel_post',
    is_post_owner | rules.predicate(lambda u, p: u.is_staff if u else False)
)

# User can view post if authenticated
rules.add_perm(
    'posts.can_view_post',
    rules.is_authenticated
)

# --- Engagement ---
# User can engage with a post if:
# - Authenticated
# - Not banned
# - Has X account linked
# - Does not own the post
# - Post is active
# - Post has escrow
# - User hasn't already engaged
# - User is not in cooldown
rules.add_perm(
    'posts.can_engage',
    rules.is_authenticated &
    ~rules.predicate(lambda u, p: u.is_banned if u else True) &
    rules.predicate(lambda u, p: bool(u.x_username) if u else False) &
    is_not_post_owner &
    post_is_active &
    post_has_escrow &
    not_already_engaged &
    not_in_cooldown
)

# Full engagement check including daily cap
rules.add_perm(
    'posts.can_engage_full',
    rules.is_authenticated &
    ~rules.predicate(lambda u, p: u.is_banned if u else True) &
    rules.predicate(lambda u, p: bool(u.x_username) if u else False) &
    is_not_post_owner &
    post_is_active &
    post_has_escrow &
    not_already_engaged &
    not_in_cooldown &
    rules.predicate(lambda u, p: _check_can_earn(u))
)

# --- Settlement ---
rules.add_perm(
    'posts.can_settle_engagement',
    rules.is_authenticated &
    can_be_settled &
    post_allows_settlement &
    post_has_escrow_for_settlement
)

# --- Campaign Entry ---
# User can enter a campaign if:
# - Authenticated
# - Not banned
# - Campaign is active
# - Campaign not full
# - User hasn't already entered
rules.add_perm(
    'posts.can_enter_campaign',
    rules.is_authenticated &
    ~rules.predicate(lambda u, c: u.is_banned if u else True) &
    campaign_is_active &
    campaign_not_full &
    not_already_entered
)

# Full campaign entry check with all eligibility requirements
rules.add_perm(
    'posts.can_enter_campaign_full',
    rules.is_authenticated &
    ~rules.predicate(lambda u, c: u.is_banned if u else True) &
    campaign_is_active &
    campaign_not_full &
    not_already_entered &
    meets_all_campaign_requirements
)

# --- Campaign Management (Admin) ---
rules.add_perm(
    'posts.can_activate_campaign',
    rules.predicate(lambda u: u.is_staff if u else False)
)

rules.add_perm(
    'posts.can_cancel_campaign',
    rules.predicate(lambda u: u.is_staff if u else False)
)

rules.add_perm(
    'posts.can_select_winners',
    rules.predicate(lambda u: u.is_staff if u else False) &
    winners_not_announced
)

# --- Prize Claiming ---
rules.add_perm(
    'posts.can_claim_prize',
    rules.is_authenticated &
    is_campaign_winner &
    has_not_claimed_prize
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _check_can_earn(user) -> bool:
    """Check if user can earn more credits today."""
    if not user:
        return False
    from core.services.credits import CreditService
    credit_service = CreditService(user)
    return credit_service.can_earn()


def check_engagement_eligibility(user, post) -> tuple[bool, str]:
    """
    Check all engagement eligibility rules.

    Returns:
        (can_engage, error_message)
    """
    if not user:
        return (False, "Not authenticated")
    if user.is_banned:
        return (False, "Account is banned")
    if not user.x_username:
        return (False, "X account not linked")
    if not post:
        return (False, "Post not found")
    if post.user_id == user.id:
        return (False, "Cannot engage with your own post")

    from posts.models import Post, Engagement
    if post.status != Post.Status.ACTIVE:
        return (False, "Post is not active")
    if post.escrow <= Decimal('0'):
        return (False, "Post has no escrow remaining")
    if Engagement.objects.filter(user=user, post=post).exists():
        return (False, "Already engaged with this post")

    from django.core.cache import cache
    cooldown_key = f"engagement_cooldown:{user.id}"
    if cache.get(cooldown_key):
        return (False, "Please wait before engaging again")

    from core.services.credits import CreditService
    credit_service = CreditService(user)
    if not credit_service.can_earn():
        return (False, "Daily earning cap reached")

    return (True, "")


def check_campaign_eligibility(user, campaign) -> tuple[bool, list[str]]:
    """
    Check all campaign eligibility rules.

    Returns:
        (is_eligible, list_of_failure_reasons)
    """
    from core.services.campaigns import CampaignService
    return CampaignService.check_eligibility(user, campaign)


def get_engagement_failures(user, post) -> list[str]:
    """
    Get list of all reasons why user cannot engage with post.

    Useful for detailed error messages.
    """
    failures = []
    if not user:
        failures.append("Not authenticated")
        return failures
    if user.is_banned:
        failures.append("Account is banned")
    if not user.x_username:
        failures.append("X account not linked")
    if not post:
        failures.append("Post not found")
        return failures
    if post.user_id == user.id:
        failures.append("Cannot engage with your own post")

    from posts.models import Post, Engagement
    if post.status != Post.Status.ACTIVE:
        failures.append("Post is not active")
    if post.escrow <= Decimal('0'):
        failures.append("Post has no escrow remaining")
    if Engagement.objects.filter(user=user, post=post).exists():
        failures.append("Already engaged with this post")

    from django.core.cache import cache
    cooldown_key = f"engagement_cooldown:{user.id}"
    if cache.get(cooldown_key):
        from core.services.settings import get_setting
        cooldown = get_setting('ENGAGEMENT_COOLDOWN', 60)
        failures.append(f"Please wait {cooldown} seconds between engagements")

    from core.services.credits import CreditService
    credit_service = CreditService(user)
    if not credit_service.can_earn():
        failures.append("Daily earning cap reached")

    return failures
