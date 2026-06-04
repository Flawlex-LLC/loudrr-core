"""Tests for TweetScout API client (app.integrations.tweetscout).

The client wraps an async httpx call. The "any failure -> None" contract is the
whole point of this module, so we exercise each failure shape (404, 500,
network error, missing key) and confirm we never raise.

Mocking strategy: patch ``httpx.AsyncClient`` *inside the tweetscout module*
with an AsyncMock whose ``__aenter__`` returns a fake client whose ``.get``
returns a fake response (or raises ``httpx.HTTPError``). This keeps the test
fully offline and lets us assert on the exact URL the client built.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.tweetscout import TweetScoutClient, TWEETSCOUT_BASE_URL


def _mock_response(status_code: int, json_data=None, text: str = ""):
    """A fake httpx.Response with the bits the client touches."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data if json_data is not None else {})
    resp.text = text
    return resp


def _patch_async_client(get_side_effect=None, get_return_value=None):
    """Build a context-manager mock for ``httpx.AsyncClient(...)``.

    Returns (patcher, mock_get). The patcher is the unstarted ``patch`` object;
    use it as a context manager. ``mock_get`` is the AsyncMock the test can
    assert was called with the right URL.
    """
    mock_get = AsyncMock()
    if get_side_effect is not None:
        mock_get.side_effect = get_side_effect
    else:
        mock_get.return_value = get_return_value

    fake_client = MagicMock()
    fake_client.get = mock_get

    # async-with: __aenter__ returns the client, __aexit__ returns None
    async_cm = MagicMock()
    async_cm.__aenter__ = AsyncMock(return_value=fake_client)
    async_cm.__aexit__ = AsyncMock(return_value=None)

    # ``httpx.AsyncClient(timeout=_TIMEOUT)`` -> the async-context-manager mock
    constructor = MagicMock(return_value=async_cm)
    patcher = patch("app.integrations.tweetscout.httpx.AsyncClient", constructor)
    return patcher, mock_get


# ---------------------------------------------------------------------------
# get_score
# ---------------------------------------------------------------------------

async def test_get_score_returns_float_on_200():
    client = TweetScoutClient(api_key="test-key")
    patcher, mock_get = _patch_async_client(
        get_return_value=_mock_response(200, json_data={"score": 42.5})
    )
    with patcher:
        score = await client.get_score("alice")
    assert score == 42.5
    assert isinstance(score, float)
    # URL was built from the cleaned username
    called_url = mock_get.call_args.args[0]
    assert called_url == f"{TWEETSCOUT_BASE_URL}/score/alice"


async def test_get_score_returns_float_when_score_is_int():
    """JSON may give an int; client must coerce to float."""
    client = TweetScoutClient(api_key="test-key")
    patcher, _ = _patch_async_client(
        get_return_value=_mock_response(200, json_data={"score": 7})
    )
    with patcher:
        score = await client.get_score("alice")
    assert score == 7.0
    assert isinstance(score, float)


async def test_get_score_returns_none_on_404():
    client = TweetScoutClient(api_key="test-key")
    patcher, _ = _patch_async_client(
        get_return_value=_mock_response(404, text="not found")
    )
    with patcher:
        score = await client.get_score("ghost")
    assert score is None


async def test_get_score_returns_none_on_500():
    client = TweetScoutClient(api_key="test-key")
    patcher, _ = _patch_async_client(
        get_return_value=_mock_response(500, text="boom")
    )
    with patcher:
        score = await client.get_score("alice")
    assert score is None


async def test_get_score_returns_none_on_network_error():
    """httpx.HTTPError (timeout, connect error, …) must be swallowed."""
    client = TweetScoutClient(api_key="test-key")
    patcher, _ = _patch_async_client(
        get_side_effect=httpx.ConnectError("connection refused")
    )
    with patcher:
        score = await client.get_score("alice")
    assert score is None


async def test_get_score_returns_none_on_timeout():
    client = TweetScoutClient(api_key="test-key")
    patcher, _ = _patch_async_client(
        get_side_effect=httpx.TimeoutException("timed out")
    )
    with patcher:
        score = await client.get_score("alice")
    assert score is None


async def test_get_score_returns_none_when_api_key_empty():
    """No key -> log warning and skip the HTTP call entirely."""
    client = TweetScoutClient(api_key="")
    patcher, mock_get = _patch_async_client(
        get_return_value=_mock_response(200, json_data={"score": 99})
    )
    with patcher:
        score = await client.get_score("alice")
    assert score is None
    # The whole point: we did not pay for a call we cannot authenticate.
    mock_get.assert_not_called()


async def test_get_score_returns_none_when_score_field_missing():
    """200 with a payload that has no ``score`` key -> None, not KeyError."""
    client = TweetScoutClient(api_key="test-key")
    patcher, _ = _patch_async_client(
        get_return_value=_mock_response(200, json_data={"other": 1})
    )
    with patcher:
        score = await client.get_score("alice")
    assert score is None


# ---------------------------------------------------------------------------
# get_info
# ---------------------------------------------------------------------------

async def test_get_info_returns_dict_on_200():
    client = TweetScoutClient(api_key="test-key")
    payload = {
        "id": "1",
        "name": "Alice",
        "screen_name": "alice",
        "followers_count": 1000,
    }
    patcher, mock_get = _patch_async_client(
        get_return_value=_mock_response(200, json_data=payload)
    )
    with patcher:
        info = await client.get_info("alice")
    assert info == payload
    assert mock_get.call_args.args[0] == f"{TWEETSCOUT_BASE_URL}/info/alice"


