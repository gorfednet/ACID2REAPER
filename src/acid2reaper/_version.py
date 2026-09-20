"""
Single source of truth for release metadata (used by CLI, GUI, and packagers).

``__version__`` follows PEP 440; ``__version_label__`` is the human-facing
label. ``scripts/verify_changelog.py`` checks both against ``pyproject.toml``
and ``CHANGELOG.md``.
"""

__version__ = "0.2.0"
__version_label__ = "0.2.0 (Beta)"
