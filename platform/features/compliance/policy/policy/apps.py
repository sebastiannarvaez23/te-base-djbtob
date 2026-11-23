from django.apps import AppConfig


class PolicyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.compliance.policy.policy'
    label = 'compliance_policy'
    verbose_name = 'Compliance policies'
