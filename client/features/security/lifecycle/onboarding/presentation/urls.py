from django.urls import path

from platform.features.billing.commerce.promotion.presentation.onboarding_api import (
    OnboardingPromotionApplyView,
    OnboardingPromotionValidateView,
)

from .api import (
    OnboardingAdminUserAPIView,
    OnboardingCheckUsernameAPIView,
    OnboardingCompanyAPIView,
    OnboardingFinalizeAPIView,
    OnboardingPaymentAPIView,
    OnboardingPublishedPolicyAPIView,
    OnboardingResendResumeLinkAPIView,
    OnboardingResumeAPIView,
    OnboardingStartAPIView,
    OnboardingStateAPIView,
    OnboardingSubscriptionAPIView,
)

urlpatterns = [
    path('start/',         OnboardingStartAPIView.as_view(),             name='onboarding-start'),
    path('resume/',        OnboardingResumeAPIView.as_view(),            name='onboarding-resume'),
    path('resume-link/',   OnboardingResendResumeLinkAPIView.as_view(),  name='onboarding-resume-link'),
    path('state/',         OnboardingStateAPIView.as_view(),             name='onboarding-state'),
    path('company/',       OnboardingCompanyAPIView.as_view(),           name='onboarding-company'),
    path('check-username/', OnboardingCheckUsernameAPIView.as_view(),    name='onboarding-check-username'),
    path('admin-user/',    OnboardingAdminUserAPIView.as_view(),         name='onboarding-admin-user'),
    path('subscription/',  OnboardingSubscriptionAPIView.as_view(),      name='onboarding-subscription'),
    path('payment/',       OnboardingPaymentAPIView.as_view(),           name='onboarding-payment'),
    path('finalize/',      OnboardingFinalizeAPIView.as_view(),          name='onboarding-finalize'),
    path(
        'policies/<str:code>/',
        OnboardingPublishedPolicyAPIView.as_view(),
        name='onboarding-published-policy',
    ),
    path('promotions/validate/', OnboardingPromotionValidateView.as_view(), name='onboarding-promotion-validate'),
    path('promotions/apply/',    OnboardingPromotionApplyView.as_view(),    name='onboarding-promotion-apply'),
]
