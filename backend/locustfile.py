"""
Comprehensive Locust load testing for Loudrr API.

Simulates real user behavior across all endpoints:
- Engagement flow (70% of traffic)
- Post submission (15%)
- LOUD participation (10%)
- New user onboarding (5%)

Setup:
    1. Set environment variables on server:
       LOAD_TEST_MODE=true
       LOAD_TEST_SECRET=your-secret-key

    2. Create test users:
       python manage.py create_load_test_users --count 100

    3. Run Locust:
       locust -f locustfile.py --host=https://api.loudrr.com

    4. Open http://localhost:8089 and start test

Test Scenarios:
    - Baseline: 50 users, 5/sec spawn
    - Peak: 200 users, 10/sec spawn
    - Stress: 500+ users until failure
"""

import os
import random
import time
from locust import HttpUser, task, between, events


# Configuration
LOAD_TEST_SECRET = os.getenv("LOAD_TEST_SECRET", "test-secret-change-me")
TEST_USER_START_ID = 900000001
TEST_USER_COUNT = 100


class BaseLoudrrUser(HttpUser):
    """Base class with authentication setup."""

    abstract = True

    def on_start(self):
        """Called when user starts - set up auth headers."""
        self.telegram_id = random.randint(
            TEST_USER_START_ID,
            TEST_USER_START_ID + TEST_USER_COUNT - 1
        )
        self.client.headers = {
            "X-Load-Test-Auth": LOAD_TEST_SECRET,
            "X-Load-Test-User": str(self.telegram_id),
            "Content-Type": "application/json",
        }


class EngagerUser(BaseLoudrrUser):
    """
    Main engagement flow - represents 70% of real traffic.

    Simulates users:
    1. Starting engagement session
    2. Clicking through posts
    3. Claiming rewards
    """

    weight = 7
    wait_time = between(2, 5)

    @task(10)
    def full_engagement_flow(self):
        """Complete engagement cycle."""
        # 1. Start session - get posts
        with self.client.post(
            "/api/miniapp/session/start/",
            name="/session/start",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Start failed: {response.status_code}")
                return

            try:
                data = response.json()
                posts = data.get("posts", [])
            except Exception:
                response.failure("Invalid JSON response")
                return

        if not posts:
            return

        # 2. Click through posts (with realistic delays)
        posts_to_engage = random.sample(posts, min(5, len(posts)))

        for post in posts_to_engage:
            # Simulate time spent viewing/engaging on X
            time.sleep(random.uniform(3, 8))

            post_id = post.get("id")
            if post_id:
                self.client.post(
                    "/api/miniapp/session/click/",
                    json={"post_id": str(post_id)},
                    name="/session/click",
                )

        # 3. Wait minimum session duration
        time.sleep(random.uniform(5, 10))

        # 4. Claim rewards (queue for async processing)
        self.client.post(
            "/api/miniapp/session/queue-claim/",
            name="/session/queue-claim",
        )

    @task(3)
    def check_user_profile(self):
        """Check own profile."""
        self.client.get("/api/miniapp/user/", name="/user")

    @task(2)
    def check_user_stats(self):
        """Check detailed stats."""
        self.client.get("/api/miniapp/user/stats/", name="/user/stats")

    @task(1)
    def check_claims_history(self):
        """Check verification history."""
        self.client.get("/api/miniapp/claims/history/", name="/claims/history")


class PostCreator(BaseLoudrrUser):
    """
    Post submission flow - represents 15% of traffic.

    Users who have earned karma and want to promote their content.
    """

    weight = 2
    wait_time = between(10, 30)

    @task(5)
    def check_balance_before_post(self):
        """Check credits before posting."""
        self.client.get("/api/miniapp/user/", name="/user")

    @task(1)
    def submit_post(self):
        """Attempt to submit a post (may fail if insufficient credits)."""
        # Generate fake tweet URL
        fake_tweet_id = random.randint(1000000000000000000, 9999999999999999999)
        x_link = f"https://x.com/loadtest_user/status/{fake_tweet_id}"

        with self.client.post(
            "/api/miniapp/post/submit/",
            json={"x_link": x_link},
            name="/post/submit",
            catch_response=True,
        ) as response:
            # Accept both success and "insufficient credits" as valid
            if response.status_code in [200, 201, 400]:
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")


class LOUDParticipant(BaseLoudrrUser):
    """
    LOUD submission flow - represents 10% of traffic.

    Users participating in UGC contests.
    """

    weight = 1
    wait_time = between(15, 45)

    def on_start(self):
        super().on_start()
        self.project_slugs = []

    @task(5)
    def browse_projects(self):
        """Browse available LOUD projects."""
        with self.client.get(
            "/api/loud/projects/",
            name="/loud/projects",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    projects = data.get("projects", [])
                    self.project_slugs = [p.get("slug") for p in projects if p.get("slug")]
                except Exception:
                    pass

    @task(2)
    def view_leaderboard(self):
        """View a project leaderboard."""
        if self.project_slugs:
            slug = random.choice(self.project_slugs)
            self.client.get(
                f"/api/loud/leaderboard/{slug}/",
                name="/loud/leaderboard/[slug]",
            )

    @task(1)
    def submit_content(self):
        """Submit content to LOUD project."""
        # Generate fake submission
        fake_tweet_id = random.randint(1000000000000000000, 9999999999999999999)
        x_link = f"https://x.com/loadtest_user/status/{fake_tweet_id}"

        with self.client.post(
            "/api/loud/submit/",
            json={
                "project_slug": self.project_slugs[0] if self.project_slugs else "test",
                "x_link": x_link,
            },
            name="/loud/submit",
            catch_response=True,
        ) as response:
            # Accept success or validation errors
            if response.status_code in [200, 201, 400, 404]:
                response.success()


class NewUser(BaseLoudrrUser):
    """
    New user onboarding - represents 5% of traffic.

    Simulates new users going through waitlist/onboarding.
    """

    weight = 1
    wait_time = between(30, 60)

    @task(3)
    def check_waitlist_status(self):
        """Check waitlist status."""
        self.client.get("/api/miniapp/waitlist/status/", name="/waitlist/status")

    @task(2)
    def get_referral_info(self):
        """Get referral code (if approved user)."""
        self.client.get("/api/miniapp/referral/", name="/referral")

    @task(1)
    def complete_onboarding(self):
        """Trigger onboarding completion."""
        self.client.post(
            "/api/miniapp/onboarding/complete/",
            name="/onboarding/complete",
        )


class PublicEndpointsUser(HttpUser):
    """
    Unauthenticated public traffic.

    Health checks, settings, API docs - always running.
    """

    weight = 1
    wait_time = between(5, 15)

    @task(5)
    def health_check(self):
        """Health endpoint (high frequency from monitoring)."""
        self.client.get("/api/miniapp/health/", name="/health")

    @task(3)
    def get_settings(self):
        """App settings."""
        self.client.get("/api/miniapp/settings/", name="/settings")

    @task(1)
    def api_docs(self):
        """Swagger UI."""
        self.client.get("/api/docs/", name="/docs")


# Event handlers for logging
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("=" * 60)
    print("LOUDRR LOAD TEST STARTING")
    print(f"Target: {environment.host}")
    print(f"Test users: {TEST_USER_START_ID} - {TEST_USER_START_ID + TEST_USER_COUNT - 1}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("=" * 60)
    print("LOUDRR LOAD TEST COMPLETE")
    print("=" * 60)
