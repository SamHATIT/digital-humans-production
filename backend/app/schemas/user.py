"""
Pydantic schemas for User model validation and serialization.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema with common attributes."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)


class UserCreate(UserBase):
    """Schema for creating a new user.

    The optional ``requested_tier`` carries the tier the user clicked on
    in /pricing. We honour it ONLY for ``free`` for now (the other tiers
    are not self-serve yet — see BIZ-001 in BACKLOG.md). Anything else
    falls back to ``free`` server-side.

    RGPD (vague B / lot B3) — ``consent_cgv`` and ``consent_version`` are
    left optional/defaulted here (not FastAPI-required) on purpose: a
    missing or false consent must surface as an explicit 400 with a clear
    message from the route handler, not a generic 422 from pydantic.
    """
    password: str = Field(..., min_length=8, max_length=100)
    requested_tier: str | None = Field(default=None, max_length=20)
    consent_cgv: bool = False
    consent_version: str | None = Field(default=None, max_length=16)


class SignupRequest(BaseModel):
    """Schema for the first step of signup (ONBOARDING-002).

    The user fills the form, we generate a verify-token and email the link.
    Nothing is persisted in the users table at this point.

    RGPD (vague B / lot B3) — same rationale as ``UserCreate`` above for
    ``consent_cgv``/``consent_version`` being optional here rather than
    pydantic-required.
    """
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    requested_tier: str | None = Field(default=None, max_length=20)
    lang: str | None = Field(default="fr", max_length=4)
    consent_cgv: bool = False
    consent_version: str | None = Field(default=None, max_length=16)


class SignupConfirm(BaseModel):
    """Schema for the second step — redeeming the verify-token."""
    token: str = Field(..., min_length=20)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None


class UserInDB(UserBase):
    """Schema for user stored in database."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class User(UserInDB):
    """Schema for user response (public)."""
    pass


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data."""
    user_id: Optional[int] = None
    email: Optional[str] = None
