# Generated manually — integrity constraints + motive/body length + rating check

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support_session', '0002_support_settings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='supportsession',
            name='motive',
            field=models.CharField(max_length=4000),
        ),
        migrations.AlterField(
            model_name='supportsessionmessage',
            name='body',
            field=models.CharField(max_length=4000),
        ),
        migrations.AddConstraint(
            model_name='supportsession',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('status__in', ['QUEUED', 'ACTIVE', 'AWAITING_RATING']),
                ),
                fields=('requester_user_id',),
                name='uq_sup_sess_open_requester',
            ),
        ),
        migrations.AddConstraint(
            model_name='supportsession',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'ACTIVE')),
                fields=('accepted_by_id',),
                name='uq_sup_sess_active_agent',
            ),
        ),
        migrations.AddConstraint(
            model_name='supportsession',
            constraint=models.CheckConstraint(
                check=models.Q(('rating__isnull', True))
                | (
                    models.Q(('rating__gte', 1))
                    & models.Q(('rating__lte', 5))
                ),
                name='chk_sup_sess_rating_range',
            ),
        ),
    ]
