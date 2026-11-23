from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0007_fix_location_icon'),
    ]

    operations = [
        migrations.RunSQL(
            sql="UPDATE security_modules SET icon = 'bx-cabinet' WHERE code = 'location';",
            reverse_sql="UPDATE security_modules SET icon = 'bx-buildings' WHERE code = 'location';",
        ),
    ]
