from core.query import QueryFilter, QueryParam
from handbook.core.constants import LOCALES
from platform.features.security.access.functionalities.domain.categories import (
    FUNCTIONALITY_CATEGORIES,
)


class HandbookHelpQuery(QueryFilter):
    ALLOW_UNPAGINATED = True
    locale = QueryParam(coerce=str, choices=sorted(LOCALES))
    feature_key = QueryParam(
        coerce=str,
        min_length=3,
        max_length=80,
        pattern=r'^[a-z0-9]+(?:[.\-][a-z0-9]+)*$',
        required=True,
    )


class HandbookLocaleQuery(QueryFilter):
    ALLOW_UNPAGINATED = True
    locale = QueryParam(coerce=str, choices=sorted(LOCALES))


class HandbookSearchQuery(QueryFilter):
    ALLOW_UNPAGINATED = True
    locale = QueryParam(coerce=str, choices=sorted(LOCALES))
    q = QueryParam(coerce=str, min_length=2, max_length=80, pattern=r'^[\w\s\-áéíóúñÁÉÍÓÚÑ]+$')


class HandbookFeatureQuery(QueryFilter):
    audience = QueryParam(coerce=str, choices=['wms', 'admin'])
    q = QueryParam(coerce=str, max_length=80, pattern=r'^[\w .\-]*$')
    category = QueryParam(coerce=str, choices=list(FUNCTIONALITY_CATEGORIES))


class HandbookManagePageQuery(QueryFilter):
    """Listado paginado. Sin filtros de negocio."""


class HandbookRequestQuery(QueryFilter):
    status = QueryParam(coerce=str, choices=['pending'])
