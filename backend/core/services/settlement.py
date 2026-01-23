"""
Settlement Service - Atomic Credit Transfer.

This service handles ALL database writes for engagement settlement.
NO external API calls happen here - that's VerificationService's job.

Architecture:
    Phase 1: VerificationService.verify_engagements() - External API calls, no locks
    Phase 2: SettlementService.settle_engagements() - Atomic DB writes, no external calls

Key guarantees:
    - Escrow deduction and credit award are atomic (savepoints)
    - If credit award fails, escrow is NOT deducted (rollback)
    - Lock ordering prevents deadlocks
    - Partial payment supported (user gets remaining escrow if < full amount)
"""
import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import User
from core.services.credits import CreditService, DailyCapReachedError
from core.services.settings import get_setting
from core.services.tweet_score import calculate_engagement_karma
from core.services.verification import VerificationResult
from posts.models import Engagement, Post

logger = logging.getLogger(__name__)


@dataclass
class SingleSettlementResult:
    """Result of settling a single engagement."""
    engagement_id: UUID
    post_id: UUID
    status: str  # 'awarded', 'partial', 'skipped', 'failed', 'error'
    amount_awarded: Decimal = Decimal('0')
    multiplier: Decimal = Decimal('1')
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'engagement_id': str(self.engagement_id),
            'post_id': str(self.post_id),
            'status': self.status,
            'amount_awarded': float(self.amount_awarded),
            'multiplier': float(self.multiplier),
            'error': self.error,
        }


@dataclass
class BatchSettlementResult:
    """Result of settling a batch of engagements."""
    user_id: UUID
    total_awarded: Decimal = Decimal('0')
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    honesty_score_change: int = 0
    new_balance: Decimal = Decimal('0')
    new_honesty_score: int = 10
    results: list[SingleSettlementResult] = field(default_factory=list)
    message: str = ""

    def add(self, result: SingleSettlementResult):
        self.results.append(result)
        if result.status in ('awarded', 'partial'):
            self.total_awarded += result.amount_awarded
            self.total_passed += 1
        elif result.status == 'failed':
            self.total_failed += 1
        else:
            self.total_skipped += 1

    def to_dict(self) -> dict:
        return {
            'user_id': str(self.user_id),
            'total_awarded': float(self.total_awarded),
            'total_passed': self.total_passed,
            'total_failed': self.total_failed,
            'total_skipped': self.total_skipped,
            'honesty_score_change': self.honesty_score_change,
            'new_balance': float(self.new_balance),
            'new_honesty_score': self.new_honesty_score,
            'message': self.message,
            'results': [r.to_dict() for r in self.results],
        }


