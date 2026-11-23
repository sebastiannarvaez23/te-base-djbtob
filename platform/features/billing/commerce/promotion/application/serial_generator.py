"""Backwards-compatible re-export of the pure serial generator (domain service)."""

from ..domain.services.serial import generate_voucher_serial

__all__ = ['generate_voucher_serial']
