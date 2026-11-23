from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription_limit', '0004_subscriptionlimit_window'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='subscriptionlimit',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(
                        validation_type='window',
                        window_hours__gte=1,
                        window_hours__lte=168,
                    )
                    | (
                        ~models.Q(validation_type='window')
                        & models.Q(window_hours__isnull=True)
                    )
                ),
                name='slimit_window_hours_invariant',
            ),
        ),
    ]