async def test_get_info_returns_none_on_404():
    client = TweetScoutClient(api_key="test-key")
    patcher, _ = _patch_async_client(
        get_return_value=_mock_response(404, text="not found")
    )
    with patcher:
        info = await client.get_info("ghost")
    assert info is None


async def test_get_info_returns_none_on_500():
    client = TweetScoutClient(api_key="test-key")
    patcher, _ = _patch_async_client(
        get_return_value=_mock_response(500, text="boom")
    )
    with patcher:
        info = await client.get_info("alice")
    assert info is None


async def test_get_info_sends_api_key_header():
    """Spec: ApiKey header carries the key."""
    client = TweetScoutClient(api_key="secret-123")
    patcher, mock_get = _patch_async_client(
        get_return_value=_mock_response(200, json_data={"id": "1"})
    )
    with patcher:
        await client.get_info("alice")
    headers = mock_get.call_args.kwargs["headers"]
    assert headers == {"ApiKey": "secret-123"}


# ---------------------------------------------------------------------------
# get_user_data
# ---------------------------------------------------------------------------

async def test_get_user_data_merges_score_and_info():
    client = TweetScoutClient(api_key="test-key")
    # _get is called twice (score, then info) in that order. Sequence the
    # responses with side_effect so each call gets the right one.
    score_resp = _mock_response(200, json_data={"score": 88.5})
    info_resp = _mock_response(
        200,
        json_data={
            "id": "1",
            "name": "Alice",
            "screen_name": "alice",
            "followers_count": 500,
        },
    )
    patcher, _ = _patch_async_client(get_side_effect=[score_resp, info_resp])
    with patcher:
        data = await client.get_user_data("alice")
    assert data == {
        "id": "1",
        "name": "Alice",
        "screen_name": "alice",
        "followers_count": 500,
        "score": 88.5,
    }


async def test_get_user_data_returns_none_when_both_fail():
    client = TweetScoutClient(api_key="test-key")
    not_found = _mock_response(404)
    patcher, _ = _patch_async_client(get_side_effect=[not_found, not_found])
    with patcher:
        data = await client.get_user_data("ghost")
    assert data is None


async def test_get_user_data_info_only_when_score_missing():
    """Score 404 but info 200 -> the info dict, no ``score`` key."""
    client = TweetScoutClient(api_key="test-key")
    score_resp = _mock_response(404)
    info_resp = _mock_response(200, json_data={"id": "1", "name": "Alice"})
    patcher, _ = _patch_async_client(get_side_effect=[score_resp, info_resp])
    with patcher:
        data = await client.get_user_data("alice")
    assert data == {"id": "1", "name": "Alice"}
    assert "score" not in data


async def test_get_user_data_score_only_when_info_missing():
    """Info 404 but score 200 -> just ``{'score': ...}``."""
    client = TweetScoutClient(api_key="test-key")
    score_resp = _mock_response(200, json_data={"score": 12.0})
    info_resp = _mock_response(404)
    patcher, _ = _patch_async_client(get_side_effect=[score_resp, info_resp])
    with patcher:
        data = await client.get_user_data("alice")
    assert data == {"score": 12.0}


async def test_get_user_data_strips_at_sign():
    """``@alice`` and ``alice`` must produce the SAME upstream URL."""
    client = TweetScoutClient(api_key="test-key")
    patcher, mock_get = _patch_async_client(
        get_return_value=_mock_response(200, json_data={"score": 1.0})
    )
    with patcher:
        await client.get_user_data("@alice")
    # Two calls: /score/alice and /info/alice — never /score/@alice
    urls = [c.args[0] for c in mock_get.call_args_list]
    assert urls == [
        f"{TWEETSCOUT_BASE_URL}/score/alice",
        f"{TWEETSCOUT_BASE_URL}/info/alice",
    ]
    assert all("@" not in u for u in urls)


# ---------------------------------------------------------------------------
# Username cleaning — _clean is the contract that '@user' and 'user' are equal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("alice", "alice"),
        ("@alice", "alice"),
        ("  alice  ", "alice"),
        ("  @alice  ", "alice"),
        ("@@alice", "alice"),  # lstrip removes ALL leading @
    ],
)
def test_clean_username_variants(raw, expected):
    assert TweetScoutClient._clean(raw) == expected


async def test_get_score_same_url_with_or_without_at():
    """Behavioural twin of the _clean test: ``@user`` and ``user`` hit the
    same endpoint, so a caller doesn't have to normalise upstream."""
    client = TweetScoutClient(api_key="test-key")

    patcher_a, mock_get_a = _patch_async_client(
        get_return_value=_mock_response(200, json_data={"score": 1.0})
    )
    with patcher_a:
        await client.get_score("@alice")
    url_with_at = mock_get_a.call_args.args[0]

    patcher_b, mock_get_b = _patch_async_client(
        get_return_value=_mock_response(200, json_data={"score": 1.0})
    )
    with patcher_b:
        await client.get_score("alice")
    url_without_at = mock_get_b.call_args.args[0]

    assert url_with_at == url_without_at == f"{TWEETSCOUT_BASE_URL}/score/alice"
