"""
JinjaTemplateEngine — sandboxed implementation of ITemplateEngine.

Why sandboxed:
  Users (admins) write templates. We cannot allow them to reach Python
  builtins, filesystem, or arbitrary attributes (Jinja's default
  Environment exposes things like {{ foo.__class__.__mro__ }}).

  SandboxedEnvironment blocks unsafe attribute access and dangerous
  imports while keeping {{ var }}, {% if %}, {% for %} fully usable.
"""
from typing import Any

from jinja2 import StrictUndefined, Undefined
from jinja2.sandbox import SandboxedEnvironment

from core.errors import AppErrorCode, AppException

from ..domain.template_engine import ITemplateEngine


class JinjaTemplateEngine(ITemplateEngine):
    """Two SandboxedEnvironments share the same security config; they
    differ only in how they handle missing variables.

    Keeping two envs is cheaper than reconfiguring on every render and
    lets the strict/lenient distinction live entirely in this class.
    """

    def __init__(self):
        self._lenient = self._build_env(strict=False)
        self._strict  = self._build_env(strict=True)

    @staticmethod
    def _build_env(strict: bool) -> SandboxedEnvironment:
        return SandboxedEnvironment(
            autoescape=False,       # autoescape handled per-call (HTML yes, path no)
            undefined=StrictUndefined if strict else Undefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def interpolate(
        self,
        template:    str,
        data:        dict[str, Any],
        system_vars: dict[str, Any] = None,
    ) -> str:
        return self._render(self._lenient, template, data, system_vars)

    def interpolate_strict(
        self,
        template:    str,
        data:        dict[str, Any],
        system_vars: dict[str, Any] = None,
    ) -> str:
        return self._render(self._strict, template, data, system_vars)

    def _render(self, env, template, data, system_vars):
        try:
            jinja_template = env.from_string(template)
            context = {**(system_vars or {}), **(data or {})}
            return jinja_template.render(**context)
        except Exception as exc:
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'Template interpolation failed: {exc.__class__.__name__}: {exc}',
            )
