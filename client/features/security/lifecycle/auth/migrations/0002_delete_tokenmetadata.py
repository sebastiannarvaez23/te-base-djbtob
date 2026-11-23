from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user_auth', '0001_add_token_metadata'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TokenMetadata',
        ),
    ]
