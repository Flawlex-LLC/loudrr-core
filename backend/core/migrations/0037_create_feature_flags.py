"""
Create initial waffle feature flags for gradual rollout.

These flags allow features to be enabled/disabled without deployment:
- loud_v2_enabled: New LOUD submission flow
- new_verification_flow: Improved verification pipeline
- campaign_entries_enabled: Campaign entry feature
- maintenance_mode (switch): Global maintenance toggle
- registration_enabled (switch): Allow new registrations
"""
from django.db import migrations


def create_flags(apps, schema_editor):
    """Create initial feature flags and switches."""
    Flag = apps.get_model('waffle', 'Flag')
    Switch = apps.get_model('waffle', 'Switch')

    # Feature flags (can target specific users/groups)
    flags = [
        {
            'name': 'loud_v2_enabled',
            'everyone': False,
            'percent': None,
            'superusers': True,
            'staff': True,
            'note': 'Enable LOUD v2 submission flow',
        },
        {
            'name': 'new_verification_flow',
            'everyone': False,
            'percent': None,
            'superusers': True,
            'staff': True,
            'note': 'Enable improved verification pipeline',
        },
        {
            'name': 'campaign_entries_enabled',
            'everyone': True,
            'percent': None,
            'superusers': True,
            'staff': True,
            'note': 'Enable campaign entry feature',
        },
    ]

    for flag_data in flags:
        Flag.objects.get_or_create(
            name=flag_data['name'],
            defaults={
                'everyone': flag_data['everyone'],
                'percent': flag_data['percent'],
                'superusers': flag_data['superusers'],
                'staff': flag_data['staff'],
                'note': flag_data['note'],
            }
        )

    # Switches (global on/off)
    switches = [
        {
            'name': 'maintenance_mode',
            'active': False,
            'note': 'Enable maintenance mode (blocks all API requests)',
        },
        {
            'name': 'registration_enabled',
            'active': True,
            'note': 'Allow new user registrations via waitlist',
        },
    ]

    for switch_data in switches:
        Switch.objects.get_or_create(
            name=switch_data['name'],
            defaults={
                'active': switch_data['active'],
                'note': switch_data['note'],
            }
        )


def remove_flags(apps, schema_editor):
    """Remove feature flags and switches."""
    Flag = apps.get_model('waffle', 'Flag')
    Switch = apps.get_model('waffle', 'Switch')

    Flag.objects.filter(name__in=[
        'loud_v2_enabled',
        'new_verification_flow',
        'campaign_entries_enabled',
    ]).delete()

    Switch.objects.filter(name__in=[
        'maintenance_mode',
        'registration_enabled',
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0036_add_outbox_event'),
        ('waffle', '0004_update_everyone_nullbooleanfield'),
    ]

    operations = [
        migrations.RunPython(create_flags, remove_flags),
    ]
