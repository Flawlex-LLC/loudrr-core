"""
Django-rules predicates for LOUD (UGC rewards) feature.

These predicates centralize ALL permission checks for:
- LOUD project submission eligibility
- X link validation
- Rate limiting (daily and per-project)
- Admin actions on submissions

The rules mirror checks in:
- loud/services/loud.py
"""
import rules
import re
from decimal import Decimal
from django.utils import timezone


# ============================================================================
# LOUD PROJECT PREDICATES
# ============================================================================

@rules.predicate
def has_loud_access(user):
    """User has LOUD feature enabled."""
    if not user:
        return False
    return getattr(user, 'loud_access', False)


@rules.predicate
def loud_project_is_live(user, project):
    """Project is active and within time window."""
    if not project:
        return False
    now = timezone.now()
    return (
        project.is_active and
        project.starts_at <= now <= project.ends_at
    )


@rules.predicate
def loud_project_is_active(user, project):
    """Project is_active flag is True."""
    if not project:
        return False
    return project.is_active


@rules.predicate
def loud_project_has_started(user, project):
    """Project start time has passed."""
    if not project:
        return False
    return timezone.now() >= project.starts_at


@rules.predicate
def loud_project_not_ended(user, project):
    """Project end time has not passed."""
    if not project:
        return False
    return timezone.now() <= project.ends_at


@rules.predicate
def meets_loud_min_score(user, project):
    """User meets minimum TweetScout score for the project."""
    if not user or not project:
        return False
    user_score = user.tweetscout_score or Decimal('0')
    min_score = project.min_tweetscout_score or Decimal('0')
    return user_score >= min_score


@rules.predicate
def within_daily_loud_limit(user, project):
    """User hasn't exceeded daily LOUD submissions."""
    if not user:
        return False
    from loud.models import LoudSubmission
    from core.services.settings import get_setting

    # Get daily limit from settings
    daily_limit = get_setting('LOUD_DAILY_LIMIT', 6)

    # Count today's submissions
    today_count = LoudSubmission.objects.filter(
        user=user,
        submitted_at__date=timezone.now().date()
    ).count()

    return today_count < daily_limit


@rules.predicate
def within_project_loud_limit(user, project):
    """User hasn't exceeded project submission limit."""
    if not user or not project:
        return False
    from loud.models import LoudSubmission

    max_per_user = project.max_submissions_per_user or 1
    count = LoudSubmission.objects.filter(user=user, project=project).count()
    return count < max_per_user


# ============================================================================
# X LINK VALIDATION PREDICATES
# ============================================================================

@rules.predicate
def is_valid_loud_x_link(user, x_link):
    """Validates X/Twitter link format for LOUD submission."""
    if not x_link:
        return False

    # Reject anonymous i/status links
    if '/i/status/' in x_link:
        return False

    # Extract username and tweet_id pattern
    pattern = r'(?:x\.com|twitter\.com)/([^/]+)/status/(\d+)'
    match = re.search(pattern, x_link)

    if not match:
        return False

    username = match.group(1)

    # Reject reserved usernames
    if username.lower() in ['i', 'intent', 'share', 'search']:
        return False

    return True


@rules.predicate
def is_not_anonymous_x_link(user, x_link):
    """Link is not an anonymous /i/status/ link."""
    if not x_link:
        return False
    return '/i/status/' not in x_link


# ============================================================================
# SUBMISSION PREDICATES
# ============================================================================

@rules.predicate
def is_submission_owner(user, submission):
    """User owns the submission."""
    if not user or not submission:
        return False
    return submission.user_id == user.id


@rules.predicate
def submission_not_voided(user, submission):
    """Submission has not been voided."""
    if not submission:
        return False
    return not getattr(submission, 'voided', False)


@rules.predicate
def submission_project_is_live(user, submission):
    """The submission's project is still live."""
    if not submission or not submission.project:
        return False
    now = timezone.now()
    project = submission.project
    return (
        project.is_active and
        project.starts_at <= now <= project.ends_at
    )


# ============================================================================
# ADMIN PREDICATES
# ============================================================================

@rules.predicate
def is_superuser(user):
    """User is a superuser."""
    if not user:
        return False
    return user.is_superuser


@rules.predicate
def is_staff(user):
    """User is a staff member."""
    if not user:
        return False
    return user.is_staff


# ============================================================================
# PERMISSION RULES
# ============================================================================

# --- Basic LOUD Access ---
rules.add_perm(
    'loud.can_access',
    rules.is_authenticated &
    ~rules.predicate(lambda u, p=None: u.is_banned if u else True) &
    has_loud_access
)

# --- LOUD Submission ---
# User can submit if:
# - Authenticated
# - Not banned
# - Has X account linked
# - Has LOUD access
# - Project is live
# - Meets minimum TweetScout score
# - Within daily limit
# - Within project limit
rules.add_perm(
    'loud.can_submit',
    rules.is_authenticated &
    ~rules.predicate(lambda u, p: u.is_banned if u else True) &
    rules.predicate(lambda u, p: bool(u.x_username) if u else False) &
    has_loud_access &
    loud_project_is_live &
    meets_loud_min_score &
    within_daily_loud_limit &
    within_project_loud_limit
)

# --- Full Submission Check ---
# Includes X link validation
rules.add_perm(
    'loud.can_submit_full',
    rules.is_authenticated &
    ~rules.predicate(lambda u, p: u.is_banned if u else True) &
    rules.predicate(lambda u, p: bool(u.x_username) if u else False) &
    has_loud_access &
    loud_project_is_live &
    meets_loud_min_score &
    within_daily_loud_limit &
    within_project_loud_limit
)

