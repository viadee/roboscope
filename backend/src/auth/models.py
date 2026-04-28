"""User, IdP, and SSO models for authentication and authorization."""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, LargeBinary, String, Text, UniqueConstraint, false, func
from sqlalchemy.orm import Mapped, mapped_column

from src.auth.constants import Role
from src.database import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.RUNNER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)
    first_login_complete: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=false()
    )
    # Story SECURITY-1 — set on the seed admin so the frontend forces
    # a password change before the user can do anything else.
    password_change_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=false()
    )


class IdentityProvider(Base, TimestampMixin):
    """Configured OIDC identity provider (Azure AD, Google, GitHub, generic)."""

    __tablename__ = "identity_providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(30))
    issuer_url: Mapped[str] = mapped_column(String(500))
    client_id: Mapped[str] = mapped_column(String(255))
    client_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    scopes: Mapped[str] = mapped_column(String(500), default="openid profile email")
    group_claim_name: Mapped[str] = mapped_column(String(100), default="groups")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    discovery_cache_json: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    discovery_cached_at: Mapped[datetime | None] = mapped_column(default=None, nullable=True)
    last_dry_run_at: Mapped[datetime | None] = mapped_column(default=None, nullable=True)
    last_dry_run_status: Mapped[str | None] = mapped_column(
        String(20), default=None, nullable=True
    )


class IdPGroupMapping(Base, TimestampMixin):
    """Mapping between an IdP group claim value and a Team role grant."""

    __tablename__ = "idp_group_mappings"
    __table_args__ = (
        UniqueConstraint(
            "idp_id", "group_claim_value", name="uq_idp_group_mappings_idp_group"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    idp_id: Mapped[int] = mapped_column(
        ForeignKey("identity_providers.id", ondelete="CASCADE"), index=True
    )
    group_claim_value: Mapped[str] = mapped_column(String(255))
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="viewer")


class OidcLoginAttempt(Base):
    """Ephemeral OIDC login state (state, nonce, PKCE verifier). 10-min TTL."""

    __tablename__ = "oidc_login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    nonce: Mapped[str] = mapped_column(String(128))
    pkce_verifier: Mapped[str] = mapped_column(String(128))
    idp_id: Mapped[int] = mapped_column(
        ForeignKey("identity_providers.id", ondelete="CASCADE")
    )
    return_to: Mapped[str] = mapped_column(String(500), default="/")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True, nullable=False)
