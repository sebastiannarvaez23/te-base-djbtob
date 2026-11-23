import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='CompanyRegistration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[
                        ('in_progress', 'In progress'),
                        ('completed', 'Completed'),
                        ('expired', 'Expired'),
                        ('failed_provisioning', 'Failed provisioning'),
                    ],
                    db_index=True,
                    default='in_progress',
                    max_length=32,
                )),
                ('current_step', models.CharField(
                    choices=[
                        ('company', 'Company'),
                        ('admin_user', 'Admin user'),
                        ('subscription', 'Subscription'),
                        ('payment', 'Payment'),
                        ('confirmation', 'Confirmation'),
                    ],
                    default='company',
                    max_length=32,
                )),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('nit', models.CharField(blank=True, db_index=True, default='', max_length=40)),
                ('schema_name', models.CharField(blank=True, db_index=True, default='', max_length=120)),
                ('company_data', models.JSONField(blank=True, default=dict)),
                ('admin_user_data', models.JSONField(blank=True, default=dict)),
                ('subscription_data', models.JSONField(blank=True, default=dict)),
                ('payment_data', models.JSONField(blank=True, default=dict)),
                ('company_data_completed', models.BooleanField(default=False)),
                ('admin_user_completed', models.BooleanField(default=False)),
                ('subscription_selected', models.BooleanField(default=False)),
                ('payment_completed', models.BooleanField(default=False)),
                ('subscription_id', models.UUIDField(blank=True, null=True)),
                ('requires_payment', models.BooleanField(default=False)),
                ('finalized_company_id', models.UUIDField(blank=True, null=True)),
                ('failure_reason', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField()),
            ],
            options={
                'verbose_name': 'Company registration',
                'verbose_name_plural': 'Company registrations',
                'db_table': 'onboarding_company_registrations',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='companyregistration',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'in_progress')),
                fields=('email',),
                name='uniq_active_onboarding_email',
            ),
        ),
        migrations.AddConstraint(
            model_name='companyregistration',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'in_progress')) & ~models.Q(('nit', '')),
                fields=('nit',),
                name='uniq_active_onboarding_nit',
            ),
        ),
        migrations.AddConstraint(
            model_name='companyregistration',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'in_progress')) & ~models.Q(('schema_name', '')),
                fields=('schema_name',),
                name='uniq_active_onboarding_schema',
            ),
        ),
    ]
