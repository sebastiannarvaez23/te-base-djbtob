import uuid
from pydantic import BaseModel


class RolSchema(BaseModel):
    """Lightweight projection of the ``Rol`` model.

    Lives here for historical reasons (was originally part of the legacy
    signup feature). It is now consumed by other features
    (e.g. ``client.features.security.identity.users``) so the file stays even
    after the legacy ``SignUpUserUseCase`` was removed.
    """
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}
