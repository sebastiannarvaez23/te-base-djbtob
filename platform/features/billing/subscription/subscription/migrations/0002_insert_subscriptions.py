from django.db import migrations


def insert_subscriptions(apps, schema_editor):
    Subscription = apps.get_model('subscription', 'Subscription')

    plans = [
        {
            'name': 'Basic',
            'code': 'basic',
            'price': '0.00',
            'is_active': True,
        },
        {
            'name': 'Standard',
            'code': 'standard',
            'price': '29.00',
            'is_active': True,
        },
        {
            'name': 'Professional',
            'code': 'pro',
            'price': '99.00',
            'is_active': True,
        },
        {
            'name': 'Enterprise',
            'code': 'enterprise',
            'price': '249.00',
            'is_active': True,
        },
    ]

    for plan in plans:
        Subscription.objects.get_or_create(code=plan['code'], defaults=plan)


def reverse_subscriptions(apps, schema_editor):
    Subscription = apps.get_model('subscription', 'Subscription')
    Subscription.objects.filter(
        code__in=['basic', 'standard', 'pro', 'enterprise']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(insert_subscriptions, reverse_subscriptions),
    ]
