"""Permisos DRF del handbook. La ACL de cada recurso vive en use cases."""

from rest_framework.permissions import BasePermission

from handbook.core.access import can_approve, can_manage, can_propose
from handbook.core.session import resolve_viewer


class AllowHandbookRead(BasePermission):
    """Lectura pública opcionalmente autenticada. El use case filtra el árbol."""

    def has_permission(self, request, view):
        return True


class IsHandbookStaff(BasePermission):
    """CMS: tecnológico o Administrador de Plataforma."""

    def has_permission(self, request, view):
        return can_manage(resolve_viewer(request))


class IsHandbookProposer(BasePermission):
    """Admin tecnológico: working copy y envío de solicitud."""

    def has_permission(self, request, view):
        return can_propose(resolve_viewer(request))


class IsHandbookApprover(BasePermission):
    """Administrador de Plataforma: aprobar o denegar."""

    def has_permission(self, request, view):
        return can_approve(resolve_viewer(request))


# Alias histórico: el "editor" ya no publica; solo staff del CMS.
IsHandbookEditor = IsHandbookStaff
