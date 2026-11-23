"""Seed the ONBOARDING_RESUME magic-link email template.

Sent on /onboarding/start/ so the user can pick up registration from
any device by clicking the link in their inbox.

Idempotent via ``get_or_create``.
"""

from django.db import migrations


_TEMPLATE_CODE = 'ONBOARDING_RESUME'

_SUBJECT = 'Continúa tu registro en la base'

_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color:#222; background:#f7f7f7; padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px; margin:0 auto; background:#fff; border-radius:8px; padding:32px;">
    <tr><td>
      <h2 style="margin:0 0 16px 0;">Tu registro est&aacute; pendiente</h2>
      <p>Iniciaste el registro de tu empresa en <strong>la base</strong>. Puedes retomarlo desde cualquier dispositivo durante los pr&oacute;ximos <strong>{{ expires_in_days }} d&iacute;as</strong>.</p>
      <p style="text-align:center; margin:32px 0;">
        <a href="{{ resume_url }}" style="background:#1f6feb; color:#fff; padding:12px 24px; border-radius:6px; text-decoration:none; display:inline-block;">Continuar mi registro</a>
      </p>
      <p style="font-size:12px; color:#666;">Si el bot&oacute;n no funciona, copia este enlace en tu navegador:<br>{{ resume_url }}</p>
      <hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
      <p style="font-size:12px; color:#666;">
        &iquest;No iniciaste este registro? Puedes ignorar este correo o escribir a
        <a href="mailto:{{ support_email }}">{{ support_email }}</a>.
      </p>
      <p style="font-size:12px; color:#999;">&copy; {{ current_year }} la base</p>
    </td></tr>
  </table>
</body>
</html>
"""

_PLAIN = """\
Tu registro esta pendiente.

Iniciaste el registro de tu empresa en la base. Puedes retomarlo
desde cualquier dispositivo durante los proximos {{ expires_in_days }} dias
abriendo el siguiente enlace:

{{ resume_url }}

Si no iniciaste este registro puedes ignorar este correo o escribirnos a
{{ support_email }}.

(c) {{ current_year }} la base
"""

_MOCK_DATA = {
    'resume_url': 'https://warehouse-anywhere.com/onboarding/resume?token=sample',
    'expires_in_days': 7,
    'support_email': 'soporte@warehouse-anywhere.com',
    'current_year': 2026,
}

_DESCRIPTION = (
    'Sent on /onboarding/start/ so the user can resume an in-progress '
    'registration from email. The link points to ONB_RESUME_URL with '
    '?token=<raw>; the resume token is one-shot.'
)


def seed(apps, schema_editor):
    EmailTemplate = apps.get_model('email_template', 'EmailTemplate')
    EmailTemplate.objects.get_or_create(
        code=_TEMPLATE_CODE,
        defaults={
            'name': 'Onboarding resume link',
            'subject': _SUBJECT,
            'body': _PLAIN,
            'html_template': _HTML,
            'mock_data': _MOCK_DATA,
            'description': _DESCRIPTION,
            'is_active': True,
        },
    )


def unseed(apps, schema_editor):
    EmailTemplate = apps.get_model('email_template', 'EmailTemplate')
    EmailTemplate.objects.filter(code=_TEMPLATE_CODE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('email_template', '0004_seed_email_confirm_template'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
