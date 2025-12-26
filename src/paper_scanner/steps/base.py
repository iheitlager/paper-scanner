"""
Base class for all pipeline steps.

All steps in the paper-scanner pipeline inherit from BaseStep, providing
a standard interface for step discovery, configuration validation, and execution.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Tuple

from paper_scanner.core.database import PapersDatabase



class BaseStep(ABC):
    """
    Abstract base class for all pipeline steps.

    Steps follow a three-level configuration model:
    1. general_config: Project-level configuration (passed to all steps)
    2. step_config: Step-specific configuration (parsed from YAML workflow)
    3. Runtime flags: verbose, dry_run, debug (passed during execution)

    Example usage:
        # 1. Validate configuration at parse time
        is_valid, errors = MyStep.validate(step_config)
        if not is_valid:
            raise ValueError(f"Invalid config: {errors}")

        # 2. Instantiate with project dependencies
        step = MyStep(
            general_config=project_config,
            db=papers_db,
            cache_dir=Path("/path/to/cache")
        )

        # 3. Execute with step configuration and runtime flags
        results = step.execute(
            step_config=step_config,
            verbose=True,
            dry_run=False,
            debug=False
        )

        # 4. Check results
        if results["status"] == "success":
            print(f"Processed {results['count']} papers")
    """

    def __init__(
        self,
        general_config: Dict[str, Any],
        db: PapersDatabase,
        cache_dir: Path,
    ):
        """
        Initialize step with project-level dependencies.

        Args:
            general_config: Project-level configuration dictionary containing
                          settings that may be needed by multiple steps
            db: PapersDatabase instance for reading/writing papers
            cache_dir: Directory for caching fetched data and intermediate results
        """
        self.general_config = general_config
        self.db = db
        self.cache_dir = cache_dir

    @property
    def name(self) -> str:
        """Return the step's class name as its identifier."""
        return self.__class__.__name__

    @staticmethod
    @abstractmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate step-specific configuration.

        This static method is called at workflow parse time to validate the
        step configuration before instantiation. It allows early detection of
        configuration errors without requiring the step to be instantiated.

        Args:
            config: Step-specific configuration from workflow YAML

        Returns:
            Tuple of (is_valid, errors) where:
            - is_valid: True if configuration is valid, False otherwise
            - errors: List of validation error messages (empty if valid)

        Example:
            >>> is_valid, errors = RetrieveMetadataStep.validate(config)
            >>> if not is_valid:
            ...     print(f"Config errors: {errors}")
        """
        pass

    @abstractmethod
    def execute(
        self,
        step_config: Dict[str, Any],
        on_event: Optional[callable],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the step with given configuration.

        This instance method performs the actual work. It has access to:
        - self.general_config: Project configuration
        - self.db: Database instance
        - self.cache_dir: Cache directory path

        Args:
            step_config: Step-specific configuration from workflow YAML
            verbose: Enable verbose output
            dry_run: If True, don't persist changes (read-only execution)
            debug: Enable debug logging and re-raise exceptions for debugging

        Returns:
            Dictionary with execution results. Must include:
            - "status": StepStatus.[SUCCESS, ERROR, WARNING, HALTED]
            - "message": Summary message
            - "count": Number of items processed (or 0 on error)
            
            May include:
            - "details": Step-specific result details
            - "error": Error message (if status is "error")
            - Other step-specific fields for reporting

        Example:
            >>> results = step.execute(config, verbose=True)
            >>> print(f"Processed {results['count']} papers")
            >>> assert results["status"] == "success"
        """
        pass
