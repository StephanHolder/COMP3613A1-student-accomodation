"""Service-layer errors.

All three subclass ``ValueError`` so the existing HTML routes (which catch
``ValueError``) keep working unchanged. The JSON API maps each class to an
HTTP status code: NotFoundError -> 404, ForbiddenError -> 403,
ConflictError -> 409, plain ValueError -> 422.
"""


class NotFoundError(ValueError):
    """The requested listing, application or booking does not exist."""


class ForbiddenError(ValueError):
    """The user's role or ownership does not allow this action."""


class ConflictError(ValueError):
    """The action is not allowed in the record's current state."""
