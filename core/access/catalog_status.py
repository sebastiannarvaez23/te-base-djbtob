"""
Diagnóstico de catálogo (sección / módulo / funcionalidad) para denegaciones
con códigos específicos (SEC_003, MOD_004, FUNC_003).
"""

from __future__ import annotations

from core.access.result import AccessResult


def diagnose_feature_key(feature_key: str) -> AccessResult | None:
    """Si la feature está bloqueada por catálogo, retorna AccessResult; si no, None.

    Un fallo de base de datos se propaga. No se convierte en «feature fuera
    del plan» (SUB_002).
    """
    if not feature_key:
        return None
    from platform.features.security.access.functionalities.models import Functionality

    row = (
        Functionality.objects
        .filter(key=feature_key)
        .select_related('module', 'module__section')
        .only(
            'key', 'is_active',
            'module__code', 'module__is_active',
            'module__section__code', 'module__section__is_active',
        )
        .first()
    )
    if row is None:
        return None
    section = getattr(row.module, 'section', None)
    if section is not None and not section.is_active:
        return AccessResult.section_inactive(
            section_code=section.code,
            module_code=row.module.code,
        )
    if not row.module.is_active:
        return AccessResult.module_inactive(
            module_code=row.module.code,
            feature_key=feature_key,
        )
    if not row.is_active:
        return AccessResult.functionality_inactive(feature_key)
    return None


def check_module_code(module_code: str) -> AccessResult:
    """Verifica que el módulo (y su sección) estén activos."""
    if not module_code:
        return AccessResult.module_inactive()
    from platform.features.security.access.modules.models import Module

    module = (
        Module.objects
        .filter(code=module_code)
        .select_related('section')
        .only('code', 'is_active', 'section__code', 'section__is_active')
        .first()
    )
    if module is None:
        return AccessResult.module_inactive(module_code=module_code)
    section = getattr(module, 'section', None)
    if section is not None and not section.is_active:
        return AccessResult.section_inactive(
            section_code=section.code,
            module_code=module.code,
        )
    if not module.is_active:
        return AccessResult.module_inactive(module_code=module.code)
    return AccessResult.allowed()


def check_section_code(section_code: str) -> AccessResult:
    """Verifica que la sección esté activa."""
    if not section_code:
        return AccessResult.section_inactive()
    from platform.features.security.access.sections.models import Section

    section = Section.objects.filter(code=section_code).only('code', 'is_active').first()
    if section is None or not section.is_active:
        return AccessResult.section_inactive(section_code=section_code)
    return AccessResult.allowed()
