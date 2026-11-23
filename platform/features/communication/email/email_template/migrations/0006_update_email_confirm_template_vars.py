"""Update the EMAIL_CONFIRM template body, html and mock_data to the
canonical variable names used by the dispatcher (`confirmation_url` and
`expiration_time`) and to the base brand.

The original 0004 seed used ``confirm_url`` / ``expires_in_hours`` and the
previous product brand. ``get_or_create`` in 0004 means existing rows
were never refreshed when the dispatcher contract changed, so emails went
out with empty placeholders. This migration force-updates the row so any
already-seeded environment catches up.

Idempotent: re-running yields the same row state.
"""

from django.db import migrations


_TEMPLATE_CODE = 'EMAIL_CONFIRM'

_SUBJECT = 'Confirma tu correo en la base'

_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color:#222; background:#f7f7f7; padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px; margin:0 auto; background:#fff; border-radius:8px; padding:32px;">
    <tr><td>
      <h2 style="margin:0 0 16px 0;">Hola, {{ user_name }}</h2>
      <p>Gracias por registrar tu empresa en <strong>la base</strong>.</p>
      <p>Para activar tu cuenta y poder iniciar sesi&oacute;n, confirma tu correo electr&oacute;nico dentro de las pr&oacute;ximas <strong>{{ expiration_time }} horas</strong>:</p>
      <p style="text-align:center; margin:32px 0;">
        <a href="{{ confirmation_url }}" style="background:#1f6feb; color:#fff; padding:12px 24px; border-radius:6px; text-decoration:none; display:inline-block;">Confirmar mi correo</a>
      </p>
      <p style="font-size:12px; color:#666;">Si el bot&oacute;n no funciona, copia este enlace en tu navegador:<br>{{ confirmation_url }}</p>
      <hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
      <p style="font-size:12px; color:#666;">
        &iquest;No solicitaste esta cuenta? Puedes ignorar este correo o escribir a
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

Gracias por registrar tu empresa en la base.

Para activar tu cuenta, confirma tu correo electronico dentro de las proximas
{{ expiration_time }} horas abriendo el siguiente enlace:

{{ confirmation_url }}

Si no solicitaste esta cuenta puedes ignorar este correo o escribirnos a
{{ support_email }}.

(c) {{ current_year }} la base
"""

_MOCK_DATA = {
    'user_name': 'Ana Gomez',
    'confirmation_url': 'https://base.local/confirm-email?token=sample',
    'expiration_time': 24,
    'support_email': 'soporte@base.local',
    'current_year': 2026,
}


def update(apps, schema_editor):
    EmailTemplate = apps.get_model('email_template', 'EmailTemplate')
    EmailTemplate.objects.filter(code=_TEMPLATE_CODE).update(
        subject=_SUBJECT,
        body=_PLAIN,
        html_template=_HTML,
        mock_data=_MOCK_DATA,
        is_active=True,
    )


def noop(apps, schema_editor):
    # No-op reverse: the previous state was inconsistent across environments
    # (some had `confirm_url`, others had `confirmation_url` due to manual
    # edits), so there is no single previous body to restore. Re-running
    # 0004's seed is also unsafe because it uses get_or_create.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('email_template', '0005_seed_onboarding_resume_template'),
    ]

    operations = [
        migrations.RunPython(update, noop),
    ]
