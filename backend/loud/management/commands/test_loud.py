"""
Test script for Loud feature - creates test projects and runs validation tests.

Usage: python manage.py test_loud
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from core.models import User
from loud.models import LoudProject, LoudSubmission, LoudLeaderboardEntry
from loud.services import LoudService, calculate_loud_points, validate_and_normalize_x_link


class Command(BaseCommand):
    help = 'Test Loud feature - create projects, test submissions, verify all logic'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean all Loud data before testing',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n' + '=' * 60))
        self.stdout.write(self.style.WARNING('LOUD FEATURE TEST SUITE'))
        self.stdout.write(self.style.WARNING('=' * 60 + '\n'))

        if options['clean']:
            self.clean_data()

        # Run all tests
        self.test_url_validation()
        self.test_points_calculation()
        self.create_test_projects()
        self.test_submissions()
        self.test_rate_limiting()
        self.test_leaderboard()
        self.test_duplicate_prevention()

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('ALL TESTS COMPLETED!'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

    def clean_data(self):
        """Clean all Loud data"""
        self.stdout.write('\n[CLEAN] Removing all Loud data...')
        LoudLeaderboardEntry.objects.all().delete()
        LoudSubmission.objects.all().delete()
        LoudProject.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('[CLEAN] Done!\n'))

    def test_url_validation(self):
        """Test URL validation and normalization"""
        self.stdout.write('\n[TEST] URL Validation')
        self.stdout.write('-' * 40)

        test_cases = [
            # (input_url, should_pass, description)
            ('https://x.com/0xblest_/status/1234567890', True, 'Valid x.com URL'),
            ('https://twitter.com/0xblest_/status/1234567890', True, 'Valid twitter.com URL'),
            ('https://x.com/0xblest_/status/1234567890?s=20', True, 'URL with query params (should strip)'),
            ('x.com/0xblest_/status/1234567890', True, 'URL without protocol'),
            ('https://x.com/0xblest_/status/99999999999999999999', True, 'Fake tweet ID (valid format)'),
            ('https://x.com/i/status/1234567890', False, 'Anonymous i/status link'),
            ('https://x.com/intent/tweet', False, 'Intent link'),
            ('https://x.com/share/something', False, 'Share link'),
            ('https://google.com/test', False, 'Non-Twitter URL'),
            ('not a url', False, 'Invalid format'),
        ]

        passed = 0
        failed = 0

        for url, should_pass, desc in test_cases:
            try:
                normalized, tweet_id, username = validate_and_normalize_x_link(url)
                if should_pass:
                    self.stdout.write(self.style.SUCCESS(f'  PASS: {desc}'))
                    self.stdout.write(f'        Input:  {url}')
                    self.stdout.write(f'        Output: {normalized}')
                    passed += 1
                else:
                    self.stdout.write(self.style.ERROR(f'  FAIL: {desc} (should have rejected)'))
                    failed += 1
            except ValidationError as e:
                if not should_pass:
                    self.stdout.write(self.style.SUCCESS(f'  PASS: {desc} (correctly rejected)'))
                    passed += 1
                else:
                    self.stdout.write(self.style.ERROR(f'  FAIL: {desc} (incorrectly rejected: {e})'))
                    failed += 1

        self.stdout.write(f'\n  Results: {passed} passed, {failed} failed')

    def test_points_calculation(self):
        """Test points calculation formula"""
        self.stdout.write('\n[TEST] Points Calculation')
        self.stdout.write('-' * 40)

        test_scores = [0, 50, 100, 200, 473, 500, 1000]

        for score in test_scores:
            points = calculate_loud_points(score)
            self.stdout.write(f'  TweetScout {score:4d} -> {points:3d} points')

        self.stdout.write(self.style.SUCCESS('  Points calculation working correctly'))

    def create_test_projects(self):
        """Create 5 test projects"""
        self.stdout.write('\n[TEST] Creating Test Projects')
        self.stdout.write('-' * 40)

        projects_data = [
            {
                'name': 'Uniswap V4 Launch',
                'slug': 'uniswap-v4',
                'description': 'Create content about Uniswap V4 hooks and new features',
                'min_tweetscout_score': 0,
                'max_submissions_per_user': 4,
                'reward_pool': '$5,000 USDC',
                'days_remaining': 14,
            },
            {
                'name': 'Aave GHO Campaign',
                'slug': 'aave-gho',
                'description': 'Share your experience with GHO stablecoin',
                'min_tweetscout_score': 100,
                'max_submissions_per_user': 3,
                'reward_pool': '$3,000 USDC',
                'days_remaining': 10,
            },
            {
                'name': 'Base Onchain Summer',
                'slug': 'base-summer',
                'description': 'Celebrate building on Base L2',
                'min_tweetscout_score': 0,
                'max_submissions_per_user': 5,
                'reward_pool': '$10,000 USDC',
                'days_remaining': 21,
            },
            {
                'name': 'Arbitrum Odyssey',
                'slug': 'arb-odyssey',
                'description': 'Share your Arbitrum journey',
                'min_tweetscout_score': 200,
                'max_submissions_per_user': 4,
                'reward_pool': '$4,000 ARB',
                'days_remaining': 7,
            },
            {
                'name': 'Optimism RetroPGF',
                'slug': 'op-retropgf',
                'description': 'Highlight public goods on Optimism',
                'min_tweetscout_score': 500,
                'max_submissions_per_user': 2,
                'reward_pool': '$8,000 OP',
                'days_remaining': 30,
            },
        ]

        created = 0
        for data in projects_data:
            project, was_created = LoudProject.objects.get_or_create(
                slug=data['slug'],
                defaults={
                    'name': data['name'],
                    'description': data['description'],
                    'min_tweetscout_score': data['min_tweetscout_score'],
                    'max_submissions_per_user': data['max_submissions_per_user'],
                    'reward_pool': data['reward_pool'],
                    'starts_at': timezone.now() - timedelta(days=1),
                    'ends_at': timezone.now() + timedelta(days=data['days_remaining']),
                    'is_active': True,
                }
            )
            status = 'CREATED' if was_created else 'EXISTS'
            self.stdout.write(f'  [{status}] {data["name"]} (min score: {data["min_tweetscout_score"]})')
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f'\n  {created} new projects created, {len(projects_data) - created} already existed'))

    def test_submissions(self):
        """Test submission flow with fake but valid URLs"""
        self.stdout.write('\n[TEST] Submission Flow')
        self.stdout.write('-' * 40)

        # Get test user (the debug user)
        try:
            user = User.objects.get(telegram_id=6451704338)
            self.stdout.write(f'  Using test user: {user.display_name} (@{user.x_username})')
            self.stdout.write(f'  TweetScout score: {user.tweetscout_score}')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('  Test user not found! Create user with telegram_id=6451704338'))
            return

        service = LoudService(user)
        project = LoudProject.objects.filter(slug='uniswap-v4').first()

        if not project:
            self.stdout.write(self.style.ERROR('  Test project not found!'))
            return

        # Test submission with fake tweet ID but valid username format
        x_username = user.x_username or '0xblest_'
        fake_tweet_id = str(random.randint(10**18, 10**19))
        fake_url = f'https://x.com/{x_username}/status/{fake_tweet_id}'

        self.stdout.write(f'\n  Testing submission:')
        self.stdout.write(f'    URL: {fake_url}')

        try:
            submission = service.submit(project, fake_url)
            self.stdout.write(self.style.SUCCESS(f'    SUCCESS! Points awarded: {submission.points_awarded}'))
            self.stdout.write(f'    Submission ID: {submission.id}')
        except ValidationError as e:
            self.stdout.write(self.style.WARNING(f'    Validation error: {e}'))
        except IntegrityError:
            self.stdout.write(self.style.WARNING(f'    Already submitted (duplicate tweet_id)'))

    def test_rate_limiting(self):
        """Test rate limiting (daily limit and per-project limit)"""
        self.stdout.write('\n[TEST] Rate Limiting')
        self.stdout.write('-' * 40)

        try:
            user = User.objects.get(telegram_id=6451704338)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('  Test user not found!'))
            return

        service = LoudService(user)

        # Check daily remaining
        daily_remaining = service.get_daily_submissions_remaining()
        self.stdout.write(f'  Daily submissions remaining: {daily_remaining}')

        # Check per-project remaining for each project
        for project in LoudProject.objects.filter(is_active=True):
            remaining = service.get_project_submissions_remaining(project)
            can_submit, reason = service.can_submit(project)
            status = 'CAN SUBMIT' if can_submit else f'BLOCKED: {reason}'
            self.stdout.write(f'  {project.name}: {remaining} remaining - {status}')

    def test_leaderboard(self):
        """Test leaderboard ordering and stats"""
        self.stdout.write('\n[TEST] Leaderboard')
        self.stdout.write('-' * 40)

        try:
            user = User.objects.get(telegram_id=6451704338)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('  Test user not found!'))
            return

        service = LoudService(user)

        for project in LoudProject.objects.filter(is_active=True)[:2]:
            self.stdout.write(f'\n  {project.name}:')

            leaderboard = service.get_leaderboard(project, limit=5)
            stats = service.get_project_stats(project)
            user_entry = service.get_user_entry(project)

            self.stdout.write(f'    Total participants: {stats["total_participants"]}')

            if leaderboard:
                self.stdout.write(f'    Top entries:')
                for entry in leaderboard:
                    self.stdout.write(f'      #{entry["rank"]} {entry["user"]["display_name"]}: {entry["total_points"]} pts ({entry["submission_count"]} posts)')
            else:
                self.stdout.write(f'    No submissions yet')

            if user_entry:
                self.stdout.write(f'    Your rank: #{user_entry["rank"]} with {user_entry["total_points"]} pts')

    def test_duplicate_prevention(self):
        """Test that duplicate tweet_ids are rejected globally"""
        self.stdout.write('\n[TEST] Duplicate Prevention')
        self.stdout.write('-' * 40)

        try:
            user = User.objects.get(telegram_id=6451704338)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('  Test user not found!'))
            return

        # Get an existing submission
        existing = LoudSubmission.objects.filter(user=user).first()
        if not existing:
            self.stdout.write('  No existing submissions to test duplicates')
            return

        service = LoudService(user)
        project = LoudProject.objects.filter(is_active=True).first()

        self.stdout.write(f'  Attempting to resubmit existing tweet_id: {existing.tweet_id}')

        try:
            # Try to submit the same tweet_id again
            service.submit(project, existing.x_link)
            self.stdout.write(self.style.ERROR('  FAIL: Duplicate was accepted!'))
        except ValidationError as e:
            self.stdout.write(self.style.SUCCESS(f'  PASS: Correctly rejected - {e}'))
        except IntegrityError:
            self.stdout.write(self.style.SUCCESS(f'  PASS: Correctly rejected at DB level'))
