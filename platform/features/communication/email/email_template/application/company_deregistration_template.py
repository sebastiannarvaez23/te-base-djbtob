"""Canonical COMPANY_DEREGISTRATION HTML — email-client safe (no SVG).

Gmail/Outlook strip inline SVG and often drop ``linear-gradient``; the
stored admin HTML used both, so the header arrived as a dark block with an
empty rounded square. This markup matches WELCOME_USER: solid bgcolor,
emoji illustration, inline styles, Django variables on a single line.
"""

TEMPLATE_CODE = 'COMPANY_DEREGISTRATION'

HTML_TEMPLATE = '''\
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width">
    <title>Empresa dada de baja - BASE</title>
</head>
<body style="margin:0;padding:0;background:#f8f8f8;font-family:Arial,Helvetica,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
        <tr>
            <td align="center" style="padding:40px 16px;">
                <table width="600" cellpadding="0" cellspacing="0" border="0" role="presentation"
                    style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;border:1px solid #e8e8e8;">
                    <tr>
                        <td bgcolor="#313131" align="center"
                            style="background-color:#313131;background:linear-gradient(135deg,#313131,#4a4a4a);padding:36px 40px;text-align:center;">
                            <span style="color:#ffffff;font-weight:700;font-size:18px;letter-spacing:0.4px;">BASE</span>
                            <div style="margin-top:20px;line-height:1;">
                                <span style="font-size:30px;">&#127970;</span>
                            </div>
                            <h1 style="color:#ffffff;font-size:24px;margin:16px 0 0;font-weight:700;">Empresa dada de baja</h1>
                            <p style="color:#d0d0d0;font-size:14px;margin:8px 0 0;">Información importante sobre tu empresa</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px 40px 0;">
                            <p style="font-size:15px;color:#313131;margin:0 0 16px;">Hola <strong>{{ user_name }}</strong>,</p>
                            <p style="font-size:14px;color:#777777;line-height:1.7;margin:0;">
                                Te informamos que la empresa
                                <strong style="color:#313131;">{{ company_name }}</strong>
                                ha sido dada de baja de la plataforma
                                <strong style="color:#313131;">BASE</strong>.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:28px 40px 24px;">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"
                                style="background:#f8f8f8;border:1px solid #e8e8e8;border-radius:12px;">
                                <tr>
                                    <td style="padding:18px 20px;">
                                        <p style="margin:0 0 14px;font-size:12px;color:#999999;text-transform:uppercase;font-weight:600;letter-spacing:0.5px;">
                                            Información de la empresa
                                        </p>
                                        <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
                                            <tr>
                                                <td style="padding:6px 0;font-size:13px;color:#999999;">Empresa</td>
                                                <td align="right" style="padding:6px 0;font-size:13px;color:#313131;font-weight:600;">{{ company_name }}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding:6px 0;font-size:13px;color:#999999;">Identificación</td>
                                                <td align="right" style="padding:6px 0;font-size:13px;color:#313131;">{{ company_document }}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding:6px 0;font-size:13px;color:#999999;">Fecha de baja</td>
                                                <td align="right" style="padding:6px 0;font-size:13px;color:#313131;">{{ deactivation_date }}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding:6px 0;font-size:13px;color:#999999;">Motivo</td>
                                                <td align="right" style="padding:6px 0;font-size:13px;color:#313131;">{{ deactivation_reason }}</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 40px 24px;">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"
                                style="background:#fff4f4;border-radius:12px;border:1px solid #fecaca;">
                                <tr>
                                    <td style="padding:18px 20px;text-align:center;">
                                        <p style="margin:0 0 8px;font-size:22px;line-height:1;">&#9888;&#65039;</p>
                                        <p style="margin:10px 0 4px;font-size:13px;color:#7f1d1d;font-weight:600;">
                                            Acceso a la empresa deshabilitado
                                        </p>
                                        <p style="margin:0;font-size:12px;color:#991b1b;line-height:1.6;">
                                            Los usuarios asociados a esta empresa ya no podrán acceder a sus módulos y
                                            funcionalidades en BASE.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 40px 24px;">
                            <p style="font-size:13px;color:#777777;line-height:1.7;margin:0;">
                                Si consideras que esta acción fue realizada por error o necesitas información adicional
                                sobre el estado de la empresa, puedes comunicarte con nuestro equipo de soporte.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:24px 40px;text-align:center;font-size:13px;color:#999999;">
                            ¿Necesitas ayuda?<br>
                            <a href="mailto:{{ support_email }}" style="color:#e53935;text-decoration:none;font-weight:500;">{{ support_email }}</a>
                        </td>
                    </tr>
                    <tr>
                        <td bgcolor="#f8f8f8" style="background-color:#f8f8f8;padding:24px;text-align:center;border-top:1px solid #e8e8e8;">
                            <strong style="color:#313131;">BASE</strong><br>
                            <span style="font-size:11px;color:#999999;">Plataforma de gestión de almacenes</span><br>
                            <span style="font-size:10px;color:#c8c8c8;">© {{ current_year }} Todos los derechos reservados.</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
'''.strip()
