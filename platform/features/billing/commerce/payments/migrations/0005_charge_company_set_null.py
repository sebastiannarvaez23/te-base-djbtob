from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0011_company_export_and_gone'),
        ('payments', '0004_charge_tenant_snapshot'),
    ]

    operations = [
        migrations.AlterField(
            model_name='charge',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='charges',
                to='company.company',
                verbose_name='Empresa',
            ),
        ),
    ]
