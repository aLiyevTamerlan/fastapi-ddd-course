from pydantic import BaseModel

# Fields are deliberately loose (optional strings): the domain validates them and returns its own error codes.


class RegisterAcademyRequest(BaseModel):
    name: str | None = None
    contact_email: str | None = None


class UpdateAcademyRequest(BaseModel):
    """Partial update: omitted fields are left unchanged."""

    name: str | None = None
    contact_email: str | None = None


class RejectAcademyRequest(BaseModel):
    reason: str | None = None
