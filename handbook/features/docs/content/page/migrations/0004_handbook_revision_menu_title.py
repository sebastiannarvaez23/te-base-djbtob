from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('handbook_page', '0003_handbook_locale_search_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='handbookrevision',
            name='menu_title',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
