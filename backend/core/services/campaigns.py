"""
Campaign/Giveaway service.

Handles:
- Eligibility checking against campaign requirements
- Campaign entry submission
- Winner selection (random, weighted, first-come)

ROBUSTNESS GUARANTEES:
- Entry creation is atomic with duplicate prevention
- Winner selection locks campaign to prevent race conditions
- Eligibility snapshot captured at entry time for audit
"""
import logging
import random
from typing import Optional
from django.db import transaction, IntegrityError
from django.utils import timezone

from core.models import User
from posts.models import Campaign, CampaignEntry

logger = logging.getLogger(__name__)


# === Custom Exceptions ===

class CampaignError(Exception):
    """Base exception for campaign operations."""
    pass


class CampaignNotActiveError(CampaignError):
    """Campaign is not accepting entries."""
    pass


class AlreadyEnteredError(CampaignError):
    """User has already entered this campaign."""
    pass


class NotEligibleError(CampaignError):
    """User does not meet eligibility requirements."""
    def __init__(self, failures: list):
        self.failures = failures
        super().__init__(f"Not eligible: {', '.join(failures)}")


class CampaignFullError(CampaignError):
    """Campaign has reached maximum entries."""
    pass


# === Main Service ===

class CampaignService:
    """
    Service for campaign/giveaway operations.

    All eligibility criteria default to 0/False, meaning no requirement.
    Set min_sponsored_xp=0 for open giveaways.
    """

    @staticmethod
    def check_eligibility(user: User, campaign: Campaign) -> tuple[bool, list[str]]:
        """
        Check if user meets all eligibility criteria for a campaign.

        Args:
            user: User to check
            campaign: Campaign with eligibility requirements

        Returns:
            (is_eligible, list_of_failed_criteria)
            - is_eligible: True if all criteria met
            - list_of_failed_criteria: Human-readable list of what failed
        """
        failures = []

        # XP requirement
        if campaign.min_sponsored_xp > 0:
            if user.sponsored_xp < campaign.min_sponsored_xp:
                failures.append(
                    f"Requires {campaign.min_sponsored_xp} XP (you have {user.sponsored_xp})"
                )

        # Engagement requirement
        if campaign.min_engagements > 0:
            if user.total_engagements < campaign.min_engagements:
                failures.append(
                    f"Requires {campaign.min_engagements} engagements (you have {user.total_engagements})"
                )

        # Posts requirement
        if campaign.min_posts > 0:
            if user.total_posts < campaign.min_posts:
                failures.append(
                    f"Requires {campaign.min_posts} posts (you have {user.total_posts})"
                )

        # Streak requirement
        if campaign.min_streak > 0:
            if user.current_streak < campaign.min_streak:
                failures.append(
                    f"Requires {campaign.min_streak} day streak (you have {user.current_streak})"
                )

        # TweetScout score requirement
        if campaign.min_tweetscout_score > 0:
            if user.tweetscout_score < campaign.min_tweetscout_score:
                failures.append(
                    f"Requires TweetScout score of {campaign.min_tweetscout_score} (you have {user.tweetscout_score})"
                )

        # X account linked requirement
        if campaign.require_x_linked:
            if not user.x_username:
                failures.append("Requires linked X/Twitter account")

        # Check if user is banned
        if user.is_banned:
            failures.append("Your account is banned")

        return (len(failures) == 0, failures)

    @staticmethod
    def create_eligibility_snapshot(user: User) -> dict:
        """
        Capture user stats at entry time for audit trail.

        This snapshot is stored with the entry and shows what the user's
        stats were when they entered, even if they change later.
        """
        return {
            'sponsored_xp': user.sponsored_xp,
            'total_engagements': user.total_engagements,
            'total_posts': user.total_posts,
            'current_streak': user.current_streak,
            'tweetscout_score': user.tweetscout_score,
            'x_username': user.x_username or None,
            'tier': user.tier,
            'is_pro': user.is_pro,
            'credits': user.credits,
            'captured_at': timezone.now().isoformat(),
        }

    @transaction.atomic
    def enter_campaign(
        self,
        user: User,
        campaign: Campaign,
        tweet_url: str = "",
        source: str = "miniapp",
    ) -> CampaignEntry:
        """
        Submit user entry to a campaign.

        Args:
            user: User entering the campaign
            campaign: Campaign to enter
            tweet_url: Optional tweet URL for the entry
            source: Entry source (miniapp, bot, admin)

        Returns:
            CampaignEntry object

        Raises:
            CampaignNotActiveError: Campaign not accepting entries
            AlreadyEnteredError: User already entered
            NotEligibleError: User doesn't meet requirements
            CampaignFullError: Campaign at max capacity
        """
        # Validate campaign is accepting entries
        if campaign.status != Campaign.Status.ACTIVE:
            raise CampaignNotActiveError("Campaign is not active")

        # Check timing
        now = timezone.now()
        if now < campaign.starts_at:
            raise CampaignNotActiveError("Campaign has not started yet")

        deadline = campaign.entry_deadline or campaign.ends_at
        if now > deadline:
            raise CampaignNotActiveError("Entry deadline has passed")

        # Check max entries
        if campaign.max_entries is not None:
            current_count = campaign.entries.filter(
                status__in=[
                    CampaignEntry.EntryStatus.ELIGIBLE,
                    CampaignEntry.EntryStatus.WINNER,
                    CampaignEntry.EntryStatus.CLAIMED,
                ]
            ).count()
            if current_count >= campaign.max_entries:
                raise CampaignFullError(
                    f"Campaign has reached maximum entries ({campaign.max_entries})"
                )

        # Check eligibility
        is_eligible, failures = self.check_eligibility(user, campaign)

        # Create eligibility snapshot
        snapshot = self.create_eligibility_snapshot(user)

        # Determine status
        if is_eligible:
            status = CampaignEntry.EntryStatus.ELIGIBLE
        else:
            status = CampaignEntry.EntryStatus.INELIGIBLE

        # Try to create entry (handles duplicate via unique constraint)
        try:
            entry = CampaignEntry.objects.create(
                campaign=campaign,
                user=user,
                status=status,
                eligibility_snapshot=snapshot,
                ineligibility_reason='\n'.join(failures) if failures else '',
                tweet_url=tweet_url,
                entry_source=source,
            )
        except IntegrityError:
            raise AlreadyEnteredError("You have already entered this campaign")

        logger.info(
            f"Campaign entry: user={user.pk}, campaign={campaign.pk}, "
            f"status={status}, eligible={is_eligible}"
        )

        # If not eligible, raise after creating the entry (for transparency)
        if not is_eligible:
            raise NotEligibleError(failures)

        return entry

    @transaction.atomic
    def select_winners(self, campaign: Campaign) -> list[CampaignEntry]:
        """
        Select winners for a campaign.

        Must be called after campaign ends. Updates entry statuses
        and marks campaign as completed.

        Args:
            campaign: Campaign to select winners for

        Returns:
            List of winning CampaignEntry objects
        """
        # Lock campaign to prevent race conditions
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)

        if campaign.winners_announced_at:
            logger.warning(f"Winners already announced for campaign {campaign.pk}")
            return list(campaign.entries.filter(is_winner=True))

        # Get eligible entries
        eligible_entries = list(campaign.entries.filter(
            status=CampaignEntry.EntryStatus.ELIGIBLE
        ))

        if not eligible_entries:
            logger.info(f"No eligible entries for campaign {campaign.pk}")
            campaign.winners_announced_at = timezone.now()
            campaign.status = Campaign.Status.COMPLETED
            campaign.save()
            return []

        # Determine number of winners
        num_winners = min(campaign.max_winners, len(eligible_entries))

        # Select winners based on method
        method = campaign.winner_selection_method

        if method == Campaign.WinnerMethod.RANDOM:
            winners = random.sample(eligible_entries, num_winners)

        elif method == Campaign.WinnerMethod.WEIGHTED_XP:
            winners = self._weighted_selection(
                eligible_entries, 'sponsored_xp', num_winners
            )

        elif method == Campaign.WinnerMethod.WEIGHTED_SCORE:
            winners = self._weighted_selection(
                eligible_entries, 'tweetscout_score', num_winners
            )

        elif method == Campaign.WinnerMethod.FIRST_COME:
            # Sort by created_at ascending (earliest first)
            eligible_entries.sort(key=lambda e: e.created_at)
            winners = eligible_entries[:num_winners]

        else:
            # Default to random
            winners = random.sample(eligible_entries, num_winners)

        # Update winner entries
        winner_ids = [w.pk for w in winners]
        CampaignEntry.objects.filter(pk__in=winner_ids).update(
            status=CampaignEntry.EntryStatus.WINNER,
            is_winner=True,
        )

        # Update campaign
        campaign.winners_announced_at = timezone.now()
        campaign.status = Campaign.Status.COMPLETED
        campaign.save()

        logger.info(
            f"Winners selected for campaign {campaign.pk}: "
            f"{len(winners)} winners from {len(eligible_entries)} eligible entries"
        )

        # Refresh and return winners
        return list(CampaignEntry.objects.filter(pk__in=winner_ids))

    def _weighted_selection(
        self,
        entries: list[CampaignEntry],
        weight_key: str,
        num_winners: int,
    ) -> list[CampaignEntry]:
        """
        Select winners with probability weighted by a snapshot field.

        Higher values = higher chance of winning.

        Args:
            entries: List of eligible entries
            weight_key: Key in eligibility_snapshot to use for weighting
            num_winners: Number of winners to select

        Returns:
            List of selected entries
        """
        # Get weights from snapshots
        weights = []
        for entry in entries:
            weight = entry.eligibility_snapshot.get(weight_key, 0)
            # Ensure minimum weight of 1 so everyone has a chance
            weights.append(max(1, float(weight)))

        # Normalize weights
        total_weight = sum(weights)
        probabilities = [w / total_weight for w in weights]

        # Select winners without replacement
        winners = []
        remaining_entries = list(entries)
        remaining_probs = list(probabilities)

        for _ in range(min(num_winners, len(remaining_entries))):
            # Renormalize remaining probabilities
            prob_sum = sum(remaining_probs)
            if prob_sum == 0:
                break
            normalized = [p / prob_sum for p in remaining_probs]

            # Select one winner
            winner_idx = random.choices(
                range(len(remaining_entries)),
                weights=normalized,
                k=1
            )[0]

            winners.append(remaining_entries[winner_idx])

            # Remove selected entry
            del remaining_entries[winner_idx]
            del remaining_probs[winner_idx]

        return winners

    @staticmethod
    def get_active_campaigns() -> list[Campaign]:
        """Get all currently active campaigns."""
        now = timezone.now()
        return list(Campaign.objects.filter(
            status=Campaign.Status.ACTIVE,
            starts_at__lte=now,
        ).order_by('-created_at'))

    @staticmethod
    def get_user_entries(user: User, campaign: Optional[Campaign] = None) -> list[CampaignEntry]:
        """Get user's campaign entries."""
        queryset = CampaignEntry.objects.filter(user=user)
        if campaign:
            queryset = queryset.filter(campaign=campaign)
        return list(queryset.select_related('campaign').order_by('-created_at'))

    @staticmethod
    def has_user_entered(user: User, campaign: Campaign) -> bool:
        """Check if user has already entered a campaign."""
        return CampaignEntry.objects.filter(user=user, campaign=campaign).exists()
