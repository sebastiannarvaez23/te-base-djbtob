from django.apps import AppConfig


class AuditLogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.logging.audit_trail.audit'
    label = 'logging_audit'
