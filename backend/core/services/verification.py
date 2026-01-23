"""
Verification Service - Pure, Stateless Twitter API Verification.

This service handles ONLY external API calls for verification.
NO database writes happen here - that's SettlementService's job.

Architecture:
    Phase 1: VerificationService.verify_engagements() - External API calls, no locks
    Phase 2: SettlementService.settle_engagements() - Atomic DB writes, no external calls

This separation ensures:
    - No database locks held during slow network calls
    - Clean retry semantics (verification can be retried without side effects)
    - Testable in isolation
"""
import logging
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from core.services.twitter_verification import twitter_verification

logger = logging.getLogger(__name__)


@dataclass
class EngagementToVerify:
    """Input for verification - minimal data needed."""
    engagement_id: UUID
    post_id: UUID
    tweet_id: str


@dataclass
class VerificationResult:
    """Result of a single verification attempt."""
    engagement_id: UUID
    post_id: UUID
    passed: bool
    reply_verified: bool = False
    like_verified: bool = True  # Always true (Twitter made likes private)
    skipped: bool = False  # True if API key missing or API unavailable
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'engagement_id': str(self.engagement_id),
            'post_id': str(self.post_id),
            'passed': self.passed,
            'reply_verified': self.reply_verified,
            'like_verified': self.like_verified,
            'skipped': self.skipped,
            'error': self.error,
        }


@dataclass
class BatchVerificationResult:
    """Result of verifying a batch of engagements."""
    results: list[VerificationResult] = field(default_factory=list)
    total_verified: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0

    def add(self, result: VerificationResult):
        self.results.append(result)
        self.total_verified += 1
        if result.skipped:
            self.total_skipped += 1
            # Skipped counts as passed (benefit of doubt when API unavailable)
            self.total_passed += 1
        elif result.passed:
            self.total_passed += 1
        else:
            self.total_failed += 1


class VerificationService:
    """
    Stateless verification service.

    Only makes external API calls - NO database operations.
    Thread-safe and can be called from anywhere.

    Usage:
        service = VerificationService()
        results = service.verify_engagements(engagements, x_username)
        # Then pass results to SettlementService for atomic DB updates
    """

    def verify_single(
        self,
        engagement: EngagementToVerify,
        x_username: str,
    ) -> VerificationResult:
        """
        Verify a single engagement via Twitter API.

        Args:
            engagement: Engagement data to verify
            x_username: User's X/Twitter username

        Returns:
            VerificationResult with pass/fail status
        """
        if not engagement.tweet_id:
            logger.warning(f"No tweet_id for engagement {engagement.engagement_id}")
            return VerificationResult(
                engagement_id=engagement.engagement_id,
                post_id=engagement.post_id,
                passed=True,  # Benefit of doubt
                skipped=True,
                error="No tweet_id available",
            )

        if not x_username:
            logger.warning(f"No x_username for engagement {engagement.engagement_id}")
            return VerificationResult(
                engagement_id=engagement.engagement_id,
                post_id=engagement.post_id,
                passed=False,
                error="User has no X account linked",
            )

        try:
            # Call Twitter API (this is the only external call)
            api_result = twitter_verification.verify_reply(
                tweet_id=engagement.tweet_id,
                x_username=x_username,
            )

            # Handle skipped (no API key configured)
            if api_result.get('skipped', False):
                return VerificationResult(
                    engagement_id=engagement.engagement_id,
                    post_id=engagement.post_id,
                    passed=True,  # Benefit of doubt when API unavailable
                    reply_verified=False,
                    skipped=True,
                    error=api_result.get('error'),
                )

            # Normal verification result
            passed = api_result.get('passed', False)
            return VerificationResult(
                engagement_id=engagement.engagement_id,
                post_id=engagement.post_id,
                passed=passed,
                reply_verified=api_result.get('reply_verified', False),
                like_verified=True,  # Always true (likes are private)
                skipped=False,
                error=api_result.get('error') if not passed else None,
            )

        except Exception as e:
            logger.error(f"Verification API error for engagement {engagement.engagement_id}: {e}")
            # On API error, fail the verification (don't give benefit of doubt for errors)
            return VerificationResult(
                engagement_id=engagement.engagement_id,
                post_id=engagement.post_id,
                passed=False,
                error=f"API error: {str(e)}",
            )

    def verify_engagements(
        self,
        engagements: list[EngagementToVerify],
        x_username: str,
    ) -> BatchVerificationResult:
        """
        Verify multiple engagements via Twitter API.

        This method makes NO database changes - it only calls external APIs.
        Pass the results to SettlementService for atomic DB updates.

        Args:
            engagements: List of engagements to verify
            x_username: User's X/Twitter username

        Returns:
            BatchVerificationResult with all verification outcomes
        """
        batch_result = BatchVerificationResult()

        for engagement in engagements:
            result = self.verify_single(engagement, x_username)
            batch_result.add(result)

        logger.info(
            f"Verification batch complete: {batch_result.total_passed} passed, "
            f"{batch_result.total_failed} failed, {batch_result.total_skipped} skipped"
        )

        return batch_result


# Singleton instance for convenience
verification_service = VerificationService()
