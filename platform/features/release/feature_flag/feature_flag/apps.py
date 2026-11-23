from django.apps import AppConfig


class FeatureFlagAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.release.feature_flag.feature_flag'
    label = 'feature_flag'
    verbose_name = 'Feature Flags'
