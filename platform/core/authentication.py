"""Backwards-compatible shim.

All platform views that need admin authentication import
`AdminTokenAuthentication` from here.  It points to the JWT-based
cookie authenticator so every import site keeps working.
"""
from core.auth.cookie_authentication import JWTAdminAccessAuthentication as AdminTokenAuthentication

__all__ = ['AdminTokenAuthentication']
