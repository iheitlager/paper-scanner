from abc import ABC, abstractmethod

from paper_scanner.core.executor import StepExecutor
from paper_scanner.core.step_result import StepResult

class StepReporter(ABC):

    def __init__(self, executor: StepExecutor):
        self.executor = executor

    @abstractmethod
    def on_step_start(self, idx: int, step_config: Dict[str, Any], total: int):
        """Called when a step starts."""
        pass

    @abstractmethod
    def on_step_end(self, idx: int, step_config: Dict[str, Any], result: Any):
        """Called when a step ends."""
        pass

    @abstractmethod
    def on_execution_start(self, total_steps: int):
        """Called when execution starts."""
        pass

    @abstractmethod
    def on_execution_complete(self, results: StepResult):
        """Called when all steps have completed."""
        pass

    @abstractmethod
    def on_execution_error(self, error: str
        """Called when an error occurs during execution."""
        pass

    @abstractmethod
    def on_configuration_error(self, error: str
        """Called when an error occurs during execution."""
        pass
