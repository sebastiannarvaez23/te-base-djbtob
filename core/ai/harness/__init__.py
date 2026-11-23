"""
core/ai/harness
───────────────
Runtime genérico del agente (AI / Harness Engineering).

Capas del harness (no es una feature L4; es transversal como el resto de core/ai):
  - parse / facts_gate — protocolo JSON y gate tool-before-facts
  - cancel — señal de interrupción (Redis/cache + Event in-process)
  - extensions — HookBus ordenado
  - environment — CapabilityBoundary (deny-by-default)
  - schemas — contratos Pydantic del run

La lógica de producto (prompts WMS, tools de pedidos) vive en
``client/features/communication/assistant/chat/``.
"""

from .approval import RunApprovalStore
from .cancel import RunCancelStore, is_cancelled
from .environment import CapabilityBoundary
from .extensions import HookBus, HookPoint
from .facts_gate import enforce_tool_before_facts, looks_like_warehouse_fact
from .parse import chunk_text, parse_agent_action
from .schemas import AgentRunStatus, LoopConfig

__all__ = [
    'AgentRunStatus',
    'CapabilityBoundary',
    'HookBus',
    'HookPoint',
    'LoopConfig',
    'RunApprovalStore',
    'RunCancelStore',
    'chunk_text',
    'enforce_tool_before_facts',
    'is_cancelled',
    'looks_like_warehouse_fact',
    'parse_agent_action',
]
