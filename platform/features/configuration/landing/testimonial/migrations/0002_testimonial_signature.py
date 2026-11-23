from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testimonial', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='testimonial',
            name='canonical_payload',
            field=models.TextField(blank=True, default='', verbose_name='Canonical payload'),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='channel',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='content_hash',
            field=models.CharField(
                blank=True,
                default='',
                help_text='SHA-256 of the canonical quote the author signed.',
                max_length=64,
                verbose_name='Content hash',
            ),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='ip_address',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='request_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='seal',
            field=models.CharField(
                blank=True,
                default='',
                help_text='HMAC seal bound to the authenticated author.',
                max_length=64,
                verbose_name='Seal',
            ),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='seal_algorithm',
            field=models.CharField(
                blank=True, default='', max_length=32, verbose_name='Seal algorithm',
            ),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='signatory_id',
            field=models.CharField(
                blank=True, default='', max_length=64, verbose_name='Signatory id',
            ),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='signed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Signed at'),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='tenant_id',
            field=models.CharField(
                blank=True, default='', max_length=64, verbose_name='Tenant id',
            ),
        ),
        migrations.AddField(
            model_name='testimonial',
            name='user_agent',
            field=models.CharField(blank=True, default='', max_length=512),
        ),
        migrations.AddIndex(
            model_name='testimonial',
            index=models.Index(
                fields=['is_published', 'signed_at'],
                name='idx_tst_published_signed',
            ),
        ),
    ]
