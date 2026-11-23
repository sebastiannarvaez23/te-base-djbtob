from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('handbook_page', '0004_handbook_revision_menu_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='handbookrevision',
            name='http_method',
            field=models.CharField(blank=True, default='', max_length=8),
        ),
    ]
