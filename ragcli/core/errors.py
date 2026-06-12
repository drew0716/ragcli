"""Shared exception types for human-readable error reporting."""


class RagError(RuntimeError):
    """An error with a human-readable message, safe to show directly to users.

    CLI commands and API routes catch this and display the message without a
    stack trace.
    """
