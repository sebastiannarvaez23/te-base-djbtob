from django.urls import path

from platform.features.configuration.landing.testimonial.presentation.prompt_api import (
    AckTestimonialPromptView,
    RecordTestimonialPromptSeenView,
    TestimonialPromptDecisionView,
)
from platform.features.configuration.landing.testimonial.presentation.submit_api import (
    SubmitMyTestimonialAPIView,
)

urlpatterns = [
    path('prompt/ack/', AckTestimonialPromptView.as_view(), name='ack-testimonial-prompt'),
    path('prompt/seen/', RecordTestimonialPromptSeenView.as_view(), name='seen-testimonial-prompt'),
    path('prompt/', TestimonialPromptDecisionView.as_view(), name='testimonial-prompt'),
    path('', SubmitMyTestimonialAPIView.as_view(), name='submit-my-testimonial'),
]
