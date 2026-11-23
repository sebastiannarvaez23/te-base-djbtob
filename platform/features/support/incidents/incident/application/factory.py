"""
Factory que cablea use cases de incidencias con sus implementaciones concretas.
"""

from datetime import timedelta

from platform.features.support.incidents.incident.application.admin_use_cases import (
    UpdateIncidentStatusUseCase,
)
from platform.features.support.incidents.incident.application.attachments import (
    AttachIncidentMediaUseCase,
    SignIncidentAttachmentsUseCase,
)
from platform.features.support.incidents.incident.application.report_incident import (
    ReportIncidentUseCase,
)
from platform.features.support.incidents.incident.application.report_manual_incident import (
    ReportManualIncidentUseCase,
)
from platform.features.support.incidents.incident.application.report_task_failure import (
    ReportTaskFailureUseCase,
)
from platform.features.support.incidents.incident.infrastructure.attachment_storage import (
    MinioIncidentAttachmentStorage,
)
from platform.features.support.incidents.incident.infrastructure.feature_ref_resolver import (
    DjangoFeatureRefResolver,
)
from platform.features.support.incidents.incident.infrastructure.notifier import (
    CeleryIncidentNotifier,
)
from platform.features.support.incidents.incident.infrastructure.reporter_inbox_notifier import (
    OutboxIncidentReporterNotifier,
)
from platform.features.support.incidents.incident.infrastructure.redis_buffer import (
    RedisSessionLogBuffer,
)
from platform.features.support.incidents.incident.infrastructure.redis_draft_store import (
    RedisIncidentDraftStore,
)
from platform.features.support.incidents.incident.infrastructure.repositories import (
    DjangoIncidentRepository,
)


def build_report_use_case() -> ReportIncidentUseCase:
    return ReportIncidentUseCase(
        repository=DjangoIncidentRepository(),
        draft_store=RedisIncidentDraftStore(),
        notifier=CeleryIncidentNotifier(),
        feature_resolver=DjangoFeatureRefResolver(),
    )


def build_report_task_failure_use_case() -> ReportTaskFailureUseCase:
    return ReportTaskFailureUseCase(
        repository=DjangoIncidentRepository(),
        notifier=CeleryIncidentNotifier(),
    )


def build_report_manual_use_case() -> ReportManualIncidentUseCase:
    return ReportManualIncidentUseCase(
        repository=DjangoIncidentRepository(),
        buffer=RedisSessionLogBuffer(),
        notifier=CeleryIncidentNotifier(),
        feature_resolver=DjangoFeatureRefResolver(),
    )


def build_attach_media_use_case() -> AttachIncidentMediaUseCase:
    from django.conf import settings
    window = int(getattr(settings, 'INCIDENT_ATTACHMENT_WINDOW_SECONDS', 900))
    return AttachIncidentMediaUseCase(
        repository=DjangoIncidentRepository(),
        storage=MinioIncidentAttachmentStorage(),
        window=timedelta(seconds=window),
    )


def build_sign_attachments_use_case() -> SignIncidentAttachmentsUseCase:
    return SignIncidentAttachmentsUseCase(storage=MinioIncidentAttachmentStorage())


def build_update_status_use_case() -> UpdateIncidentStatusUseCase:
    from platform.features.communication.messaging.inbox.application.use_cases import (
        CreateAdminNotificationUseCase,
    )
    from platform.features.communication.messaging.inbox.infrastructure.dispatch_trigger import (
        CeleryOutboxDispatchTrigger,
    )
    from platform.features.communication.messaging.inbox.infrastructure.repositories import (
        DjangoOutboxRepository,
    )

    return UpdateIncidentStatusUseCase(
        repository=DjangoIncidentRepository(),
        reporter_notifier=OutboxIncidentReporterNotifier(
            CreateAdminNotificationUseCase(
                outbox_repo=DjangoOutboxRepository(),
                dispatch_trigger=CeleryOutboxDispatchTrigger(),
            ),
        ),
    )
