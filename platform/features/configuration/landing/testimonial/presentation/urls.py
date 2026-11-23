from django.urls import path

from platform.features.configuration.landing.testimonial.presentation.api import (
    TestimonialDetailView,
    TestimonialListCreateView,
)
from platform.features.configuration.landing.testimonial.presentation.settings_api import (
    RepromptTestimonialsView,
    TestimonialPromptSettingsView,
)

urlpatterns = [
    path('settings/', TestimonialPromptSettingsView.as_view(), name='platform-testimonial-settings'),
    path('reprompt/', RepromptTestimonialsView.as_view(), name='platform-testimonials-reprompt'),
    path('', TestimonialListCreateView.as_view(), name='platform-testimonials'),
    path('<uuid:pk>/', TestimonialDetailView.as_view(), name='platform-testimonial-detail'),
]
