# Generated manually for policy locale versioning / revocation.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compliance_policy', '0002_policy_signatures'),
    ]

    operations = [
        migrations.AddField(
            model_name='policylocale',
            name='version',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='policylocale',
            name='status',
            field=models.CharField(
                choices=[('published', 'published'), ('revoked', 'revoked')],
                default='published',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='policylocale',
            name='revoked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='policylocale',
            name='revoked_reason',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.RemoveConstraint(
            model_name='policylocale',
            name='uniq_compliance_policy_locale',
        ),
        migrations.AddConstraint(
            model_name='policylocale',
            constraint=models.UniqueConstraint(
                fields=('policy', 'locale', 'version'),
                name='uniq_compliance_policy_locale_version',
            ),
        ),
        migrations.AddConstraint(
            model_name='policylocale',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'published')),
                fields=('policy', 'locale'),
                name='uniq_compliance_policy_locale_published',
            ),
        ),
        migrations.AddIndex(
            model_name='policylocale',
            index=models.Index(
                fields=['policy', 'locale', 'status'],
                name='idx_pol_locale_status',
            ),
        ),
        migrations.AlterModelOptions(
            name='policylocale',
            options={
                'ordering': ['locale', '-version'],
                'verbose_name': 'Policy locale version',
                'verbose_name_plural': 'Policy locale versions',
            },
        ),
    ]
