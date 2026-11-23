from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testimonial', '0003_testimonial_prompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='testimonialpromptreceipt',
            name='pending_reprompt',
            field=models.BooleanField(
                default=False,
                help_text='When set, the client asks again even if the author already signed.',
                verbose_name='Pending reprompt',
            ),
        ),
    ]
