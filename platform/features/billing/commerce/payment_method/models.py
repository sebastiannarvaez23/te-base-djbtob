from django.db import models

from core.ids import uuid7


class PaymentMethod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="Id")
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='payment_methods',
        verbose_name="Empresa",
    )
    name = models.CharField(max_length=200, verbose_name="Nombre")
    provider = models.CharField(max_length=100, verbose_name="Proveedor")
    holder = models.CharField(max_length=200, blank=True, verbose_name="Titular")
    last4 = models.CharField(max_length=4, blank=True, verbose_name="Últimos 4 dígitos")
    expiry = models.CharField(max_length=5, blank=True, verbose_name="Vencimiento (MM/YY)")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado en")

    class Meta:
        db_table = 'billing_payment_methods'
        verbose_name = "Método de pago"
        verbose_name_plural = "Métodos de pago"
        indexes = [
            models.Index(fields=['company', '-created_at'], name='idx_pm_company_created'),
        ]

    def __str__(self):
        return f"{self.name} - {self.company.name}"
