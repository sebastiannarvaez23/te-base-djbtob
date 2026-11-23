from django.db import models

from core.ids import uuid7


class PromotionVoucher(models.Model):
    class VoucherType(models.TextChoices):
        GIFT = 'GIFT', 'Regalo'
        DISCOUNT = 'DISCOUNT', 'Descuento'

    class Scope(models.TextChoices):
        COMPANY = 'COMPANY', 'Empresa'
        OPEN = 'OPEN', 'Abierto'
        FIRST_TAKE = 'FIRST_TAKE', 'Primera empresa'

    class Origin(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        PUBLIC_PURCHASE = 'PUBLIC_PURCHASE', 'Compra pública'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Activo'
        REDEEMED = 'REDEEMED', 'Redimido'
        EXPIRED = 'EXPIRED', 'Expirado'
        REVOKED = 'REVOKED', 'Revocado'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    serial = models.CharField(max_length=32, unique=True, db_index=True)
    voucher_type = models.CharField(max_length=16, choices=VoucherType.choices)
    scope = models.CharField(max_length=16, choices=Scope.choices)
    origin = models.CharField(max_length=20, choices=Origin.choices, default=Origin.ADMIN)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='promotion_vouchers',
    )
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    benefit_months = models.PositiveSmallIntegerField(null=True, blank=True)
    discount_duration_months = models.PositiveSmallIntegerField(default=1)
    redeem_valid_from = models.DateTimeField()
    redeem_valid_until = models.DateTimeField()
    subscriptions = models.ManyToManyField(
        'subscription.Subscription',
        related_name='promotion_vouchers',
        blank=True,
    )
    created_by = models.ForeignKey(
        'platform_users.AdminUser',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='created_promotion_vouchers',
    )
    notes = models.TextField(blank=True, default='')
    metadata = models.JSONField(blank=True, default=dict)
    checkout_idempotency_key = models.CharField(
        max_length=64, null=True, blank=True, unique=True, db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_promotion_vouchers'
        verbose_name = 'Bono promocional'
        verbose_name_plural = 'Bonos promocionales'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.serial} ({self.voucher_type}/{self.status})'


class PromotionRedemption(models.Model):
    class Context(models.TextChoices):
        ONBOARDING = 'ONBOARDING', 'Onboarding'
        SETTINGS = 'SETTINGS', 'Configuración'
        PUBLIC_PURCHASE = 'PUBLIC_PURCHASE', 'Compra pública'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    voucher = models.ForeignKey(
        PromotionVoucher,
        on_delete=models.DO_NOTHING,
        related_name='redemptions',
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.DO_NOTHING,
        related_name='promotion_redemptions',
    )
    redeemed_at = models.DateTimeField()
    context = models.CharField(max_length=20, choices=Context.choices)
    subscription = models.ForeignKey(
        'subscription.Subscription',
        on_delete=models.DO_NOTHING,
        related_name='promotion_redemptions',
    )
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    idempotency_key = models.CharField(max_length=64, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_promotion_redemptions'
        verbose_name = 'Redención de bono'
        verbose_name_plural = 'Redenciones de bonos'
        ordering = ['-redeemed_at']


class PromotionBenefit(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Activo'
        COMPLETED = 'COMPLETED', 'Completado'
        CANCELLED = 'CANCELLED', 'Cancelado'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.DO_NOTHING,
        related_name='promotion_benefits',
    )
    redemption = models.OneToOneField(
        PromotionRedemption,
        on_delete=models.DO_NOTHING,
        related_name='benefit',
    )
    voucher_type = models.CharField(max_length=16, choices=PromotionVoucher.VoucherType.choices)
    subscription = models.ForeignKey(
        'subscription.Subscription',
        on_delete=models.DO_NOTHING,
        related_name='promotion_benefits',
    )
    previous_subscription = models.ForeignKey(
        'subscription.Subscription',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='promotion_benefits_reverted_from',
    )
    benefit_start = models.DateTimeField()
    benefit_end = models.DateTimeField()
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    remaining_discount_cycles = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_promotion_benefits'
        verbose_name = 'Beneficio promocional'
        verbose_name_plural = 'Beneficios promocionales'
        indexes = [
            models.Index(fields=['company', 'status'], name='idx_promo_benefit_co_st'),
        ]
