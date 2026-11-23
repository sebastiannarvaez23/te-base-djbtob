# Draft / approved statuses and uniqueness for policy country versions.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compliance_policy', '0005_policy_country'),
    ]

    operations = [
        migrations.AlterField(
            model_name='policycountry',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'draft'),
                    ('approved', 'approved'),
                    ('published', 'published'),
                    ('revoked', 'revoked'),
                ],
                default='draft',
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name='policycountry',
            name='version',
            field=models.PositiveIntegerField(
                default=0,
                help_text='0 for drafts; >=1 for approved/published/revoked versions.',
            ),
        ),
        migrations.AddConstraint(
            model_name='policycountry',
            constraint=models.UniqueConstraint(
                condition=models.Q(status='draft'),
                fields=('policy', 'country'),
                name='uniq_compliance_policy_country_draft',
            ),
        ),
        migrations.AddConstraint(
            model_name='policycountry',
            constraint=models.UniqueConstraint(
                condition=models.Q(status='approved'),
                fields=('policy', 'country'),
                name='uniq_compliance_policy_country_approved',
            ),
        ),
        migrations.AddConstraint(
            model_name='policycountry',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(status='draft', version=0)
                    | models.Q(
                        status__in=['approved', 'published', 'revoked'],
                        version__gte=1,
                    )
                ),
                name='chk_compliance_policy_country_version_status',
            ),
        ),
    ]
