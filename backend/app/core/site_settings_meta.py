"""Single source of truth for site-settings metadata: groups, defaults,
types, descriptions, and whether each setting is currently READ by backend
code at runtime (`live=True`) vs just persisted for future wiring
(`live=False`). The admin UI uses the groups for sectioning; seed_settings
uses (key, default, data_type, description) for upserts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: str
    data_type: str  # "int" | "float" | "decimal" | "bool" | "str"
    description: str
    live: bool      # True if backend code reads this setting today


@dataclass(frozen=True)
class SettingGroup:
    name: str
    description: str
    settings: tuple[SettingSpec, ...]


ALL_GROUPS: tuple[SettingGroup, ...] = (
    SettingGroup(
        name="Economy",
        description="Core karma cost & earn rates",
        settings=(
            SettingSpec("POST_COST", "80", "int", "Default karma stake when submitting a post", live=True),
            SettingSpec("POST_COST_MIN", "10", "int", "Minimum karma stake (lower bound on submit form)", live=True),
            SettingSpec("POST_COST_MAX", "200", "int", "Maximum karma stake (upper bound on submit form)", live=True),
            SettingSpec("CREDIT_PER_ENGAGEMENT", "1", "int", "Base karma awarded per verified engagement (multiplied by tier)", live=True),
            SettingSpec("DAILY_EARN_CAP", "160", "int", "Per-user daily karma earning ceiling", live=True),
            SettingSpec("ENGAGEMENT_COOLDOWN", "0", "int", "Cooldown seconds between engagements by the same user", live=False),
        ),
    ),
    SettingGroup(
        name="Verification & anti-gaming",
        description="Controls how strictly engagements are verified before crediting",
        settings=(
            SettingSpec("MIN_ENGAGEMENTS_TO_CLAIM", "10", "int", "How many pending engagements a user needs before /session/complete/", live=True),
            SettingSpec("MIN_SESSION_DURATION_SECONDS", "150", "int", "Anti-gaming: required seconds between first click and claim", live=True),
            SettingSpec("POST_EXPIRY_HOURS", "48", "int", "Hours after which an active post auto-expires", live=True),
            SettingSpec("AUDIT_PROBABILITY", "0.05", "float", "Random fraction of engagements to TwitterAPI-verify (rest trusted)", live=False),
            SettingSpec("VERIFICATION_BATCH_SIZE", "10", "int", "Engagements per verification batch", live=False),
            SettingSpec("VERIFICATION_SAMPLE_SIZE", "3", "int", "How many out of batch to actually verify against Twitter API", live=False),
            SettingSpec("MAX_VERIFICATION_RETRIES", "2", "int", "Max times to retry a failed Twitter API verification", live=False),
        ),
    ),
    SettingGroup(
        name="Tier thresholds (TweetScout score)",
        description="Score breakpoints that determine which karma tier a user falls into",
        settings=(
            SettingSpec("TIER_NORMIE_THRESHOLD", "100", "int", "TweetScout score ≥ this to reach Normie", live=True),
            SettingSpec("TIER_DEGEN_THRESHOLD", "200", "int", "…Degen", live=True),
            SettingSpec("TIER_BASED_THRESHOLD", "400", "int", "…Based", live=True),
            SettingSpec("TIER_LEGEND_THRESHOLD", "600", "int", "…Legend", live=True),
            SettingSpec("TIER_OG_THRESHOLD", "800", "int", "…OG", live=True),
            SettingSpec("TIER_GOAT_THRESHOLD", "1000", "int", "…GOAT (top tier)", live=True),
        ),
    ),
    SettingGroup(
        name="Tier multipliers",
        description="Karma multiplier applied per tier on every earn",
        settings=(
            SettingSpec("TIER_ANON_MULTIPLIER", "1.00", "decimal", "Anon — base, no boost", live=True),
            SettingSpec("TIER_NORMIE_MULTIPLIER", "1.10", "decimal", "Normie", live=True),
            SettingSpec("TIER_DEGEN_MULTIPLIER", "1.15", "decimal", "Degen", live=True),
            SettingSpec("TIER_BASED_MULTIPLIER", "1.20", "decimal", "Based", live=True),
            SettingSpec("TIER_LEGEND_MULTIPLIER", "1.25", "decimal", "Legend", live=True),
            SettingSpec("TIER_OG_MULTIPLIER", "1.30", "decimal", "OG", live=True),
            SettingSpec("TIER_GOAT_MULTIPLIER", "1.35", "decimal", "GOAT", live=True),
        ),
    ),
    SettingGroup(
        name="Streaks",
        description="Bonuses for consecutive daily activity",
        settings=(
            SettingSpec("STREAK_7_DAY_MULTIPLIER", "1.0", "decimal", "Extra multiplier at a 7-day streak", live=False),
            SettingSpec("STREAK_7_DAY_BONUS", "5", "int", "Flat karma bonus at 7-day streak", live=False),
            SettingSpec("STREAK_14_DAY_MULTIPLIER", "1.0", "decimal", "Extra multiplier at 14-day streak", live=False),
            SettingSpec("STREAK_14_DAY_BONUS", "6", "int", "Flat karma bonus at 14-day streak", live=False),
            SettingSpec("STREAK_30_DAY_MULTIPLIER", "1.0", "decimal", "Extra multiplier at 30-day streak", live=False),
            SettingSpec("STREAK_30_DAY_BONUS", "10", "int", "Flat karma bonus at 30-day streak", live=False),
        ),
    ),
    SettingGroup(
        name="Sponsored posts",
        description="XP awarded on sponsored-post engagements (no karma cost)",
        settings=(
            SettingSpec("SPONSORED_XP_PER_ENGAGEMENT", "5", "int", "XP per sponsored-post engagement", live=False),
        ),
    ),
    SettingGroup(
        name="Karma decay",
        description="Inactive-user karma decay policy",
        settings=(
            SettingSpec("KARMA_DECAY_THRESHOLD_DAYS", "14", "int", "Days of inactivity before decay kicks in", live=False),
            SettingSpec("KARMA_DECAY_RATE", "0.015", "float", "Daily fraction of karma decayed once over threshold", live=False),
        ),
    ),
    SettingGroup(
        name="Telegram message templates",
        description=(
            "Text shown in the Telegram cards sent to users by the outbox. "
            "Supports {x_username_part} placeholder (rendered as ', @handle' "
            "if known, otherwise empty)."
        ),
        settings=(
            SettingSpec(
                "TG_MSG_WAITLIST_SUBMITTED",
                "🎉 You are on the Loudrr waitlist{x_username_part}! We will message you the moment you are approved.",
                "str",
                "Telegram message sent when a user joins the waitlist.",
                live=True,
            ),
            SettingSpec(
                "TG_MSG_WAITLIST_APPROVED",
                "✅ You are in! Your Loudrr access is approved{x_username_part}. Open the app to start earning karma.",
                "str",
                "Telegram message sent when a user is approved off the waitlist.",
                live=True,
            ),
        ),
    ),
)


def all_specs():
    """Flatten all groups to a single (group_name, SettingSpec) sequence."""
    for g in ALL_GROUPS:
        for s in g.settings:
            yield g.name, s


def spec_by_key(key: str) -> SettingSpec | None:
    for _g, s in all_specs():
        if s.key == key:
            return s
    return None
