"""
Modelos de notificaciones del lado PÚBLICO (schema ``public``).

Aquí viven solo las dos piezas globales:
  - ``NotificationResourceType``: registro configurable de QUÉ elementos
    pueden compartirse (Orden de Compra, Picking, Despacho, …).
  - ``AdminNotificationOutbox``: fuente de verdad ÚNICA de cada envío que
    hace un administrador. El fan-out materializa luego ``Notification`` +
    ``NotificationRecipient`` dentro de cada schema de tenant.

El inbox de los tenants vive en ``client.features.communication.messaging.inbox``.
La campanita del portal admin (``AdminInboxNotification`` /
``AdminInboxRecipient``) también vive aquí, en schema público.
"""


from django.db import models

from core.ids import uuid7


class NotificationResourceType(models.Model):
    """Tipo de elemento que está habilitado para compartirse por la campanita."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    code = models.CharField(max_length=80, unique=True, verbose_name='Código')
    label = models.CharField(max_length=120, verbose_name='Etiqueta')
    icon = models.CharField(max_length=80, blank=True, default='', verbose_name='Ícono')
    # Plantilla de ruta para el deep-link del front, ej. '/warehouse/pickings/:id'.
    route_template = models.CharField(max_length=255, blank=True, default='', verbose_name='Ruta')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'inbox_platform'
        db_table = 'notification_resource_types'
        verbose_name = 'Tipo de recurso compartible'
        verbose_name_plural = 'Tipos de recurso compartible'

    def __str__(self):
        return self.code


class AdminNotificationOutbox(models.Model):
    """Registro de un envío realizado por un administrador de plataforma.

    Una sola fila por acción del admin, sin importar a cuántos tenants /
    usuarios llegue. El fan-out (Celery) lee esta fila, resuelve la
    audiencia y escribe las notificaciones dentro de cada schema destino,
    actualizando ``status`` y ``recipients_count`` al terminar.
    """

    class Scope(models.TextChoices):
        SINGLE_USER = 'SINGLE_USER', 'Un usuario'
        COMPANY_USERS = 'COMPANY_USERS', 'Todos los usuarios de una empresa'
        ALL_TENANTS = 'ALL_TENANTS', 'Todos los usuarios de todas las empresas'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        DISPATCHING = 'DISPATCHING', 'Despachando'
        SENT = 'SENT', 'Enviada'
        FAILED = 'FAILED', 'Fallida'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    # Actor (AdminUser, referencia suelta — vive en otra tabla del público).
    admin_id = models.UUIDField(verbose_name='Admin emisor')
    admin_label = models.CharField(max_length=200, verbose_name='Nombre del admin')

    # Audiencia
    scope = models.CharField(max_length=20, choices=Scope.choices)
    target_company_id = models.UUIDField(null=True, blank=True)
    target_user_id = models.UUIDField(null=True, blank=True)

    # Contenido
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default='')
    level = models.CharField(max_length=20, default='INFO')

    # Estado del despacho
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    recipients_count = models.IntegerField(default=0)
    error_detail = models.CharField(max_length=500, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'inbox_platform'
        db_table = 'admin_notification_outbox'
        verbose_name = 'Notificación de administrador'
        verbose_name_plural = 'Notificaciones de administrador'
        indexes = [
            models.Index(fields=['-created_at'], name='admin_notif_created_idx'),
            models.Index(fields=['status'], name='admin_notif_status_idx'),
        ]

    def __str__(self):
        return f'{self.scope} · {self.title}'


class AdminInboxNotification(models.Model):
    """Contenido de una notificación de la campanita del portal admin."""

    class Kind(models.TextChoices):
        SYSTEM = 'SYSTEM', 'Sistema'

    class ActorKind(models.TextChoices):
        SYSTEM = 'SYSTEM', 'Sistema'
        ADMIN = 'ADMIN', 'Administrador'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SYSTEM)
    actor_kind = models.CharField(max_length=10, choices=ActorKind.choices, default=ActorKind.SYSTEM)
    actor_id = models.UUIDField(null=True, blank=True)
    actor_label = models.CharField(max_length=200)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default='')
    level = models.CharField(max_length=20, default='INFO')
    resource_type_code = models.CharField(max_length=80, blank=True, default='')
    resource_id = models.UUIDField(null=True, blank=True)
    resource_route = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'inbox_platform'
        db_table = 'admin_inbox_notifications'
        verbose_name = 'Notificación de campanita admin'
        verbose_name_plural = 'Notificaciones de campanita admin'
        indexes = [
            models.Index(fields=['-created_at'], name='adm_inbox_notif_created_idx'),
        ]

    def __str__(self):
        return f'{self.kind} · {self.title}'


class AdminInboxRecipient(models.Model):
    """Estado por AdminUser de una notificación de la campanita admin."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    notification = models.ForeignKey(
        AdminInboxNotification,
        on_delete=models.DO_NOTHING,
        related_name='recipients',
    )
    user_id = models.UUIDField()
    read_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'inbox_platform'
        db_table = 'admin_inbox_recipients'
        verbose_name = 'Destinatario de campanita admin'
        verbose_name_plural = 'Destinatarios de campanita admin'
        indexes = [
            models.Index(fields=['user_id', 'read_at'], name='adm_inbox_rcpt_read_idx'),
            models.Index(fields=['user_id', '-created_at'], name='adm_inbox_rcpt_crt_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['notification', 'user_id'],
                name='uniq_adm_inbox_rcpt_user',
            ),
        ]

    def __str__(self):
        return f'{self.user_id} · {self.notification_id}'
