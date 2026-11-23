import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('company', '0005_alter_company_table_alter_domain_table'),
        ('invoice', '0002_alter_invoice_table'),
        ('payment_method', '0004_paymentmethod_idx_pm_company_created'),
    ]

    operations = [
        migrations.CreateModel(
            name='Charge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('idempotency_key', models.CharField(blank=True, max_length=128, null=True, unique=True, verbose_name='Clave de idempotencia')),
                ('gateway_provider', models.CharField(help_text='Identificador del adapter usado (simulator, stripe, wompi, ...).', max_length=50, verbose_name='Proveedor de pago')),
                ('gateway_charge_id', models.CharField(blank=True, default='', max_length=255, verbose_name='Id del cargo en el proveedor')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Monto')),
                ('currency', models.CharField(default='COP', max_length=3, verbose_name='Moneda (ISO 4217)')),
                ('method_type', models.CharField(
                    choices=[
                        ('card', 'Tarjeta'),
                        ('bank_transfer', 'Transferencia bancaria'),
                        ('pse', 'PSE'),
                        ('wallet', 'Billetera digital'),
                        ('voucher', 'Recaudo en efectivo'),
                        ('bnpl', 'Pago a cuotas'),
                        ('crypto', 'Criptomoneda'),
                        ('other', 'Otro'),
                    ],
                    default='card', max_length=20, verbose_name='Tipo de método',
                )),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='Descripción')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pendiente'),
                        ('processing', 'Procesando'),
                        ('requires_action', 'Requiere acción del usuario'),
                        ('authorized', 'Autorizado'),
                        ('captured', 'Capturado'),
                        ('failed', 'Fallido'),
                        ('canceled', 'Cancelado'),
                        ('refunded', 'Reembolsado'),
                        ('partially_refunded', 'Reembolsado parcialmente'),
                        ('disputed', 'En disputa'),
                    ],
                    default='pending', max_length=20, verbose_name='Estado',
                )),
                ('next_action_type', models.CharField(
                    blank=True, default='',
                    choices=[
                        ('redirect', 'Redirección'),
                        ('display_qr', 'Mostrar QR'),
                        ('display_voucher', 'Mostrar comprobante'),
                        ('await_webhook', 'Esperar webhook'),
                    ],
                    max_length=20, verbose_name='Tipo de acción siguiente',
                )),
                ('next_action_url', models.URLField(blank=True, default='', verbose_name='URL de acción siguiente')),
                ('failure_code', models.CharField(blank=True, default='', max_length=64, verbose_name='Código de fallo')),
                ('failure_message', models.CharField(blank=True, default='', max_length=255, verbose_name='Mensaje de fallo')),
                ('authorized_at', models.DateTimeField(blank=True, null=True, verbose_name='Autorizado en')),
                ('captured_at', models.DateTimeField(blank=True, null=True, verbose_name='Capturado en')),
                ('canceled_at', models.DateTimeField(blank=True, null=True, verbose_name='Cancelado en')),
                ('refunded_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Monto reembolsado')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='Metadatos')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='charges',
                    to='company.company',
                    verbose_name='Empresa',
                )),
                ('invoice', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='charges',
                    to='invoice.invoice',
                    verbose_name='Factura asociada',
                )),
                ('payment_method', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='charges',
                    to='payment_method.paymentmethod',
                    verbose_name='Método de pago',
                )),
            ],
            options={
                'verbose_name': 'Cargo',
                'verbose_name_plural': 'Cargos',
                'db_table': 'billing_charges',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='charge',
            index=models.Index(fields=['company', '-created_at'], name='idx_charge_company_created'),
        ),
        migrations.AddIndex(
            model_name='charge',
            index=models.Index(fields=['gateway_provider', 'gateway_charge_id'], name='idx_charge_gateway_ref'),
        ),
        migrations.AddIndex(
            model_name='charge',
            index=models.Index(fields=['status'], name='idx_charge_status'),
        ),

        migrations.CreateModel(
            name='ChargeAttempt',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('operation', models.CharField(
                    choices=[
                        ('create', 'Crear cargo'),
                        ('confirm', 'Confirmar'),
                        ('capture', 'Capturar'),
                        ('cancel', 'Cancelar'),
                        ('refund', 'Reembolsar'),
                        ('fetch', 'Consultar'),
                    ],
                    max_length=20, verbose_name='Operación',
                )),
                ('gateway_provider', models.CharField(max_length=50, verbose_name='Proveedor')),
                ('request_payload', models.JSONField(blank=True, default=dict, verbose_name='Payload de salida')),
                ('response_payload', models.JSONField(blank=True, default=dict, verbose_name='Payload de respuesta')),
                ('result', models.CharField(
                    choices=[
                        ('succeeded', 'Exitoso'),
                        ('failed', 'Fallido'),
                        ('pending', 'Pendiente'),
                    ],
                    max_length=20, verbose_name='Resultado',
                )),
                ('error_message', models.CharField(blank=True, default='', max_length=512, verbose_name='Error')),
                ('attempted_at', models.DateTimeField(auto_now_add=True, verbose_name='Intentado en')),
                ('charge', models.ForeignKey(
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='attempts',
                    to='payments.charge',
                    verbose_name='Cargo',
                )),
            ],
            options={
                'verbose_name': 'Intento de cargo',
                'verbose_name_plural': 'Intentos de cargo',
                'db_table': 'billing_charge_attempts',
                'ordering': ['-attempted_at'],
            },
        ),
        migrations.AddIndex(
            model_name='chargeattempt',
            index=models.Index(fields=['charge', '-attempted_at'], name='idx_attempt_charge_time'),
        ),

        migrations.CreateModel(
            name='WebhookInbox',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='Id')),
                ('provider', models.CharField(max_length=50, verbose_name='Proveedor')),
                ('external_event_id', models.CharField(max_length=255, verbose_name='Id externo del evento')),
                ('event_type', models.CharField(blank=True, default='', max_length=100, verbose_name='Tipo de evento')),
                ('payload', models.JSONField(default=dict, verbose_name='Payload')),
                ('signature', models.CharField(blank=True, default='', max_length=512, verbose_name='Firma')),
                ('signature_verified', models.BooleanField(default=False, verbose_name='Firma verificada')),
                ('received_at', models.DateTimeField(auto_now_add=True, verbose_name='Recibido en')),
                ('processed_at', models.DateTimeField(blank=True, null=True, verbose_name='Procesado en')),
                ('processing_error', models.CharField(blank=True, default='', max_length=512, verbose_name='Error de procesamiento')),
                ('charge', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='webhook_events',
                    to='payments.charge',
                    verbose_name='Cargo relacionado',
                )),
            ],
            options={
                'verbose_name': 'Webhook entrante',
                'verbose_name_plural': 'Webhooks entrantes',
                'db_table': 'billing_webhook_inbox',
                'ordering': ['-received_at'],
                'unique_together': {('provider', 'external_event_id')},
            },
        ),
        migrations.AddIndex(
            model_name='webhookinbox',
            index=models.Index(fields=['processed_at'], name='idx_inbox_processed_at'),
        ),
        migrations.AddIndex(
            model_name='webhookinbox',
            index=models.Index(fields=['provider', '-received_at'], name='idx_inbox_provider_time'),
        ),

        migrations.CreateModel(
            name='IdempotencyKey',
            fields=[
                ('key', models.CharField(max_length=128, primary_key=True, serialize=False, verbose_name='Clave')),
                ('scope', models.CharField(max_length=100, verbose_name='Operación protegida')),
                ('request_hash', models.CharField(max_length=64, verbose_name='Hash del request (sha256)')),
                ('response_payload', models.JSONField(blank=True, default=dict, verbose_name='Respuesta cacheada')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ('expires_at', models.DateTimeField(verbose_name='Expira en')),
            ],
            options={
                'verbose_name': 'Clave de idempotencia',
                'verbose_name_plural': 'Claves de idempotencia',
                'db_table': 'billing_idempotency_keys',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='idempotencykey',
            index=models.Index(fields=['scope', '-created_at'], name='idx_idem_scope_time'),
        ),
        migrations.AddIndex(
            model_name='idempotencykey',
            index=models.Index(fields=['expires_at'], name='idx_idem_expires_at'),
        ),
    ]
