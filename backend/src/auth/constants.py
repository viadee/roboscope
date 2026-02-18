"""Auth-related constants and enums."""

from enum import StrEnum


class Role(StrEnum):
    """User roles for RBAC."""

    VIEWER = "viewer"
    RUNNER = "runner"
    EDITOR = "editor"
    ADMIN = "admin"


# Role hierarchy: higher index = more permissions
ROLE_HIERARCHY = {
    Role.VIEWER: 0,
    Role.RUNNER: 1,
    Role.EDITOR: 2,
    Role.ADMIN: 3,
}

# Error messages
ERR_INVALID_CREDENTIALS = "Invalid email or password"
ERR_INACTIVE_USER = "User account is inactive"
ERR_TOKEN_EXPIRED = "Token has expired"
ERR_TOKEN_INVALID = "Invalid token"
ERR_INSUFFICIENT_PERMISSIONS = "Insufficient permissions"
