"""Resolve the company schema so inbox views work on the public URLconf."""

from django_tenants.utils import schema_context


def schema_name_for_request(request) -> str:
    company = getattr(getattr(request, 'user', None), 'company', None)
    if company is not None and getattr(company, 'schema_name', None):
        return company.schema_name
    tenant = getattr(request, 'tenant', None)
    return getattr(tenant, 'schema_name', '') or ''


class CompanySchemaMixin:
    """Run the handler inside the JWT company's schema (SPA host = public)."""

    def dispatch(self, request, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        request = self.initialize_request(request, *args, **kwargs)
        self.request = request
        self.headers = self.default_response_headers
        try:
            self.initial(request, *args, **kwargs)
            if request.method.lower() in self.http_method_names:
                handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
            else:
                handler = self.http_method_not_allowed
            schema = schema_name_for_request(request)
            if schema:
                with schema_context(schema):
                    response = handler(request, *args, **kwargs)
            else:
                response = handler(request, *args, **kwargs)
        except Exception as exc:
            response = self.handle_exception(exc)
        self.response = self.finalize_response(request, response, *args, **kwargs)
        return self.response
