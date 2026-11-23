from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

from core.ids import uuid7
from platform.features.company.tenant.company.models import Company
from platform.features.security.access.functionalities.models import Functionality

from .domain.enums import IdentityDocumentType


class UserManager(BaseUserManager):
    def _create_user(self, username, email, first_name, last_name, telephone, company, password, is_staff, is_superuser, **extra_fields):
        user = self.model(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            telephone=telephone,
            rol=Rol.objects.get_or_create(name='Administrator')[0],
            company=Company.objects.get(id=company),
            is_staff=is_staff,
            is_superuser=is_superuser,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self.db)
        return user

    def create_user(self, username, email, first_name, last_name, telephone, company, password=None, **extra_fields):
        return self._create_user(username, email, first_name, last_name, telephone, company, password, False, False, **extra_fields)
    
    def create_superuser(self, username, email, first_name, last_name, telephone, company, password=None, **extra_fields):
        return self._create_user(username, email, first_name, last_name, telephone, company, password, True, True, **extra_fields)

class Rol(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="id")
    name = models.CharField(max_length=200, verbose_name="Nombre Rol")
    description = models.CharField(max_length=500, blank=True, default='', verbose_name="Descripción")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='roles',
        verbose_name="Empresa",
    )

    class Meta:
        db_table = 'security_roles'

    def __str__(self):
        return self.name


class RolFeature(models.Model):
    rol     = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='rol_features')
    feature = models.ForeignKey(Functionality, on_delete=models.CASCADE, related_name='rol_features')

    class Meta:
        db_table = 'security_rol_features'
        unique_together = ('rol', 'feature')


class RolModule(models.Model):
    """Acceso directo de un rol a un módulo (aparece en sidebar sin requerir features)."""
    rol         = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='rol_modules')
    module_code = models.CharField(max_length=100, verbose_name="Código del módulo")

    class Meta:
        db_table = 'security_rol_modules'
        unique_together = ('rol', 'module_code')

    def __str__(self):
        return f'{self.rol.name} – {self.module_code}'


class CompanyRolAccess(models.Model):
    """Activación/desactivación de roles genéricos por empresa."""
    company  = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='rol_accesses', verbose_name="Empresa")
    rol      = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='company_accesses', verbose_name="Rol")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        db_table = 'security_company_rol_access'
        unique_together = ('company', 'rol')

    def __str__(self):
        return f'{self.company_id} – {self.rol.name} – {self.is_active}'


class User(AbstractBaseUser, PermissionsMixin):
    class DocumentType(models.TextChoices):
        CEDULA_CIUDADANIA = (
            IdentityDocumentType.CEDULA_CIUDADANIA.value,
            'Citizenship ID card',
        )
        CEDULA_EXTRANJERIA = (
            IdentityDocumentType.CEDULA_EXTRANJERIA.value,
            'Foreigner ID card',
        )
        PASAPORTE = (
            IdentityDocumentType.PASAPORTE.value,
            'Passport',
        )

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False, verbose_name="Id")
    username = models.CharField(max_length=200, unique=True, verbose_name="Nombre de Usuario")
    email = models.EmailField(max_length=254, unique=True, verbose_name="Correo electronico")
    first_name = models.CharField(max_length=100, blank=True, null=True)
    second_name = models.CharField(max_length=100, blank=True, default='')
    last_name = models.CharField(max_length=100, blank=True, null=True)
    second_last_name = models.CharField(max_length=100, blank=True, default='')
    document_type = models.CharField(
        max_length=2,
        choices=DocumentType.choices,
        blank=True,
        default='',
    )
    document_number = models.CharField(max_length=20, blank=True, default='')
    birth_date = models.DateField(null=True, blank=True, verbose_name="Fecha de nacimiento")
    telephone = models.CharField(max_length=100, verbose_name="Telefono")
    phone_country_code = models.CharField(max_length=2, blank=True, default='CO')
    # Stores the MinIO object key (e.g. client/tenants/<schema>/assets/profiles/
    # pic-<username>.<ext>), not a local media file. Served via presigned URL.
    picture = models.ImageField(upload_to='perfil/', max_length=500, blank=True, null=True, verbose_name="Foto de perfil")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    # NULL until the user clicks the confirmation link. Login is gated on
    # this field only when the REG_EMAIL_CONFIRM platform parameter is true.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # Last time the password hash changed. NULL = never tracked (grandfathered:
    # PASSWORD_EXPIRED does not lock these accounts until they rotate once).
    password_changed_at = models.DateTimeField(null=True, blank=True)
    deactivated_by_company_close = models.BooleanField(default=False)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = [
        'email',
        'first_name',
        'last_name',
        'telephone',
        'company'
    ]

    class Meta:
        db_table = 'security_users'
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(document_type='')
                    | models.Q(document_type__in=IdentityDocumentType.values())
                ),
                name='chk_user_document_type',
            ),
            models.UniqueConstraint(
                fields=['company', 'document_type', 'document_number'],
                condition=~models.Q(document_number=''),
                name='uniq_user_company_document',
            ),
        ]

    def __str__(self):
        return self.username
