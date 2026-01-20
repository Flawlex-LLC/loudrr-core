"""
X URL resolver service.

Extracts username from X/Twitter URLs, handling shortened URLs via web fetch.
Note: X uses Cloudflare protection, so resolution may fail. We handle this gracefully.
"""
import re
import logging
from typing import Optional, Tuple

import httpx
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache resolved URLs for 24 hours to avoid repeated requests
URL_CACHE_TTL = 86400


def extract_username_from_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract X username from a post URL.

    Args:
        url: X/Twitter post URL

    Returns:
        Tuple of (username, tweet_id) or (None, None) if extraction fails.
    """
    if not url:
        return None, None

    # Pattern for direct URLs: x.com/username/status/id or twitter.com/username/status/id
    direct_pattern = r"(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)/status/(\d+)"
    match = re.search(direct_pattern, url)
    if match:
        return match.group(1), match.group(2)

    # Pattern for shortened URLs without username
    shortened_patterns = [
        r"x\.co/i/status/(\d+)",
        r"t\.co/(\w+)",
    ]

    for pattern in shortened_patterns:
        if re.search(pattern, url):
            return resolve_shortened_url(url)

    return None, None


def resolve_shortened_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve a shortened X URL to get username and tweet_id.
    Uses web fetch to follow redirects and get final URL.

    Note: X uses Cloudflare, so this may fail. Returns (None, None) on failure.
    """
    # Check cache first
    cache_key = f"x_url_resolve:{url}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"URL cache hit: {url}")
        return cached

    try:
        # Follow redirects to get final URL
        # Use a realistic User-Agent to avoid Cloudflare blocks
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            response = client.head(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            })
            final_url = str(response.url)

        # Extract from final URL
        pattern = r"(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)/status/(\d+)"
        match = re.search(pattern, final_url)
        if match:
            result = (match.group(1), match.group(2))
            logger.info(f"Resolved {url} -> @{result[0]}")
            cache.set(cache_key, result, URL_CACHE_TTL)
            return result

        logger.warning(f"Could not extract username from resolved URL: {final_url}")
        # Cache the failure too to avoid repeated attempts
        cache.set(cache_key, (None, None), URL_CACHE_TTL)
        return None, None

    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error resolving URL {url}: {e.response.status_code}")
        return None, None
    except Exception as e:
        # Cloudflare or network issues - fail gracefully
        logger.warning(f"Could not resolve shortened URL {url}: {e}")
        return None, None


def get_tweet_id_from_url(url: str) -> Optional[str]:
    """
    Extract just the tweet ID from any X URL format.

    Args:
        url: X/Twitter URL

    Returns:
        Tweet ID string or None
    """
    if not url:
        return None

    # Direct extraction from status path
    pattern = r"status/(\d+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)

    # Try resolving if shortened
    _, tweet_id = extract_username_from_url(url)
    return tweet_id


def validate_x_url(url: str) -> bool:
    """
    Check if a URL looks like a valid X/Twitter post URL.

    Args:
        url: URL to validate

    Returns:
        True if it looks like an X/Twitter URL
    """
    if not url:
        return False

    url_lower = url.lower()
    return any(domain in url_lower for domain in [
        "twitter.com",
        "x.com",
        "t.co",
    ])
