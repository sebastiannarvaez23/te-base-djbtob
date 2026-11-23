"""Pure domain services for promotion vouchers.

No Django, no ORM, no infrastructure — only Python + Pydantic schemas +
``core.errors`` codes. These encode the promotion business rules so both the
application use cases and the infrastructure adapters can reuse them without
duplicating logic or reaching into Django.
"""
