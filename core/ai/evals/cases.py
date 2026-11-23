"""Casos golden del harness (deterministas, sin red)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class EvalCase:
    key: str
    description: str
    run: Callable[[], bool]


def _case_facts_gate_blocks() -> bool:
    from core.ai.harness.facts_gate import enforce_tool_before_facts
    out = enforce_tool_before_facts(
        'Hay 3 pedidos en stock',
        require_tool_before_facts=True,
        orientation=False,
        had_successful_tool=False,
        out_of_scope_message='OUT',
    )
    return out == 'OUT'


def _case_facts_gate_allows_after_tool() -> bool:
    from core.ai.harness.facts_gate import enforce_tool_before_facts
    text = 'Hay 3 pedidos en stock'
    out = enforce_tool_before_facts(
        text,
        require_tool_before_facts=True,
        orientation=False,
        had_successful_tool=True,
        out_of_scope_message='OUT',
    )
    return out == text


def _case_parse_tool() -> bool:
    from core.ai.harness.parse import parse_agent_action
    action = parse_agent_action(
        '{"action":"tool","name":"list_orders","arguments":{"limit":1}}',
    )
    return bool(action and action.action == 'tool' and action.name == 'list_orders')


def _case_capability_deny() -> bool:
    from core.ai.harness.environment import CapabilityBoundary
    return not CapabilityBoundary(['list_orders']).allows('drop_database')


def _case_router_fallback() -> bool:
    from core.ai.model_layer.router import ModelRouter
    from core.ai.model_layer.schemas import ModelRouteDecision, ModelRoutingTable
    table = ModelRoutingTable(routes={
        'chat': ModelRouteDecision(provider='local', fallbacks=['fake']),
    })
    route = ModelRouter(table).resolve('chat', preferred_provider='openai')
    return route.provider == 'openai' and 'local' in route.fallbacks


def _case_approval_store_roundtrip() -> bool:
    from core.ai.harness.approval import RunApprovalStore
    from core.ids import uuid7
    store = RunApprovalStore()
    run_id = uuid7()
    store.begin_wait(run_id)
    store.resolve(run_id, 'approved')
    decision = store.wait(run_id, timeout_s=0.5)
    store.clear(run_id)
    return decision == 'approved'


HARNESS_EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase('facts_gate_blocks', 'Blocks warehouse facts without tool', _case_facts_gate_blocks),
    EvalCase('facts_gate_after_tool', 'Keeps facts after successful tool', _case_facts_gate_allows_after_tool),
    EvalCase('parse_tool', 'Parses tool JSON action', _case_parse_tool),
    EvalCase('capability_deny', 'CapabilityBoundary deny-by-default', _case_capability_deny),
    EvalCase('router_fallback', 'Preferred provider reorders fallbacks', _case_router_fallback),
    EvalCase('approval_store', 'HITL approval store roundtrip', _case_approval_store_roundtrip),
)
