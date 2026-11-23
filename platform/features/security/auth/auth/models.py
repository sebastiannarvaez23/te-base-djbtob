"""Admin auth persistence — trusted devices for DOUBLE_FA_AUTH."""

from django.db import models

from core.ids import uuid7


class AdminTrustedDevice(models.Model):
    """A browser/device an admin has already completed 2FA on."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.ForeignKey(
        'platform_users.AdminUser',
        on_delete=models.DO_NOTHING,
        related_name='trusted_devices',
    )
    device_hash = models.CharField(max_length=64)
    label = models.CharField(max_length=64, blank=True, default='')
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    last_ua = models.CharField(max_length=512, blank=True, default='')
    last_used_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'platform_auth'
        db_table = 'admin_trusted_devices'
        verbose_name = 'Admin trusted device'
        verbose_name_plural = 'Admin trusted devices'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'device_hash'],
                name='uniq_admin_trusted_device_user_hash',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'revoked_at'], name='adm_tdev_user_revoked_idx'),
        ]
