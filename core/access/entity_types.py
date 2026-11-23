"""
core/access/entity_types.py
───────────────────────────
Tipos de entidad con acceso por usuario. Módulo puro (sin I/O) para que las
capas de dominio lo importen sin arrastrar caché ni base de datos.

El template no trae tipos de producto. Un producto nuevo añade miembros aquí
y registra su catálogo en entity_grants.
"""

from enum import Enum


class EntityScopeType(str, Enum):
    """Entidades con acceso por usuario. Vacío hasta que un producto registre tipos."""
