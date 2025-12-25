# paper_scanner/core/controller.py
import sys

from abc import ABC, abstractmethod
from typing import Optional, Any

from .executor import StepExecutor
# from .reporter import Reporter

class BaseController(ABC):
    """Abstract base controller for execution modes."""
    
    def __init__(
        self,
        executor_class: Type[StepExecutor],
        # reporter: Reporter,
        args: Optional[dict[str, Any]] = None,
    ):
        # self.reporter = reporter
        self.debug = args.get("debug") if args else False
        self.verbose = args.get("verbose") if args else False
        self.timings = args.get("timings") if args else False
        self.should_quit = args.get("quit") if args else False
        self.executor = executor_class(debug=self.debug, verbose=self.verbose, timings=self.timings)

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize controller. Returns True if successful."""
        pass

    @abstractmethod
    def exec(self) -> int:
        """Execute the controller. Returns exit code."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup before exit."""
        pass
