"""Ensure SUB_INVOICING email HTML shows applied promotion fields."""

from django.core.management.base import BaseCommand

from platform.features.communication.email.email_template.models import EmailTemplate

_PROMO_MARKER = '<!-- promotion-annex -->'

_PROMO_BLOCK = """
                    <!-- promotion-annex -->
                    {% if has_promotion %}
                    <tr>
                        <td style="padding:16px 32px 0;">
                            <table width="100%" cellpadding="0" cellspacing="0"
                                   style="background:#fff8f6;border:1px solid #ffcdd2;border-radius:8px;">
                                <tr>
                                    <td style="padding:14px 16px;font-size:13px;color:#424242;line-height:1.5;">
                                        <strong style="color:#c62828;">Promoción aplicada</strong><br>
                                        Bono {{ promotion_serial }}
                                        {% if promotion_voucher_type %} ({{ promotion_voucher_type }}){% endif %}
                                        {% if promotion_discount_amount %}
                                        — descuento ${{ promotion_discount_amount }}
                                        {% endif %}
                                        {% if promotion_annex %}
                                        <br><span style="color:#757575;">{{ promotion_annex }}</span>
                                        {% endif %}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    {% endif %}
"""


class Command(BaseCommand):
    help = 'Patch SUB_INVOICING html_template with promotion annex block (idempotent).'

    def handle(self, *args, **options):
        tpl = EmailTemplate.objects.filter(code='SUB_INVOICING').first()
        if tpl is None:
            self.stderr.write(self.style.ERROR('SUB_INVOICING template not found'))
            return

        html = tpl.html_template or ''
        if _PROMO_MARKER in html:
            self.stdout.write(self.style.SUCCESS('SUB_INVOICING already has promotion block'))
            return

        anchor = '<!-- FOOTER -->'
        if anchor in html:
            html = html.replace(anchor, _PROMO_BLOCK + '\n                    ' + anchor, 1)
        else:
            # Fallback: insert before closing body
            html = html.replace('</body>', _PROMO_BLOCK + '\n</body>', 1)

        mock = dict(tpl.mock_data or {})
        mock.setdefault('has_promotion', True)
        mock.setdefault('promotion_serial', 'WLGX-DSC-PREVIEW')
        mock.setdefault('promotion_voucher_type', 'DISCOUNT')
        mock.setdefault('promotion_discount_amount', 20)
        mock.setdefault('promotion_annex', 'Bono promocional aplicado: WLGX-DSC-PREVIEW')

        tpl.html_template = html
        tpl.mock_data = mock
        tpl.save(update_fields=['html_template', 'mock_data', 'updated_at'])
        self.stdout.write(self.style.SUCCESS('SUB_INVOICING updated with promotion annex'))
