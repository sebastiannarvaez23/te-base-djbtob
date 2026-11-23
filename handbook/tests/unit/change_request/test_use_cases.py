"""Solicitud de cambio: el tecnológico propone; el Administrador de Plataforma aplica o descarta."""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.errors import (
    AppErrorCode,
    ConflictException,
    PermissionException,
    ValidationAppException,
)
from handbook.core.constants import (
    APPROVE_FEATURE_KEY,
    CHANGE_REQUEST_APPROVED,
    CHANGE_REQUEST_PENDING,
    CHANGE_REQUEST_REJECTED,
    PROPOSE_FEATURE_KEY,
)
from handbook.core.viewer import HandbookViewer
from handbook.features.docs.governance.change_request.application.use_cases import (
    ApproveChangeRequestUseCase,
    RejectChangeRequestUseCase,
    SubmitChangeRequestUseCase,
)
from handbook.features.docs.governance.change_request.infrastructure.memory import (
    InMemoryChangeRequestRepository,
)


pytestmark = pytest.mark.unit

TECH_ID = uuid4()
PLATFORM_ADMIN_ID = uuid4()
PAGE_ID = uuid4()
WORKING_ID = uuid4()
REASON = 'Alineamos el manual de pedidos con el flujo actual de reserva.'


def _tech() -> HandbookViewer:
    return HandbookViewer.admin(
        user_id=str(TECH_ID),
        features=frozenset({PROPOSE_FEATURE_KEY}),
    )


def _platform_admin() -> HandbookViewer:
    return HandbookViewer.admin(
        user_id=str(PLATFORM_ADMIN_ID),
        features=frozenset({APPROVE_FEATURE_KEY}),
        is_superuser=True,
    )


def _client() -> HandbookViewer:
    return HandbookViewer.client(
        user_id=str(uuid4()),
        features=frozenset({PROPOSE_FEATURE_KEY, APPROVE_FEATURE_KEY}),
        schema_name='acme',
    )


@pytest.fixture
def repo() -> InMemoryChangeRequestRepository:
    return InMemoryChangeRequestRepository()


def test_client_admin_cannot_submit(repo):
    with pytest.raises(PermissionException) as exc:
        SubmitChangeRequestUseCase(repo).execute(
            page_id=PAGE_ID,
            working_version_id=WORKING_ID,
            reason=REASON,
            viewer=_client(),
        )
    assert exc.value.code == AppErrorCode.HBK_PROPOSE_FORBIDDEN
    assert repo.rows == {}


def test_tech_cannot_approve_or_reject(repo):
    pending = SubmitChangeRequestUseCase(repo).execute(
        page_id=PAGE_ID,
        working_version_id=WORKING_ID,
        reason=REASON,
        viewer=_tech(),
    )
    with pytest.raises(PermissionException) as exc:
        ApproveChangeRequestUseCase(repo).execute(pending.id, _tech())
    assert exc.value.code == AppErrorCode.HBK_APPROVE_FORBIDDEN
    with pytest.raises(PermissionException):
        RejectChangeRequestUseCase(repo).execute(pending.id, _tech())
    assert repo.get(pending.id).status == CHANGE_REQUEST_PENDING
    assert PAGE_ID not in repo.published


def test_submit_requires_a_real_reason(repo):
    with pytest.raises(ValidationAppException) as exc:
        SubmitChangeRequestUseCase(repo).execute(
            page_id=PAGE_ID,
            working_version_id=WORKING_ID,
            reason='   corto  ',
            viewer=_tech(),
        )
    assert exc.value.code == AppErrorCode.HBK_REASON_REQUIRED


def test_one_pending_per_page(repo):
    SubmitChangeRequestUseCase(repo).execute(
        page_id=PAGE_ID,
        working_version_id=WORKING_ID,
        reason=REASON,
        viewer=_tech(),
    )
    with pytest.raises(ConflictException) as exc:
        SubmitChangeRequestUseCase(repo).execute(
            page_id=PAGE_ID,
            working_version_id=uuid4(),
            reason=REASON,
            viewer=_tech(),
        )
    assert exc.value.code == AppErrorCode.HBK_PENDING_EXISTS


def test_approve_publishes_working_copy(repo):
    pending = SubmitChangeRequestUseCase(repo).execute(
        page_id=PAGE_ID,
        working_version_id=WORKING_ID,
        reason=REASON,
        viewer=_tech(),
    )
    approved = ApproveChangeRequestUseCase(repo).execute(
        pending.id, _platform_admin(), review_note='Ok para operación.',
    )
    assert approved.status == CHANGE_REQUEST_APPROVED
    assert approved.reviewed_by == PLATFORM_ADMIN_ID
    assert repo.published[PAGE_ID] == WORKING_ID
    assert repo.discarded == []


def test_reject_discards_working_copy(repo):
    pending = SubmitChangeRequestUseCase(repo).execute(
        page_id=PAGE_ID,
        working_version_id=WORKING_ID,
        reason=REASON,
        viewer=_tech(),
    )
    rejected = RejectChangeRequestUseCase(repo).execute(
        pending.id, _platform_admin(), review_note='El procedimiento cambió.',
    )
    assert rejected.status == CHANGE_REQUEST_REJECTED
    assert WORKING_ID in repo.discarded
    assert PAGE_ID not in repo.published


def test_cannot_review_twice(repo):
    pending = SubmitChangeRequestUseCase(repo).execute(
        page_id=PAGE_ID,
        working_version_id=WORKING_ID,
        reason=REASON,
        viewer=_tech(),
    )
    ApproveChangeRequestUseCase(repo).execute(pending.id, _platform_admin())
    with pytest.raises(ConflictException) as exc:
        RejectChangeRequestUseCase(repo).execute(pending.id, _platform_admin())
    assert exc.value.code == AppErrorCode.HBK_NOT_PENDING
