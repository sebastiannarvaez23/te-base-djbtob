from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('testimonial', '0002_testimonial_signature'),
    ]

    operations = [
        migrations.CreateModel(
            name='TestimonialPromptSettings',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True,
                    serialize=False, verbose_name='Id',
                )),
                ('singleton_key', models.CharField(
                    default='default', editable=False, max_length=16, unique=True,
                )),
                ('prompt_enabled', models.BooleanField(
                    default=True,
                    help_text='When off, the client never asks for a testimonial.',
                    verbose_name='Prompt enabled',
                )),
                ('frequency_days', models.PositiveSmallIntegerField(
                    default=30,
                    help_text='0 = every login until submitted; otherwise wait this many days after skip.',
                    verbose_name='Frequency (days)',
                )),
                ('ask_after_submit', models.BooleanField(
                    default=False,
                    help_text='If off, authors who already signed are not asked again.',
                    verbose_name='Ask after submit',
                )),
                ('prompt_generation', models.PositiveIntegerField(
                    default=0,
                    help_text='Bumped when admin requests testimonials again.',
                    verbose_name='Prompt generation',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
            ],
            options={
                'verbose_name': 'Testimonial prompt settings',
                'db_table': 'configuration_testimonial_prompt_settings',
            },
        ),
        migrations.AddConstraint(
            model_name='testimonialpromptsettings',
            constraint=models.CheckConstraint(
                check=models.Q(frequency_days__lte=365),
                name='chk_tst_prompt_frequency_days',
            ),
        ),
        migrations.CreateModel(
            name='TestimonialPromptReceipt',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True,
                    serialize=False, verbose_name='Id',
                )),
                ('last_seen_generation', models.PositiveIntegerField(default=0)),
                ('last_prompted_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='testimonial_prompt_receipt',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='User',
                )),
            ],
            options={
                'verbose_name': 'Testimonial prompt receipt',
                'db_table': 'configuration_testimonial_prompt_receipts',
            },
        ),
    ]
