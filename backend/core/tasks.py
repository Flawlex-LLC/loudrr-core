"""
Async tasks for core app (django-q2).

Handles asynchronous operations including:
- OutboxEvent processing (reliable notification delivery)
- TweetScout data fetching
- Daily credit resets

Features:
- Idempotency via database tracking (prevents duplicates)
- Row-level locking via select_for_update (prevents race conditions)
- Application-level retry via retry_failed_outbox_events (hourly sweep)
- Comprehensive error logging and tracking
"""
import logging
from datetime import timedelta
from django.db import transaction
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def fetch_tweetscout_for_user_task(user_id: str):
    """
    Fetch TweetScout data for a newly approved user.

    Called asynchronously after admin approval to avoid blocking.
    Creates XProfile and updates User with TweetScout score.

    Args:
        user_id: UUID of the User

    Returns:
        dict with status: 'success', 'no_data', or 'error'
    """
    from datetime import datetime
    from core.models import User, XProfile
    from core.services.tweetscout import get_tweetscout_service

    logger.info(f"[TWEETSCOUT] Fetching data for user {user_id}")

    try:
        user = User.objects.get(id=user_id)

        if not user.x_username:
            logger.warning(f"[TWEETSCOUT] User {user_id} has no X username")
            return {"status": "error", "error": "No X username"}

        # Check if XProfile already exists (idempotency)
        if XProfile.objects.filter(user=user).exists():
            logger.info(f"[TWEETSCOUT] XProfile already exists for user {user_id}, skipping")
            return {"status": "already_exists"}

        # Fetch TweetScout data
        tweetscout = get_tweetscout_service()
        tweetscout_data = tweetscout.get_user_data(user.x_username)

        if not tweetscout_data:
            logger.warning(f"[TWEETSCOUT] No data returned for @{user.x_username}")
            return {"status": "no_data", "username": user.x_username}

        score = tweetscout_data.get("score", 0) or 0

        # Parse X account creation date
        x_created_at = None
        if tweetscout_data.get("register_date"):
            try:
                x_created_at = datetime.strptime(
                    tweetscout_data["register_date"], "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                pass

        # Create XProfile with TweetScout data
        with transaction.atomic():
            XProfile.objects.update_or_create(
                user=user,
                defaults={
                    "x_user_id": str(tweetscout_data.get("id", "")),
                    "username": tweetscout_data.get("screen_name", user.x_username),
                    "display_name": tweetscout_data.get("name", ""),
                    "bio": tweetscout_data.get("description", "") or "",
                    "followers_count": tweetscout_data.get("followers_count", 0) or 0,
                    "following_count": tweetscout_data.get("friends_count", 0) or 0,
                    "tweets_count": tweetscout_data.get("tweets_count", 0) or 0,
                    "score": score,
                    "avatar_url": tweetscout_data.get("avatar", "") or "",
                    "banner_url": tweetscout_data.get("banner", "") or "",
                    "is_verified": bool(tweetscout_data.get("verified", False)),
                    "can_dm": bool(tweetscout_data.get("can_dm", False)),
                    "x_created_at": x_created_at,
                    "raw_tweetscout_data": tweetscout_data,
                }
            )

            # Update user with actual TweetScout score
            user.tweetscout_score = score
            user.save(update_fields=['tweetscout_score', 'updated_at'])

        logger.info(f"[TWEETSCOUT] Successfully fetched data for user {user_id}, score: {score}")
        return {"status": "success", "score": score, "username": user.x_username}

    except User.DoesNotExist:
        logger.error(f"[TWEETSCOUT] User {user_id} not found")
        return {"status": "error", "error": "User not found"}

    except Exception:
        logger.exception(f"[TWEETSCOUT] Error fetching data for user {user_id}")
        # django-q2 re-enqueues the task if it crashes without completing within
        # Q_CLUSTER['retry'] seconds. For transient errors we let the exception
        # propagate so the task is marked failed; admin can re-run if needed.
        raise


# =============================================================================
# OUTBOX EVENT PROCESSING
# =============================================================================

def process_pending_outbox_events(batch_size: int = 50):
    """
    Process pending OutboxEvents in batches.

    This task is called periodically by django-q2 scheduler to ensure
    all pending notifications are processed.

    Args:
        batch_size: Maximum events to process per run

    Returns:
        Dict with processing statistics
    """
    from core.models import OutboxEvent
    from core.services.outbox import OutboxService

    # Get pending events, oldest first
    pending_events = OutboxEvent.objects.filter(
        status=OutboxEvent.Status.PENDING,
        retry_count__lt=3,  # Don't retry more than max_retries
    ).order_by('created_at')[:batch_size]

    processed = 0
    succeeded = 0
    failed = 0

    for event in pending_events:
        processed += 1
        try:
            success = OutboxService.process_event(event)
            if success:
                succeeded += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"[OUTBOX] Error processing event {event.id}: {e}")
            failed += 1

    if processed > 0:
        logger.info(
            f"[OUTBOX] Processing complete: {processed} processed, "
            f"{succeeded} succeeded, {failed} failed"
        )

    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
    }


def process_single_outbox_event(event_id: str):
    """
    Process a single OutboxEvent immediately.

    Called when we want to process an event right away instead
    of waiting for the periodic task.

    Args:
        event_id: UUID string of the OutboxEvent
    """
    from core.models import OutboxEvent
    from core.services.outbox import OutboxService

    try:
        event = OutboxEvent.objects.get(id=event_id)
    except OutboxEvent.DoesNotExist:
        logger.error(f"[OUTBOX] Event {event_id} not found")
        return {"success": False, "error": "Event not found"}

    try:
        success = OutboxService.process_event(event)
        return {"success": success}
    except Exception:
        logger.exception(f"[OUTBOX] Error processing event {event_id}")
        # retry_failed_outbox_events (hourly) will reset this to PENDING.
        raise


def cleanup_old_outbox_events(days: int = 30):
    """
    Clean up old processed OutboxEvents.

    Deletes SENT events older than specified days.
    Keeps FAILED events for debugging.

    Args:
        days: Delete events older than this many days
    """
    from core.models import OutboxEvent

    cutoff = timezone.now() - timedelta(days=days)

    deleted_count, _ = OutboxEvent.objects.filter(
        status=OutboxEvent.Status.SENT,
        processed_at__lt=cutoff,
    ).delete()

    if deleted_count > 0:
        logger.info(f"[OUTBOX] Deleted {deleted_count} old outbox events")

    return {"deleted": deleted_count}


def reset_daily_credits():
    """
    Reset daily_credits_earned for all users.

    Called at midnight UTC by django-q2 scheduler.
    """
    from core.models import User

    # Reset users whose reset date is before today
    today = timezone.now().date()

    updated = User.objects.filter(
        daily_earned_reset_at__date__lt=today
    ).update(
        daily_credits_earned=0,
        daily_earned_reset_at=timezone.now(),
    )

    if updated > 0:
        logger.info(f"[DAILY] Reset daily credits for {updated} users")

    return {"reset_count": updated}


def retry_failed_outbox_events():
    """
    Reset failed OutboxEvents for retry.

    Events that have failed less than max_retries are reset to PENDING.
    """
    from core.models import OutboxEvent

    # Find failed events that can still be retried
    retriable = OutboxEvent.objects.filter(
        status=OutboxEvent.Status.FAILED,
        retry_count__lt=3,
    )

    count = retriable.update(status=OutboxEvent.Status.PENDING)

    if count > 0:
        logger.info(f"[OUTBOX] Reset {count} failed outbox events for retry")

    return {"reset_count": count}
