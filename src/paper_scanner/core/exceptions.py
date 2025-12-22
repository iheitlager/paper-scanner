"""
Custom exceptions for paper-scanner.

Provides a hierarchy of exceptions for different error categories:
- ConfigurationError: Invalid YAML/step/pipeline configuration
- StepError: Step not found, instantiation, or validation failed
- CheckpointError: Checkpoint I/O, corruption, or restoration failed
- PipelineExecutionError: Step execution failed
"""


class PaperScannerError(Exception):
    """Base exception for all paper-scanner errors."""
    pass


class ConfigurationError(PaperScannerError):
    """
    Raised when pipeline or step configuration is invalid.
    
    Examples:
    - Missing required configuration keys
    - Invalid step name in configuration
    - Malformed YAML or JSON
    """
    pass


class StepError(PaperScannerError):
    """
    Raised when a step cannot be found, instantiated, or validated.
    
    Examples:
    - Unknown step name
    - Step instantiation fails
    - Step validation fails
    """
    pass


class CheckpointError(PaperScannerError):
    """
    Raised when checkpoint operations fail.
    
    Examples:
    - Checkpoint file I/O errors
    - Corrupt checkpoint data
    - Checkpoint restoration fails
    """
    pass


class PipelineExecutionError(PaperScannerError):
    """
    Raised when a step execution fails during pipeline run.
    
    Examples:
    - Step processing fails
    - Data transformation errors
    - External service failures
    """
    pass
