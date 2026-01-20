# Generated manually - Add engagement credit requires verification constraint
#
# SECURITY FIX:
# Prevents invalid state where credit_granted=True but verified=False
# This ensures credits can only be granted after verification

from django.db import migrations, models


def check_invalid_engagements(apps, schema_editor):
    """
    Check for any existing invalid engagements before adding constraint.
    If found, raise an error with instructions.
    """
    Engagement = apps.get_model('posts', 'Engagement')
    invalid_count = Engagement.objects.filter(
        verified=False,
        credit_granted=True
    ).count()

    if invalid_count > 0:
        raise Exception(
            f"Found {invalid_count} engagements with invalid state "
            f"(verified=False, credit_granted=True). "
            f"Please fix these records before running this migration:\n"
            f"UPDATE engagements SET verified=True WHERE verified=False AND credit_granted=True;"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0005_convert_karma_to_decimal"),
    ]

    operations = [
        # First check for invalid data
        migrations.RunPython(check_invalid_engagements, migrations.RunPython.noop),

        # Add constraint to prevent invalid state
        migrations.AddConstraint(
            model_name="engagement",
            constraint=models.CheckConstraint(
                check=~models.Q(verified=False, credit_granted=True),
                name="engagement_credit_requires_verification",
            ),
        ),
    ]
