"""
core/access/invalidation.py
───────────────────────────
Puntos de entrada únicos para invalidar acceso cuando el admin cambia
catálogo (módulo / funcionalidad / plan) o desactiva un rol.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('app.api')


def invalidate_on_section_change(section_id) -> None:
    """Sección activa/inactiva: bump epoch global (features se recargan sin módulos de esa sección)."""
    from core.access.subscription import SubscriptionCache
    SubscriptionCache.bump_catalog_epoch()


def invalidate_on_functionality_change(functionality_id) -> None:
    from core.access.subscription import SubscriptionCache
    SubscriptionCache.invalidate_by_functionality(functionality_id)


def invalidate_on_module_change(module_id) -> None:
    from core.access.subscription import SubscriptionCache
    SubscriptionCache.invalidate_by_module(module_id)


def invalidate_on_subscription_plan_change(subscription_id) -> None:
    from core.access.subscription import SubscriptionCache
    SubscriptionCache.invalidate_subscription(str(subscription_id))
    SubscriptionCache.bump_catalog_epoch()


def revoke_sessions_for_tenant_role(role_id) -> int:
    """Revoca refresh tokens de todos los usuarios con el rol dado."""
    try:
        from django.contrib.auth import get_user_model
        from core.auth.refresh_service import revoke_all_for_users
        from core.access.role_cache import RoleFeatureCache

        RoleFeatureCache.invalidate(str(role_id))
        User = get_user_model()
        user_ids = list(
            User.objects.filter(rol_id=role_id).values_list('id', flat=True)
        )
        if not user_ids:
            return 0
        return revoke_all_for_users(user_ids, 'client')
    except Exception:
        logger.warning(
            'Failed to revoke sessions for tenant role_id=%s',
            role_id,
            exc_info=True,
        )
        return 0


def revoke_sessions_for_tenant_role_in_company(role_id, company_id) -> int:
    """Revoca sesiones de usuarios del rol en una empresa (CompanyRolAccess)."""
    try:
        from django.contrib.auth import get_user_model
        from core.auth.refresh_service import revoke_all_for_users
        from core.access.role_cache import RoleFeatureCache

        RoleFeatureCache.invalidate(str(role_id))
        User = get_user_model()
        user_ids = list(
            User.objects.filter(rol_id=role_id, company_id=company_id)
            .values_list('id', flat=True)
        )
        if not user_ids:
            return 0
        return revoke_all_for_users(user_ids, 'client')
    except Exception:
        logger.warning(
            'Failed to revoke sessions role=%s company=%s',
            role_id, company_id,
            exc_info=True,
        )
        return 0


def revoke_sessions_for_admin_role(role_id) -> int:
    """Revoca sesiones de admins de plataforma con el rol dado."""
    try:
        from platform.features.security.identity.users.models import AdminUser
        from core.auth.refresh_service import revoke_all_for_users

        user_ids = list(
            AdminUser.objects.filter(role_id=role_id).values_list('id', flat=True)
        )
        if not user_ids:
            return 0
        return revoke_all_for_users(user_ids, 'admin')
    except Exception:
        logger.warning(
            'Failed to revoke sessions for admin role_id=%s',
            role_id,
            exc_info=True,
        )
        return 0
