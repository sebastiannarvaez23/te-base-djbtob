from enum import Enum


class OnboardingStatus(str, Enum):
    IN_PROGRESS         = 'in_progress'
    COMPLETED           = 'completed'
    EXPIRED             = 'expired'
    FAILED_PROVISIONING = 'failed_provisioning'


class OnboardingStep(str, Enum):
    COMPANY      = 'company'
    ADMIN_USER   = 'admin_user'
    SUBSCRIPTION = 'subscription'
    PAYMENT      = 'payment'
    CONFIRMATION = 'confirmation'
