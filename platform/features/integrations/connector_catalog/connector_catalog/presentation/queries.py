from core.query import QueryFilter, QueryParam


class ConnectorCatalogListQuery(QueryFilter):
    active_only = QueryParam(coerce=bool)
