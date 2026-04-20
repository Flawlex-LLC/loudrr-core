"""Requeue stuck verification batches."""
from django.core.management.base import BaseCommand
from posts.models import VerificationBatch
from django_q.tasks import async_task


class Command(BaseCommand):
    help = "Requeue stuck PENDING verification batches"

    def handle(self, *args, **options):
        stuck = VerificationBatch.objects.filter(status=VerificationBatch.Status.PENDING)
        count = stuck.count()

        if count == 0:
            self.stdout.write("No stuck batches found")
            return

        self.stdout.write(f"Found {count} stuck batches, requeuing...")

        for batch in stuck:
            try:
                async_task("posts.tasks.process_verification_batch", str(batch.id))
                self.stdout.write(f"  Requeued: {batch.id}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Failed {batch.id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Done! Requeued {count} batches"))
