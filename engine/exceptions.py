"""
exceptions.py — Custom Exception Hierarchy

Standardised error handling for the GroundTruth engine.

Hierarchy:
    GroundTruthError (base)
    ├── ProfileError          — Invalid or malformed profile data
    │   ├── MissingSectionError
    │   └── InvalidFieldError
    ├── AssumptionError       — Invalid or missing assumptions
    ├── CalculationError      — Runtime calculation failure
    └── ReportError           — Report assembly or output failure
"""

from __future__ import annotations


class GroundTruthError(Exception):
    """Base exception for all GroundTruth engine errors."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message)


class ProfileError(GroundTruthError):
    """Raised when profile data is invalid or malformed."""


class MissingSectionError(ProfileError):
    """Raised when a required profile section is absent."""


class InvalidFieldError(ProfileError):
    """Raised when a profile field has an invalid value."""


class AssumptionError(GroundTruthError):
    """Raised when assumptions are invalid or missing required keys."""


class CalculationError(GroundTruthError):
    """Raised when an engine calculation encounters an unrecoverable error."""


class ReportError(GroundTruthError):
    """Raised when report assembly or output fails."""
