"""
Sincroniza el catálogo de errores del backend hacia los frontends.

Fuente de verdad: ``core.errors.codes.ERROR_REGISTRY`` (ensamblado desde
``core.errors.domains``).
Genera ``errors.json`` (en/es) en ``base-client-web`` y ``base-admin-web``.

Uso preferido:

    python manage.py syncerrors
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

ES_OVERRIDES: dict[str, str] = {
    'AUTH_001': 'Usuario o contraseña incorrectos.',
    'AUTH_002': 'Tu rol está inactivo. Contacta al administrador.',
    'AUTH_003': 'Tu cuenta está inactiva. Contacta al administrador.',
    'AUTH_004': 'Tu sesión expiró. Vuelve a iniciar sesión.',
    'AUTH_005': 'Necesitas iniciar sesión para continuar.',
    'AUTH_006': 'Tu empresa está suspendida. Contacta al administrador.',
    'AUTH_007': 'Tu correo aún no está confirmado.',
    'AUTH_008': 'Esta aplicación de integración está deshabilitada o revocada.',
    'AUTH_009': 'El tipo de concesión OAuth no es compatible. Usa client_credentials.',
    'AUTH_010': 'Uno o más scopes solicitados no están concedidos a esta aplicación.',
    'AUTH_011': 'El código de verificación es incorrecto.',
    'AUTH_012': 'La verificación de dos factores expiró. Vuelve a iniciar sesión.',
    'AUTH_013': 'Demasiados intentos de verificación. Vuelve a iniciar sesión.',
    'AUTH_014': 'Ese dispositivo de confianza no existe o ya fue revocado.',
    'AUTH_015': 'Tu contraseña caducó. Elige una nueva para continuar.',
    'AUTH_016': 'Esa contraseña se usó recientemente. Elige una diferente.',
    'AUTH_017': 'Tu usuario quedó bloqueado por demasiados intentos fallidos. Inténtalo más tarde.',
    'AUTH_018': 'Ya tienes una sesión activa. Cierra sesión en el otro dispositivo para continuar.',
    'AUTH_019': 'Esta empresa fue dada de baja. Contacta a la base si necesitas reactivarla durante el periodo de gracia.',
    'AUTH_020': 'Llevas un rato sin usar la sesión. Vuelve a iniciar sesión.',
    'PERM_001': 'No tienes permisos suficientes para realizar esta acción.',
    'PERM_002': 'Tu rol no tiene acceso a esta funcionalidad.',
    'ROLE_001': 'El rol solicitado no existe.',
    'ROLE_002': 'Ya existe un rol con ese nombre.',
    'ROLE_003': 'Este rol no se puede eliminar porque tiene usuarios asignados.',
    'ROLE_004': 'Este rol es gestionado por la plataforma y no puede ser modificado por la empresa.',
    'SESS_001': 'La sesión solicitada no existe o ya expiró.',
    'USER_001': 'El usuario solicitado no existe.',
    'USER_002': 'Ya existe un usuario con ese nombre de usuario.',
    'USER_003': 'Ya existe un usuario con ese correo electrónico.',
    'USER_004': 'Ya existe un usuario con ese documento de identidad en la empresa.',
    'MOD_001': 'El módulo solicitado no existe.',
    'MOD_002': 'Ya existe un módulo con ese código.',
    'SEC_001': 'La sección solicitada no existe.',
    'SEC_002': 'Ya existe una sección con ese código.',
    'SEC_003': 'Esta sección está desactivada. Contacta al administrador si necesitas acceso.',
    'MOD_003': 'No se pudo eliminar el módulo: todavía hay registros que dependen de él. Revisa funcionalidades, planes o incidencias.',
    'MOD_004': 'Este módulo está desactivado. Contacta al administrador si necesitas acceso.',
    'FUNC_002': 'Ya existe una funcionalidad con esa clave.',
    'FUNC_003': 'Esta acción está desactivada. Contacta al administrador si necesitas acceso.',
    'CMP_001': 'La modalidad no corresponde a cómo se contrata la funcionalidad. Un plan va incluido; un complemento es renovación o adquisición única.',
    'CMP_002': 'Ese complemento no se incluye en el plan. Actívalo en la empresa.',
    'CMP_003': 'No se puede cambiar cómo se contrata: la funcionalidad ya está en un plan o tiene una licencia activa.',
    'CMP_004': 'Esa funcionalidad no está disponible como complemento.',
    'CMP_005': 'Esta empresa ya tiene ese complemento activo.',
    'CMP_006': 'Esa licencia de complemento no existe.',
    'CMP_007': 'Ese complemento ya no está activo.',
    'CMP_008': 'Un complemento que se suma a la suscripción necesita un servicio activo de Neurana con precio.',
    'COMP_001': 'La empresa solicitada no existe.',
    'COMP_002': 'El dominio indicado no corresponde a ninguna empresa registrada.',
    'COMP_003': 'Ya existe una empresa con ese NIT.',
    'COMP_004': 'Esta empresa ya está dada de baja. Reactívala en el periodo de gracia o espera la purga.',
    'COMP_005': 'Solo se puede reactivar una empresa cerrada que siga en el periodo de gracia.',
    'COMP_006': 'Se acabó el plazo para reactivar esta empresa. Si necesitas acceso, registra una empresa nueva.',
    'COMP_007': 'Esta empresa tiene un bloqueo legal. Resuélvelo antes de reactivar o purgar.',
    'COMP_008': 'No se puede dar de baja el tenant de plataforma. Elige una empresa cliente.',
    'COMP_009': 'La purga está bloqueada por un hold legal o porque falta la constancia de export. Resuélvelo antes de borrar el tenant.',
    'COMP_010': 'Acepta la política de baja de empresa antes de cerrar la cuenta.',
    'SUB_001': 'Tu empresa no tiene un plan de suscripción activo. Contacta al administrador.',
    'SUB_002': 'Esta funcionalidad no está incluida en tu plan actual.',
    'SUB_003': 'Has alcanzado el límite de uso de esta funcionalidad en tu plan actual.',
    'SUB_004': 'Ya tienes un cambio de plan en proceso. Podrás solicitar otro cuando se active.',
    'SUB_005': 'No se pudo asociar el cobro al período de suscripción. Reintenta o contacta a soporte.',
    'SUB_006': 'Mientras la suscripción está suspendida, solo puedes acceder a configuración de suscripción y medios de pago.',
    'SUB_007': 'No hay una suscripción suspendida que se pueda reactivar.',
    'SUB_008': 'Ese servicio del catálogo no se puede asociar al plan. Elige un servicio activo del catálogo.',
    'SUB_009': 'No se pudo leer el catálogo de servicios. Inténtalo de nuevo en un momento.',
    'RFD_001': 'Los reembolsos solo aplican durante las primeras 24 horas del plan actual.',
    'RFD_002': 'Tras un reembolso con cambio de plan debes esperar 3 meses para solicitar otro.',
    'RFD_003': 'El reembolso solo aplica si pasas al plan gratuito o a uno de menor valor.',
    'RFD_004': 'En esta vigencia no hay un cobro que se pueda devolver.',
    'RFD_005': 'Ya tienes una solicitud de reembolso en curso. Sigue ese ticket hasta que termine.',
    'RFD_006': 'El plan al que quieres cambiar no está disponible.',
    'RFD_007': 'La solicitud de reembolso no existe para tu empresa.',
    'RFD_008': 'Esta solicitud ya no está pendiente de aprobación.',
    'SLIMIT_001': 'El tope de suscripción solicitado no existe.',
    'SLIMIT_002': 'Ya existe un tope para esta funcionalidad en la suscripción indicada.',
    'INV_001': 'La factura solicitada no existe.',
    'INV_002': 'No se pudo determinar un destinatario de correo para esta factura.',
    'INV_003': 'El PDF de la factura se generó, pero el correo no pudo entregarse.',
    'EMAIL_001': 'La plantilla de correo solicitada no existe.',
    'EMAIL_002': 'Ya existe una plantilla de correo con ese código.',
    'EMAIL_003': 'La plantilla de correo está inactiva y no puede usarse para envíos.',
    'EMAIL_004': 'Ocurrió un error al renderizar la plantilla de correo.',
    'EMAIL_005': 'Ocurrió un error al intentar enviar el correo.',
    'EMAIL_006': 'El remitente de correo solicitado no existe.',
    'EMAIL_007': 'Ya existe un remitente con ese código.',
    'EMAIL_008': 'El envío de correo no está configurado en este entorno.',
    'DOC_001': 'La plantilla de documento solicitada no existe.',
    'DOC_002': 'Ya existe una plantilla de documento con ese código.',
    'DOC_003': 'La plantilla de documento está inactiva y no puede usarse.',
    'DOC_004': 'El formato solicitado no está en los formatos permitidos de la plantilla.',
    'DOC_005': 'La plantilla declara el formato como permitido, pero no tiene configuración.',
    'DOC_006': 'La configuración del formato solicitado está malformada.',
    'DOC_007': 'No hay un renderizador registrado para el formato solicitado.',
    'DOC_008': 'Ocurrió un error al renderizar el documento.',
    'DOC_009': 'Esta plantilla no está configurada para almacenamiento; persist=true no está permitido.',
    'DOC_010': 'La plantilla de ruta de almacenamiento no tiene tokens de unicidad o contiene segmentos ilegales.',
    'DOC_011': 'El formato predeterminado debe estar en los formatos permitidos.',
    'DOC_012': 'La plantilla debe permitir al menos un formato.',
    'PTYPE_001': 'El tipo de parámetro solicitado no existe.',
    'PTYPE_002': 'Ya existe un tipo de parámetro con ese código.',
    'APTYPE_001': 'El tipo de parámetro de administración solicitado no existe.',
    'APTYPE_002': 'Ya existe un tipo de parámetro de administración con ese código.',
    'APTYPE_003': (
        'No se puede eliminar el tipo: aún hay parámetros de administración '
        'asignados. Reasígnalos o elimínalos primero.'
    ),
    'APARAM_001': 'El parámetro de administración solicitado no existe.',
    'APARAM_002': 'Ya existe un parámetro de administración con ese código.',
    'APARAM_003': (
        'El tipo de dato indicado no es compatible. '
        'Tipos válidos: STRING, INT, DECIMAL, BOOL, JSON.'
    ),
    'APARAM_004': 'El valor no es compatible con el tipo de dato declarado.',
    'PARAM_001': 'El parámetro solicitado no existe.',
    'LAND_001': 'La sección del landing solicitada no existe.',
    'LAND_002': 'La clave de sección no pertenece al catálogo del landing.',
    'TST_001': 'El testimonio solicitado no existe.',
    'TST_002': 'El usuario autor no está disponible. Revisa que exista en la empresa.',
    'TST_003': 'Ya existe un testimonio de este usuario.',
    'TST_004': 'El usuario autor está inactivo. Actívalo o elige otro usuario.',
    'TST_005': 'Debes firmar digitalmente el testimonio antes de enviarlo.',
    'TST_006': 'Solo puedes volver a solicitar el testimonio a usuarios que ya calificaron.',
    'PARAM_002': 'Ya existe un parámetro con ese código.',
    'PARAM_003': 'El tipo de dato indicado no es compatible. Tipos válidos: STRING, INT, DECIMAL, BOOL, JSON.',
    'PARAM_004': 'El valor no es compatible con el tipo de dato declarado.',
    'FLAG_001': 'La feature flag solicitada no existe.',
    'FLAG_002': 'Ya existe una feature flag con esa clave.',
    'FLAG_003': 'El payload de la feature flag no superó la validación.',
    'MFLT_001': 'Ese filtro avanzado ya no está disponible. Recarga la lista.',
    'MFLT_002': 'Ya tienes un filtro avanzado con ese nombre en este módulo.',
    'MFLT_003': 'La bodega elegida está inactiva o fue retirada. Elige otra bodega.',
    'MFLT_004': 'Alguna zona elegida no pertenece a la bodega. Revisa las zonas.',
    'MFLT_005': 'Llegaste al máximo de filtros avanzados del módulo. Elimina uno primero.',
    'GRANT_001': 'Ese almacén ya no está disponible para asignar accesos. Recarga la lista.',
    'GRANT_002': 'Algún almacén elegido fue retirado. Recarga la lista y vuelve a elegir.',
    'GRANT_003': 'Algún usuario elegido no pertenece a tu empresa. Recarga la lista de usuarios.',
    'PROMO_001': 'No se encontró el serial del bono promocional.',
    'PROMO_002': 'Este bono promocional no está activo.',
    'PROMO_003': 'El plan de suscripción seleccionado no es elegible para este bono.',
    'PROMO_004': 'Este bono está fuera de su vigencia de redención.',
    'PROMO_005': 'Este bono no puede ser redimido por esta empresa.',
    'PROMO_006': 'Este bono promocional ya fue consumido.',
    'PROMO_007': 'Este bono no es compatible con la operación solicitada.',
    'PROMO_008': 'La redención de este bono ya fue procesada.',
    'PROMO_009': 'Los datos del bono no superaron la validación.',
    'PROMO_010': 'Ocurrió un error interno al procesar la promoción.',
    'PROMO_011': 'La empresa ya tiene un beneficio promocional activo.',
    'STR_001': 'El bucket de almacenamiento solicitado no existe.',
    'STR_002': 'El archivo solicitado no existe en el bucket de almacenamiento.',
    'STR_003': 'Ocurrió un error al subir el archivo al almacenamiento.',
    'STR_004': 'Ocurrió un error al eliminar el archivo del almacenamiento.',
    'STR_005': 'Ya existe un bucket con ese nombre.',
    'STR_006': 'Ocurrió un error al generar la URL prefirmada.',
    'STR_007': 'Ocurrió un error inesperado en el servicio de almacenamiento.',
    'VAL_001': 'Revisa los campos del formulario.',
    'ONB_001': 'No encontramos tu registro. Empieza de nuevo.',
    'ONB_002': 'El proceso expiró. Empieza de nuevo.',
    'ONB_003': 'Este registro ya fue completado. Inicia sesión.',
    'ONB_004': 'Debes completar los pasos anteriores primero.',
    'ONB_005': 'Ya empezaste a registrarte con este correo. Reenvíate el enlace para continuar donde lo dejaste.',
    'ONB_006': 'Ya existe una empresa con ese NIT.',
    'ONB_007': 'Sesión inválida. Empieza el registro de nuevo.',
    'ONB_008': 'Ese identificador de empresa ya está en uso.',
    'ONB_009': 'El plan seleccionado no existe o no está disponible.',
    'ONB_010': 'El plan requiere método de pago.',
    'ONB_011': 'Ya tienes una cuenta con ese correo. Inicia sesión.',
    'ONB_012': 'Espera unos segundos antes de pedir un nuevo enlace.',
    'ONB_013': 'Debes aceptar la política de privacidad para registrarte.',
    'ONB_014': 'La política de privacidad cambió. Ábrela de nuevo y acéptala.',
    'ONB_015': 'Debes aceptar los términos y condiciones para registrarte.',
    'ONB_016': 'Los términos y condiciones cambiaron. Ábrelos de nuevo y acéptalos.',
    'PAY_001': 'No hay un proveedor de pagos disponible. Revisa los parámetros SIMULATE_PAYMENT y PAYMENT_PROVIDER.',
    'PAY_002': 'El cambio de estado solicitado para este cargo no está permitido.',
    'PAY_003': 'El cargo solicitado no existe.',
    'PAY_004': 'Ya se procesó una operación con la misma clave de idempotencia y un cuerpo distinto.',
    'PAY_005': 'El proveedor de pagos rechazó el cargo.',
    'PAY_006': 'No se pudo verificar la firma del webhook entrante.',
    'PAY_007': 'Ocurrió un error al comunicarse con el proveedor de pagos.',
    'PAY_008': 'La moneda del cobro no está permitida para el país de la empresa.',
    'PAY_009': 'La moneda no coincide con la del cobro o la factura para esta operación.',
    'NOTIF_001': 'El tipo de recurso compartible solicitado no existe.',
    'NOTIF_002': 'Ya existe un tipo de recurso compartible con ese código.',
    'NOTIF_003': 'Este tipo de recurso no está habilitado para compartir.',
    'NOTIF_004': 'El destinatario de la audiencia no coincide con el alcance seleccionado.',
    'NOTIF_005': 'La notificación solicitada no existe para este usuario.',
    'INC_001': 'La incidencia ya no está disponible para reportar (enlace inválido o expirado).',
    'INC_002': 'La incidencia solicitada no existe.',
    'INC_003': 'Asigna a una persona para atender esta incidencia antes de resolverla o cerrarla.',
    'INC_004': 'Escribe las notas del cambio antes de resolver o cerrar la incidencia.',
    'INC_005': 'Solo quien envió el reporte puede adjuntar archivos, y justo después de enviarlo.',
    'INC_006': 'Un reporte acepta máximo 5 archivos.',
    'INC_007': 'Solo se aceptan imágenes JPG, PNG, WEBP o GIF de hasta 8 MB y videos MP4 de hasta 20 MB.',
    'INC_008': 'No pudimos guardar los archivos en este momento. Intenta enviarlos de nuevo.',
    'SSES_001': 'Esa conversación de soporte ya no está disponible.',
    'SSES_002': 'Ya tienes una conversación de soporte abierta. Termínala o cancélala antes de iniciar otra.',
    'SSES_003': 'Otro agente ya aceptó esta solicitud de soporte.',
    'SSES_004': 'Esta conversación de soporte no está en un estado que permita ese paso.',
    'SSES_005': 'Solo el agente que aceptó esta conversación puede continuarla.',
    'SSES_006': 'Termina tu conversación de soporte actual antes de aceptar otra.',
    'SSES_007': 'Elige una calificación de 1 a 5 estrellas.',
    'HBK_001': 'Ese contenido del manual no está disponible.',
    'HBK_002': 'No puedes consultar este manual con tu rol o plan actual.',
    'HBK_003': 'Solo un administrador de plataforma puede gestionar el manual.',
    'HBK_004': 'La audiencia de este contenido no es válida.',
    'HBK_005': 'El tipo de contenido del manual no es válido.',
    'HBK_006': 'Explica por qué hace falta este cambio en el manual antes de enviarlo a aprobación.',
    'HBK_007': 'Solo se puede aprobar o rechazar un cambio que esté pendiente.',
    'HBK_008': 'Solo un administrador tecnológico de plataforma puede proponer cambios al manual.',
    'HBK_009': 'Solo el Administrador de Plataforma puede aprobar o rechazar cambios del manual.',
    'HBK_010': 'Esta página del manual ya tiene un cambio pendiente de aprobación.',
    'HBK_011': 'Ya existe una página del manual con ese identificador.',
    'HBK_012': 'Cambiaste el contenido de un idioma que ya está publicado con esa versión. Súbele el número (por ejemplo, de 1.0 a 1.1) para guardarlo.',
    'HBK_013': 'Esa página no puede quedar debajo de sí misma ni de una página hija.',
    'HBK_014': (
        'La funcionalidad elegida no está activa para esa audiencia, '
        'o no corresponde a este tipo de página (las páginas API requieren un permiso API).'
    ),
    'HBK_015': 'El archivo markdown debe ser texto UTF-8 dentro del tamaño permitido.',
    'HBK_016': 'El idioma del manual debe ser español o inglés.',
    'HBK_017': 'El identificador de la página solo admite minúsculas, números y guiones.',
    'HBK_018': 'Guarda un borrador antes de enviarlo a aprobación.',
    'HBK_019': 'Una página sin contenido necesita un nombre en el menú para agrupar sus páginas hijas.',
    'HBK_020': 'Las páginas de nivel principal se quedan en el manual. Elimina las que están dentro de ellas.',
    'HBK_021': 'Esta página todavía agrupa otras. Elimina primero las que están dentro.',
    'HBK_022': 'Una página de API necesita su método HTTP (GET, POST, PUT, PATCH o DELETE) para mostrarlo en el menú.',
    'POL_001': 'La política solicitada no existe.',
    'POL_002': 'Ya existe una política con ese código.',
    'POL_003': 'No hay una versión de esa política para el país solicitado.',
    'POL_004': 'El contenido markdown de la política no puede estar vacío.',
    'POL_005': 'El país de la política no es válido. Usa un código ISO de dos letras como CO o US.',
    'POL_006': 'No se pudo leer o guardar el contenido de la política en el almacenamiento.',
    'POL_007': 'Ya firmaste esta versión de la política.',
    'POL_008': 'Esta política está inactiva y no se puede firmar.',
    'POL_009': 'Tu tipo de usuario no corresponde a la audiencia de esta política.',
    'POL_010': 'La firma de política solicitada no existe.',
    'POL_011': 'El contenido de la política no coincide con su huella registrada. No se puede firmar.',
    'POL_012': 'El sello digital de la firma no es válido.',
    'POL_013': 'No se puede eliminar: ya existen firmas digitales asociadas a esta política.',
    'POL_014': 'Esta versión del país fue revocada y no se puede firmar. Debes aceptar la versión publicada vigente.',
    'POL_015': 'No hay un borrador para ese país. Empieza a editar para crear uno.',
    'POL_016': 'Ya existe un borrador para ese país. Continúa editándolo o descártalo antes.',
    'POL_017': 'No hay una versión aprobada lista para liberar en ese país.',
    'POL_018': 'Solo se puede firmar la versión publicada de la política.',
    'POL_019': (
        'Debes indicar un resumen de los cambios al liberar una actualización '
        'de una política que ya estaba publicada.'
    ),
    'POL_020': (
        'El país de la política debe coincidir con la jurisdicción de la empresa. '
        'Usa el país ISO derivado de la ubicación de la compañía.'
    ),
    'GEO_001': 'El país solicitado no existe en la maestra de locaciones.',
    'GEO_002': 'Ya existe un país con ese código.',
    'GEO_003': 'El departamento solicitado no existe.',
    'GEO_004': 'Ya existe un departamento con ese código en este país.',
    'GEO_005': 'La ciudad solicitada no existe.',
    'GEO_006': 'Ya existe una ciudad con ese código en este departamento.',
    'GEO_007': 'El archivo de carga de locaciones no es válido o está incompleto.',
    'GEO_008': 'Una o más filas del archivo de locaciones no se pudieron procesar.',
    'GEO_009': 'El país está inactivo: actívalo en Locaciones antes de usarlo en políticas.',
    'GEO_010': 'La ciudad está inactiva: elige una ciudad activa para la ubicación de la empresa.',
    'GEO_011': 'No se puede eliminar el país: hay departamentos u otros registros que lo usan.',
    'GEO_012': 'No se puede eliminar el departamento: hay ciudades u otros registros que lo usan.',
    'GEO_013': 'No se puede eliminar la ciudad: hay empresas u otros registros que la usan.',
    'GEO_014': 'La moneda solicitada no existe en la maestra de monedas.',
    'GEO_015': 'Ya existe una moneda con ese código ISO 4217.',
    'GEO_016': 'La moneda está inactiva: actívala antes de usarla en un país o cobro.',
    'GEO_017': 'La asociación país–moneda solicitada no existe.',
    'GEO_018': 'Esa moneda no está habilitada para el país seleccionado.',
    'GEO_019': 'Esa moneda ya está vinculada a este país.',
    'GEO_020': 'No se puede eliminar la moneda: hay países u otros registros que la usan.',
    'TASKMON_001': 'La tarea automatizada solicitada no está registrada en el catálogo de monitoreo.',
    'TASKMON_002': 'La ejecución de tarea automatizada solicitada no existe.',
    'AI_001': 'No hay un proveedor de IA configurado o disponible. Revisa la configuración AI_PROVIDER.',
    'AI_002': 'El proveedor de IA no respondió dentro del tiempo permitido.',
    'AI_003': 'Se superó la cuota de uso de IA para este tenant o plan.',
    'AI_004': 'El proveedor de IA devolvió una respuesta vacía o malformada.',
    'AI_005': 'Ocurrió un error al comunicarse con el proveedor de IA.',
    'AI_006': 'La funcionalidad de IA está deshabilitada por configuración.',
    'AI_007': 'No hay una conversación del asistente para esa solicitud. Abre o inicia un chat desde el panel.',
    'AI_008': 'Esa herramienta no forma parte del catálogo del assistant.',
    'AI_009': 'Ya hay otra respuesta del asistente en curso. Espera a que termine.',
    'AI_010': 'La optimización de bodega está deshabilitada por configuración.',
    'AI_011': 'El ML predictivo está deshabilitado por configuración.',
    'AI_012': 'No hay una clave de proveedor de IA guardada. Agrégala o actívala en configuración.',
    'AI_013': 'Se rechazó la acción pendiente del asistente.',
    'SIGN_001': 'No hay un secreto de firma digital configurado. Revisa SIGNING_SECRET_KEY.',
    'SIGN_002': 'No se puede firmar un documento sin contenido.',
    'SIGN_003': 'El algoritmo de firma digital solicitado no está soportado.',
    'SIGN_004': 'Los datos de la firma digital son inválidos. Revisa el documento y el firmante.',
    # Ecosistema Neurana (facturación electrónica)
    'ECO_001': 'La sesión con Neurana expiró o no es válida. Se renovará automáticamente.',
    'ECO_002': 'La conexión con Neurana no tiene permiso para esta operación.',
    'ECO_003': 'Falta la llave de idempotencia en la solicitud a Neurana.',
    'ECO_004': 'Esta solicitud ya se envió a Neurana con datos distintos.',
    'ECO_005': 'No se pudo verificar la firma del aviso de Neurana.',
    'ECO_006': 'Este aviso de Neurana ya se había procesado.',
    'ECO_007': 'La base no está registrada como aplicación activa en Neurana.',
    'ECO_008': 'Las credenciales de la base en Neurana son incorrectas.',
    'ECO_009': 'Neurana devolvió un error al procesar la factura.',
    'ECO_010': 'Falta identificar el producto en la solicitud a Neurana.',
    'ECO_011': 'Neurana aún está procesando esta factura. Se reintentará en breve.',
    'ECO_012': 'Neurana no está disponible por ahora. La factura quedó en cola y se enviará sola.',
    'ECO_013': 'No se pudo contactar a Neurana. La factura quedó en cola y se enviará sola.',
    'ECO_014': 'Neurana rechazó la firma de la base. Revisa la llave registrada.',
    'ECO_015': 'Demasiadas solicitudes a Neurana. Se reintentará en unos minutos.',
    'ECO_016': 'Los datos de la factura no cumplen el formato acordado con Neurana.',
    'ECO_017': 'La conexión con Neurana debe ser segura (HTTPS).',
    'FIS_001': 'Completa el perfil fiscal del emisor (NIT, dirección y software) antes de emitir.',
    'FIS_002': 'El perfil fiscal del emisor no cumple las reglas de la autoridad. Revisa los campos indicados.',
    'FIS_003': 'El documento no cumple las reglas de la autoridad tributaria. Revisa los problemas e inténtalo de nuevo.',
    'FIS_004': 'El canal con la autoridad tributaria no está disponible. El documento permanece en cola.',
    'FIS_005': 'No hay un envío a la autoridad tributaria con ese identificador.',
    'FIS_006': 'Solo se pueden reenviar envíos fallidos a la autoridad tributaria.',
    'FIS_007': 'No hay una nota crédito con ese identificador.',
    'FIS_008': 'La resolución de numeración activa para este tipo de documento está fuera de vigencia.',
    'FIS_009': 'La jurisdicción fiscal configurada no coincide con ningún país soportado.',
    'INT_001': 'No hay un conector registrado para el proveedor solicitado.',
    'INT_002': 'No se pudo establecer conexión con el sistema externo.',
    'INT_003': 'El sistema externo no respondió dentro del tiempo permitido.',
    'INT_004': 'El proveedor de integración no está disponible temporalmente.',
    'INT_005': 'Conflicto de sincronización resuelto a favor del WMS.',
    'INT_006': 'Esta operación de integración ya fue procesada (idempotencia).',
    'INT_007': 'Las credenciales del sistema externo son inválidas o expiraron.',
    'INT_008': 'La configuración de mapeo de datos es inválida o está incompleta.',
    'INT_009': 'Las integraciones están deshabilitadas por configuración.',
    'INT_010': 'No encontramos esa aplicación de integración. Recarga la lista e inténtalo de nuevo.',
    'INT_011': 'Uno o más permisos de API no son válidos. Revisa la selección e inténtalo de nuevo.',
    'INT_012': 'La aplicación de integración está revocada: ya no se puede modificar ni reactivar.',
    'INT_013': 'Revoca la aplicación de integración antes de eliminarla.',
    'INT_014': 'La aplicación de integración cambió mientras se procesaba la solicitud. Recarga e inténtalo de nuevo.',
    'INT_015': 'Tu suscripción o tu rol no incluyen uno o más de los permisos de API seleccionados.',
    'INT_016': 'A una aplicación solo puedes darle permisos de API. Quita los demás de la selección.',
    'SRV_001': 'Ocurrió un error inesperado. Puedes reportarlo para que lo revisemos.',
    'SRV_002': 'Ocurrió un error al procesar la solicitud. Inténtalo de nuevo.',
    'RL_001': 'Hay demasiadas solicitudes en este momento.',
    'HTTP_001': 'El recurso solicitado no existe o fue eliminado.',
}


class SyncErrorsError(Exception):
    """Error de validación al sincronizar el catálogo de errores."""


@dataclass(frozen=True)
class SyncErrorsResult:
    code_count: int
    written_paths: list[Path]


def default_frontend_roots() -> list[Path]:
    """Raíces de los frontends hermanos del monorepo (client, admin y docs).

    ``settings.BASE_DIR`` apunta al paquete ``base``, así que el monorepo
    (carpeta que contiene base, base-client-web y base-admin-web) es
    ``BASE_DIR.parent.parent``.
    """
    monorepo_root = Path(settings.BASE_DIR).resolve().parent.parent
    return [
        monorepo_root / 'base-client-web',
        monorepo_root / 'base-admin-web',
        monorepo_root / 'base-docs-web',
    ]


def i18n_targets(frontend_roots: list[Path] | None = None) -> list[Path]:
    roots = frontend_roots if frontend_roots is not None else default_frontend_roots()
    targets: list[Path] = []
    for root in roots:
        targets.append(root / 'src' / 'assets' / 'i18n' / 'en' / 'errors.json')
        targets.append(root / 'src' / 'assets' / 'i18n' / 'es' / 'errors.json')
    return targets


def load_en_details() -> dict[str, str]:
    from core.errors.codes import ERROR_REGISTRY

    en: dict[str, str] = {}
    spanish_left: list[tuple[str, str, str]] = []

    for code, entry in ERROR_REGISTRY.items():
        message = entry['message']
        detail = entry['detail']
        if detail and not detail.endswith('.'):
            detail = f'{detail}.'
        en[code.value] = detail
        for field, val in (('message', message), ('detail', detail)):
            if re.search(r'[áéíóúñüÁÉÍÓÚÑÜ¿¡]', val):
                spanish_left.append((code.value, field, val))

    if spanish_left:
        details = ', '.join(f'{code}.{field}' for code, field, _ in spanish_left)
        raise SyncErrorsError(
            f'ERROR_REGISTRY still has Spanish message/detail: {details}. '
            'Backend responses must be English-only.'
        )
    return en


# Códigos sintéticos del frontend (no existen en ERROR_REGISTRY).
FRONTEND_ONLY_EN: dict[str, str] = {
    'NET_001': 'Could not reach the server. Check your connection and try again.',
    'retry_after_seconds': 'Try again in {{retryAfter}} seconds.',
    'retry_after_minutes': 'Try again in {{retryAfter}} minutes.',
}

FRONTEND_ONLY_ES: dict[str, str] = {
    'NET_001': 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.',
    'retry_after_seconds': 'Inténtalo de nuevo en {{retryAfter}} segundos.',
    'retry_after_minutes': 'Inténtalo de nuevo en {{retryAfter}} minutos.',
}


def _ordered(errors: dict[str, str], default: str) -> dict:
    payload = {k: errors[k] for k in sorted(errors)}
    payload['default'] = default
    return {'errors': payload}


def sync_error_i18n(
    *,
    dry_run: bool = False,
    frontend_roots: list[Path] | None = None,
) -> SyncErrorsResult:
    """
    Valida el registro de errores y escribe ``errors.json`` en los frontends.

    Product keeps ``ES_OVERRIDES`` and default frontend roots; write logic
    lives in ``necore.errors.sync_i18n``.

    Raises:
        SyncErrorsError: si el registro tiene español o faltan traducciones ES.
    """
    from core.errors.codes import ERROR_REGISTRY
    from necore.errors import sync_i18n as ne_sync

    roots = frontend_roots if frontend_roots is not None else default_frontend_roots()
    missing_roots = [str(root) for root in roots if not root.is_dir()]
    if missing_roots:
        raise SyncErrorsError(
            'Frontend roots not found (expected siblings of base): '
            + ', '.join(missing_roots)
        )

    try:
        result = ne_sync.sync_error_i18n(
            registry=ERROR_REGISTRY,
            es_overrides=ES_OVERRIDES,
            dry_run=dry_run,
            targets=roots,
        )
    except ne_sync.SyncErrorsError as exc:
        msg = str(exc)
        if msg.startswith('Missing Spanish overrides'):
            raise SyncErrorsError(
                f'Missing Spanish overrides in core.errors.sync_i18n.ES_OVERRIDES: '
                f'{msg.split(": ", 1)[-1]}'
            ) from exc
        raise SyncErrorsError(msg) from exc

    return SyncErrorsResult(
        code_count=result.code_count,
        written_paths=result.written_paths,
    )
