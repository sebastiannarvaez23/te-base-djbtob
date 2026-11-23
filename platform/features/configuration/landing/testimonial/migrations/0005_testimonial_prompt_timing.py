from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testimonial', '0004_testimonial_pending_reprompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='testimonialpromptsettings',
            name='first_appearance_days',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Days to wait after the user first reaches the app before the first prompt. 0 = immediately.',
                verbose_name='First appearance (days)',
            ),
        ),
        migrations.AddField(
            model_name='testimonialpromptsettings',
            name='login_delay_seconds',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Seconds to wait after login before showing the prompt.',
                verbose_name='Login delay (seconds)',
            ),
        ),
        migrations.AddField(
            model_name='testimonialpromptreceipt',
            name='first_seen_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the user first became a candidate for the prompt clock.',
                null=True,
                verbose_name='First seen at',
            ),
        ),
        migrations.AddConstraint(
            model_name='testimonialpromptsettings',
            constraint=models.CheckConstraint(
                check=models.Q(first_appearance_days__lte=365),
                name='chk_tst_prompt_first_appearance_days',
            ),
        ),
        migrations.AddConstraint(
            model_name='testimonialpromptsettings',
            constraint=models.CheckConstraint(
                check=models.Q(login_delay_seconds__lte=300),
                name='chk_tst_prompt_login_delay_seconds',
            ),
        ),
    ]
