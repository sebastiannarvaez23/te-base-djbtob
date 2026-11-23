from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0006_update_location_icon'),
    ]

    operations = [
        migrations.RunSQL(
            sql="UPDATE security_modules SET icon = 'bx-buildings' WHERE code = 'location';",
            reverse_sql="UPDATE security_modules SET icon = 'bx-warehouse' WHERE code = 'location';",
        ),
    ]
