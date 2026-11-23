from datetime import timedelta
from django.db import migrations, models
from django.utils import timezone


def migrate_to_company_subscription(apps, schema_editor):
    """
    For every Company that already has a subscription FK, create a
    CompanySubscription record so no data is lost.
    """
    Company = apps.get_model('company', 'Company')
    CompanySubscription = apps.get_model('subscription', 'CompanySubscription')

    now = timezone.now()
    one_year = now + timedelta(days=365)

    for company in Company.objects.filter(subscription__isnull=False).select_related('subscription'):
        CompanySubscription.objects.get_or_create(
            company=company,
            subscription=company.subscription,
            defaults={
                'start_date': now,
                'end_date': one_year,
                'status': 'active',
                'price_paid': company.subscription.price,
                'auto_renew': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0003_company_add_subscription'),
        ('subscription', '0003_company_subscription'),
    ]

    operations = [
        migrations.RunPython(migrate_to_company_subscription, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='company',
            name='subscription',
        ),
    ]
