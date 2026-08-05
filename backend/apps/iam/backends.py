"""Authentication backend allowing sign-in by username **or** PF/staff number."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from apps.iam.models import User


class PFOrUsernameBackend(ModelBackend):
    """Authenticate against either ``username`` or a non-empty ``pf_number``.

    Counter staff often have no email/username they remember — they sign in with
    their payroll-file (PF) number. Falls through to the default username match.
    """

    def authenticate(
        self,
        request: Any,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        if not username or password is None:
            return None
        qs = User.objects.filter(Q(username=username) | Q(pf_number=username, pf_number__gt=""))
        # Prefer an exact username match; fall back to the PF-number match. This avoids
        # ambiguity if one person's PF number happens to equal another's username.
        user = qs.filter(username=username).first() or qs.first()
        if user is None:
            # Run the default hasher once to reduce timing differences.
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
