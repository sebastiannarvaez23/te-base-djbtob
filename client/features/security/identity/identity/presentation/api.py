from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser

from client.features.security.identity.identity.application.use_cases import (
    DeleteUserProfilePictureUseCase,
    GetUserPreferencesUseCase,
    GetUserProfileUseCase,
    UpdateUserPreferencesUseCase,
    UpdateUserProfilePictureUseCase,
    UpdateUserProfileUseCase,
)
from client.features.security.identity.identity.infrastructure.repositories import (
    DjangoUserPreferencesRepository,
    DjangoUserProfileRepository,
)
from client.features.security.identity.identity.domain.schemas import (
    UpdateUserPreferencesSchema,
    UpdateUserProfileSchema,
)
from client.features.security.identity.identity.presentation.bodies import (
    UpdateUserPreferencesBody,
    UpdateUserProfileBody,
)
from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from core.permissions import HasSubscriptionAccess
from core.validators import validated_body


# Mapeo de campos de preferencias a feature keys de suscripción.
_PREF_FIELD_TO_FEATURE = {
    'theme':       'settings.preferences.change-theme',
    'date_format': 'settings.preferences.change-date-format',
    'time_format': 'settings.preferences.change-date-format',
    'language':    'settings.preferences.change-language',
    'timezone':    'settings.preferences.change-timezone',
}


def preference_feature_keys(payload: object) -> list[str] | None:
    """Feature keys for fields that passed presentation validation."""
    data = dict(payload) if isinstance(payload, dict) else {}
    body = UpdateUserPreferencesBody(data)
    body.validate()
    keys: list[str] = []
    for field in body.validated_data:
        feature = _PREF_FIELD_TO_FEATURE.get(field)
        if feature and feature not in keys:
            keys.append(feature)
    return keys or None


class UserPreferencesAPIView(APIView):
    """Retrieve and update the authenticated user's preferences."""

    permission_classes = [IsAuthenticated, HasSubscriptionAccess]

    def get_subscription_functionality(self, request):
        """GET valida acceso a la sección; PATCH valida cada campo modificado."""
        if request.method == 'GET':
            return 'settings.preferences.view'
        return preference_feature_keys(request.data)

    def _get_repository(self):
        return DjangoUserPreferencesRepository()

    def get(self, request, *args, **kwargs):
        use_case = GetUserPreferencesUseCase(self._get_repository())
        preferences = use_case.execute(request.user.id)
        return wrap_response(preferences.model_dump(mode='json'))

    @validated_body(UpdateUserPreferencesBody)
    def patch(self, request, *args, body: dict, **kwargs):

        schema = UpdateUserPreferencesSchema(**body)
        use_case = UpdateUserPreferencesUseCase(self._get_repository())
        preferences = use_case.execute(request.user.id, schema)
        audit_log(request, 'UserPreferences', request.user.id, 'UPDATE', changes=body)
        return wrap_response(preferences.model_dump(mode='json'))


# Tipos y tamaño máximo aceptados para la foto de perfil.
_PICTURE_ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
_PICTURE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _serialize_profile(request, profile) -> dict:
    """The repository already exposes ``picture`` as a presigned MinIO URL."""
    return profile.model_dump(mode='json')


class UserProfileAPIView(APIView):
    """Retrieve and update the authenticated user's own profile."""

    permission_classes = [IsAuthenticated, HasSubscriptionAccess]

    def get_subscription_functionality(self, request):
        if request.method == 'GET':
            return 'settings.profile.view'
        return 'settings.profile.edit'

    def _get_repository(self):
        return DjangoUserProfileRepository()

    def get(self, request, *args, **kwargs):
        profile = GetUserProfileUseCase(self._get_repository()).execute(request.user.id)
        if not profile:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        return wrap_response(_serialize_profile(request, profile))

    @validated_body(UpdateUserProfileBody)
    def patch(self, request, *args, body: dict, **kwargs):

        schema = UpdateUserProfileSchema(**body)
        profile = UpdateUserProfileUseCase(self._get_repository()).execute(request.user.id, schema)
        if not profile:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'UserProfile', request.user.id, 'UPDATE', changes=body)
        return wrap_response(_serialize_profile(request, profile))


class UserProfilePictureAPIView(APIView):
    """Upload / replace / remove the authenticated user's profile picture."""

    permission_classes = [IsAuthenticated, HasSubscriptionAccess]
    parser_classes = [MultiPartParser, FormParser]
    subscription_functionality = 'settings.profile.edit'

    def _get_repository(self):
        return DjangoUserProfileRepository()

    def put(self, request, *args, **kwargs):
        picture = request.FILES.get('picture')
        if not picture:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='No image was received (field "picture").',
            )
        if picture.content_type not in _PICTURE_ALLOWED_TYPES:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='Image format not allowed. Use JPG, PNG, WEBP or GIF.',
            )
        if picture.size > _PICTURE_MAX_BYTES:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='The image exceeds the maximum allowed size (5 MB).',
            )

        profile = UpdateUserProfilePictureUseCase(self._get_repository()).execute(request.user.id, picture)
        if not profile:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'UserProfile', request.user.id, 'UPDATE_PICTURE', f'name={picture.name}')
        return wrap_response(_serialize_profile(request, profile))

    def delete(self, request, *args, **kwargs):
        profile = DeleteUserProfilePictureUseCase(self._get_repository()).execute(request.user.id)
        if not profile:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'UserProfile', request.user.id, 'DELETE_PICTURE')
        return wrap_response(_serialize_profile(request, profile))
