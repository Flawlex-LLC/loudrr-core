"""
Populate Loud with test submissions from various users.

Usage: python manage.py populate_loud
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import IntegrityError

from core.models import User
from loud.models import LoudProject, LoudSubmission, LoudLeaderboardEntry
from loud.services import LoudService, calculate_loud_points


class Command(BaseCommand):
    help = 'Populate Loud with test submissions for demo/testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n' + '=' * 60))
        self.stdout.write(self.style.WARNING('POPULATING LOUD WITH TEST DATA'))
        self.stdout.write(self.style.WARNING('=' * 60 + '\n'))

        # Get all users with X accounts linked
        users = list(User.objects.filter(
            x_username__isnull=False
        ).exclude(x_username='').order_by('-tweetscout_score')[:20])

        if len(users) < 3:
            self.stdout.write(self.style.ERROR('Need at least 3 users with X accounts linked!'))
            return

        self.stdout.write(f'Found {len(users)} users with X accounts\n')

        # Get all active projects
        projects = list(LoudProject.objects.filter(is_active=True))

        if not projects:
            self.stdout.write(self.style.ERROR('No active projects found! Run test_loud first.'))
            return

        self.stdout.write(f'Found {len(projects)} active projects\n')

        total_submissions = 0

        for project in projects:
            self.stdout.write(f'\n[{project.name}]')
            self.stdout.write(f'  Min TweetScout: {project.min_tweetscout_score}')

            # Filter eligible users
            eligible_users = [u for u in users if (u.tweetscout_score or 0) >= project.min_tweetscout_score]
            self.stdout.write(f'  Eligible users: {len(eligible_users)}')

            if not eligible_users:
                self.stdout.write(self.style.WARNING('  No eligible users, skipping'))
                continue

            # Create submissions for random users
            submissions_to_create = min(len(eligible_users), random.randint(3, 8))
            selected_users = random.sample(eligible_users, submissions_to_create)

            for user in selected_users:
                # Each user submits 1-4 posts to this project
                num_submissions = random.randint(1, min(4, project.max_submissions_per_user))

                for i in range(num_submissions):
                    # Generate fake but valid tweet ID
                    fake_tweet_id = str(random.randint(10**18, 10**19))
                    x_username = user.x_username or 'testuser'
                    fake_url = f'https://x.com/{x_username}/status/{fake_tweet_id}'

                    try:
                        service = LoudService(user)
                        submission = service.submit(project, fake_url)
                        total_submissions += 1
                        self.stdout.write(f'  + {user.display_name}: {submission.points_awarded} pts')
                    except Exception as e:
                        # Skip duplicates or validation errors
                        pass

        # Show final stats
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'Created {total_submissions} test submissions'))
        self.stdout.write('=' * 60)

        # Show leaderboards
        self.stdout.write('\n[LEADERBOARDS]\n')

        for project in projects:
            entries = LoudLeaderboardEntry.objects.filter(
                project=project
            ).select_related('user').order_by('-total_points')[:5]

            self.stdout.write(f'\n{project.name}:')
            if entries:
                for i, entry in enumerate(entries, 1):
                    self.stdout.write(
                        f'  #{i} {entry.user.display_name} (@{entry.user.x_username}): '
                        f'{entry.total_points} pts ({entry.submission_count} posts)'
                    )
            else:
                self.stdout.write('  No submissions yet')

        self.stdout.write('\n')
