import getpass

from django.core.management.base import BaseCommand, CommandError

from platform.features.security.access.roles.models import AdminRole
from platform.features.security.identity.users.models import AdminUser


class Command(BaseCommand):
    help = 'Crea el usuario administrador raíz de la plataforma.'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Nombre de usuario')
        parser.add_argument('--email', type=str, help='Correo electrónico')
        parser.add_argument('--first-name', type=str, dest='first_name', default='', help='Nombre')
        parser.add_argument('--last-name', type=str, dest='last_name', default='', help='Apellido')
        parser.add_argument('--password', type=str, help='Contraseña (si no se provee, se solicitará interactivamente)')
        parser.add_argument('--role-name', type=str, dest='role_name', default='Super Admin', help='Nombre del rol a asignar (se crea si no existe)')

    def handle(self, *args, **options):
        username = options['username'] or input('Username: ')
        email = options['email'] or input('Email: ')
        first_name = options['first_name']
        last_name = options['last_name']
        password = options['password'] or getpass.getpass('Password: ')
        role_name = options['role_name']

        if not username:
            raise CommandError('El username es obligatorio.')
        if not email:
            raise CommandError('El email es obligatorio.')
        if len(password) < 8:
            raise CommandError('La contraseña debe tener al menos 8 caracteres.')

        if AdminUser.objects.filter(username=username).exists():
            raise CommandError(f'Ya existe un usuario con username "{username}".')
        if AdminUser.objects.filter(email=email).exists():
            raise CommandError(f'Ya existe un usuario con email "{email}".')

        role, created = AdminRole.objects.get_or_create(
            name=role_name,
            defaults={'description': 'Rol de administrador raíz', 'is_active': True},
        )
        if created:
            self.stdout.write(self.style.WARNING(f'Rol "{role_name}" creado.'))

        user = AdminUser(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_active=True,
            is_superuser=True,
        )
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f'Usuario administrador "{username}" creado exitosamente.'
        ))

        try:
            from client.features.logging.facade.factory import LogManagerFactory
            from client.features.logging.facade.context import LogContextBuilder
            from client.features.logging.audit_trail.audit.domain.schemas import AuditLogInputSchema
            from client.features.logging.security.security.domain.schemas import SecurityLogInputSchema

            ctx = LogContextBuilder.from_system('create_platform_admin')
            mgr = LogManagerFactory.create()
            mgr.audit(ctx, AuditLogInputSchema(
                entity_type='AdminUser', entity_id=str(user.pk),
                action='CREATE', description=f'Platform admin created via CLI: {username} ({email})',
            ))
            mgr.security(ctx, SecurityLogInputSchema(
                event_type='ADMIN_CREATED',
                description=f'Platform admin user created: {username}',
                severity='HIGH',
            ))
        except Exception:
            pass
