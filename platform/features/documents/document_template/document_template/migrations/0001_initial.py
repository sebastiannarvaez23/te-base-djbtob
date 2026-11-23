import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='DocumentTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('code', models.CharField(help_text='Machine-readable identifier (e.g. INVOICE_DEFAULT, REMISSION_V2).', max_length=80, unique=True, verbose_name='Unique code')),
                ('name', models.CharField(help_text='Human-readable label shown in the admin UI.', max_length=200, verbose_name='Template name')),
                ('kind', models.CharField(db_index=True, help_text='Free-form document type tag (e.g. INVOICE, REMISSION, QUOTATION, PURCHASE_ORDER).', max_length=50, verbose_name='Document kind')),
                ('html_template', models.TextField(help_text='Jinja2/Django-style HTML template. Use {{ variable }} for dynamic content.', verbose_name='HTML template')),
                ('mock_data', models.JSONField(blank=True, default=dict, help_text='JSON with sample values for template variables, used for preview emulation.', verbose_name='Mock data')),
                ('description', models.TextField(blank=True, default='', help_text='Internal notes about when and how this template is used.', verbose_name='Description')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
            ],
            options={
                'verbose_name': 'Document template',
                'verbose_name_plural': 'Document templates',
                'db_table': 'documents_document_templates',
                'ordering': ['kind', 'code'],
            },
        ),
    ]
