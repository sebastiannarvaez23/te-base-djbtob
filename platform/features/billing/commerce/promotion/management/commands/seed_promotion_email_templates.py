"""Seed email templates for promotion vouchers (admin + public purchase)."""

from django.core.management.base import BaseCommand

from platform.features.communication.email.email_template.models import EmailTemplate

TEMPLATES = [
    {
        'code': 'GIFT_VOUCHER',
        'name': 'Bono regalo — destinatario',
        'subject': '¡Te regalaron un bono de la base!',
        'description': 'Enviado al destinatario tras compra pública o creación admin COMPANY.',
        'mock_data': {
            'gift_value': '$600.000 COP',
            'redeem_url': 'https://app.base.local/redeem/WLGX-GFT-9P4M7X',
            'sender_name': 'Carlos Rodríguez',
            'usage_limit': '1 uso',
            'company_name': 'Logística Andina S.A.S.',
            'current_year': '2026',
            'gift_message': (
                'Este bono regalo puede redimirse una única vez para activar la suscripción indicada. '
                'Una vez utilizado no podrá transferirse ni reutilizarse. '
                'Redímelo antes de la fecha de vencimiento para disfrutar de todos los beneficios de BASE.'
            ),
            'voucher_code': 'WLGX-GFT-9P4M7X',
            'support_email': 'soporte@base.local',
            'recipient_name': 'Laura Gómez',
            'expiration_date': '31/12/2026',
            'subscription_name': 'Professional',
            'subscription_duration': '12 meses',
        },
        'html_template': '''
<p>Hola {{ recipient_name }},</p>
<p><strong>{{ sender_name }}</strong> de <strong>{{ company_name }}</strong> te regaló un bono de la base.</p>
<p><em>{{ gift_message }}</em></p>
<p><strong>Código:</strong> {{ voucher_code }}</p>
<p><strong>Valor:</strong> {{ gift_value }}</p>
<p><strong>Plan:</strong> {{ subscription_name }} — {{ subscription_duration }}</p>
<p><strong>Vigencia:</strong> {{ expiration_date }} ({{ usage_limit }})</p>
<p><a href="{{ redeem_url }}">Canjear bono</a></p>
<p>¿Necesitas ayuda? Escríbenos a {{ support_email }}</p>
<p>© {{ current_year }} la base</p>
'''.strip(),
    },
    {
        'code': 'DISCOUNT_VOUCHER',
        'name': 'Bono descuento — destinatario',
        'subject': 'Tienes un bono de descuento de la base',
        'description': 'Enviado al destinatario tras compra pública o creación admin COMPANY.',
        'mock_data': {
            'discount': '25%',
            'redeem_url': 'https://app.base.local/redeem/WLGX-DSC-8KX4P2',
            'sender_name': 'Carlos Rodríguez',
            'usage_limit': '1 uso',
            'company_name': 'Logística Andina S.A.S.',
            'current_year': '2026',
            'voucher_code': 'WLGX-DSC-8KX4P2',
            'discount_type': 'Porcentaje',
            'subscriptions': (
                "<ul style='padding-left:20px;margin:0;color:#1e3a5f;font-size:14px;'>"
                '<li>Professional</li><li>Enterprise</li></ul>'
            ),
            'support_email': 'soporte@base.local',
            'recipient_name': 'Laura Gómez',
            'expiration_date': '31/12/2026',
            'maximum_discount': '$150.000 COP',
            'minimum_purchase': '$300.000 COP',
            'discount_conditions': (
                'Válido únicamente para nuevas compras o renovaciones de las suscripciones elegibles. '
                'No acumulable con otras promociones. '
                'El descuento podrá utilizarse una sola vez antes de su fecha de vencimiento.'
            ),
        },
        'html_template': '''
<p>Hola {{ recipient_name }},</p>
<p><strong>{{ sender_name }}</strong> te envió un bono de descuento de la base para <strong>{{ company_name }}</strong>.</p>
<p><strong>Código:</strong> {{ voucher_code }}</p>
<p><strong>Descuento:</strong> {{ discount }} ({{ discount_type }})</p>
<p><strong>Vigencia:</strong> {{ expiration_date }} ({{ usage_limit }})</p>
<p><strong>Descuento máximo:</strong> {{ maximum_discount }}</p>
<p><strong>Compra mínima:</strong> {{ minimum_purchase }}</p>
{{ subscriptions|safe }}
<p>{{ discount_conditions }}</p>
<p><a href="{{ redeem_url }}">Canjear bono</a></p>
<p>¿Necesitas ayuda? Escríbenos a {{ support_email }}</p>
<p>© {{ current_year }} la base</p>
'''.strip(),
    },
    {
        'code': 'GIFT_VOUCHER_PURCHASE',
        'name': 'Compra pública — bono regalo destinatario',
        'subject': 'Te regalaron la base',
        'description': 'Enviado al destinatario tras una compra pública de bono regalo.',
        'mock_data': {
            'serial': 'WLGX-GFT-PUBLIC01',
            'subscription_names': 'Profesional',
            'benefit_months': 3,
            'redeem_valid_until': '31/12/2026',
            'buyer_name': 'María López',
            'recipient_name': 'Carlos Ruiz',
            'recipient_message': '¡Éxitos con tu almacén!',
            'current_year': 2026,
        },
        'html_template': '''
<p>Hola {{ recipient_name }},</p>
<p><strong>{{ buyer_name }}</strong> te regaló un bono de la base.</p>
{% if recipient_message %}<p><em>"{{ recipient_message }}"</em></p>{% endif %}
<p><strong>Serial:</strong> {{ serial }}</p>
<p><strong>Plan:</strong> {{ subscription_names }}</p>
<p><strong>Meses de beneficio:</strong> {{ benefit_months }}</p>
<p><strong>Canjea antes de:</strong> {{ redeem_valid_until }}</p>
<p>© {{ current_year }} la base</p>
'''.strip(),
    },
    {
        'code': 'DISCOUNT_VOUCHER_PURCHASE',
        'name': 'Compra pública — bono descuento destinatario',
        'subject': 'Te regalaron un descuento de la base',
        'description': 'Enviado al destinatario tras una compra pública de bono descuento.',
        'mock_data': {
            'serial': 'WLGX-DSC-PUBLIC01',
            'subscription_names': 'Profesional',
            'discount_percent': 20,
            'discount_duration_months': 3,
            'redeem_valid_until': '31/12/2026',
            'buyer_name': 'María López',
            'recipient_name': 'Carlos Ruiz',
            'current_year': 2026,
        },
        'html_template': '''
<p>Hola {{ recipient_name }},</p>
<p><strong>{{ buyer_name }}</strong> te envió un bono de descuento de la base.</p>
<p><strong>Serial:</strong> {{ serial }}</p>
<p><strong>Plan:</strong> {{ subscription_names }}</p>
<p><strong>Descuento:</strong> {{ discount_percent }}% por {{ discount_duration_months }} renovación(es)</p>
<p><strong>Canjea antes de:</strong> {{ redeem_valid_until }}</p>
<p>© {{ current_year }} la base</p>
'''.strip(),
    },
    {
        'code': 'VOUCHER_PURCHASED',
        'name': 'Compra pública — confirmación comprador con factura',
        'subject': 'Confirmación de compra de bono de la base',
        'description': 'Recibo con factura adjunta enviado al comprador tras checkout público.',
        'mock_data': {
            'buyer_name': 'Carlos Rodríguez',
            'total_paid': '$100.000 COP',
            'company_name': 'Logística Andina S.A.S.',
            'current_year': '2026',
            'order_number': 'ORD-20260709-000158',
            'voucher_code': 'WLGX-DSC-8KX4P2',
            'voucher_type': 'Bono Descuento',
            'purchase_date': '09/07/2026 10:42 AM',
            'support_email': 'soporte@base.local',
            'voucher_value': '$100.000 COP',
            'invoice_number': 'FE-2026-0012458',
            'payment_status': 'Pagado',
            'recipient_name': 'Laura Gómez',
            'recipient_email': 'laura.gomez@empresa.com',
            'purchase_detail_url': 'https://app.base.local/public/gift-voucher/success?serial=WLGX-DSC-8KX4P2',
        },
        'html_template': '''
<p>Hola {{ buyer_name }},</p>
<p>Confirmamos tu compra de <strong>{{ voucher_type }}</strong>.</p>
<p><strong>Pedido:</strong> {{ order_number }}</p>
<p><strong>Factura:</strong> {{ invoice_number }}</p>
<p><strong>Total pagado:</strong> {{ total_paid }}</p>
<p><strong>Estado:</strong> {{ payment_status }}</p>
<p><strong>Código del bono:</strong> {{ voucher_code }}</p>
<p>Enviamos el bono a <strong>{{ recipient_name }}</strong> ({{ recipient_email }}).</p>
<p><a href="{{ purchase_detail_url }}">Ver detalle de compra</a></p>
<p>La factura va adjunta en PDF.</p>
<p>¿Necesitas ayuda? Escríbenos a {{ support_email }}</p>
<p>© {{ current_year }} la base</p>
'''.strip(),
    },
]


