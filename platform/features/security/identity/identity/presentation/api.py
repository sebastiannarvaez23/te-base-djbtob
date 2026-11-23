from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.security.identity.identity.application.use_cases import (
    DeleteAdminUserProfilePictureUseCase,
    GetAdminUserPreferencesUseCase,
    GetAdminUserProfileUseCase,
    UpdateAdminUserPreferencesUseCase,
    UpdateAdminUserProfilePictureUseCase,
    UpdateAdminUserProfileUseCase,
)
from platform.features.security.identity.identity.domain.schemas import (
    UpdateAdminUserPreferencesSchema,
    UpdateAdminUserProfileSchema,
)
from platform.features.security.identity.identity.infrastructure.repositories import (
    DjangoAdminUserPreferencesRepository,
    DjangoAdminUserProfileRepository,
)
from platform.features.security.identity.identity.presentation.bodies import (
    UpdateAdminUserPreferencesBody,
    UpdateAdminUserProfileBody,
)


_PICTURE_ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
_PICTURE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _serialize_profile(profile) -> dict:
    return profile.model_dump(mode='json')


class AdminUserPreferencesAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminUserPreferencesRepository()

    def get(self, request):
        preferences = GetAdminUserPreferencesUseCase(self._get_repository()).execute(request.user.id)
        return wrap_response(preferences.model_dump(mode='json'))

    @validated_body(UpdateAdminUserPreferencesBody)
    def patch(self, request, *, body: dict):

        schema = UpdateAdminUserPreferencesSchema(**body)
        preferences = UpdateAdminUserPreferencesUseCase(self._get_repository()).execute(request.user.id, schema)
        audit_log(request, 'AdminUserPreferences', request.user.id, 'UPDATE', changes=body)
        return wrap_response(preferences.model_dump(mode='json'))


class AdminUserProfileAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminUserProfileRepository()

    def get(self, request):
        profile = GetAdminUserProfileUseCase(self._get_repository()).execute(request.user.id)
        if not profile:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        return wrap_response(_serialize_profile(profile))

    @validated_body(UpdateAdminUserProfileBody)
    def patch(self, request, *, body: dict):

        schema = UpdateAdminUserProfileSchema(**body)
        profile = UpdateAdminUserProfileUseCase(self._get_repository()).execute(request.user.id, schema)
        if not profile:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'AdminUserProfile', request.user.id, 'UPDATE', changes=body)
        return wrap_response(_serialize_profile(profile))


class AdminUserProfilePictureAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_repository(self):
        return DjangoAdminUserProfileRepository()

    def put(self, request):
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

        profile = UpdateAdminUserProfilePictureUseCase(self._get_repository()).execute(request.user.id, picture)
        if not profile:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'AdminUserProfile', request.user.id, 'UPDATE_PICTURE', f'name={picture.name}')
        return wrap_response(_serialize_profile(profile))

    def delete(self, request):
        profile = DeleteAdminUserProfilePictureUseCase(self._get_repository()).execute(request.user.id)
        if not profile:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'AdminUserProfile', request.user.id, 'DELETE_PICTURE')
        return wrap_response(_serialize_profile(profile))
