from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from paper_scanner.core.enum import StepStatus


@dataclass
class StepResult:
    """Standardized result from step execution"""

    # Required fields
    status: StepStatus  # Use StepStatus.SUCCESS, WARNING, ERROR, or HALTED
    message: str = ""  # Summary message for CLI display

    # Step description
    description: Optional[str] = None  # From YAML workflow definition
    step: Optional[str] = None  # Step name (set by executor)

    # Statistics - flexible dict for any step-specific counts
    # Common keys: processed, created, updated, deleted, skipped, errors
    stats: Dict[str, int] = field(default_factory=dict)
    timings: Dict[str, Any] = field(default_factory=dict)

    # Rich messages for operators
    details: Optional[str] = None  # Detailed result (markdown format, multi-line)

    # Error details (only if status is "error")
    error: Optional[str] = None  # Error summary
    error_detail: Optional[str] = None  # Full error with traceback

    # Metadata - flexible dict for timestamps, duration, etc.
    # Common keys: duration_seconds, duration_ms, started_at, ended_at
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        """
        Dict-like access for backward compatibility.

        Allows: result['message'] → result.message
        Preferred: Use attribute access directly (result.message)

        Args:
            key: Field name

        Returns:
            Field value

        Raises:
            KeyError: If field doesn't exist
        """
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Dict-like get method for backward compatibility.

        Allows: result.get('message', 'default') → result.message or 'default'
        Preferred: Use attribute access directly (result.message)

        Args:
            key: Field name
            default: Default value if field doesn't exist

        Returns:
            Field value or default
        """
        return getattr(self, key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Dict-like set for backward compatibility.

        Allows: result['message'] = "New message" → result.message = "New message"
        Preferred: Use attribute access directly (result.message = "New message")

        Args:
            key: Field name
            value: New value

        Raises:
            KeyError: If field doesn't exist
        """
        if not hasattr(self, key):
            raise KeyError(key)
        setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dict for serialization.

        Recommended when you need JSON output or logging:
            result_dict = result.to_dict()
            json.dumps(result_dict)

        Returns:
            Dictionary representation
        """
        return {
            "status": self.status.value,
            "step": self.step,
            "message": self.message,
            "description": self.description,
            "stats": self.stats,
            "details": self.details,
            "error": self.error,
            "error_detail": self.error_detail,
            "metadata": self.metadata,
        }

# ======================================================================
# Predefined common step results
# ======================================================================

FINAL_STEP = StepResult(
    status=StepStatus.FINAL,
    message="No more steps to execute",
)
