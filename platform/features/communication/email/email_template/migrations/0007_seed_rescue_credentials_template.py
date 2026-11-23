"""Seed the RESCUE_CREDENTIALS email template used by the password-reset flow.

Idempotent via ``get_or_create``. The link points to PASSWORD_RESET_URL
with ?token=<raw>; the recovery token is single-use and short-lived.
"""

from django.db import migrations


_TEMPLATE_CODE = 'RESCUE_CREDENTIALS'

_SUBJECT = 'Recupera tu contraseña en la base'

_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color:#222; background:#f7f7f7; padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px; margin:0 auto; background:#fff; border-radius:8px; padding:32px;">
    <tr><td>
      <h2 style="margin:0 0 16px 0;">Hola, {{ user_name }}</h2>
      <p>Recibimos una solicitud para restablecer tu contrase&ntilde;a en <strong>la base</strong>.</p>
      <p>Haz clic en el bot&oacute;n para crear una nueva contrase&ntilde;a. El enlace caduca en <strong>{{ expiration_time }} minutos</strong> y solo puede usarse una vez.</p>
      <p style="text-align:center; margin:32px 0;">
        <a href="{{ reset_password_url }}" style="background:#1f6feb; color:#fff; padding:12px 24px; border-radius:6px; text-decoration:none; display:inline-block;">Restablecer mi contrase&ntilde;a</a>
      </p>
      <p style="font-size:12px; color:#666;">Si el bot&oacute;n no funciona, copia este enlace en tu navegador:<br>{{ reset_password_url }}</p>
      <hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
      <p style="font-size:12px; color:#666;">
        &iquest;No solicitaste este cambio? Puedes ignorar este correo &mdash; tu contrase&ntilde;a actual seguir&aacute; activa. Si crees que alguien intenta acceder a tu cuenta, escr&iacute;benos a
        <a href="mailto:{{ support_email }}">{{ support_email }}</a>.
      </p>
      <p style="font-size:12px; color:#999;">&copy; {{ current_year }} la base</p>
    </td></tr>
  </table>
</body>
</html>
"""

_PLAIN = """\
Hola, {{ user_name }}

Recibimos una solicitud para restablecer tu contrasena en la base.

Abre el siguiente enlace para crear una nueva contrasena. Caduca en
{{ expiration_time }} minutos y solo puede usarse una vez:

{{ reset_password_url }}

Si no solicitaste este cambio, puedes ignorar este correo. Tu contrasena
actual seguira activa. Si crees que alguien intenta acceder a tu cuenta,
escribenos a {{ support_email }}.

(c) {{ current_year }} la base
"""

_MOCK_DATA = {
    'user_name': 'Ana Gomez',
    'user_email': 'ana.gomez@example.com',
    'reset_password_url': 'https://base.local/security/password-reset?token=sample',
    'expiration_time': 60,
    'support_email': 'soporte@base.local',
    'current_year': 2026,
}

_DESCRIPTION = (
    'Sent on /auth/password-reset/request/ when an account exists for the '
    'submitted email. The link points to PASSWORD_RESET_URL with ?token=<raw>; '
    'the reset token is single-use and expires after PWD_RESET_TTL_M minutes.'
)


def seed(apps, schema_editor):
    EmailTemplate = apps.get_model('email_template', 'EmailTemplate')
    EmailTemplate.objects.get_or_create(
        code=_TEMPLATE_CODE,
        defaults={
            'name': 'Password recovery',
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
        ('email_template', '0006_update_email_confirm_template_vars'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
