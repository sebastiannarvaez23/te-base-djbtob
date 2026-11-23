from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect

from core.audit import security_log
from platform.features.company.tenant.company.models import Domain


class CompanyAdminMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            if request.user.is_authenticated and request.user.company is not None:
                company_domain = Domain.objects.filter(tenant=request.user.company).first()
                request_domain = request.get_host().split(':')[0]
                if company_domain is None or request_domain != company_domain.domain:
                    expected = company_domain.domain if company_domain else 'None'
                    security_log(request, 'ADMIN_DOMAIN_MISMATCH',
                                 target_user_id=request.user.pk,
                                 resource='/admin/',
                                 detail=f'request_domain={request_domain} expected={expected}')
                    auth_logout(request)
                    messages.error(request, 'Credenciales incorrectas. Ingrese el dominio correcto.')
                    return redirect('admin:login')
        return self.get_response(request)
