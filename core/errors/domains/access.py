"""Códigos de error — access."""
from enum import Enum


class PermErrorCode(str, Enum):
    """Permisos."""

    PERM_INSUFFICIENT        = 'PERM_001'  # Sin permisos para la acción
    PERM_FEATURE_NOT_ALLOWED = 'PERM_002'  # Funcionalidad no habilitada en el rol


PERM_REGISTRY: dict[PermErrorCode, dict] = {
    PermErrorCode.PERM_INSUFFICIENT: {
        'http_status': 403,
        'message': 'Insufficient permissions',
        'detail': 'You do not have enough permissions to perform this action.',
    },
    PermErrorCode.PERM_FEATURE_NOT_ALLOWED: {
        'http_status': 403,
        'message': 'Feature not allowed',
        'detail': 'Your role does not have access to this feature.',
    },
}


class RoleErrorCode(str, Enum):
    """Roles."""

    ROLE_NOT_FOUND              = 'ROLE_001'  # Rol no encontrado
    ROLE_DUPLICATE_NAME         = 'ROLE_002'  # Nombre de rol ya existe
    ROLE_HAS_USERS              = 'ROLE_003'  # Rol con usuarios asignados, no eliminable
    ROLE_UNIVERSAL_NOT_EDITABLE = 'ROLE_004'  # Rol universal, no puede ser modificado por la empresa


ROLE_REGISTRY: dict[RoleErrorCode, dict] = {
    RoleErrorCode.ROLE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Role not found',
        'detail': 'The requested role does not exist.',
    },
    RoleErrorCode.ROLE_DUPLICATE_NAME: {
        'http_status': 409,
        'message': 'Duplicate role name',
        'detail': 'A role with that name already exists.',
    },
    RoleErrorCode.ROLE_HAS_USERS: {
        'http_status': 409,
        'message': 'Role has assigned users',
        'detail': 'This role cannot be deleted because it has users assigned to it.',
    },
    RoleErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE: {
        'http_status': 403,
        'message': 'Universal role not editable',
        'detail': 'This role is managed by the platform and cannot be modified by a company.',
    },
}


class SessionErrorCode(str, Enum):
    """Sesiones."""

    SESSION_NOT_FOUND = 'SESS_001'  # Sesión no encontrada


SESS_REGISTRY: dict[SessionErrorCode, dict] = {
    SessionErrorCode.SESSION_NOT_FOUND: {
        'http_status': 404,
        'message': 'Session not found',
        'detail': 'The requested session does not exist or has already expired.',
    },
}


class UserErrorCode(str, Enum):
    """Usuarios."""

    USER_NOT_FOUND            = 'USER_001'  # Usuario no encontrado
    USER_DUPLICATE_USERNAME   = 'USER_002'  # Username ya existe
    USER_DUPLICATE_EMAIL      = 'USER_003'  # Email ya existe
    USER_DUPLICATE_DOCUMENT   = 'USER_004'  # Documento de identidad duplicado en la empresa


USER_REGISTRY: dict[UserErrorCode, dict] = {
    UserErrorCode.USER_NOT_FOUND: {
        'http_status': 404,
        'message': 'User not found',
        'detail': 'The requested user does not exist.',
    },
    UserErrorCode.USER_DUPLICATE_USERNAME: {
        'http_status': 409,
        'message': 'Duplicate username',
        'detail': 'A user with that username already exists.',
    },
    UserErrorCode.USER_DUPLICATE_EMAIL: {
        'http_status': 409,
        'message': 'Duplicate email',
        'detail': 'A user with that email address already exists.',
    },
    UserErrorCode.USER_DUPLICATE_DOCUMENT: {
        'http_status': 409,
        'message': 'Duplicate identity document',
        'detail': 'Another user in this company already has that identity document.',
    },
}


class ModuleFilterErrorCode(str, Enum):
    """Filtros avanzados por usuario en módulos operativos."""

    MFLT_NOT_FOUND              = 'MFLT_001'  # Filtro no encontrado para el usuario
    MFLT_DUPLICATE_NAME         = 'MFLT_002'  # Nombre repetido en el módulo
    MFLT_WAREHOUSE_UNAVAILABLE  = 'MFLT_003'  # Bodega inexistente o inactiva
    MFLT_ZONE_OUTSIDE_WAREHOUSE = 'MFLT_004'  # Zona no pertenece a la bodega
    MFLT_LIMIT_REACHED          = 'MFLT_005'  # Tope de filtros por módulo


MFLT_REGISTRY: dict[ModuleFilterErrorCode, dict] = {
    ModuleFilterErrorCode.MFLT_NOT_FOUND: {
        'http_status': 404,
        'message': 'Advanced filter not found',
        'detail': 'That advanced filter is no longer available. Reload the list.',
    },
    ModuleFilterErrorCode.MFLT_DUPLICATE_NAME: {
        'http_status': 409,
        'message': 'Duplicate advanced filter name',
        'detail': 'You already have an advanced filter with that name in this module.',
    },
    ModuleFilterErrorCode.MFLT_WAREHOUSE_UNAVAILABLE: {
        'http_status': 400,
        'message': 'Warehouse not available',
        'detail': 'The selected warehouse is inactive or was removed. Choose another warehouse.',
    },
    ModuleFilterErrorCode.MFLT_ZONE_OUTSIDE_WAREHOUSE: {
        'http_status': 400,
        'message': 'Zone outside warehouse',
        'detail': 'One or more selected zones do not belong to the warehouse. Review the zones.',
    },
    ModuleFilterErrorCode.MFLT_LIMIT_REACHED: {
        'http_status': 409,
        'message': 'Advanced filter limit reached',
        'detail': 'You reached the maximum number of advanced filters for this module. Delete one first.',
    },
}


