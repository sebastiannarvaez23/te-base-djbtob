from django.contrib import admin
from django.contrib import admin
from django_tenants.admin import TenantAdminMixin
from platform.features.company.tenant.company.models import Company


@admin.register(Company)
class CompanyAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('schema_name', 'name')
