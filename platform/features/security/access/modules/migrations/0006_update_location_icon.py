from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0005_rename_location_module'),
    ]

    operations = [
        migrations.RunSQL(
            sql="UPDATE security_modules SET icon = 'bx-buildings' WHERE code = 'location';",
            reverse_sql="UPDATE security_modules SET icon = 'bxs-store' WHERE code = 'location';",
        ),
    ]
