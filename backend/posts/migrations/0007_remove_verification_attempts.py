# Generated manually - Remove verification_attempts column

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove verification_attempts column from engagements table.

    This column was added but is no longer needed with the simplified
    100% verification system (no retry tracking required).

    Uses raw SQL because the column exists in DB but not in model state.
    """

    dependencies = [
        ('posts', '0006_add_engagement_verification_constraint'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE engagements DROP COLUMN IF EXISTS verification_attempts;",
            reverse_sql="ALTER TABLE engagements ADD COLUMN verification_attempts INTEGER NOT NULL DEFAULT 0;",
        ),
    ]
