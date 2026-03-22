"""
Application-specific errors.

Keeping conversion failures distinct from bugs helps the CLI and GUI show
clear, actionable messages without dumping raw tracebacks to end users.
"""


class Acid2ReaperError(Exception):
    """Base class for expected failures (bad input, limits, unsupported files)."""


class SecurityError(Acid2ReaperError):
    """
    Raised when a path or archive looks unsafe.

    Examples: path traversal in a ZIP, files larger than configured limits,
    or paths containing characters that are often used in exploits.
    """


class ProjectTooLargeError(SecurityError):
    """The project file exceeds the configured maximum read size."""


class ZipBombError(SecurityError):
    """ZIP contents exceed safe member count or uncompressed size limits."""
