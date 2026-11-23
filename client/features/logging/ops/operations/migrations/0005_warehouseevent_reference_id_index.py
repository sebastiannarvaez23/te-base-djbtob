from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logging_operations', '0004_uuid_actor_ids'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='warehouseevent',
            index=models.Index(fields=['reference_id', '-created_at'], name='warehouse_e_ref_id_idx'),
        ),
    ]