class SettlementService:
    """
    Atomic settlement service.

    Handles escrow → user credit transfers with full atomicity.
    NO external API calls - only database operations.

    Key features:
    - Per-engagement savepoints (one failure doesn't break others)
    - Partial payment support (caps karma at available escrow)
    - Consistent lock ordering (prevents deadlocks)
    - Honesty score tracking

    Usage:
        service = SettlementService()
        results = service.settle_engagements(user_id, verification_results)
    """

    @transaction.atomic
    def settle_engagements(
        self,
        user_id: UUID,
        verification_results: list[VerificationResult],
    ) -> BatchSettlementResult:
        """
        Atomically settle verified engagements.

        For each PASSED verification:
        1. Lock user and posts (consistent ordering)
        2. Calculate karma with tier multiplier
        3. Cap karma at available escrow (partial payment)
        4. Deduct escrow atomically
        5. Credit user atomically
        6. Mark engagement as verified + credited

        For each FAILED verification:
        1. Delete engagement (user can re-engage fresh)

        Args:
            user_id: User to settle engagements for
            verification_results: Results from VerificationService

        Returns:
            BatchSettlementResult with all outcomes
        """
        batch_result = BatchSettlementResult(user_id=user_id)

        if not verification_results:
            batch_result.message = "No engagements to settle"
            return batch_result

        # Lock user row FIRST
        user = User.objects.select_for_update().get(pk=user_id)
        batch_result.new_balance = user.credits
        batch_result.new_honesty_score = user.honesty_score

        # Collect all post IDs and lock in consistent order
        post_ids = sorted(set(r.post_id for r in verification_results))
        posts_locked = {
            p.pk: p for p in
            Post.objects.select_for_update().filter(pk__in=post_ids).order_by('pk')
        }

        # Lock all engagements
        engagement_ids = [r.engagement_id for r in verification_results]
        engagements_locked = {
            e.pk: e for e in
            Engagement.objects.select_for_update().filter(
                pk__in=engagement_ids,
                user=user,
            )
        }

        # Get base credit from settings
        base_credit = Decimal(str(get_setting('CREDIT_PER_ENGAGEMENT', 1)))

        # Process each verification result
        for vr in verification_results:
            if vr.passed:
                result = self._settle_single_passed(
                    user=user,
                    post=posts_locked.get(vr.post_id),
                    engagement=engagements_locked.get(vr.engagement_id),
                    verification_result=vr,
                    base_credit=base_credit,
                )
            else:
                result = self._handle_failed_verification(
                    engagement=engagements_locked.get(vr.engagement_id),
                    verification_result=vr,
                )

            batch_result.add(result)

        # Update honesty score if there were failures
        if batch_result.total_failed > 0:
            # Scale drop by failures: ceil(failures/2) -> 1-2 fails = -1, 3-4 = -2, etc.
            drop = max(1, math.ceil(batch_result.total_failed / 2))
            old_score = user.honesty_score
            user.honesty_score = max(0, user.honesty_score - drop)
            user.save(update_fields=['honesty_score'])
            batch_result.honesty_score_change = user.honesty_score - old_score
            batch_result.new_honesty_score = user.honesty_score

        # Refresh user to get final balance
        user.refresh_from_db()
        batch_result.new_balance = user.credits

        # Build message
        if batch_result.total_failed == 0:
            batch_result.message = (
                f"Earned {float(batch_result.total_awarded):.2f} karma "
                f"for {batch_result.total_passed} engagements!"
            )
        else:
            batch_result.message = (
                f"Earned {float(batch_result.total_awarded):.2f} karma "
                f"for {batch_result.total_passed} engagements. "
                f"{batch_result.total_failed} failed verification."
            )

        logger.info(
            f"Settlement complete for user {user_id}: "
            f"{batch_result.total_awarded} karma, "
            f"{batch_result.total_passed} passed, "
            f"{batch_result.total_failed} failed"
        )

        return batch_result

    def _settle_single_passed(
        self,
        user: User,
        post: Optional[Post],
        engagement: Optional[Engagement],
        verification_result: VerificationResult,
        base_credit: Decimal,
    ) -> SingleSettlementResult:
        """
        Settle a single PASSED engagement with savepoint.

        Uses savepoint so one failure doesn't affect others.
        Supports partial payment (caps at available escrow).
        """
        if not engagement:
            return SingleSettlementResult(
                engagement_id=verification_result.engagement_id,
                post_id=verification_result.post_id,
                status='skipped',
                error='Engagement not found (may have been processed already)',
            )

        if engagement.credit_granted:
            return SingleSettlementResult(
                engagement_id=verification_result.engagement_id,
                post_id=verification_result.post_id,
                status='skipped',
                error='Already credited (idempotency check)',
            )

        if not post:
            return SingleSettlementResult(
                engagement_id=verification_result.engagement_id,
                post_id=verification_result.post_id,
                status='skipped',
                error='Post not found',
            )

        if post.status != Post.Status.ACTIVE:
            # Mark as verified but no credit (post completed/cancelled)
            engagement.verified = True
            engagement.reply_verified = verification_result.reply_verified
            engagement.like_verified = verification_result.like_verified
            engagement.credit_granted = False
            engagement.verification_data = {
                'verified_at': timezone.now().isoformat(),
                'method': 'settlement_service',
                'result': 'skipped_post_inactive',
            }
            engagement.save()
            return SingleSettlementResult(
                engagement_id=verification_result.engagement_id,
                post_id=verification_result.post_id,
                status='skipped',
                error=f'Post status is {post.status}',
            )

        # Calculate karma with tier multiplier
        karma_amount, multiplier = calculate_engagement_karma(
            base_credit, user.tweetscout_score or 0
        )

        # PARTIAL PAYMENT: Cap at available escrow
        if post.escrow < karma_amount:
            if post.escrow <= Decimal('0'):
                # No escrow left at all
                engagement.verified = True
                engagement.credit_granted = False
                engagement.verification_data = {
                    'verified_at': timezone.now().isoformat(),
                    'method': 'settlement_service',
                    'result': 'skipped_no_escrow',
                }
                engagement.save()
                return SingleSettlementResult(
                    engagement_id=verification_result.engagement_id,
                    post_id=verification_result.post_id,
                    status='skipped',
                    error='Post escrow depleted',
                )
            # Partial: take what's available
            karma_amount = post.escrow
            logger.info(
                f"Partial payment for engagement {engagement.pk}: "
                f"user tier wants {multiplier}x but only {karma_amount} available"
            )

        # Use savepoint for atomic escrow+credit
        sid = transaction.savepoint()
        try:
            # Check daily cap
            credit_service = CreditService(user)
            if not credit_service.can_earn(karma_amount):
                transaction.savepoint_rollback(sid)
                engagement.verified = True
                engagement.credit_granted = False
                engagement.verification_data = {
                    'verified_at': timezone.now().isoformat(),
                    'method': 'settlement_service',
                    'result': 'skipped_daily_cap',
                }
                engagement.save()
                return SingleSettlementResult(
                    engagement_id=verification_result.engagement_id,
                    post_id=verification_result.post_id,
                    status='skipped',
                    error='Daily earning cap reached',
                )

            # Deduct escrow atomically
            updated = Post.objects.filter(
                pk=post.pk,
                escrow__gte=karma_amount,
            ).update(escrow=F('escrow') - karma_amount)

            if not updated:
                # Race condition - escrow depleted between check and update
                transaction.savepoint_rollback(sid)
                engagement.verified = True
                engagement.credit_granted = False
                engagement.verification_data = {
                    'verified_at': timezone.now().isoformat(),
                    'method': 'settlement_service',
                    'result': 'skipped_escrow_race',
                }
                engagement.save()
                return SingleSettlementResult(
                    engagement_id=verification_result.engagement_id,
                    post_id=verification_result.post_id,
                    status='skipped',
                    error='Escrow depleted (race condition)',
                )

            # Credit user
            credit_service.earn(
                amount=karma_amount,
                reference_id=engagement.id,
                reference_type="engagement",
                description=f"Engagement verified (x{multiplier})",
            )

            # Mark engagement complete
            engagement.verified = True
            engagement.reply_verified = verification_result.reply_verified
            engagement.like_verified = verification_result.like_verified
            engagement.credit_granted = True
            engagement.verification_data = {
                'verified_at': timezone.now().isoformat(),
                'method': 'settlement_service',
                'result': 'awarded',
                'amount': str(karma_amount),
                'multiplier': str(multiplier),
            }
            engagement.save()

            # Award XP for sponsored posts
            if post.is_sponsored:
                try:
                    from core.services.xp import XPService, get_xp_for_sponsored_engagement
                    xp_amount = get_xp_for_sponsored_engagement()
                    xp_service = XPService(user)
                    xp_service.earn_from_sponsored(
                        amount=xp_amount,
                        post_id=post.pk,
                        description="Sponsored engagement reward",
                    )
                except Exception as e:
                    logger.warning(f"XP award failed (non-critical): {e}")

            # Check if post completed
            post.refresh_from_db()
            if post.escrow <= 0:
                Post.objects.filter(pk=post.pk).update(
                    status=Post.Status.COMPLETED,
                    completed_at=timezone.now(),
                )

            # Update engagement stats
            User.objects.filter(pk=user.pk).update(
                total_engagements=F('total_engagements') + 1
            )

            transaction.savepoint_commit(sid)

            is_partial = karma_amount < (base_credit * multiplier)
            return SingleSettlementResult(
                engagement_id=verification_result.engagement_id,
                post_id=verification_result.post_id,
                status='partial' if is_partial else 'awarded',
                amount_awarded=karma_amount,
                multiplier=multiplier,
            )

        except DailyCapReachedError:
            transaction.savepoint_rollback(sid)
            engagement.verified = True
            engagement.credit_granted = False
            engagement.save()
            return SingleSettlementResult(
                engagement_id=verification_result.engagement_id,
                post_id=verification_result.post_id,
                status='skipped',
                error='Daily earning cap reached',
            )

        except Exception as e:
            transaction.savepoint_rollback(sid)
            logger.error(f"Settlement failed for engagement {engagement.pk}: {e}")
            return SingleSettlementResult(
                engagement_id=verification_result.engagement_id,
                post_id=verification_result.post_id,
                status='error',
                error=str(e),
            )

    def _handle_failed_verification(
        self,
        engagement: Optional[Engagement],
        verification_result: VerificationResult,
    ) -> SingleSettlementResult:
        """
        Handle a FAILED verification by deleting the engagement.

        User can re-engage fresh (click again, actually engage, verify).
        """
        if engagement:
            engagement.delete()
            logger.info(
                f"Deleted failed engagement {verification_result.engagement_id}: "
                f"{verification_result.error}"
            )

        return SingleSettlementResult(
            engagement_id=verification_result.engagement_id,
            post_id=verification_result.post_id,
            status='failed',
            error=verification_result.error or 'Verification failed',
        )


# Singleton instance for convenience
settlement_service = SettlementService()
