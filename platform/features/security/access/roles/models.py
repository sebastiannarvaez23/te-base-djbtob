from django.db import models

from core.ids import uuid7


# ── Admin catalog (mirror of security_sections / security_modules / security_features) ──


class AdminSection(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    code      = models.CharField(max_length=50, unique=True, verbose_name='Código')
    name      = models.CharField(max_length=200, verbose_name='Nombre')
    icon      = models.CharField(max_length=100, blank=True, default='', verbose_name='Icono')
    order     = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        app_label = 'platform_roles'
        db_table = 'admin_sections'
        ordering = ['order']
        verbose_name = 'Sección de administrador'
        verbose_name_plural = 'Secciones de administrador'

    def __str__(self):
        return self.name


class AdminModule(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    code        = models.CharField(max_length=100, unique=True, verbose_name='Código')
    name        = models.CharField(max_length=200, verbose_name='Nombre')
    description = models.CharField(max_length=500, blank=True, default='', verbose_name='Descripción')
    icon        = models.CharField(max_length=100, verbose_name='Icono')
    route       = models.CharField(max_length=255, verbose_name='Ruta')
    section     = models.ForeignKey(
        AdminSection,
        on_delete=models.PROTECT,
        related_name='modules',
        verbose_name='Sección',
    )
    order       = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    is_sidebar  = models.BooleanField(default=True, verbose_name='Menú del sidebar')
    is_active   = models.BooleanField(default=True, verbose_name='Activo')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        app_label = 'platform_roles'
        db_table = 'admin_modules'
        ordering = ['section__order', 'order']
        verbose_name = 'Módulo de administrador'
        verbose_name_plural = 'Módulos de administrador'

    def __str__(self):
        return f'{self.name} ({self.code})'


class AdminFeature(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    key        = models.CharField(max_length=100, unique=True, verbose_name='Clave')
    label      = models.CharField(max_length=200, verbose_name='Etiqueta')
    module     = models.ForeignKey(
        AdminModule,
        on_delete=models.PROTECT,
        related_name='features',
        verbose_name='Módulo',
    )
    category   = models.CharField(max_length=50, default='features', verbose_name='Categoría')
    is_active  = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        app_label = 'platform_roles'
        db_table = 'admin_features'
        ordering = ['module__order', 'key']
        verbose_name = 'Feature de administrador'
        verbose_name_plural = 'Features de administrador'

    def __str__(self):
        return f'{self.label} ({self.key})'


# ── Admin roles and grants ─────────────────────────────────────────────────────


class AdminRole(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    name        = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name='Descripción')
    is_active   = models.BooleanField(default=True, verbose_name='Activo')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')

    class Meta:
        app_label = 'platform_roles'
        db_table = 'admin_roles'
        verbose_name = 'Rol de administrador'
        verbose_name_plural = 'Roles de administrador'

    def __str__(self):
        return self.name


class AdminRoleFeature(models.Model):
    """Grant of an admin catalog feature to an admin role."""
    rol     = models.ForeignKey(AdminRole, on_delete=models.CASCADE, related_name='rol_features')
    feature = models.ForeignKey(
        AdminFeature,
        on_delete=models.CASCADE,
        related_name='rol_features',
    )

    class Meta:
        app_label = 'platform_roles'
        db_table = 'admin_rol_features'
        unique_together = ('rol', 'feature')


class AdminRoleModule(models.Model):
    """Direct module access for an admin role (sidebar entry without features)."""
    rol         = models.ForeignKey(AdminRole, on_delete=models.CASCADE, related_name='rol_modules')
    module_code = models.CharField(max_length=100, verbose_name='Código del módulo')

    class Meta:
        app_label = 'platform_roles'
        db_table = 'admin_rol_modules'
        unique_together = ('rol', 'module_code')

    def __str__(self):
        return f'{self.rol.name} – {self.module_code}'
