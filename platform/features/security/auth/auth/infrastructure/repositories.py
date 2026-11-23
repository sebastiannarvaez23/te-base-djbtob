from typing import List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from platform.features.security.auth.auth.domain.interfaces import (
    IAdminAuthRepository,
    IAdminSessionRepository,
    IAdminTrustedDeviceRepository,
    IAdminUserLookup,
)
from platform.features.security.auth.auth.domain.schemas import AdminMenuItemSchema
from platform.features.security.auth.auth.models import AdminTrustedDevice
from platform.features.security.identity.users.models import AdminUser


class DjangoAdminAuthRepository(IAdminAuthRepository):

    def get_by_username(self, username: str) -> Optional[AdminUser]:
        try:
            return AdminUser.objects.select_related('role').get(
                username=username, is_active=True,
            )
        except AdminUser.DoesNotExist:
            return None

    def authenticate(self, username: str, password: str) -> Optional[AdminUser]:
        user = self.get_by_username(username)
        if user is None:
            return None
        if not user.check_password(password):
            return None
        if user.role_id and not user.role.is_active:
            return None
        return user

    def touch_last_login(self, user: AdminUser) -> None:
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])


class DjangoAdminSessionRepository(IAdminSessionRepository):

    def build_menu(
        self,
        role: object,
        *,
        is_superuser: bool = False,
    ) -> Tuple[List[AdminMenuItemSchema], List[str]]:
        from core.module_codes import admin_module_catalog_index, canonicalize_module_codes, normalize_module_route

        from platform.features.security.access.roles.models import (
            AdminFeature,
            AdminModule,
            AdminRoleFeature,
            AdminRoleModule,
        )

        if is_superuser:
            features = list(
                AdminFeature.objects.filter(is_active=True)
                .order_by('module__code', 'key')
                .values_list('key', flat=True)
            )
            modules = list(
                AdminModule.objects.filter(is_active=True, is_sidebar=True)
                .select_related('section')
                .order_by('section__order', 'order')
            )
            menu = [
                AdminMenuItemSchema(
                    id=str(m.id),
                    code=m.code,
                    name=m.name,
                    icon=m.icon,
                    route=normalize_module_route(m.route),
                    section=m.section.code,
                    section_name=m.section.name,
                )
                for m in modules
                if (m.route or '').strip()
            ]
            return menu, features

        if not role:
            return [], []

        rol_features = (
            AdminRoleFeature.objects
            .filter(rol=role, feature__is_active=True)
            .select_related('feature', 'feature__module')
        )
        features = [rf.feature.key for rf in rol_features]
        feature_module_codes = list(dict.fromkeys(rf.feature.module.code for rf in rol_features))

        direct_module_codes = list(
            AdminRoleModule.objects.filter(rol=role).values_list('module_code', flat=True)
        )
        allowed_codes = list(dict.fromkeys(feature_module_codes + direct_module_codes))
        allowed_codes = canonicalize_module_codes(
            allowed_codes,
            catalog=admin_module_catalog_index(),
        )

        module_map = {
            m.code: m
            for m in AdminModule.objects.filter(
                code__in=allowed_codes, is_active=True, is_sidebar=True,
            ).select_related('section')
        }
        menu = sorted(
            [
                AdminMenuItemSchema(
                    id=str(module_map[code].id),
                    code=code,
                    name=module_map[code].name,
                    icon=module_map[code].icon,
                    route=normalize_module_route(module_map[code].route),
                    section=module_map[code].section.code,
                    section_name=module_map[code].section.name,
                )
                for code in allowed_codes
                if code in module_map and (module_map[code].route or '').strip()
            ],
            key=lambda item: (module_map[item.code].section.order, module_map[item.code].order),
        )
        return menu, features


class DjangoAdminUserLookup(IAdminUserLookup):

    def get_active_by_id(self, user_id, *, with_role: bool = False):
        qs = AdminUser.objects.filter(pk=user_id, is_active=True)
        if with_role:
            qs = qs.select_related('role')
        return qs.first()


class DjangoAdminTrustedDeviceRepository(IAdminTrustedDeviceRepository):

    def find_active(self, user, device_hash: str, *, cutoff):
        return (
            AdminTrustedDevice.objects
            .filter(
                user=user,
                device_hash=device_hash,
                revoked_at__isnull=True,
                last_used_at__gte=cutoff,
            )
            .first()
        )

    def touch(self, device, *, ip: str = '', user_agent: str = '') -> None:
        device.last_used_at = timezone.now()
        device.last_ip = ip or None
        device.last_ua = (user_agent or '')[:512]
        device.save(update_fields=['last_used_at', 'last_ip', 'last_ua'])

    def register(
        self, user, device_hash: str, *, ip: str = '', user_agent: str = '',
        max_devices: int = 10,
    ) -> None:
        now = timezone.now()
        with transaction.atomic():
            device, created = AdminTrustedDevice.objects.select_for_update().get_or_create(
                user=user,
                device_hash=device_hash,
                defaults={
                    'last_used_at': now,
                    'last_ip': ip or None,
                    'last_ua': (user_agent or '')[:512],
                    'revoked_at': None,
                },
            )
            if not created:
                device.revoked_at = None
                device.last_used_at = now
                device.last_ip = ip or None
                device.last_ua = (user_agent or '')[:512]
                device.save(update_fields=['revoked_at', 'last_used_at', 'last_ip', 'last_ua'])
            active = (
                AdminTrustedDevice.objects
                .filter(user=user, revoked_at__isnull=True)
                .order_by('-last_used_at')
            )
            for stale in active[max_devices:]:
                stale.revoked_at = now
                stale.save(update_fields=['revoked_at'])
