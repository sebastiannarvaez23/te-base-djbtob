"""
Inbox de notificaciones PARTICIONADO POR TENANT (schema de cada empresa).

``Notification`` es el contenido (una fila por evento) y
``NotificationRecipient`` el estado por usuario que lee la campanita. Como
viven en el schema del tenant, las consultas quedan auto-aisladas por
empresa y el elemento compartido (Picking/OC) vive en el mismo schema.

El destinatario referencia al ``User`` (que vive en ``public``) por UUID
suelto, en línea con la filosofía ``on_delete=DO_NOTHING`` del proyecto.
"""


from django.db import models

from core.ids import uuid7


class Notification(models.Model):

    class Kind(models.TextChoices):
        SHARE = 'SHARE', 'Compartido por un usuario'
        ADMIN_DIRECT = 'ADMIN_DIRECT', 'Admin → un usuario'
        ADMIN_COMPANY = 'ADMIN_COMPANY', 'Admin → empresa'
        ADMIN_BROADCAST = 'ADMIN_BROADCAST', 'Admin → todas las empresas'

    class ActorKind(models.TextChoices):
        USER = 'USER', 'Usuario'
        ADMIN = 'ADMIN', 'Administrador'
        SYSTEM = 'SYSTEM', 'Sistema'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    kind = models.CharField(max_length=20, choices=Kind.choices)

    # Trazabilidad: id del AdminNotificationOutbox (público) cuando el origen
    # es un admin; NULL cuando es un SHARE entre usuarios.
    origin_id = models.UUIDField(null=True, blank=True)

    # Actor (polimórfico, denormalizado).
    actor_kind = models.CharField(max_length=10, choices=ActorKind.choices)
    actor_id = models.UUIDField(null=True, blank=True)
    actor_label = models.CharField(max_length=200)

    # Contenido
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default='')
    level = models.CharField(max_length=20, default='INFO')

    # Referencia suelta al elemento compartido (vive en ESTE schema).
    resource_type_code = models.CharField(max_length=80, blank=True, default='')
    resource_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'inbox'
        db_table = 'notifications'
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        indexes = [
            models.Index(fields=['-created_at'], name='notif_created_idx'),
        ]

    def __str__(self):
        return f'{self.kind} · {self.title}'


class NotificationRecipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.DO_NOTHING,
        related_name='recipients',
    )
    user_id = models.UUIDField()
    read_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'inbox'
        db_table = 'notification_recipients'
        verbose_name = 'Destinatario de notificación'
        verbose_name_plural = 'Destinatarios de notificación'
        constraints = [
            models.UniqueConstraint(
                fields=['notification', 'user_id'],
                name='uniq_notification_user',
            ),
        ]
        indexes = [
            models.Index(fields=['user_id', 'read_at'], name='notif_rcpt_user_read_idx'),
            models.Index(fields=['user_id', '-created_at'], name='notif_rcpt_user_created_idx'),
        ]

    def __str__(self):
        return f'{self.user_id} · {self.notification_id}'
