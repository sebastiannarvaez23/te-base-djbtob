from django.db import migrations, models


def _backfill_defaults(apps, schema_editor):
    """Set sensible defaults for existing rows so they keep working.

    Existing templates get allowed_formats=['HTML','PDF'] and a minimal
    format_configs entry for each, derived from html_template.
    """
    DocumentTemplate = apps.get_model('document_template', 'DocumentTemplate')
    for tpl in DocumentTemplate.objects.all():
        if not tpl.allowed_formats:
            tpl.allowed_formats = ['HTML', 'PDF']
        if not tpl.default_format:
            tpl.default_format = 'PDF'
        if not tpl.format_configs:
            tpl.format_configs = {
                'HTML': {'css_overrides': ''},
                'PDF': {
                    'page_size': 'letter',
                    'margin_mm': 16,
                    'header_html': '',
                    'footer_html': '',
                },
            }
        tpl.save(update_fields=['allowed_formats', 'default_format', 'format_configs'])


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('document_template', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='documenttemplate',
            name='allowed_formats',
            field=models.JSONField(
                blank=True, default=list,
                help_text='List of DocumentFormat values, e.g. ["HTML","PDF","XLSX"].',
                verbose_name='Allowed formats',
            ),
        ),
        migrations.AddField(
            model_name='documenttemplate',
            name='default_format',
            field=models.CharField(
                default='PDF', max_length=10,
                help_text='Format used when caller does not specify one. Must be in allowed_formats.',
                verbose_name='Default format',
            ),
        ),
        migrations.AddField(
            model_name='documenttemplate',
            name='format_configs',
            field=models.JSONField(
                blank=True, default=dict,
                help_text=(
                    'Object keyed by DocumentFormat. For each format in allowed_formats '
                    'a matching config must exist (see domain.format_configs schemas).'
                ),
                verbose_name='Per-format configurations',
            ),
        ),
        migrations.AddField(
            model_name='documenttemplate',
            name='is_storable',
            field=models.BooleanField(
                default=False,
                help_text='If true, generated documents are uploaded to MinIO.',
                verbose_name='Storable',
            ),
        ),
        migrations.AddField(
            model_name='documenttemplate',
            name='storage_bucket',
            field=models.CharField(
                blank=True, default='', max_length=120,
                help_text='Override MinIO bucket. Empty → default documents bucket from settings.',
                verbose_name='Storage bucket',
            ),
        ),
        migrations.AddField(
            model_name='documenttemplate',
            name='storage_path_template',
            field=models.CharField(
                blank=True, default='', max_length=500,
                help_text=(
                    'Interpolated path. Must include {{ uuid }} or {{ timestamp }} for uniqueness. '
                    'System vars: {{ uuid }}, {{ timestamp }}, {{ year }}, {{ month }}, {{ day }}, {{ ext }}.'
                ),
                verbose_name='Storage path template',
            ),
        ),
        migrations.RunPython(_backfill_defaults, reverse_code=_noop_reverse),
    ]