class GrantErrorCode(str, Enum):
    """Accesos otorgados por entidad (almacenes, zonas, …)."""

    GRANT_ENTITY_NOT_FOUND     = 'GRANT_001'  # Entidad a administrar no existe
    GRANT_ENTITY_UNAVAILABLE   = 'GRANT_002'  # Alguna entidad elegida ya no existe
    GRANT_USER_OUTSIDE_COMPANY = 'GRANT_003'  # Algún usuario no es de la empresa


GRANT_REGISTRY: dict[GrantErrorCode, dict] = {
    GrantErrorCode.GRANT_ENTITY_NOT_FOUND: {
        'http_status': 404,
        'message': 'Record not available for access grants',
        'detail': 'That record is no longer available to manage access. Reload the list.',
    },
    GrantErrorCode.GRANT_ENTITY_UNAVAILABLE: {
        'http_status': 400,
        'message': 'Selected records not available',
        'detail': 'One or more selected records were removed. Reload the list and choose again.',
    },
    GrantErrorCode.GRANT_USER_OUTSIDE_COMPANY: {
        'http_status': 400,
        'message': 'User outside company',
        'detail': 'One or more selected users do not belong to your company. Reload the user list.',
    },
}


class SectionErrorCode(str, Enum):
    """Secciones del catálogo (admin / tenant)."""

    SECTION_NOT_FOUND = 'SEC_001'  # Sección no encontrada
    SECTION_DUPLICATE_CODE = 'SEC_002'  # Código de sección ya existe
    SECTION_INACTIVE = 'SEC_003'  # Sección desactivada — acceso bloqueado


SEC_REGISTRY: dict[SectionErrorCode, dict] = {
    SectionErrorCode.SECTION_NOT_FOUND: {
        'http_status': 404,
        'message': 'Section not found',
        'detail': 'The requested section does not exist.',
    },
    SectionErrorCode.SECTION_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate section code',
        'detail': 'A section with that code already exists.',
    },
    SectionErrorCode.SECTION_INACTIVE: {
        'http_status': 403,
        'message': 'Section unavailable',
        'detail': 'This section has been deactivated. Contact your administrator if you need access.',
    },
}


class ModuleErrorCode(str, Enum):
    """Módulos."""

    MODULE_NOT_FOUND      = 'MOD_001'  # Módulo no encontrado
    MODULE_DUPLICATE_CODE = 'MOD_002'  # Código de módulo ya existe
    MODULE_HAS_DEPENDENCIES = 'MOD_003'  # No se pudo borrar: hay registros dependientes
    MODULE_INACTIVE = 'MOD_004'  # Módulo desactivado — acceso bloqueado


MOD_REGISTRY: dict[ModuleErrorCode, dict] = {
    ModuleErrorCode.MODULE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Module not found',
        'detail': 'The requested module does not exist.',
    },
    ModuleErrorCode.MODULE_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate module code',
        'detail': 'A module with that code already exists.',
    },
    ModuleErrorCode.MODULE_HAS_DEPENDENCIES: {
        'http_status': 409,
        'message': 'Module cannot be deleted',
        'detail': 'This module could not be deleted because other records still depend on it. Check features, plans or incidents.',
    },
    ModuleErrorCode.MODULE_INACTIVE: {
        'http_status': 403,
        'message': 'Module unavailable',
        'detail': 'This module has been deactivated. Contact your administrator if you need access.',
    },
}


class FuncErrorCode(str, Enum):
    """Funcionalidades."""

    FUNC_DUPLICATE_KEY = 'FUNC_002'  # Clave de funcionalidad ya existe
    FUNC_INACTIVE = 'FUNC_003'  # Funcionalidad desactivada — acceso bloqueado


FUNC_REGISTRY: dict[FuncErrorCode, dict] = {
    FuncErrorCode.FUNC_DUPLICATE_KEY: {
        'http_status': 409,
        'message': 'Duplicate functionality key',
        'detail': 'A functionality with that key already exists.',
    },
    FuncErrorCode.FUNC_INACTIVE: {
        'http_status': 403,
        'message': 'Functionality unavailable',
        'detail': 'This action has been deactivated. Contact your administrator if you need access.',
    },
}

__all__ = ['PermErrorCode', 'RoleErrorCode', 'SessionErrorCode', 'UserErrorCode', 'GrantErrorCode', 'SectionErrorCode', 'ModuleErrorCode', 'FuncErrorCode', 'PERM_REGISTRY', 'ROLE_REGISTRY', 'SESS_REGISTRY', 'USER_REGISTRY', 'GRANT_REGISTRY', 'SEC_REGISTRY', 'MOD_REGISTRY', 'FUNC_REGISTRY']
