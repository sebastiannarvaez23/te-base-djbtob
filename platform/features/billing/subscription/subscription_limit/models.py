from django.db import models

from core.ids import uuid7


class SubscriptionLimit(models.Model):
    """Tope máximo permitido de una funcionalidad dentro de un plan de suscripción."""

    class ValidationType(models.TextChoices):
        DAILY    = 'daily',    'Diario'
        LIFETIME = 'lifetime', 'Por suscripción'
        WINDOW   = 'window',   'Por ventana'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name='Id')
    subscription = models.ForeignKey(
        'subscription.Subscription',
        on_delete=models.DO_NOTHING,
        related_name='limits',
        verbose_name='Suscripción',
    )
    functionality = models.ForeignKey(
        'functionalities.Functionality',
        on_delete=models.DO_NOTHING,
        related_name='subscription_limits',
        verbose_name='Funcionalidad',
    )
    name             = models.CharField(max_length=150, verbose_name='Nombre del tope', blank=True, default='')
    max_value        = models.PositiveIntegerField(verbose_name='Tope máximo')
    validation_type  = models.CharField(
        max_length=20,
        choices=ValidationType.choices,
        default=ValidationType.LIFETIME,
        verbose_name='Tipo de validación',
    )
    window_hours     = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Duración de la ventana (horas)',
        help_text='Obligatorio si el tipo de validación es por ventana. Ejemplo: 3 horas × 3 usos.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        db_table = 'billing_subscription_limits'
        verbose_name = 'Tope de suscripción'
        verbose_name_plural = 'Topes de suscripción'
        unique_together = [('subscription', 'functionality')]
        ordering = ['subscription', 'functionality']
        constraints = [
            models.CheckConstraint(
                name='slimit_window_hours_invariant',
                check=(
                    models.Q(
                        validation_type='window',
                        window_hours__gte=1,
                        window_hours__lte=168,
                    )
                    | (
                        ~models.Q(validation_type='window')
                        & models.Q(window_hours__isnull=True)
                    )
                ),
            ),
        ]

    def __str__(self):
        return f'{self.subscription.name} – {self.functionality.label}: {self.max_value}'