class Command(BaseCommand):
    help = 'Seed promotion email templates (admin + public purchase).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only print what would be created or updated.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        created = 0
        updated = 0
        skipped = 0

        for item in TEMPLATES:
            code = item['code']
            existing = EmailTemplate.objects.filter(code=code).first()
            if existing and dry_run:
                self.stdout.write(f'would upsert {code}')
                continue
            if existing:
                changed = False
                for field in ('name', 'subject', 'description', 'html_template', 'mock_data'):
                    if getattr(existing, field) != item[field]:
                        if not dry_run:
                            setattr(existing, field, item[field])
                        changed = True
                if changed:
                    if not dry_run:
                        existing.is_active = True
                        existing.save()
                    updated += 1
                    self.stdout.write(self.style.WARNING(f'updated {code}'))
                else:
                    skipped += 1
                    self.stdout.write(f'skip {code} (unchanged)')
                continue

            if dry_run:
                self.stdout.write(f'would create {code}')
                created += 1
                continue

            EmailTemplate.objects.create(
                code=code,
                name=item['name'],
                subject=item['subject'],
                description=item['description'],
                html_template=item['html_template'],
                mock_data=item['mock_data'],
                is_active=True,
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(f'created {code}'))

        self.stdout.write(
            self.style.SUCCESS(f'done: created={created} updated={updated} skipped={skipped}'),
        )
