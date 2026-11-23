from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('testimonial', '0005_testimonial_prompt_timing'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testimonial',
            name='author',
            field=models.ForeignKey(
                help_text='Company user who wrote the testimonial.',
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='testimonials',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Author',
            ),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='revoked_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When a newer signed quote superseded this document.',
                null=True,
                verbose_name='Revoked at',
            ),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='superseded_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='supersedes',
                to='testimonial.testimonial',
                verbose_name='Superseded by',
            ),
        ),
        migrations.AddConstraint(
            model_name='testimonial',
            constraint=models.UniqueConstraint(
                condition=models.Q(('revoked_at__isnull', True)),
                fields=('author',),
                name='uniq_tst_live_author',
            ),
        ),
        migrations.AddIndex(
            model_name='testimonial',
            index=models.Index(
                fields=['author', 'revoked_at'],
                name='idx_tst_author_revoked',
            ),
        ),
        migrations.RemoveField(
            model_name='testimonialpromptsettings',
            name='prompt_generation',
        ),
        migrations.RemoveField(
            model_name='testimonialpromptreceipt',
            name='last_seen_generation',
        ),
    ]
