# Generated manually - Remove Kaito/Yaps fields

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove all Kaito/Yaps related fields from User and XProfile models.

    Kaito API has been removed - we now only use TweetScout for scoring.
    """

    dependencies = [
        ('core', '0022_simplify_verification'),
    ]

    operations = [
        # Remove Kaito fields from users table
        migrations.RunSQL(
            sql="""
                ALTER TABLE users DROP COLUMN IF EXISTS kaito_yaps_lifetime;
                ALTER TABLE users DROP COLUMN IF EXISTS kaito_yaps_30d;
                ALTER TABLE users DROP COLUMN IF EXISTS kaito_linked_at;
                ALTER TABLE users DROP COLUMN IF EXISTS kaito_last_updated;
            """,
            reverse_sql="""
                ALTER TABLE users ADD COLUMN kaito_yaps_lifetime DOUBLE PRECISION DEFAULT 0;
                ALTER TABLE users ADD COLUMN kaito_yaps_30d DOUBLE PRECISION DEFAULT 0;
                ALTER TABLE users ADD COLUMN kaito_linked_at TIMESTAMP WITH TIME ZONE NULL;
                ALTER TABLE users ADD COLUMN kaito_last_updated TIMESTAMP WITH TIME ZONE NULL;
            """,
        ),
        # Remove Kaito fields from x_profiles table
        migrations.RunSQL(
            sql="""
                ALTER TABLE x_profiles DROP COLUMN IF EXISTS kaito_yaps_lifetime;
                ALTER TABLE x_profiles DROP COLUMN IF EXISTS raw_kaito_data;
            """,
            reverse_sql="""
                ALTER TABLE x_profiles ADD COLUMN kaito_yaps_lifetime DOUBLE PRECISION DEFAULT 0;
                ALTER TABLE x_profiles ADD COLUMN raw_kaito_data JSONB DEFAULT '{}';
            """,
        ),
    ]
