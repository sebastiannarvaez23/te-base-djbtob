from django.db import models
from django.contrib.auth.hashers import make_password, check_password

from core.ids import uuid7


class AdminUser(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    username    = models.CharField(max_length=150, unique=True, verbose_name='Usuario')
    email       = models.EmailField(unique=True, verbose_name='Correo electrónico')
    first_name  = models.CharField(max_length=100, verbose_name='Nombre')
    last_name   = models.CharField(max_length=100, verbose_name='Apellido')
    telephone   = models.CharField(max_length=100, blank=True, default='', verbose_name='Teléfono')
    picture     = models.CharField(max_length=500, blank=True, null=True, verbose_name='Foto de perfil')
    password    = models.CharField(max_length=128, verbose_name='Contraseña')
    role        = models.ForeignKey(
        'platform_roles.AdminRole',
        on_delete=models.PROTECT,
        related_name='users',
        verbose_name='Rol',
    )
    is_active   = models.BooleanField(default=True, verbose_name='Activo')
    is_superuser = models.BooleanField(default=False, verbose_name='Superusuario')
    last_login  = models.DateTimeField(null=True, blank=True, verbose_name='Último acceso')
    password_changed_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Password changed at',
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        app_label = 'platform_users'
        db_table = 'admin_users'
        verbose_name = 'Usuario administrador'
        verbose_name_plural = 'Usuarios administradores'

    @property
    def is_authenticated(self):
        return True

    def set_password(self, raw_password: str):
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.username


class AdminPasswordHistory(models.Model):
    """Previous admin password hashes for HISTORY_PASS reuse checks."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.ForeignKey(
        AdminUser,
        on_delete=models.DO_NOTHING,
        related_name='password_history',
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'platform_users'
        db_table = 'admin_password_history'
        verbose_name = 'Admin password history'
        verbose_name_plural = 'Admin password history'
        indexes = [
            models.Index(fields=['user', '-created_at'], name='adm_pwdhist_user_created_idx'),
        ]