# --- View Leaderboard ---
rules.add_perm(
    'loud.can_view_leaderboard',
    rules.is_authenticated
)

# --- View Own Submissions ---
rules.add_perm(
    'loud.can_view_own_submissions',
    rules.is_authenticated &
    is_submission_owner
)

# --- Admin Actions ---
rules.add_perm(
    'loud.can_void_submission',
    is_superuser
)

rules.add_perm(
    'loud.can_adjust_points',
    is_superuser
)

rules.add_perm(
    'loud.can_manage_projects',
    is_staff
)

rules.add_perm(
    'loud.can_view_all_submissions',
    is_staff
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def check_loud_eligibility(user, project) -> tuple[bool, str]:
    """
    Check all LOUD submission eligibility rules.

    Returns:
        (can_submit, error_message)
    """
    if not user:
        return (False, "Not authenticated")
    if user.is_banned:
        return (False, "Account is banned")
    if not user.x_username:
        return (False, "Link your X account to submit")
    if not getattr(user, 'loud_access', False):
        return (False, "LOUD access not enabled")

    if not project:
        return (False, "Project not found")

    now = timezone.now()
    if not project.is_active:
        return (False, "Project is not active")
    if now < project.starts_at:
        return (False, "Project has not started yet")
    if now > project.ends_at:
        return (False, "Project has ended")

    # TweetScout score check
    user_score = user.tweetscout_score or 0
    if user_score < (project.min_tweetscout_score or 0):
        return (False, f"Requires TweetScout score of {project.min_tweetscout_score}+")

    # Daily limit check
    from loud.models import LoudSubmission
    from core.services.settings import get_setting

    daily_limit = get_setting('LOUD_DAILY_LIMIT', 6)
    today_count = LoudSubmission.objects.filter(
        user=user,
        submitted_at__date=timezone.now().date()
    ).count()
    if today_count >= daily_limit:
        return (False, f"Daily limit reached ({daily_limit} posts)")

    # Project limit check
    max_per_user = project.max_submissions_per_user or 1
    project_count = LoudSubmission.objects.filter(user=user, project=project).count()
    if project_count >= max_per_user:
        return (False, f"Project limit reached ({max_per_user} posts)")

    return (True, "")


def validate_loud_x_link(x_link: str) -> tuple[bool, str, str, str]:
    """
    Validate and normalize an X/Twitter link for LOUD submission.

    Returns:
        (is_valid, error_message, normalized_url, tweet_id)
    """
    if not x_link:
        return (False, "Link is required", "", "")

    # Strip query params and fragments
    url = x_link.split('?')[0].split('#')[0]

    # Reject anonymous links
    if '/i/status/' in url:
        return (False, "Anonymous links not accepted. Use link with username.", "", "")

    # Extract username and tweet_id
    pattern = r'(?:x\.com|twitter\.com)/([^/]+)/status/(\d+)'
    match = re.search(pattern, url)

    if not match:
        return (False, "Invalid X/Twitter link format. Use: x.com/username/status/...", "", "")

    username, tweet_id = match.groups()

    # Reject reserved usernames
    if username.lower() in ['i', 'intent', 'share', 'search']:
        return (False, "Invalid link format", "", "")

    # Normalize to x.com format
    normalized = f"https://x.com/{username}/status/{tweet_id}"

    return (True, "", normalized, tweet_id)


def get_loud_eligibility_failures(user, project) -> list[str]:
    """
    Get list of all reasons why user cannot submit to LOUD project.

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
    if not getattr(user, 'loud_access', False):
        failures.append("LOUD access not enabled")

    if not project:
        failures.append("Project not found")
        return failures

    now = timezone.now()
    if not project.is_active:
        failures.append("Project is not active")
    if now < project.starts_at:
        failures.append("Project has not started yet")
    if now > project.ends_at:
        failures.append("Project has ended")

    # TweetScout score check
    user_score = user.tweetscout_score or 0
    min_score = project.min_tweetscout_score or 0
    if user_score < min_score:
        failures.append(f"Requires TweetScout score of {min_score}+ (you have {user_score})")

    # Rate limits
    from loud.models import LoudSubmission
    from core.services.settings import get_setting

    daily_limit = get_setting('LOUD_DAILY_LIMIT', 6)
    today_count = LoudSubmission.objects.filter(
        user=user,
        submitted_at__date=timezone.now().date()
    ).count()
    if today_count >= daily_limit:
        failures.append(f"Daily limit reached ({daily_limit} submissions)")

    max_per_user = project.max_submissions_per_user or 1
    project_count = LoudSubmission.objects.filter(user=user, project=project).count()
    if project_count >= max_per_user:
        failures.append(f"Project limit reached ({max_per_user} submissions)")

    return failures


def get_daily_submissions_remaining(user) -> int:
    """Get remaining LOUD submissions for today."""
    if not user:
        return 0

    from loud.models import LoudSubmission
    from core.services.settings import get_setting

    today_count = LoudSubmission.objects.filter(
        user=user,
        submitted_at__date=timezone.now().date()
    ).count()
    daily_limit = get_setting('LOUD_DAILY_LIMIT', 6)
    return max(0, daily_limit - today_count)


def get_project_submissions_remaining(user, project) -> int:
    """Get remaining submissions for a specific project."""
    if not user or not project:
        return 0

    from loud.models import LoudSubmission

    project_count = LoudSubmission.objects.filter(
        user=user,
        project=project
    ).count()
    max_per_user = project.max_submissions_per_user or 1
    return max(0, max_per_user - project_count)
