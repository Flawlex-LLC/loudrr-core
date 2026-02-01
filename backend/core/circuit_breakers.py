"""
Circuit breakers for external API calls.

Protects the application from cascading failures when external APIs
(Twitter, TweetScout, Telegram) are down or slow.

Usage:
    from core.circuit_breakers import twitter_breaker, tweetscout_breaker

    @twitter_breaker
    def verify_engagement(tweet_id, user_id):
        return call_twitter_api(tweet_id, user_id)

    # Or use with graceful degradation:
    try:
        result = verify_engagement(tweet_id, user_id)
    except CircuitBreakerError:
        # API is unavailable, use fallback logic
        result = None
"""
import pybreaker
import structlog

logger = structlog.get_logger(__name__)


class LoggingCircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """Log circuit breaker state changes for monitoring."""

    def state_change(self, cb, old_state, new_state):
        logger.warning(
            "circuit_breaker_state_change",
            breaker=cb.name,
            old_state=old_state.name,
            new_state=new_state.name,
        )

    def failure(self, cb, exc):
        logger.warning(
            "circuit_breaker_failure",
            breaker=cb.name,
            error_type=type(exc).__name__,
            error=str(exc),
        )

    def success(self, cb):
        # Only log success after circuit was half-open (recovery)
        if cb.state.name == "half-open":
            logger.info(
                "circuit_breaker_recovery",
                breaker=cb.name,
            )


# Create listener instance
_listener = LoggingCircuitBreakerListener()


# ============================================================================
# Circuit Breakers for External APIs
# ============================================================================

# Twitter API (twitterapi.io) - engagement verification
twitter_breaker = pybreaker.CircuitBreaker(
    name="twitter_api",
    fail_max=5,              # Open after 5 consecutive failures
    reset_timeout=60,        # Try again after 60 seconds
    exclude=[ValueError],    # Don't count validation errors as failures
    listeners=[_listener],
)

# TweetScout API - user scoring
tweetscout_breaker = pybreaker.CircuitBreaker(
    name="tweetscout_api",
    fail_max=3,              # Open after 3 failures (less critical)
    reset_timeout=120,       # Try again after 2 minutes
    listeners=[_listener],
)

# Telegram Bot API - notifications
telegram_breaker = pybreaker.CircuitBreaker(
    name="telegram_api",
    fail_max=5,              # Open after 5 failures
    reset_timeout=30,        # Try quickly (Telegram is usually reliable)
    listeners=[_listener],
)


# ============================================================================
# Helper Functions for Graceful Degradation
# ============================================================================

def safe_call_with_breaker(breaker, func, *args, fallback=None, **kwargs):
    """
    Call a function with circuit breaker protection and fallback.

    Args:
        breaker: The circuit breaker to use
        func: The function to call
        *args: Positional arguments for func
        fallback: Value to return if circuit is open or call fails
        **kwargs: Keyword arguments for func

    Returns:
        Result of func or fallback value

    Example:
        result = safe_call_with_breaker(
            twitter_breaker,
            verify_engagement,
            tweet_id, user_id,
            fallback=False
        )
    """
    try:
        @breaker
        def wrapped():
            return func(*args, **kwargs)
        return wrapped()
    except pybreaker.CircuitBreakerError:
        logger.warning(
            "circuit_open_fallback",
            breaker=breaker.name,
            function=func.__name__,
        )
        return fallback
    except Exception as e:
        logger.error(
            "circuit_breaker_call_failed",
            breaker=breaker.name,
            function=func.__name__,
            error_type=type(e).__name__,
            error=str(e),
        )
        return fallback


def get_circuit_status():
    """
    Get status of all circuit breakers.

    Returns:
        dict: Status of each breaker (for health checks / admin)

    Example:
        {
            "twitter_api": {"state": "closed", "failures": 0},
            "tweetscout_api": {"state": "open", "failures": 3},
            "telegram_api": {"state": "closed", "failures": 0},
        }
    """
    breakers = [twitter_breaker, tweetscout_breaker, telegram_breaker]
    return {
        cb.name: {
            "state": cb.state.name,
            "failures": cb.fail_counter,
        }
        for cb in breakers
    }
