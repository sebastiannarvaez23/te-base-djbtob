"""
Template engine port.

Canonical engine for interpolating HTML / path templates with user data.
The frontend has a smaller TS-side engine used only for live preview; the
two must keep parity on the basic syntax: {{ var }}, {% if %}, {% for %}.
"""
from abc import ABC, abstractmethod
from typing import Any


class ITemplateEngine(ABC):

    @abstractmethod
    def interpolate(
        self,
        template:    str,
        data:        dict[str, Any],
        system_vars: dict[str, Any] = None,
    ) -> str:
        """Render template with missing variables → empty string (lenient).

        Used by HTML/PDF renderers where unspecified fields should
        produce blanks rather than blow up the whole document.
        """
        ...

    @abstractmethod
    def interpolate_strict(
        self,
        template:    str,
        data:        dict[str, Any],
        system_vars: dict[str, Any] = None,
    ) -> str:
        """Render template with missing variables → raise.

        Used by PathResolver where a missing variable would silently
        produce collisions (e.g. ``facturas//x.pdf``). Always fails
        loudly instead.
        """
        ...
