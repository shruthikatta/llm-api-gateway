from __future__ import annotations

from fastapi import Depends

from app.auth.exceptions import PermissionDenied
from app.auth.dependencies import get_current_user
from app.models.user import User, UserRole


def require_role(*allowed_roles: UserRole):
    """
    Returns a dependency that ensures the authenticated user has one
    of the allowed roles.
    """

    def dependency(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise PermissionDenied()

        return user

    return dependency


require_admin = require_role(UserRole.ADMIN)

require_developer = require_role(
    UserRole.ADMIN,
    UserRole.DEVELOPER,
)

require_authenticated = require_role(
    UserRole.ADMIN,
    UserRole.DEVELOPER,
    UserRole.VIEWER,
)