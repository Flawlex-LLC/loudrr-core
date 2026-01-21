"""
Celery tasks for async verification processing.

Similar to spot trading order fills - users can queue verifications
and continue engaging while verification processes in background.
"""
import math
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import User
from core.services.credits import CreditService, DailyCapReachedError
from core.services.settings import get_setting
from core.services.tweet_score import calculate_engagement_karma
from core.services.twitter_verification import twitter_verification
from posts.models import Engagement, Post, VerificationBatch


@shared_task(bind=True, max_retries=3)
def process_verification_batch(self, batch_id: str):
    """
    Process a queued verification batch.

    This runs the same verification logic as CompleteSessionView,
    but asynchronously so users can continue engaging.
    """
    try:
        batch = VerificationBatch.objects.get(id=batch_id)
    except VerificationBatch.DoesNotExist:
        return {"error": "Batch not found"}

    # Skip if already processed
    if batch.status in ['completed', 'failed']:
        return {"status": batch.status, "already_processed": True}

    # Mark as processing
    batch.status = VerificationBatch.Status.PROCESSING
    batch.save(update_fields=['status'])

    try:
        result = _run_verification(batch)
        return result
    except Exception as exc:
        # Mark as failed and retry
        batch.status = VerificationBatch.Status.FAILED
        batch.message = str(exc)
        batch.completed_at = timezone.now()
        batch.save(update_fields=['status', 'message', 'completed_at'])

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@transaction.atomic
def _run_verification(batch: VerificationBatch) -> dict:
    """
    Run the actual verification logic for a batch.

    This is extracted from CompleteSessionView.post() for reuse.
    """
    user = User.objects.select_for_update().get(pk=batch.user_id)

    # Get engagement IDs from batch
    engagement_ids = batch.engagement_ids
    if not engagement_ids:
        batch.status = VerificationBatch.Status.COMPLETED
        batch.passed = 0
        batch.failed = 0
        batch.credits_awarded = Decimal('0')
        batch.message = "No engagements to verify"
        batch.completed_at = timezone.now()
        batch.save()
        return {"passed": 0, "failed": 0, "credits": 0}

    # Get engagements (locked for update)
    pending_engagements = Engagement.objects.select_for_update().filter(
        id__in=engagement_ids,
        user=user,
        verified=False,
        credit_granted=False,
    ).select_related('post').order_by('clicked_at')

    pending_list = list(pending_engagements)

    if not pending_list:
        batch.status = VerificationBatch.Status.COMPLETED
        batch.passed = 0
        batch.failed = 0
        batch.credits_awarded = Decimal('0')
        batch.message = "No pending engagements found"
        batch.completed_at = timezone.now()
        batch.save()
        return {"passed": 0, "failed": 0, "credits": 0}

    # Lock posts in consistent order to prevent deadlocks
    post_ids = sorted(set(eng.post_id for eng in pending_list))
    posts_locked = {
        p.pk: p for p in Post.objects.select_for_update().filter(
            pk__in=post_ids
        ).order_by('pk')
    }

    # Verify ALL engagements
    total_passed = 0
    total_failed = 0
    credits_awarded = Decimal('0')

    credit_service = CreditService(user)
    base_credit = Decimal(str(get_setting('CREDIT_PER_ENGAGEMENT', 1)))

    for eng in pending_list:
        # Get tweet_id from post
        tweet_id = eng.post.tweet_id
        if not tweet_id:
            tweet_id = twitter_verification.extract_tweet_id(eng.post.x_link)

        # Verify via Twitter API
        result = {"passed": True, "reply_verified": False, "skipped": True}
        if tweet_id and user.x_username:
            result = twitter_verification.verify_reply(
                tweet_id=tweet_id,
                x_username=user.x_username
            )
            # If API was skipped (no key), treat as passed
            if result.get("skipped"):
                result["passed"] = True

        passed = result.get("passed", False)

        if passed:
            # PASS: Mark complete, award karma
            eng.verified = True
            eng.reply_verified = True
            eng.like_verified = True
            eng.verification_data = {
                "verified_at": timezone.now().isoformat(),
                "method": "twitter_api_async",
                "result": "passed",
                "tweet_id": tweet_id,
                "batch_id": str(batch.id),
            }

            # Get locked post
            post = posts_locked.get(eng.post_id)
            if not post or post.status != Post.Status.ACTIVE or post.escrow <= 0:
                eng.credit_granted = False
                eng.save()
                total_passed += 1
                continue

            # Check daily cap
            if not credit_service.can_earn():
                eng.credit_granted = False
                eng.save()
                total_passed += 1
                continue

            try:
                # Calculate karma with tier multiplier
                karma_amount, multiplier = calculate_engagement_karma(
                    base_credit, user.tweetscout_score or 0
                )

                # Deduct escrow atomically BEFORE awarding credits
                updated = Post.objects.filter(
                    pk=post.pk,
                    escrow__gte=karma_amount
                ).update(escrow=F('escrow') - karma_amount)

                if not updated:
                    # Escrow depleted - don't award
                    eng.credit_granted = False
                    eng.save()
                    total_passed += 1
                    continue

                # Award credit to user
                credit_service.earn(
                    amount=karma_amount,
                    reference_id=eng.id,
                    reference_type="engagement",
                    description=f"Engagement verified (x{multiplier})",
                )
                credits_awarded += karma_amount
                eng.credit_granted = True

                # Award XP for sponsored posts
                if post.is_sponsored:
                    from core.services.xp import XPService, get_xp_for_sponsored_engagement
                    xp_amount = get_xp_for_sponsored_engagement()
                    xp_service = XPService(user)
                    xp_service.earn_from_sponsored(
                        amount=xp_amount,
                        post_id=post.pk,
                        description="Sponsored engagement reward",
                    )

                # Check if post completed
                post.refresh_from_db()
                if post.escrow <= 0:
                    Post.objects.filter(pk=post.pk).update(
                        status=Post.Status.COMPLETED,
                        completed_at=timezone.now()
                    )

                # Update engagement stats
                User.objects.filter(pk=user.pk).update(
                    total_engagements=F('total_engagements') + 1
                )

            except DailyCapReachedError:
                eng.credit_granted = False
            except Exception:
                eng.credit_granted = False

            eng.save()
            total_passed += 1

        else:
            # FAIL: Keep pending - don't mark as verified
            total_failed += 1

    # Update honesty score based on failure count
    if total_failed > 0:
        drop = max(1, math.ceil(total_failed / 2))
        user.honesty_score = max(0, user.honesty_score - drop)
        user.save(update_fields=['honesty_score'])

    # Build result message
    if total_failed == 0:
        message = f"Earned {float(credits_awarded):.2f} karma for {total_passed} engagements!"
    else:
        message = f"Earned {float(credits_awarded):.2f} karma for {total_passed} engagements. {total_failed} need re-engagement."

    # Update batch with results
    batch.status = VerificationBatch.Status.COMPLETED
    batch.passed = total_passed
    batch.failed = total_failed
    batch.credits_awarded = credits_awarded
    batch.message = message
    batch.completed_at = timezone.now()
    batch.save()

    return {
        "passed": total_passed,
        "failed": total_failed,
        "credits": float(credits_awarded),
        "message": message,
    }
