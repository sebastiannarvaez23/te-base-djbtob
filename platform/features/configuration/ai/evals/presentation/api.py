from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.ai.evals.application.use_cases import (
    ListEvalSuitesUseCase,
    RunHarnessEvalsUseCase,
)
from platform.features.configuration.ai.evals.infrastructure.repositories import (
    DjangoEvalSuiteRepository,
)
from platform.features.configuration.ai.evals.presentation.queries import EvalSuiteListQuery


def _repo():
    return DjangoEvalSuiteRepository()


class EvalSuiteListView(APIView):
    """``GET /api/v1/platform/ai/evals/`` — lista paginada de suites."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(EvalSuiteListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = ListEvalSuitesUseCase(_repo()).execute(query)
        return wrap_response(result.model_dump(mode='json'))


class EvalSuiteRunView(APIView):
    """``POST /api/v1/platform/ai/evals/run/`` — ejecuta suite harness (sin body)."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        result = RunHarnessEvalsUseCase(_repo()).execute()
        audit_log(
            request, 'AiEvalSuiteRun', str(result.id), 'CREATE',
            changes={'passed': result.passed, 'failed': result.failed},
        )
        return wrap_response(result.model_dump(mode='json'), status_code=201)
