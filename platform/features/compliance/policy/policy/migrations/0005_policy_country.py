# Rename policy language variants to country variants (ISO 3166-1 alpha-2).

from django.db import migrations, models
import django.db.models.deletion


def clear_incompatible_language_rows(apps, schema_editor):
    """
    Backfill estructural: las filas previas guardaban idiomas (es/en/pt-br),
    incompatible con ISO country. Se eliminan versiones y firmas asociadas
    para poder aplicar el CHECK de país.
    """
    PolicySignature = apps.get_model('compliance_policy', 'PolicySignature')
    PolicyLocale = apps.get_model('compliance_policy', 'PolicyLocale')
    PolicySignature.objects.all().delete()
    PolicyLocale.objects.all().delete()


class Migration(migrations.Migration):
    # DELETE + ALTER COLUMN in the same PG transaction hits
    # "pending trigger events"; commit between steps.
    atomic = False

    dependencies = [
        ('compliance_policy', '0004_policy_code_uppercase'),
    ]

    operations = [
        migrations.RunPython(clear_incompatible_language_rows, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='policysignature',
            name='uniq_policy_signature_subject_version',
        ),
        migrations.RenameModel(
            old_name='PolicyLocale',
            new_name='PolicyCountry',
        ),
        migrations.AlterModelTable(
            name='policycountry',
            table='compliance_policy_countries',
        ),
        migrations.RenameField(
            model_name='policycountry',
            old_name='locale',
            new_name='country',
        ),
        migrations.RenameField(
            model_name='policysignature',
            old_name='policy_locale',
            new_name='policy_country',
        ),
        migrations.RenameField(
            model_name='policysignature',
            old_name='locale',
            new_name='country',
        ),
        migrations.RemoveConstraint(
            model_name='policycountry',
            name='uniq_compliance_policy_locale_version',
        ),
        migrations.RemoveConstraint(
            model_name='policycountry',
            name='uniq_compliance_policy_locale_published',
        ),
        migrations.RemoveIndex(
            model_name='policycountry',
            name='idx_pol_locale_status',
        ),
        migrations.RemoveIndex(
            model_name='policysignature',
            name='idx_pol_sig_policy_locale',
        ),
        migrations.AlterField(
            model_name='policycountry',
            name='country',
            field=models.CharField(
                help_text='ISO 3166-1 alpha-2 uppercase (e.g. CO, US, MX)',
                max_length=2,
            ),
        ),
        migrations.AlterField(
            model_name='policysignature',
            name='country',
            field=models.CharField(max_length=2),
        ),
        migrations.AlterField(
            model_name='policycountry',
            name='policy',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='countries',
                to='compliance_policy.policy',
            ),
        ),
        migrations.AddConstraint(
            model_name='policycountry',
            constraint=models.UniqueConstraint(
                fields=('policy', 'country', 'version'),
                name='uniq_compliance_policy_country_version',
            ),
        ),
        migrations.AddConstraint(
            model_name='policycountry',
            constraint=models.UniqueConstraint(
                condition=models.Q(status='published'),
                fields=('policy', 'country'),
                name='uniq_compliance_policy_country_published',
            ),
        ),
        migrations.AddConstraint(
            model_name='policycountry',
            constraint=models.CheckConstraint(
                check=models.Q(country__regex=r'^[A-Z]{2}$'),
                name='chk_compliance_policy_country_iso',
            ),
        ),
        migrations.AddConstraint(
            model_name='policysignature',
            constraint=models.UniqueConstraint(
                fields=('subject_type', 'subject_id', 'policy_country', 'content_hash'),
                name='uniq_policy_signature_subject_version',
            ),
        ),
        migrations.AddIndex(
            model_name='policycountry',
            index=models.Index(
                fields=['policy', 'country', 'status'],
                name='idx_pol_country_status',
            ),
        ),
        migrations.AddIndex(
            model_name='policysignature',
            index=models.Index(
                fields=['policy', 'country'],
                name='idx_pol_sig_policy_country',
            ),
        ),
        migrations.AlterModelOptions(
            name='policycountry',
            options={
                'ordering': ['country', '-version'],
                'verbose_name': 'Policy country version',
                'verbose_name_plural': 'Policy country versions',
            },
        ),
    ]
