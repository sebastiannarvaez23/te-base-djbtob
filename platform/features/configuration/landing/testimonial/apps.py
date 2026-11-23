from django.apps import AppConfig


class TestimonialAppConfig(AppConfig):
    __test__ = False

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.configuration.landing.testimonial'
    label = 'testimonial'
    verbose_name = 'Testimonials'
